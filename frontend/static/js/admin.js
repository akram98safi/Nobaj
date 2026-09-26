/* Nobaj private analytics dashboard. */

const tokenStorageKey = 'nobaj_admin_token';
let adminToken = '';
let adminTranslations = {};

function adminText(key, values = {}) {
  return (adminTranslations[key] || key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ''));
}

async function loadAdminTranslations() {
  let lang = 'en';
  try { lang = localStorage.getItem('nobaj_lang') || 'en'; } catch (error) {}
  try {
    const response = await fetch(`/static/lang/${encodeURIComponent(lang)}.json`);
    if (!response.ok) throw new Error('translation unavailable');
    adminTranslations = await response.json();
  } catch (error) {
    const response = await fetch('/static/lang/en.json');
    adminTranslations = response.ok ? await response.json() : {};
  }
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const value = adminTranslations[el.dataset.i18n];
    if (value) el.textContent = value;
  });
}
try {
  adminToken = sessionStorage.getItem(tokenStorageKey) || '';
} catch (error) {
  // The dashboard can still be used for the current page session.
}

function clearStoredToken() {
  try {
    sessionStorage.removeItem(tokenStorageKey);
  } catch (error) {
    // Ignore unavailable browser storage.
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadAdminTranslations();
  const form = document.getElementById('admin-login-form');
  const refresh = document.getElementById('admin-refresh');
  const logout = document.getElementById('admin-logout');
  if (form) form.addEventListener('submit', handleLogin);
  if (refresh) refresh.addEventListener('click', () => loadDashboard());
  if (logout) logout.addEventListener('click', handleLogout);
  if (adminToken) loadDashboard();
});

function handleLogout() {
  adminToken = '';
  clearStoredToken();
  document.getElementById('admin-token').value = '';
  document.getElementById('admin-dashboard').classList.add('hidden');
  document.getElementById('admin-login').classList.remove('hidden');
  showError('');
}

async function handleLogin(event) {
  event.preventDefault();
  adminToken = document.getElementById('admin-token').value.trim();
  if (!adminToken) return showError(adminText('admin_enter_token'));
  try {
    sessionStorage.setItem(tokenStorageKey, adminToken);
  } catch (error) {
    // Authentication remains valid for this page load.
  }
  await loadDashboard();
}

async function loadDashboard() {
  try {
    const response = await fetch('/api/stats/admin', {
      headers: { 'X-Admin-Token': adminToken }
    });
    if (!response.ok) {
      clearStoredToken();
      if (response.status === 503) {
        showError(adminText('admin_disabled'));
      } else {
        showError(adminText('admin_invalid_token'));
      }
      return;
    }
    const data = await response.json();
    renderDashboard(data);
  } catch (error) {
    showError(adminText('admin_connection_error'));
  }
}

function renderDashboard(data) {
  document.getElementById('admin-login').classList.add('hidden');
  document.getElementById('admin-dashboard').classList.remove('hidden');
  setText('admin-total-visitors', formatNumber(data.total_visitors));
  setText('admin-today-visitors', formatNumber(data.today_visitors));
  setText('admin-total-operations', formatNumber(data.total_operations));
  setText('admin-completed-operations', formatNumber(data.completed_operations));

  const operations = data.operations_by_type || [];
  const maxTotal = Math.max(...operations.map(item => item.total), 1);
  document.getElementById('admin-operation-list').innerHTML = operations.length
    ? operations.map(item => `
      <div class="admin-bar-row">
        <div class="admin-bar-label"><span>${escapeHtml(item.operation)}</span><b>${item.total}</b></div>
        <div class="admin-bar-track"><i style="width:${Math.max(7, (item.total / maxTotal) * 100)}%"></i></div>
        <small>${escapeHtml(adminText('admin_completed_failed', { completed: item.completed || 0, failed: item.failed || 0 }))}</small>
      </div>`).join('')
    : `<p class="admin-empty">${escapeHtml(adminText('admin_no_operations'))}</p>`;

  document.getElementById('admin-daily-visits').innerHTML = (data.daily_visits || []).slice().reverse().map(item => `
    <tr><td>${escapeHtml(item.day)}</td><td>${item.visits}</td><td>${item.unique_visitors}</td></tr>
  `).join('') || `<tr><td colspan="3">${escapeHtml(adminText('admin_no_visits'))}</td></tr>`;
  setText('admin-status', adminText('admin_database', { database: data.database }));
}

function showError(message) {
  const error = document.getElementById('admin-error');
  if (error) error.textContent = message;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function formatNumber(value) {
  return new Intl.NumberFormat(document.documentElement.lang || 'ar').format(value || 0);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[char]));
}
