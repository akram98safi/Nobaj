(() => {
  const copy = JSON.parse(document.getElementById('image-copy')?.textContent || '{}');
  const input = document.getElementById('qr-text');
  const button = document.getElementById('qr-generate');
  const canvas = document.getElementById('qr-preview');
  const result = document.getElementById('qr-result');
  const link = document.getElementById('qr-download');
  const status = document.getElementById('qr-status');
  if (!input || !button || !canvas || !result || !link || !status) return;

  const DIMENSION = 37; // Version 5, error correction M.
  const DATA_CODEWORDS = 86;
  const ECC_CODEWORDS_PER_BLOCK = 24;
  const BLOCKS = 2;

  function multiply(a, b) {
    let product = 0;
    for (let i = 7; i >= 0; i -= 1) {
      product = (product << 1) ^ ((product >>> 7) * 0x11d);
      product ^= ((b >>> i) & 1) * a;
    }
    return product;
  }

  function errorCorrection(data) {
    let generator = [1];
    let root = 1;
    for (let i = 0; i < ECC_CODEWORDS_PER_BLOCK; i += 1) {
      const next = new Array(generator.length + 1).fill(0);
      generator.forEach((value, index) => {
        next[index] ^= value;
        next[index + 1] ^= multiply(value, root);
      });
      generator = next;
      root = multiply(root, 2);
    }

    const blocks = [];
    const blockLength = data.length / BLOCKS;
    for (let blockIndex = 0; blockIndex < BLOCKS; blockIndex += 1) {
      const block = data.slice(blockIndex * blockLength, (blockIndex + 1) * blockLength);
      const remainder = block.concat(new Array(ECC_CODEWORDS_PER_BLOCK).fill(0));
      for (let i = 0; i < block.length; i += 1) {
        const factor = remainder[i];
        for (let j = 0; j < generator.length; j += 1) remainder[i + j] ^= multiply(generator[j], factor);
      }
      blocks.push({ data: block, ecc: remainder.slice(block.length) });
    }

    const result = [];
    for (let i = 0; i < blockLength; i += 1) blocks.forEach((block) => result.push(block.data[i]));
    for (let i = 0; i < ECC_CODEWORDS_PER_BLOCK; i += 1) blocks.forEach((block) => result.push(block.ecc[i]));
    return result;
  }

  function formatInformation(mask) {
    const data = mask; // M-level format indicator is 00.
    let remainder = data << 10;
    for (let bit = 14; bit >= 10; bit -= 1) {
      if (((remainder >>> bit) & 1) !== 0) remainder ^= 0x537 << (bit - 10);
    }
    return ((data << 10) | remainder) ^ 0x5412;
  }

  function makeMatrix(bytes) {
    const modules = Array.from({ length: DIMENSION }, () => new Array(DIMENSION).fill(false));
    const fixed = Array.from({ length: DIMENSION }, () => new Array(DIMENSION).fill(false));
    const setFunction = (x, y, dark) => {
      if (x < 0 || y < 0 || x >= DIMENSION || y >= DIMENSION) return;
      modules[y][x] = dark;
      fixed[y][x] = true;
    };

    function finder(centerX, centerY) {
      for (let dy = -1; dy <= 7; dy += 1) {
        for (let dx = -1; dx <= 7; dx += 1) {
          const x = centerX + dx;
          const y = centerY + dy;
          const inside = dx >= 0 && dx <= 6 && dy >= 0 && dy <= 6;
          const dark = inside && (dx === 0 || dx === 6 || dy === 0 || dy === 6 || (dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4));
          setFunction(x, y, dark);
        }
      }
    }

    finder(0, 0);
    finder(DIMENSION - 7, 0);
    finder(0, DIMENSION - 7);
    for (let i = 8; i < DIMENSION - 8; i += 1) {
      setFunction(i, 6, i % 2 === 0);
      setFunction(6, i, i % 2 === 0);
    }

    const center = DIMENSION - 7;
    for (let dy = -2; dy <= 2; dy += 1) {
      for (let dx = -2; dx <= 2; dx += 1) {
        setFunction(center + dx, center + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
      }
    }

    const format = formatInformation(0);
    for (let i = 0; i <= 5; i += 1) setFunction(8, i, ((format >>> i) & 1) !== 0);
    setFunction(8, 7, ((format >>> 6) & 1) !== 0);
    setFunction(8, 8, ((format >>> 7) & 1) !== 0);
    setFunction(7, 8, ((format >>> 8) & 1) !== 0);
    for (let i = 9; i < 15; i += 1) setFunction(14 - i, 8, ((format >>> i) & 1) !== 0);
    for (let i = 0; i < 8; i += 1) setFunction(DIMENSION - 1 - i, 8, ((format >>> i) & 1) !== 0);
    for (let i = 8; i < 15; i += 1) setFunction(8, DIMENSION - 15 + i, ((format >>> i) & 1) !== 0);
    setFunction(8, DIMENSION - 8, true);

    const dataBits = [];
    bytes.forEach((byte) => {
      for (let bit = 7; bit >= 0; bit -= 1) dataBits.push(((byte >>> bit) & 1) !== 0);
    });
    let bitIndex = 0;
    for (let right = DIMENSION - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      const upward = ((right + 1) & 2) === 0;
      for (let vert = 0; vert < DIMENSION; vert += 1) {
        const y = upward ? DIMENSION - 1 - vert : vert;
        for (let offset = 0; offset < 2; offset += 1) {
          const x = right - offset;
          if (fixed[y][x]) continue;
          let dark = bitIndex < dataBits.length ? dataBits[bitIndex] : false;
          bitIndex += 1;
          if ((x + y) % 2 === 0) dark = !dark;
          modules[y][x] = dark;
        }
      }
    }
    return modules;
  }

  function encode(text) {
    const bytes = Array.from(new TextEncoder().encode(text));
    if (!bytes.length || bytes.length > 84) throw new Error(copy.image_qr_error_length);
    const bits = [];
    const appendBits = (value, length) => {
      for (let i = length - 1; i >= 0; i -= 1) bits.push(((value >>> i) & 1) !== 0);
    };
    appendBits(0b0100, 4);
    appendBits(bytes.length, 8);
    bytes.forEach((byte) => appendBits(byte, 8));
    const capacity = DATA_CODEWORDS * 8;
    for (let i = 0; i < Math.min(4, capacity - bits.length); i += 1) bits.push(false);
    while (bits.length % 8) bits.push(false);
    const data = [];
    for (let i = 0; i < bits.length; i += 8) {
      let byte = 0;
      for (let j = 0; j < 8; j += 1) byte = (byte << 1) | Number(bits[i + j]);
      data.push(byte);
    }
    for (let pad = 0; data.length < DATA_CODEWORDS; pad += 1) data.push(pad % 2 === 0 ? 0xec : 0x11);
    return makeMatrix(errorCorrection(data));
  }

  function draw(matrix) {
    const size = Number(document.getElementById('qr-size').value);
    const foreground = document.getElementById('qr-foreground').value;
    const background = document.getElementById('qr-background').value;
    const quietZone = 4;
    const cell = size / (DIMENSION + quietZone * 2);
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext('2d');
    context.fillStyle = background;
    context.fillRect(0, 0, size, size);
    context.fillStyle = foreground;
    matrix.forEach((row, y) => row.forEach((dark, x) => {
      if (!dark) return;
      const left = Math.round((x + quietZone) * cell);
      const right = Math.round((x + quietZone + 1) * cell);
      const top = Math.round((y + quietZone) * cell);
      const bottom = Math.round((y + quietZone + 1) * cell);
      context.fillRect(left, top, right - left, bottom - top);
    }));
    canvas.toBlob((blob) => {
      if (!blob) {
        status.textContent = copy.image_error_process;
        return;
      }
      if (link.dataset.url) URL.revokeObjectURL(link.dataset.url);
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.dataset.url = url;
      result.classList.remove('hidden');
      status.textContent = copy.image_status_done;
    }, 'image/png');
  }

  function clearResult() {
    result.classList.add('hidden');
    status.textContent = '';
    if (link.dataset.url) URL.revokeObjectURL(link.dataset.url);
    link.removeAttribute('href');
    delete link.dataset.url;
  }

  button.addEventListener('click', () => {
    clearResult();
    try {
      draw(encode(input.value.trim()));
    } catch (error) {
      status.textContent = error.message || copy.image_error_process;
    }
  });
  [input, document.getElementById('qr-size'), document.getElementById('qr-foreground'), document.getElementById('qr-background')]
    .forEach((control) => control.addEventListener('input', clearResult));
  window.addEventListener('beforeunload', () => {
    if (link.dataset.url) URL.revokeObjectURL(link.dataset.url);
  });
})();
