(() => {
  const copy = JSON.parse(document.getElementById('image-copy')?.textContent || '{}');
  const input = document.getElementById('image-file-input');
  const dropZone = document.getElementById('image-drop-zone');
  const editor = document.getElementById('image-editor');
  const canvas = document.getElementById('image-preview-canvas');
  const context = canvas?.getContext('2d');
  const status = document.getElementById('image-status');
  const result = document.getElementById('image-result');
  const outputLink = document.getElementById('image-download');
  const qualityInput = document.getElementById('image-quality');
  const qualityOutput = document.getElementById('image-quality-value');
  const formatInput = document.getElementById('image-format');
  const widthInput = document.getElementById('image-width');
  const heightInput = document.getElementById('image-height');
  const ratioInput = document.getElementById('image-keep-ratio');
  const cropRatioInput = document.getElementById('image-crop-ratio');
  const MAX_FILE_BYTES = 25 * 1024 * 1024;
  const MAX_IMAGE_PIXELS = 32_000_000;
  const MAX_OUTPUT_EDGE = 12000;

  if (!input || !canvas || !context) return;

  let mode = 'compress';
  let sourceFile = null;
  let sourceImage = null;
  let sourceUrl = null;
  let outputUrl = null;
  let previewWidth = 0;
  let previewHeight = 0;
  let cropRect = null;
  let cropStart = null;
  let updatingDimensions = false;

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  function clearOutput() {
    if (outputUrl) URL.revokeObjectURL(outputUrl);
    outputUrl = null;
    result.classList.add('hidden');
    outputLink.removeAttribute('href');
  }

  function previewPoint(event) {
    const bounds = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(canvas.width, (event.clientX - bounds.left) * canvas.width / bounds.width)),
      y: Math.max(0, Math.min(canvas.height, (event.clientY - bounds.top) * canvas.height / bounds.height)),
    };
  }

  function cropRatio() {
    const value = cropRatioInput.value;
    if (value === 'free') return null;
    const [width, height] = value.split('/').map(Number);
    return width / height;
  }

  function drawPreview() {
    if (!sourceImage || !previewWidth || !previewHeight) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(sourceImage, 0, 0, canvas.width, canvas.height);

    if (mode !== 'crop' || !cropRect) return;
    const { x, y, width, height } = cropRect;
    context.fillStyle = 'rgba(3, 5, 15, .58)';
    context.fillRect(0, 0, canvas.width, y);
    context.fillRect(0, y + height, canvas.width, canvas.height - y - height);
    context.fillRect(0, y, x, height);
    context.fillRect(x + width, y, canvas.width - x - width, height);
    context.strokeStyle = '#c4b5fd';
    context.lineWidth = Math.max(2, canvas.width / 360);
    context.setLineDash([8, 5]);
    context.strokeRect(x, y, width, height);
    context.setLineDash([]);
  }

  function updateDimensionsFromWidth() {
    if (!sourceImage || !ratioInput.checked || updatingDimensions) return;
    const width = Number(widthInput.value);
    if (!width) return;
    updatingDimensions = true;
    heightInput.value = Math.max(1, Math.round(width * sourceImage.naturalHeight / sourceImage.naturalWidth));
    updatingDimensions = false;
  }

  function updateDimensionsFromHeight() {
    if (!sourceImage || !ratioInput.checked || updatingDimensions) return;
    const height = Number(heightInput.value);
    if (!height) return;
    updatingDimensions = true;
    widthInput.value = Math.max(1, Math.round(height * sourceImage.naturalWidth / sourceImage.naturalHeight));
    updatingDimensions = false;
  }

  function updateSettings() {
    document.querySelectorAll('[data-image-mode]').forEach((button) => {
      const active = button.dataset.imageMode === mode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    document.getElementById('image-size-settings').classList.toggle('hidden', mode !== 'resize');
    document.getElementById('image-crop-settings').classList.toggle('hidden', mode !== 'crop');
    document.getElementById('image-crop-hint').classList.toggle('hidden', mode !== 'crop');
    canvas.classList.toggle('is-cropping', mode === 'crop');
    if (mode !== 'crop') cropRect = null;
    const isPng = formatInput.value === 'image/png';
    qualityInput.disabled = isPng;
    qualityOutput.textContent = isPng ? '—' : `${qualityInput.value}%`;
    document.getElementById('image-jpeg-note').classList.toggle('hidden', formatInput.value !== 'image/jpeg');
    drawPreview();
    clearOutput();
    status.textContent = '';
  }

  function setCrop(point) {
    const dx = point.x - cropStart.x;
    const dy = point.y - cropStart.y;
    const signX = dx < 0 ? -1 : 1;
    const signY = dy < 0 ? -1 : 1;
    let width = Math.abs(dx);
    let height = Math.abs(dy);
    const fixedRatio = cropRatio();

    if (fixedRatio) {
      width = Math.min(width, height * fixedRatio);
      height = width / fixedRatio;
    }

    const availableWidth = signX < 0 ? cropStart.x : canvas.width - cropStart.x;
    const availableHeight = signY < 0 ? cropStart.y : canvas.height - cropStart.y;
    if (width > availableWidth || height > availableHeight) {
      if (fixedRatio) {
        width = Math.min(availableWidth, availableHeight * fixedRatio);
        height = width / fixedRatio;
      } else {
        width = Math.min(width, availableWidth);
        height = Math.min(height, availableHeight);
      }
    }

    cropRect = {
      x: signX < 0 ? cropStart.x - width : cropStart.x,
      y: signY < 0 ? cropStart.y - height : cropStart.y,
      width,
      height,
    };
    drawPreview();
  }

  async function loadFile(file) {
    clearOutput();
    status.textContent = '';
    cropRect = null;

    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      status.textContent = copy.image_error_type;
      input.value = '';
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      status.textContent = copy.image_error_size;
      input.value = '';
      return;
    }

    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    sourceFile = file;
    sourceUrl = URL.createObjectURL(file);
    const image = new Image();
    image.decoding = 'async';
    image.src = sourceUrl;

    try {
      await image.decode();
      const pixels = image.naturalWidth * image.naturalHeight;
      if (!image.naturalWidth || !image.naturalHeight || pixels > MAX_IMAGE_PIXELS) {
        status.textContent = copy.image_error_size;
        sourceFile = null;
        input.value = '';
        return;
      }

      sourceImage = image;
      const scale = Math.min(1, 900 / image.naturalWidth, 560 / image.naturalHeight);
      previewWidth = Math.max(1, Math.round(image.naturalWidth * scale));
      previewHeight = Math.max(1, Math.round(image.naturalHeight * scale));
      canvas.width = previewWidth;
      canvas.height = previewHeight;
      canvas.style.width = `${previewWidth}px`;
      canvas.style.height = `${previewHeight}px`;
      widthInput.value = image.naturalWidth;
      heightInput.value = image.naturalHeight;
      document.getElementById('image-original-dimensions').textContent = `${image.naturalWidth} × ${image.naturalHeight}`;
      document.getElementById('image-original-size').textContent = formatBytes(file.size);
      dropZone.classList.add('hidden');
      editor.classList.remove('hidden');
      updateSettings();
      status.textContent = copy.image_status_ready;
    } catch (error) {
      sourceFile = null;
      sourceImage = null;
      input.value = '';
      status.textContent = copy.image_error_process;
    }
  }

  function updateDownload(blob, mimeType, width, height) {
    if (outputUrl) URL.revokeObjectURL(outputUrl);
    outputUrl = URL.createObjectURL(blob);
    const extension = mimeType === 'image/jpeg' ? 'jpg' : mimeType.split('/')[1];
    const safeName = sourceFile.name.replace(/\.[^.]*$/, '').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 72) || 'nobaj-image';
    outputLink.href = outputUrl;
    outputLink.download = `${safeName}-${mode}.${extension}`;
    document.getElementById('image-result-name').textContent = outputLink.download;
    document.getElementById('image-result-dimensions').textContent = `${width} × ${height}`;
    document.getElementById('image-result-size').textContent = formatBytes(blob.size);
    result.classList.remove('hidden');
    status.textContent = copy.image_status_done;
  }

  function processImage() {
    if (!sourceFile || !sourceImage) {
      status.textContent = copy.image_error_empty;
      return;
    }
    clearOutput();

    let sourceX = 0;
    let sourceY = 0;
    let sourceWidth = sourceImage.naturalWidth;
    let sourceHeight = sourceImage.naturalHeight;
    let outputWidth = sourceWidth;
    let outputHeight = sourceHeight;

    if (mode === 'resize') {
      outputWidth = Number(widthInput.value);
      outputHeight = Number(heightInput.value);
      if (!Number.isInteger(outputWidth) || !Number.isInteger(outputHeight) || outputWidth < 1 || outputHeight < 1 || outputWidth > MAX_OUTPUT_EDGE || outputHeight > MAX_OUTPUT_EDGE || outputWidth * outputHeight > MAX_IMAGE_PIXELS) {
        status.textContent = copy.image_error_dimensions;
        return;
      }
    }

    if (mode === 'crop') {
      if (!cropRect || cropRect.width < 3 || cropRect.height < 3) {
        status.textContent = copy.image_error_crop;
        return;
      }
      sourceX = cropRect.x * sourceImage.naturalWidth / canvas.width;
      sourceY = cropRect.y * sourceImage.naturalHeight / canvas.height;
      sourceWidth = cropRect.width * sourceImage.naturalWidth / canvas.width;
      sourceHeight = cropRect.height * sourceImage.naturalHeight / canvas.height;
      outputWidth = Math.max(1, Math.round(sourceWidth));
      outputHeight = Math.max(1, Math.round(sourceHeight));
    }

    const outputCanvas = document.createElement('canvas');
    outputCanvas.width = outputWidth;
    outputCanvas.height = outputHeight;
    const outputContext = outputCanvas.getContext('2d');
    if (!outputContext) {
      status.textContent = copy.image_error_process;
      return;
    }

    const mimeType = formatInput.value;
    if (mimeType === 'image/jpeg') {
      outputContext.fillStyle = '#fff';
      outputContext.fillRect(0, 0, outputWidth, outputHeight);
    }
    outputContext.drawImage(sourceImage, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, outputWidth, outputHeight);
    status.textContent = copy.image_processing;
    document.getElementById('image-process').disabled = true;

    outputCanvas.toBlob((blob) => {
      document.getElementById('image-process').disabled = false;
      if (!blob || blob.type !== mimeType) {
        status.textContent = copy.image_error_process;
        return;
      }
      updateDownload(blob, mimeType, outputWidth, outputHeight);
    }, mimeType, Number(qualityInput.value) / 100);
  }

  document.querySelectorAll('[data-image-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      mode = button.dataset.imageMode;
      updateSettings();
    });
  });

  document.getElementById('image-language')?.addEventListener('change', (event) => {
    if (event.target.value) window.location.assign(event.target.value);
  });
  document.getElementById('image-change-file')?.addEventListener('click', () => {
    input.value = '';
    input.click();
  });
  input.addEventListener('change', () => loadFile(input.files?.[0]));
  formatInput.addEventListener('change', updateSettings);
  cropRatioInput.addEventListener('change', () => {
    cropRect = null;
    drawPreview();
  });
  qualityInput.addEventListener('input', () => {
    qualityOutput.textContent = `${qualityInput.value}%`;
    clearOutput();
  });
  widthInput.addEventListener('input', () => { updateDimensionsFromWidth(); clearOutput(); });
  heightInput.addEventListener('input', () => { updateDimensionsFromHeight(); clearOutput(); });
  ratioInput.addEventListener('change', () => { if (ratioInput.checked) updateDimensionsFromWidth(); clearOutput(); });
  document.getElementById('image-process').addEventListener('click', processImage);

  ['dragenter', 'dragover'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add('dropzone-active');
  }));
  ['dragleave', 'drop'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove('dropzone-active');
  }));
  dropZone.addEventListener('drop', (event) => loadFile(event.dataTransfer?.files?.[0]));

  canvas.addEventListener('pointerdown', (event) => {
    if (mode !== 'crop' || !sourceImage) return;
    cropStart = previewPoint(event);
    cropRect = { x: cropStart.x, y: cropStart.y, width: 0, height: 0 };
    canvas.setPointerCapture(event.pointerId);
    clearOutput();
  });
  canvas.addEventListener('pointermove', (event) => {
    if (cropStart && mode === 'crop') setCrop(previewPoint(event));
  });
  const finishCrop = () => { cropStart = null; };
  canvas.addEventListener('pointerup', finishCrop);
  canvas.addEventListener('pointercancel', finishCrop);

  window.addEventListener('beforeunload', () => {
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    if (outputUrl) URL.revokeObjectURL(outputUrl);
  });
})();
