(() => {
  const id = 'jackett-core-versions';
  if (document.getElementById(id)) return;
  const badge = document.createElement('div');
  badge.id = id;
  badge.textContent = 'Mihomo 1.19.33 · Xray 26.10.21';
  badge.setAttribute('aria-label', 'Версии ядер: Mihomo 1.19.33, Xray 26.10.21');
  Object.assign(badge.style, {
    position: 'fixed',
    right: '12px',
    bottom: '12px',
    zIndex: '2147483647',
    padding: '6px 10px',
    borderRadius: '999px',
    background: 'rgba(15, 23, 42, .88)',
    color: '#e2e8f0',
    border: '1px solid rgba(148, 163, 184, .35)',
    boxShadow: '0 4px 18px rgba(0, 0, 0, .24)',
    font: '600 11px/1.2 system-ui, -apple-system, sans-serif',
    letterSpacing: '.01em',
    pointerEvents: 'none',
    backdropFilter: 'blur(8px)'
  });
  document.body.appendChild(badge);
})();
