const $ = selector => document.querySelector(selector);
const labels = {manual: 'Вручную', auto: 'Авто', fallback: 'Резерв'};
const tests = new Map();
const testing = new Set();
let state = null;

function escapeText(value) {
  const node = document.createElement('span');
  node.textContent = value;
  return node.innerHTML;
}

function testView(id) {
  if (testing.has(id)) return {label: 'Проверка…', state: 'testing'};
  const result = tests.get(id);
  if (!result) return {label: 'Проверить', state: 'idle'};
  return result.ok
    ? {label: `${result.latency} мс`, state: 'ok'}
    : {label: 'Недоступен', state: 'error'};
}

function render(data) {
  state = data;
  $('.health').classList.toggle('online', data.ready);
  $('#health-text').textContent = data.ready ? 'Xray работает' : 'Нет подключения';
  $('#core').textContent = data.core;
  $('#version').textContent = data.version;
  $('#updated').textContent = data.lastRefresh
    ? new Date(data.lastRefresh * 1000).toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'})
    : '—';
  document.querySelectorAll('[data-mode]').forEach(button => {
    button.setAttribute('aria-checked', String(button.dataset.mode === data.mode));
  });
  $('#count').textContent = data.nodes.length;
  $('#test-all').disabled = testing.size > 0 || data.nodes.length === 0;
  $('#nodes').innerHTML = data.nodes.map(node => {
    const check = testView(node.id);
    const selected = node.id === data.selected;
    return `<div class="node${selected ? ' selected' : ''}">
      <button class="node-select" type="button" role="radio" aria-checked="${selected}" data-node="${escapeText(node.id)}">
        <span class="node-icon" aria-hidden="true">${escapeText(node.flag)}</span>
        <span class="node-copy"><strong>${escapeText(node.name)}</strong><small>${escapeText(node.country)} · ${escapeText(labels[data.mode])}</small></span>
        <span class="check" aria-hidden="true"></span>
      </button>
      <button class="node-test" type="button" data-test="${escapeText(node.id)}" data-state="${check.state}" ${testing.has(node.id) ? 'disabled' : ''} aria-label="Проверить подключение ${escapeText(node.name)}">${check.label}</button>
    </div>`;
  }).join('');
  $('#error').hidden = !data.error;
  $('#error').textContent = data.error || '';
}

function setBusy(active) {
  document.body.classList.toggle('busy', active);
  document.querySelectorAll('[data-mode], [data-node], [data-test], #test-all, #refresh').forEach(button => { button.disabled = active; });
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
  } catch (error) {
    $('#error').hidden = false;
    $('#error').textContent = error.message;
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
  } catch (error) {
    $('#error').hidden = false;
    $('#error').textContent = error.message;
  } finally {
    ids.forEach(id => testing.delete(id));
    render(state);
  }
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
});

request('/api/status');
setInterval(() => request('/api/status', undefined, false), 30000);
