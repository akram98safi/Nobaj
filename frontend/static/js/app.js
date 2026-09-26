/**
 * Nobaj - Next-Gen Media Tools Platform
 * Interactive Client Application
 */

// --- Global State ---
let currentLang = 'ar';
try {
  currentLang = localStorage.getItem('nobaj_lang') || 'ar';
} catch (error) {
  // The app remains usable when browser storage is disabled.
}
let activeTab = 'compress';
let uploadedFileMeta = null;
let currentJobId = null;
let pollInterval = null;
let previewObjectUrl = null;
let uploadInProgress = false;
let processingRequestInFlight = false;

// --- i18n Localization ---
let translations = {};

const languageNames = {
  ar: 'العربية',
  en: 'English',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  pt: 'Português',
  it: 'Italiano',
  tr: 'Türkçe',
  ru: 'Русский',
  zh: '简体中文',
  ja: '日本語',
  ko: '한국어',
  hi: 'हिन्दी'
};

async function loadTranslations(lang) {
  try {
    const response = await fetch(`/static/lang/${lang}.json`);
    if (!response.ok) throw new Error('Failed to load language file');
    translations = await response.json();
  } catch (e) {
    console.error('Language load error', e);
    translations = {};
  }
}

// --- DOM Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  setupLanguage();
  setupTabs();
  setupDragAndDrop();
  setupEventListeners();
  loadPublicStats();
});

function setupLanguage() {
  const htmlEl = document.documentElement;
  const langToggleBtn = document.getElementById('lang-toggle');
  const currentLanguageEl = document.getElementById('current-language');
  const langMenu = document.getElementById('lang-menu');

  async function applyLanguage(lang) {
    if (!languageNames[lang]) lang = 'en';
    currentLang = lang;
    try {
      localStorage.setItem('nobaj_lang', lang);
    } catch (error) {
      // Language selection still applies for this page even without storage.
    }
    htmlEl.lang = lang;
    htmlEl.dir = lang === 'ar' ? 'rtl' : 'ltr';

    if (currentLanguageEl) currentLanguageEl.textContent = languageNames[lang];
    document.querySelectorAll('.language-option').forEach(option => {
      option.classList.toggle('is-selected', option.dataset.lang === lang);
      option.setAttribute('aria-current', option.dataset.lang === lang ? 'true' : 'false');
    });

    // Load translation file
    await loadTranslations(lang);

    // Replace all data-i18n elements
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (translations[key]) {
        const ttl = el.dataset.i18nTtl || '';
        el.textContent = translations[key].replace('{ttl}', ttl).replace('{size}', el.dataset.i18nSize || '');
      }
    });

    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
      const value = translations[el.dataset.i18nAriaLabel];
      if (value) el.setAttribute('aria-label', value);
    });

    // Replace placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      if (translations[key]) {
        el.placeholder = translations[key];
      }
    });

    if (langMenu) langMenu.classList.add('hidden');
    if (langToggleBtn) langToggleBtn.setAttribute('aria-expanded', 'false');
  }

  if (langToggleBtn) {
    langToggleBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      const isOpen = langMenu && !langMenu.classList.contains('hidden');
      if (langMenu) langMenu.classList.toggle('hidden', isOpen);
      langToggleBtn.setAttribute('aria-expanded', String(!isOpen));
    });
  }

  document.querySelectorAll('.language-option').forEach(option => {
    option.addEventListener('click', () => applyLanguage(option.dataset.lang));
  });

  document.addEventListener('click', (event) => {
    if (langMenu && langToggleBtn && !langMenu.contains(event.target) && !langToggleBtn.contains(event.target)) {
      langMenu.classList.add('hidden');
      langToggleBtn.setAttribute('aria-expanded', 'false');
    }
  });

  applyLanguage(currentLang);
}

async function loadPublicStats() {
  try {
    const response = await fetch('/api/stats/public');
    if (!response.ok) return;
    const stats = await response.json();
    setMetric('stat-total-visitors', stats.total_visitors);
    setMetric('stat-today-visitors', stats.today_visitors);
    setMetric('stat-completed-operations', stats.completed_operations);
    setMetric('stat-processed-size', formatBytes(stats.processed_bytes || 0));
  } catch (error) {
    // The landing page remains fully usable if analytics is unavailable.
    console.debug('Public stats unavailable:', error);
  }
}

function setMetric(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function formatBytes(bytes) {
  if (!bytes) return '0 MB';
  const megabytes = bytes / (1024 * 1024);
  if (megabytes < 1024) return `${megabytes.toFixed(megabytes < 10 ? 1 : 0)} MB`;
  return `${(megabytes / 1024).toFixed(1)} GB`;
}

function setupTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      if (target === 'more') return;

      activeTab = target;

      tabs.forEach(b => {
        b.classList.remove('active-tab');
        b.classList.add('text-slate-400');
      });

      btn.classList.add('active-tab');
      btn.classList.remove('text-slate-400');

      // Show relevant option panels
      document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.add('hidden');
      });
      const activePanel = document.getElementById(`panel-${target}`);
      if (activePanel) {
        activePanel.classList.remove('hidden');
      }
    });
  });
}

function setupDragAndDrop() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  if (!dropZone || !fileInput) return;

  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dropzone-active');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dropzone-active');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  dropZone.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
    }
  });
}

function setupEventListeners() {
  // Action buttons for each tab
  const btnCompress = document.getElementById('btn-start-compress');
  if (btnCompress) btnCompress.addEventListener('click', () => startProcessing('compress'));

  const btnAudio = document.getElementById('btn-start-audio');
  if (btnAudio) btnAudio.addEventListener('click', () => startProcessing('audio'));

  const btnGif = document.getElementById('btn-start-gif');
  if (btnGif) btnGif.addEventListener('click', () => startProcessing('gif'));

  // Cancel Button
  const btnCancel = document.getElementById('btn-cancel-job');
  if (btnCancel) btnCancel.addEventListener('click', cancelCurrentJob);

  // Convert another
  const btnAnother = document.getElementById('btn-convert-another');
  if (btnAnother) btnAnother.addEventListener('click', resetAll);
}

// --- Upload Handling ---
async function handleFileUpload(file) {
  if (!file || uploadInProgress) return;
  uploadInProgress = true;

  const dropZone = document.getElementById('drop-zone');
  const uploadProgress = document.getElementById('upload-progress-container');
  const uploadBar = document.getElementById('upload-bar');
  const editorArea = document.getElementById('editor-area');
  const completedArea = document.getElementById('completed-area');

  completedArea.classList.add('hidden');
  editorArea.classList.add('hidden');
  uploadProgress.classList.remove('hidden');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload', true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        uploadBar.style.width = `${percent}%`;
      }
    };

    xhr.onload = () => {
      uploadInProgress = false;
      uploadProgress.classList.add('hidden');
      if (xhr.status === 200) {
        try {
          const data = JSON.parse(xhr.responseText);
          uploadedFileMeta = data;
          populateMediaDetails(file, data);
        } catch (error) {
          alert(translations.err_fail || '');
        }
      } else {
        let errMessage = translations.err_fail || '';
        try {
          const errObj = JSON.parse(xhr.responseText);
          if (errObj.detail) errMessage = errObj.detail;
        } catch (_) {}
        alert(errMessage);
      }
    };

    xhr.onerror = () => {
      uploadInProgress = false;
      uploadProgress.classList.add('hidden');
      alert(translations.err_fail || '');
    };

    xhr.onabort = () => {
      uploadInProgress = false;
      uploadProgress.classList.add('hidden');
    };

    xhr.send(formData);

  } catch (err) {
    uploadInProgress = false;
    uploadProgress.classList.add('hidden');
    console.error(err);
    alert(err.message || translations.err_fail || '');
  }
}

function populateMediaDetails(file, meta) {
  const editorArea = document.getElementById('editor-area');
  const videoPlayer = document.getElementById('video-preview-player');
  const trimEndInput = document.getElementById('gif-trim-end');
  const trimStartInput = document.getElementById('gif-trim-start');

  editorArea.classList.remove('hidden');
  editorArea.scrollIntoView({ behavior: 'smooth' });

  // Update metadata tags
  document.getElementById('meta-filename').textContent = meta.original_name;
  document.getElementById('meta-size').textContent = meta.size_formatted;
  document.getElementById('meta-duration').textContent = meta.duration_formatted;
  document.getElementById('meta-resolution').textContent = meta.resolution;
  document.getElementById('meta-codec').textContent = `${meta.video_codec} / ${meta.audio_codec}`;

  // Video preview player
  if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
  previewObjectUrl = null;
  if (meta.has_video) {
    previewObjectUrl = URL.createObjectURL(file);
    videoPlayer.src = previewObjectUrl;
    videoPlayer.classList.remove('hidden');

    if (trimEndInput) {
      trimEndInput.value = Math.min(meta.duration, 10);
      trimEndInput.max = meta.duration;
    }
    if (trimStartInput) {
      trimStartInput.value = 0;
      trimStartInput.max = meta.duration;
    }
  } else {
    videoPlayer.classList.add('hidden');
  }
}

// --- Start Job Processing ---
async function startProcessing(operation) {
  if (processingRequestInFlight) return;
  if (!uploadedFileMeta || !uploadedFileMeta.file_id) {
    alert(translations.err_select || '');
    return;
  }

  let options = {};

  if (operation === 'compress') {
    const quality = document.getElementById('comp-quality-select').value;
    const resolution = document.getElementById('comp-res-select').value;
    const codec = document.getElementById('comp-codec-select').value;
    options = { quality, resolution, codec };
  } else if (operation === 'audio') {
    const format = document.getElementById('audio-format-select').value;
    const bitrate = document.getElementById('audio-bitrate-select').value;
    const channels = document.getElementById('audio-channels-select').value;
    options = { format, bitrate, channels };
  } else if (operation === 'gif') {
    const fps = parseInt(document.getElementById('gif-fps-select').value, 10);
    const resolution = document.getElementById('gif-res-select').value;
    const trim_start = parseFloat(document.getElementById('gif-trim-start').value || 0);
    const trim_end = parseFloat(document.getElementById('gif-trim-end').value || 0);
    options = { fps, resolution, trim_start, trim_end };
  }

  // Switch UI to Processing state
  processingRequestInFlight = true;
  showProcessingState();

  try {
    const response = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_id: uploadedFileMeta.file_id,
        operation: operation,
        options: options
      })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || translations.err_fail || '');
    }

    const data = await response.json();
    currentJobId = data.job_id;

    // Start polling status
    startPolling(currentJobId);

  } catch (err) {
    processingRequestInFlight = false;
    hideProcessingState();
    alert(err.message || translations.err_fail || '');
  }
}

function showProcessingState() {
  document.getElementById('processing-area').classList.remove('hidden');
  document.getElementById('editor-controls').classList.add('hidden');
  document.getElementById('completed-area').classList.add('hidden');
}

function hideProcessingState() {
  document.getElementById('processing-area').classList.add('hidden');
  document.getElementById('editor-controls').classList.remove('hidden');
}

function startPolling(jobId) {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/job/${jobId}`);
      if (!res.ok) {
        clearInterval(pollInterval);
        processingRequestInFlight = false;
        hideProcessingState();
        return;
      }

      const job = await res.json();
      updateJobProgressUI(job);

      if (job.status === 'completed') {
        clearInterval(pollInterval);
        showCompletedState(job);
      } else if (job.status === 'failed' || job.status === 'cancelled') {
        clearInterval(pollInterval);
        processingRequestInFlight = false;
        hideProcessingState();
        alert(job.error_message || translations.err_fail || '');
      }
    } catch (err) {
      console.error("Polling error:", err);
    }
  }, 750);
}

function updateJobProgressUI(job) {
  const statusEl = document.getElementById('job-status-text');
  const percentEl = document.getElementById('job-progress-percent');
  const progressBar = document.getElementById('job-progress-bar');
  const speedEl = document.getElementById('job-speed');
  const etaEl = document.getElementById('job-eta');

  if (job.status === 'queued') {
    statusEl.textContent = `${translations.status_queued || ''} ${job.queue_position || 1}`;
    percentEl.textContent = '⏳';
    progressBar.style.width = '10%';
  } else {
    statusEl.textContent = translations.status_processing || '';
    percentEl.textContent = `${Math.round(job.progress)}%`;
    progressBar.style.width = `${Math.max(5, job.progress)}%`;
  }

  speedEl.textContent = job.speed ? `${translations.speed || ''}: ${job.speed}` : '';
  etaEl.textContent = job.eta ? `${translations.eta || ''}: ${job.eta}` : '';
}

function showCompletedState(job) {
  processingRequestInFlight = false;
  hideProcessingState();
  const completedArea = document.getElementById('completed-area');
  completedArea.classList.remove('hidden');
  completedArea.scrollIntoView({ behavior: 'smooth' });

  // Format sizes
  const inputSizeMB = (job.input_size / (1024 * 1024)).toFixed(2);
  const outputSizeMB = (job.output_size / (1024 * 1024)).toFixed(2);

  document.getElementById('result-filename').textContent = job.output_filename;
  document.getElementById('result-new-size').textContent = `${outputSizeMB} MB`;

  const savingsBadge = document.getElementById('result-savings-badge');
  if (job.reduction_pct > 0) {
    savingsBadge.classList.remove('hidden');
    savingsBadge.textContent = `${translations.saved_size || ''} ${job.reduction_pct}%`;
  } else {
    savingsBadge.classList.add('hidden');
  }

  // Set download button URL
  const downloadBtn = document.getElementById('btn-download-result');
  downloadBtn.href = `/api/download/${job.id}`;
}

async function cancelCurrentJob() {
  if (!currentJobId) return;
  try {
    const response = await fetch(`/api/job/${currentJobId}/cancel`, { method: 'POST' });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || translations.err_fail || '');
    }
    clearInterval(pollInterval);
    processingRequestInFlight = false;
    hideProcessingState();
  } catch (e) {
    console.error(e);
    alert(e.message || translations.err_fail || '');
  }
}

function resetAll() {
  if (pollInterval) clearInterval(pollInterval);
  uploadedFileMeta = null;
  currentJobId = null;
  uploadInProgress = false;
  processingRequestInFlight = false;

  document.getElementById('editor-area').classList.add('hidden');
  document.getElementById('completed-area').classList.add('hidden');
  document.getElementById('processing-area').classList.add('hidden');
  document.getElementById('file-input').value = '';
  document.getElementById('video-preview-player').src = '';
  if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
  previewObjectUrl = null;
  document.getElementById('drop-zone').scrollIntoView({ behavior: 'smooth' });
}
