// Local preview of index.html with a minimal mock of the dashboard runtime (dash API + tokens).
// usage: node render.js OUTPREFIX [width ...]   -> OUTPREFIX-<width>-<theme>.png, console errors on stdout
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const dir = __dirname;
const page = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
const d3src = fs.readFileSync(path.join(dir, 'node_modules/d3/dist/d3.min.js'), 'utf8');
const data = {};
for (const f of fs.readdirSync(path.join(dir, 'data'))) {
  if (f.endsWith('.json')) data[f.replace('.json', '')] = JSON.parse(fs.readFileSync(path.join(dir, 'data', f), 'utf8'));
}
const tokens = `
:root { --color-fg:#1d1c1a; --color-fg-muted:#6b6a65; --color-bg:#ffffff; --color-panel:#f7f6f3; --color-border-line:#e4e2dc;
  --color-ok:#0ca30c; --color-warn:#fab219; --color-bad:#d03b3b; --font-anthropic-sans: system-ui, sans-serif; --font-anthropic-serif: Georgia, serif;
  --cds-font-size-caption:12px; --cds-font-size-body:14px; --cds-font-size-heading:18px; --cds-font-size-title:26px; --cds-font-weight-medium:600;
  --cds-gap-xs:4px; --cds-gap-sm:8px; --cds-gap-md:12px; --cds-gap-lg:20px; --cds-gap-xl:32px; --cds-pad-xs:4px; --cds-pad-sm:8px; --cds-pad-md:12px; --cds-pad-lg:16px; --cds-pad-xl:24px;
  --cds-radius:8px; --cds-chart-muted:#b9b7b0; --cds-chart-status-critical:#d03b3b; --cds-chart-grid:#ecebe6; --cds-chart-axis:#c3c2b7; --cds-chart-reference:#898781;
  --cds-surface-popover:#ffffff; --cds-border:#e1e0d9; --cds-shadow-popover:0 4px 16px rgba(0,0,0,.12); --cds-text-secondary:#52514e;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4; --s6:#008300; --s7:#6250d6; --s8:#e34948; }
html.dark { --color-fg:#f0efec; --color-fg-muted:#a3a29b; --color-bg:#1a1a19; --color-panel:#232321; --color-border-line:#383835;
  --cds-chart-grid:#2c2c2a; --cds-chart-axis:#383835; --cds-chart-reference:#898781; --cds-surface-popover:#262624; --cds-border:#383835; --cds-text-secondary:#c3c2b7;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767; --cds-chart-status-critical:#e66767; color-scheme: dark; }
body { margin:0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 14px; }
#dash-root { padding: 24px 16px; }
.dash-skeleton { background: var(--color-panel); }
`;
const mock = `
window.dash = (() => {
  const D = window.__DATA, calcs = {}, draws = {}, onDatas = [];
  const api = {
    colors: ['var(--s1)','var(--s2)','var(--s3)','var(--s4)','var(--s5)','var(--s6)','var(--s7)','var(--s8)'],
    data(id) {
      if (calcs[id]) { const c = calcs[id]; try { return { status: 'ok', data: c.fn(...c.inputs.map((i) => api.data(i).data)) }; } catch (e) { console.error('calc ' + id + ': ' + e); return { status: 'error', data: null }; } }
      const rows = D[id]; return rows ? { status: 'ok', data: rows, columns: Object.keys(rows[0] || {}) } : { status: 'missing', data: [] };
    },
    calc(id, spec) { calcs[id] = spec; }, loader() {},
    draw(name, fn) { if (fn) { draws[name] = fn; if (api._ready) api._run(name); } else api._run(name); },
    onData(fn) { onDatas.push(fn); fn(); },
    params: () => ({}), setParams() {}, resetParams() {}, setLink() {}, refresh() {},
    _run(name) { document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => { try { draws[name](el); } catch (e) { console.error('draw ' + name + ': ' + e.stack); } }); },
    _runAll() { api._ready = true; for (const n of Object.keys(draws)) api._run(n); },
  };
  return api;
})();
`;
const html = `<!doctype html><html><head><meta charset="utf-8"><style>${tokens}</style>
<script>${d3src}</script><script>window.__DATA=${JSON.stringify(data).replace(/<\//g, '<\\/')};</script><script>${mock}</script></head>
<body><div id="dash-root"></div>
<script>
const src = ${JSON.stringify(page).replace(/<\//g, '<\\/')};
const tpl = document.createElement('template'); tpl.innerHTML = src;
const scripts = [...tpl.content.querySelectorAll('script')].map((s) => { const t = s.textContent; s.remove(); return t; });
document.getElementById('dash-root').appendChild(tpl.content);
for (const s of scripts) { try { new Function(s)(); } catch (e) { console.error('script: ' + e.stack); } }
dash._runAll();
</script></body></html>`;
fs.writeFileSync(path.join(dir, 'harness.html'), html);

(async () => {
  const out = process.argv[2] || path.join(dir, 'shot');
  const widths = process.argv.slice(3).map(Number);
  const browser = await chromium.launch();
  for (const w of widths.length ? widths : [1100, 420]) {
    for (const theme of ['light', 'dark']) {
      const p = await browser.newPage({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 });
      const errors = [];
      p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.text()); });
      p.on('pageerror', (e) => errors.push(String(e)));
      await p.goto('file://' + path.join(dir, 'harness.html'));
      if (theme === 'dark') await p.evaluate(() => { document.documentElement.classList.add('dark'); dash._runAll(); });
      await p.waitForTimeout(300);
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      await p.screenshot({ path: `${out}-${w}-${theme}.png`, fullPage: true });
      console.log(`${w} ${theme}: overflow=${overflow}px errors=${errors.length}`);
      for (const e of errors.slice(0, 8)) console.log('   ', e.slice(0, 300));
      await p.close();
    }
  }
  await browser.close();
})();
