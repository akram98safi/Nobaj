(() => {
  const copy = JSON.parse(document.getElementById('image-copy')?.textContent || '{}');
  const input = document.getElementById('favicon-file');
  const button = document.getElementById('favicon-generate');
  const result = document.getElementById('favicon-result');
  const icoLink = document.getElementById('favicon-download');
  const appleLink = document.getElementById('favicon-apple-download');
  const status = document.getElementById('favicon-status');
  if (!input || !button || !result || !icoLink || !appleLink || !status) return;

  const maxBytes = 25 * 1024 * 1024;
  const maxPixels = 32_000_000;
  let downloadUrls = [];
  let image = null;

  function clearOutput() {
    downloadUrls.forEach((url) => URL.revokeObjectURL(url));
    downloadUrls = [];
    ['favicon-preview-16', 'favicon-preview-32', 'favicon-preview-48'].forEach((id) => {
      const preview = document.getElementById(id);
      if (preview.dataset.url) URL.revokeObjectURL(preview.dataset.url);
      preview.removeAttribute('src');
      delete preview.dataset.url;
    });
    icoLink.removeAttribute('href');
    appleLink.removeAttribute('href');
    result.classList.add('hidden');
  }

  async function readImage(file) {
    if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error(copy.image_error_type);
    if (file.size > maxBytes) throw new Error(copy.image_error_size);
    const bitmap = await createImageBitmap(file);
    if (bitmap.width * bitmap.height > maxPixels) {
      bitmap.close();
      throw new Error(copy.image_error_size);
    }
    if (image) image.close();
    image = bitmap;
  }

  function pngBlob(size) {
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext('2d');
    if (!context || !image) throw new Error(copy.image_error_process);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = 'high';
    const cropSize = Math.min(image.width, image.height);
    const sourceX = (image.width - cropSize) / 2;
    const sourceY = (image.height - cropSize) / 2;
    context.drawImage(image, sourceX, sourceY, cropSize, cropSize, 0, 0, size, size);
    return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error(copy.image_error_process)), 'image/png'));
  }

  async function makeIco(pngBlobs) {
    const header = new Uint8Array(6 + pngBlobs.length * 16);
    const view = new DataView(header.buffer);
    view.setUint16(0, 0, true);
    view.setUint16(2, 1, true);
    view.setUint16(4, pngBlobs.length, true);
    const pngBytes = await Promise.all(pngBlobs.map((blob) => blob.arrayBuffer()));
    let offset = header.length;
    pngBlobs.forEach((blob, index) => {
      const entry = 6 + index * 16;
      const size = [16, 32, 48][index];
      view.setUint8(entry, size === 256 ? 0 : size);
      view.setUint8(entry + 1, size === 256 ? 0 : size);
      view.setUint8(entry + 2, 0);
      view.setUint8(entry + 3, 0);
      view.setUint16(entry + 4, 1, true);
      view.setUint16(entry + 6, 32, true);
      view.setUint32(entry + 8, blob.size, true);
      view.setUint32(entry + 12, offset, true);
      offset += blob.size;
    });
    return new Blob([header, ...pngBytes], { type: 'image/x-icon' });
  }

  input.addEventListener('change', async () => {
    clearOutput();
    status.textContent = '';
    if (image) image.close();
    image = null;
    try {
      await readImage(input.files?.[0]);
      status.textContent = copy.image_status_ready;
    } catch (error) {
      status.textContent = error.message || copy.image_error_process;
      input.value = '';
    }
  });

  button.addEventListener('click', async () => {
    clearOutput();
    if (!image) {
      status.textContent = copy.image_error_empty;
      return;
    }
    button.disabled = true;
    status.textContent = copy.image_processing;
    try {
      const sizes = [16, 32, 48];
      const pngs = await Promise.all(sizes.map(pngBlob));
      const applePng = await pngBlob(180);
      const ico = await makeIco(pngs);
      const icoUrl = URL.createObjectURL(ico);
      const appleUrl = URL.createObjectURL(applePng);
      downloadUrls.push(icoUrl, appleUrl);
      icoLink.href = icoUrl;
      appleLink.href = appleUrl;
      sizes.forEach((size, index) => {
        const preview = document.getElementById(`favicon-preview-${size}`);
        const url = URL.createObjectURL(pngs[index]);
        preview.src = url;
        preview.dataset.url = url;
      });
      result.classList.remove('hidden');
      status.textContent = copy.image_status_done;
    } catch (error) {
      status.textContent = error.message || copy.image_error_process;
    } finally {
      button.disabled = false;
    }
  });

  window.addEventListener('beforeunload', () => {
    clearOutput();
    if (image) image.close();
  });
})();
