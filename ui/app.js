const $ = selector => document.querySelector(selector);
const labels = {manual: 'Вручную', auto: 'Авто', fallback: 'Резерв'};
const modeDetails = {
  manual: 'Трафик направляется через выбранную страну',
  auto: 'Xray выбирает маршрут с меньшей задержкой',
  fallback: 'Xray переключается на доступный резерв'
};
const localFlags = new Set(['RS', 'EE', 'SK', 'RO']);
const tests = new Map();
const testing = new Set();
let state = null;

function escapeText(value) {
  const node = document.createElement('span');
  node.textContent = value ?? '';
  return node.innerHTML;
}

function flagMarkup(node, className = 'flag') {
  const code = String(node.countryCode || '').toUpperCase();
  if (localFlags.has(code)) {
    return `<img class="${className}" src="./flags/${code.toLowerCase()}.svg" alt="" width="40" height="28">`;
  }
  return `<span class="${className} country-code" aria-hidden="true">${escapeText(code || 'VPN')}</span>`;
}

function testView(id) {
  if (testing.has(id)) return {label: 'Проверяем…', state: 'testing'};
  const result = tests.get(id);
  if (!result) return {label: 'Проверить', state: 'idle'};
  return result.ok
    ? {label: `${result.latency} мс`, state: 'ok'}
    : {label: 'Нет ответа', state: 'error'};
}

function renderActive(data) {
  const selected = data.nodes.find(node => node.id === data.selected) || data.nodes[0];
  const visual = $('#active-visual');
  if (!selected) {
    visual.innerHTML = '<span>—</span>';
    $('#route-heading').textContent = 'Нет доступных маршрутов';
    $('#route-detail').textContent = 'Обновите подписку или проверьте её адрес';
    return;
  }
  visual.innerHTML = flagMarkup(selected, 'active-flag');
  $('#route-heading').textContent = data.mode === 'manual' ? selected.country : labels[data.mode];
  $('#route-detail').textContent = data.mode === 'manual'
    ? selected.name
    : `${modeDetails[data.mode]} · резерв: ${selected.country}`;
}

function render(data) {
  state = data;
  $('.health').classList.toggle('online', data.ready);
  $('#health-text').textContent = data.ready ? 'Xray работает' : 'Xray недоступен';
  $('#core').textContent = data.core;
  $('#version').textContent = data.version;
  $('#active-mode').textContent = labels[data.mode] || data.mode;
  $('#updated').textContent = data.lastRefresh
    ? new Date(data.lastRefresh * 1000).toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})
    : '—';
  $('#count').textContent = data.nodes.length;
  renderActive(data);
  document.querySelectorAll('[data-mode]').forEach(button => {
    button.setAttribute('aria-checked', String(button.dataset.mode === data.mode));
  });
  $('#test-all').disabled = testing.size > 0 || data.nodes.length === 0;
  $('#test-all span').textContent = testing.size > 1 ? `Проверяем ${testing.size}` : 'Проверить все';
  $('#nodes').innerHTML = data.nodes.length ? data.nodes.map(node => {
    const check = testView(node.id);
    const selected = node.id === data.selected;
    return `<article class="node${selected ? ' selected' : ''}">
      <button class="node-select" type="button" role="radio" aria-checked="${selected}" data-node="${escapeText(node.id)}">
        <span class="flag-frame" aria-hidden="true">${flagMarkup(node)}</span>
        <span class="node-copy"><strong>${escapeText(node.country)}</strong><small>${escapeText(node.name)}</small></span>
        <span class="selection" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m6 12 4 4 8-9"/></svg></span>
      </button>
      <button class="node-test" type="button" data-test="${escapeText(node.id)}" data-state="${check.state}" ${testing.has(node.id) ? 'disabled' : ''} aria-label="Проверить маршрут ${escapeText(node.country)}">${check.label}</button>
    </article>`;
  }).join('') : '<div class="empty-state"><strong>Страны не найдены</strong><p>Проверьте ссылку подписки и нажмите «Обновить подписку».</p></div>';
  $('#error').hidden = !data.error;
  $('#error').textContent = data.error || '';
}

function setBusy(active) {
  document.body.classList.toggle('busy', active);
  document.querySelectorAll('[data-mode], [data-node], #refresh').forEach(button => { button.disabled = active; });
}

async function request(path, body, busy = true) {
  if (busy) setBusy(true);
  try {
    const response = await fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: {'Content-Type': 'application/json'},
      body: body ? JSON.stringify(body) : undefined
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Не удалось выполнить запрос');
    render(data);
    if (body && path === '/api/refresh') $('#announcer').textContent = 'Подписка обновлена';
  } catch (error) {
    $('#error').hidden = false;
    $('#error').textContent = `${error.message}. Повторите попытку.`;
  } finally {
    if (busy) setBusy(false);
  }
}

async function testConnections(nodeId = '') {
  const ids = nodeId ? [nodeId] : state.nodes.map(node => node.id);
  ids.forEach(id => testing.add(id));
  render(state);
  try {
    const response = await fetch('/api/test', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(nodeId ? {node: nodeId} : {})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Проверка не выполнена');
    data.results.forEach(result => tests.set(result.id, result));
    const available = data.results.filter(result => result.ok).length;
    $('#announcer').textContent = `Проверка завершена. Доступно маршрутов: ${available}`;
  } catch (error) {
    $('#error').hidden = false;
    $('#error').textContent = `${error.message}. Проверьте доступ контейнера в интернет.`;
  } finally {
    ids.forEach(id => testing.delete(id));
    render(state);
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('jackett-theme', theme);
  $('#theme-toggle').setAttribute('aria-label', theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему');
}

document.addEventListener('click', event => {
  const mode = event.target.closest('[data-mode]');
  const node = event.target.closest('[data-node]');
  const test = event.target.closest('[data-test]');
  if (mode && state) request('/api/state', {mode: mode.dataset.mode, selected: state.selected});
  if (node && state) request('/api/state', {mode: state.mode, selected: node.dataset.node});
  if (test && state) testConnections(test.dataset.test);
  if (event.target.closest('#test-all') && state) testConnections();
  if (event.target.closest('#refresh')) request('/api/refresh', {});
  if (event.target.closest('#theme-toggle')) setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

setTheme(localStorage.getItem('jackett-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
request('/api/status');
setInterval(() => request('/api/status', undefined, false), 30000);
