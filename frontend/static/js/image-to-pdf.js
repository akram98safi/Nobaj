(() => {
  const copy = JSON.parse(document.getElementById('image-copy')?.textContent || '{}');
  const input = document.getElementById('pdf-images');
  const list = document.getElementById('pdf-image-list');
  const button = document.getElementById('pdf-generate');
  const status = document.getElementById('pdf-status');
  const download = document.getElementById('pdf-download');
  if (!input || !list || !button || !status || !download) return;

  const maxFiles = 15;
  const maxFileBytes = 25 * 1024 * 1024;
  const maxTotalBytes = 100 * 1024 * 1024;
  const maxPixels = 32_000_000;
  const acceptedTypes = ['image/jpeg', 'image/png', 'image/webp'];
  const encoder = new TextEncoder();
  let files = [];
  let outputUrl = null;

  function clearDownload() {
    if (outputUrl) URL.revokeObjectURL(outputUrl);
    outputUrl = null;
    download.removeAttribute('href');
    download.classList.add('hidden');
  }

  function renderList() {
    list.replaceChildren();
    files.forEach((file, index) => {
      const item = document.createElement('li');
      item.className = 'image-pdf-list-item';
      const name = document.createElement('span');
      name.className = 'image-pdf-file-name';
      name.textContent = file.name;
      const controls = document.createElement('span');
      controls.className = 'image-pdf-item-controls';

      const moveUp = document.createElement('button');
      moveUp.type = 'button';
      moveUp.textContent = '↑';
      moveUp.disabled = index === 0;
      moveUp.setAttribute('aria-label', `${copy.image_pdf_move_up}: ${file.name}`);
      moveUp.addEventListener('click', () => move(index, index - 1));

      const moveDown = document.createElement('button');
      moveDown.type = 'button';
      moveDown.textContent = '↓';
      moveDown.disabled = index === files.length - 1;
      moveDown.setAttribute('aria-label', `${copy.image_pdf_move_down}: ${file.name}`);
      moveDown.addEventListener('click', () => move(index, index + 1));

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `${copy.image_pdf_remove}: ${file.name}`);
      remove.addEventListener('click', () => {
        files.splice(index, 1);
        clearDownload();
        renderList();
      });

      controls.append(moveUp, moveDown, remove);
      item.append(name, controls);
      list.append(item);
    });
    if (files.length) status.textContent = copy.image_pdf_count.replace('{count}', String(files.length));
  }

  function move(from, to) {
    if (to < 0 || to >= files.length) return;
    const [item] = files.splice(from, 1);
    files.splice(to, 0, item);
    clearDownload();
    renderList();
  }

  function joinBytes(parts) {
    const total = parts.reduce((sum, part) => sum + part.byteLength, 0);
    const joined = new Uint8Array(total);
    let offset = 0;
    parts.forEach((part) => {
      joined.set(part, offset);
      offset += part.byteLength;
    });
    return joined;
  }

  async function jpegData(file) {
    const bitmap = await createImageBitmap(file);
    try {
      if (!bitmap.width || !bitmap.height || bitmap.width * bitmap.height > maxPixels) throw new Error(copy.image_error_size);
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const context = canvas.getContext('2d');
      if (!context) throw new Error(copy.image_error_process);
      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0);
      const blob = await new Promise((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error(copy.image_error_process)), 'image/jpeg', 0.92));
      return { bytes: new Uint8Array(await blob.arrayBuffer()), width: bitmap.width, height: bitmap.height };
    } finally {
      bitmap.close();
    }
  }

  async function createPdf() {
    const pageSize = document.getElementById('pdf-page-size').value;
    const landscape = document.getElementById('pdf-orientation').value === 'landscape';
    let pageWidth = pageSize === 'letter' ? 612 : 595;
    let pageHeight = pageSize === 'letter' ? 792 : 842;
    if (landscape) [pageWidth, pageHeight] = [pageHeight, pageWidth];
    const margin = 24;
    const pages = [];
    let totalPixels = 0;
    for (const file of files) {
      const page = await jpegData(file);
      totalPixels += page.width * page.height;
      if (totalPixels > 100_000_000) throw new Error(copy.image_error_size);
      pages.push(page);
    }

    const pageIds = pages.map((_, index) => 3 + index * 3);
    const objectCount = 2 + pages.length * 3;
    const chunks = [];
    const offsets = new Array(objectCount + 1).fill(0);
    let byteLength = 0;
    const write = (part) => {
      const bytes = typeof part === 'string' ? encoder.encode(part) : part;
      chunks.push(bytes);
      byteLength += bytes.byteLength;
    };
    const object = (id, body) => {
      offsets[id] = byteLength;
      write(`${id} 0 obj\n`);
      body();
      write('\nendobj\n');
    };

    write('%PDF-1.4\n');
    object(1, () => write('<< /Type /Catalog /Pages 2 0 R >>'));
    object(2, () => write(`<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>`));

    pages.forEach((page, index) => {
      const pageId = pageIds[index];
      const imageId = pageId + 1;
      const contentId = pageId + 2;
      const scale = Math.min((pageWidth - margin * 2) / page.width, (pageHeight - margin * 2) / page.height);
      const drawWidth = page.width * scale;
      const drawHeight = page.height * scale;
      const x = (pageWidth - drawWidth) / 2;
      const y = (pageHeight - drawHeight) / 2;
      const stream = encoder.encode(`q\n${drawWidth.toFixed(3)} 0 0 ${drawHeight.toFixed(3)} ${x.toFixed(3)} ${y.toFixed(3)} cm\n/Im0 Do\nQ`);

      object(pageId, () => write(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /XObject << /Im0 ${imageId} 0 R >> >> /Contents ${contentId} 0 R >>`));
      object(imageId, () => {
        write(`<< /Type /XObject /Subtype /Image /Width ${page.width} /Height ${page.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${page.bytes.byteLength} >>\nstream\n`);
        write(page.bytes);
        write('\nendstream');
      });
      object(contentId, () => {
        write(`<< /Length ${stream.byteLength} >>\nstream\n`);
        write(stream);
        write('\nendstream');
      });
    });

    const xrefOffset = byteLength;
    write(`xref\n0 ${objectCount + 1}\n0000000000 65535 f \n`);
    for (let id = 1; id <= objectCount; id += 1) write(`${String(offsets[id]).padStart(10, '0')} 00000 n \n`);
    write(`trailer\n<< /Size ${objectCount + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`);
    return new Blob([joinBytes(chunks)], { type: 'application/pdf' });
  }

  input.addEventListener('change', () => {
    clearDownload();
    status.textContent = '';
    const selected = Array.from(input.files || []);
    const totalBytes = selected.reduce((sum, file) => sum + file.size, 0);
    if (!selected.length) {
      files = [];
      renderList();
      return;
    }
    if (selected.some((file) => !acceptedTypes.includes(file.type))) {
      files = [];
      input.value = '';
      status.textContent = copy.image_error_type;
      renderList();
      return;
    }
    if (selected.some((file) => file.size > maxFileBytes)) {
      files = [];
      input.value = '';
      status.textContent = copy.image_error_size;
      renderList();
      return;
    }
    if (selected.length > maxFiles || totalBytes > maxTotalBytes) {
      files = [];
      input.value = '';
      status.textContent = copy.image_pdf_error_limit;
      renderList();
      return;
    }
    files = selected;
    renderList();
  });

  button.addEventListener('click', async () => {
    clearDownload();
    if (!files.length) {
      status.textContent = copy.image_error_empty;
      return;
    }
    button.disabled = true;
    status.textContent = copy.image_processing;
    try {
      const blob = await createPdf();
      outputUrl = URL.createObjectURL(blob);
      download.href = outputUrl;
      download.classList.remove('hidden');
      status.textContent = copy.image_status_done;
    } catch (error) {
      status.textContent = error.message || copy.image_error_process;
    } finally {
      button.disabled = false;
    }
  });

  window.addEventListener('beforeunload', clearDownload);
})();
