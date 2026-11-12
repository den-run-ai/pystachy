// Offline exports of the dashboard page: a self-contained HTML file, an A4 PDF and one PNG per chart.
// usage: node export.js OUTDIR
// The page's own scripts run unchanged against a small stand-in for the dashboard runtime (data
// inlined, drawings rerun on resize), so the exported charts are the same drawings as the dashboard's.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const dir = __dirname;
const out = path.resolve(process.argv[2] || path.join(dir, 'export'));
fs.mkdirSync(path.join(out, 'images'), { recursive: true });
const page = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
const d3src = fs.readFileSync(path.join(dir, 'node_modules/d3/dist/d3.min.js'), 'utf8');
const data = {};
for (const f of fs.readdirSync(path.join(dir, 'data'))) {
  if (f.endsWith('.json')) data[f.replace('.json', '')] = JSON.parse(fs.readFileSync(path.join(dir, 'data', f), 'utf8'));
}
const sources = JSON.parse(fs.readFileSync(path.join(dir, 'sources.json'), 'utf8'));
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const inlineJSON = (v) => JSON.stringify(v).replace(/</g, '\\u003c');

const light = `--color-fg:#1d1c1a; --color-fg-muted:#5f5e59; --color-bg:#ffffff; --color-panel:#f6f5f2; --color-border-line:#e2e0da;
  --cds-chart-grid:#ecebe6; --cds-chart-axis:#c3c2b7; --cds-chart-reference:#898781; --cds-chart-status-critical:#d03b3b;
  --cds-surface-popover:#ffffff; --cds-border:#e1e0d9; --cds-text-secondary:#52514e;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4; --s6:#008300; --s7:#6250d6; --s8:#e34948;`;
const dark = `--color-fg:#f0efec; --color-fg-muted:#a9a8a1; --color-bg:#1a1a19; --color-panel:#232321; --color-border-line:#383835;
  --cds-chart-grid:#2c2c2a; --cds-chart-axis:#45453f; --cds-chart-reference:#898781; --cds-chart-status-critical:#e66767;
  --cds-surface-popover:#262624; --cds-border:#383835; --cds-text-secondary:#c3c2b7;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;`;
const css = `
:root { ${light}
  --font-anthropic-sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-anthropic-serif: Georgia, "Times New Roman", serif;
  --cds-font-size-caption:12px; --cds-font-size-body:14px; --cds-font-size-heading:18px; --cds-font-size-title:28px; --cds-font-weight-medium:600;
  --cds-gap-xs:4px; --cds-gap-sm:8px; --cds-gap-md:12px; --cds-gap-lg:20px; --cds-gap-xl:32px;
  --cds-pad-xs:4px; --cds-pad-sm:8px; --cds-pad-md:12px; --cds-pad-lg:16px; --cds-pad-xl:24px;
  --cds-radius:8px; --cds-shadow-popover:0 4px 16px rgba(0,0,0,.14); color-scheme: light; }
@media (prefers-color-scheme: dark) { :root { ${dark} color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 14px; line-height: 1.45; }
.pz-page { max-width: 1112px; margin: 0 auto; padding: 32px max(16px, env(safe-area-inset-left, 0px)) 48px max(16px, env(safe-area-inset-right, 0px)); display: flex; flex-direction: column; gap: 24px; }
.pz-masthead h1 { font-family: var(--font-anthropic-serif); font-weight: 400; font-size: var(--cds-font-size-title); margin: 0 0 6px; }
.pz-masthead p { margin: 0; color: var(--color-fg-muted); max-width: 80ch; }
.pz-sources { border-top: 1px solid var(--color-border-line); padding-top: 16px; }
.pz-sources h2 { font-size: var(--cds-font-size-heading); margin: 0 0 8px; }
.pz-sources dl { display: grid; grid-template-columns: minmax(150px, max-content) 1fr; gap: 6px 16px; margin: 0; font-size: 13px; }
.pz-sources dt { font-weight: 600; } .pz-sources dd { margin: 0; color: var(--color-fg-muted); }
@media (max-width: 560px) { .pz-sources dl { grid-template-columns: 1fr; } .pz-sources dd { margin-bottom: 8px; } }
@media print {
  body { background: #fff; }
  .pz-tip { display: none !important; }
  .pz-chart, .pz-tile, .pz-table tr, .pz-legend, .pz-two > div, .pz-sources dt, .pz-sources dd { break-inside: avoid; }
  h1, h2, h3, .pz-legend, .pz-controls { break-after: avoid; }
  .pz-controls select { appearance: none; border: 0; padding: 0; background: none; font-weight: 600; color: inherit; }
}`;
const shim = `
window.dash = (() => {
  const D = window.__DATA, calcs = {}, draws = {};
  const api = {
    colors: ['var(--s1)','var(--s2)','var(--s3)','var(--s4)','var(--s5)','var(--s6)','var(--s7)','var(--s8)'],
    data(id) {
      if (calcs[id]) { const c = calcs[id]; try { return { status: 'ok', data: c.fn(...c.inputs.map((i) => api.data(i).data)) }; } catch (e) { console.error(e); return { status: 'error', data: null }; } }
      const rows = D[id]; return rows ? { status: 'ok', data: rows, columns: Object.keys(rows[0] || {}) } : { status: 'missing', data: [] };
    },
    calc(id, spec) { calcs[id] = spec; }, loader() {},
    draw(name, fn) { if (fn) { draws[name] = fn; if (api._ready) api._run(name); } else api._run(name); },
    onData(fn) { fn(); }, params: () => ({}), setParams() {}, resetParams() {}, setLink() {}, refresh() {},
    _run(name) { document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => { try { draws[name](el); } catch (e) { console.error(name, e); } }); },
    _runAll() { api._ready = true; for (const n of Object.keys(draws)) api._run(n); },
  };
  let t = 0, w = window.innerWidth;
  addEventListener('resize', () => { if (window.innerWidth === w) return; w = window.innerWidth; clearTimeout(t); t = setTimeout(api._runAll, 120); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => api._runAll());
  addEventListener('beforeprint', () => document.querySelectorAll('details').forEach((d) => { d.open = true; }));
  return api;
})();`;
const runner = `
(() => {
  const tpl = document.createElement('template'); tpl.innerHTML = window.__PAGE;
  const scripts = [...tpl.content.querySelectorAll('script')].map((s) => { const t = s.textContent; s.remove(); return t; });
  tpl.content.querySelectorAll('meta').forEach((m) => m.remove());
  document.getElementById('dash-root').appendChild(tpl.content);
  for (const s of scripts) { try { new Function(s)(); } catch (e) { console.error(e); } }
  dash._runAll();
})();`;
const sourcesHtml = sources.map((s) => `<dt>${esc(s.title)}</dt><dd>${esc(s.description)}</dd>`).join('\n');
const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Pystachy speed vs surface</title>
<style>${css}</style>
<script>${d3src}</script>
<script>window.__DATA = ${inlineJSON(data)}; window.__PAGE = ${inlineJSON(page)};</script>
<script>${shim}</script>
</head><body>
<div class="pz-page">
<header class="pz-masthead">
<h1>Pystachy speed vs surface</h1>
<p>Performance against the amount of unmodified Python that Pystachy runs, across 34 commits of main from the project's first day (8 October 2026) to 11 November 2026; dates are UTC. Measured 12 November 2026; scripts, raw data and this report are in research/speed-vs-surface-2026-11-12 on the branch claude/peaceful-faraday-2yr9q6.</p>
</header>
<div id="dash-root"></div>
<section class="pz-sources" id="data-sources"><h2>Data sources</h2><dl>
${sourcesHtml}
</dl></section>
</div>
<script>${runner}</script>
</body></html>`;
fs.writeFileSync(path.join(out, 'report.html'), html);

// Figure mode for single-chart images: headings, legends and charts only.
const figureCss = `.pz-section > p, .pz-note, .pz-controls, .pz-masthead, .pz-sources, .pz-tip { display: none !important; }
  .pz-page { padding-top: 8px; }`;
const figures = [
  { file: '01-speed-vs-surface-all-methods.png', parts: ['#trajectory-section > h2', '#trajectory-legend', '#trajectory'], set: ['#trajectory-x', 'methods_pass'] },
  { file: '02-speed-vs-surface-language-tests.png', parts: ['#trajectory-section > h2', '#trajectory-legend', '#trajectory'], set: ['#trajectory-x', 'pass_language'] },
  { file: '03-speed-vs-surface-upstream-files.png', parts: ['#trajectory-section > h2', '#trajectory-legend', '#trajectory'], set: ['#trajectory-x', 'upstream_compiled'] },
  { file: '04-methods-passing-over-time.png', parts: ['#surface-methods-box'] },
  { file: '05-benchmarks-working-over-time.png', parts: ['#surface-bench-box'] },
  { file: '06-performance-index-over-time.png', parts: ['#surface-speed-box'] },
  { file: '07-first-errors-language-tests.png', parts: ['#blockers-section > h2', '#blockers-legend', '#blockers'], set: ['#blockers-scope', 'language'] },
  { file: '08-first-errors-all-tests.png', parts: ['#blockers-section > h2', '#blockers-legend', '#blockers'], set: ['#blockers-scope', 'all'] },
  { file: '09-newly-passing-by-previous-blocker.png', parts: ['#unlocks-head', '#unlocks-legend', '#unlocks'] },
  { file: '10-speed-by-benchmark-heatmap.png', parts: ['#heatmap-section > h2', '#heatmap-legend', '#heatmap'] },
  { file: '11-source-lines.png', parts: ['#cost-lines-box'] },
  { file: '12-compile-time.png', parts: ['#cost-jit-box'] },
];

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  // PDF: A4 portrait, light, charts drawn at the printed width, closed sections opened.
  {
    const scale = 0.72, contentPx = (210 - 2 * 10) / 25.4 * 96;
    const p = await browser.newPage({ viewport: { width: Math.round(contentPx / scale), height: 1200 }, colorScheme: 'light' });
    p.on('pageerror', (e) => errors.push('pdf: ' + e));
    p.on('console', (m) => { if (m.type() === 'error') errors.push('pdf: ' + m.text()); });
    await p.goto('file://' + path.join(out, 'report.html'));
    await p.evaluate(() => document.querySelectorAll('details').forEach((d) => { d.open = true; }));
    await p.waitForTimeout(300);
    await p.pdf({ path: path.join(out, 'report.pdf'), format: 'A4', scale, printBackground: true,
      margin: { top: '12mm', bottom: '14mm', left: '10mm', right: '10mm' }, displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="font-size:8px;width:100%;padding:0 10mm;color:#888;display:flex;justify-content:space-between;font-family:system-ui,sans-serif"><span>Pystachy speed vs surface</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>' });
    await p.close();
  }
  // Full page and single-chart images: light, 2x.
  {
    const p = await browser.newPage({ viewport: { width: 1112, height: 1000 }, deviceScaleFactor: 2, colorScheme: 'light' });
    p.on('pageerror', (e) => errors.push('png: ' + e));
    p.on('console', (m) => { if (m.type() === 'error') errors.push('png: ' + m.text()); });
    await p.goto('file://' + path.join(out, 'report.html'));
    await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(out, 'images', '00-full-report.png'), fullPage: true });
    await p.addStyleTag({ content: figureCss });
    await p.evaluate(() => dash._runAll());
    for (const f of figures) {
      if (f.set) { await p.evaluate(([sel, v]) => { const el = document.querySelector(sel); el.value = v; el.dispatchEvent(new Event('change')); }, f.set); }
      await p.waitForTimeout(150);
      const box = await p.evaluate((sels) => {
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const s of sels) {
          const el = document.querySelector(s);
          if (!el) throw new Error('missing ' + s);
          const r = el.getBoundingClientRect();
          x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top + scrollY); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom + scrollY);
        }
        return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
      }, f.parts);
      const pad = 14;
      await p.screenshot({ path: path.join(out, 'images', f.file), fullPage: true,
        clip: { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: box.width + 2 * pad, height: box.height + 2 * pad } });
    }
    await p.close();
  }
  await browser.close();
  console.log('wrote', out, errors.length ? 'ERRORS:\n' + errors.join('\n') : 'no errors');
})();
