// Render the print edition to an A4 PDF and fail if any topic page overflows its page.
// usage: node render_print.js REPORT.html OUT.pdf [PNG_DIR]
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const [html, out, pngDir] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 760, height: 1100 }, colorScheme: 'light' });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + path.resolve(html));
  await page.emulateMedia({ media: 'print' });
  await page.waitForFunction(() => document.body.dataset.charts === 'done', null, { timeout: 30000 });
  await page.evaluate(() => document.fonts.ready);
  const limit = ((297 - 15 - 17) / 25.4) * 96;  // printable height in CSS px
  const heights = await page.evaluate(() => [...document.querySelectorAll('section.page')]
    .map((s) => ({ id: s.id, h: Math.ceil(s.getBoundingClientRect().height) })));
  const fonts = await page.evaluate(() => [...new Set([...document.querySelectorAll('p, td, text, h1')]
    .map((e) => getComputedStyle(e).fontFamily))].slice(0, 4));
  for (const r of heights) console.log(`${r.id.padEnd(16)} ${String(r.h).padStart(5)} px of ${Math.floor(limit)}${r.h > limit - 4 ? '  OVERFLOW' : ''}`);
  console.log('fonts', fonts.join(' | '));
  if (errors.length) { console.log('page errors:', errors); process.exitCode = 1; }
  await page.pdf({
    path: out, preferCSSPageSize: true, printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: '<div style="width:100%;margin:0 18mm;display:flex;justify-content:space-between;'
      + 'font-family:Liberation Sans,Arial,sans-serif;font-size:7.5pt;color:#5f5e59"><span>Pystachy: speed and Python surface · '
      + '12 November 2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
  });
  if (pngDir) {
    // Page previews for checking layout (not deliverables).
    const { execSync } = require('child_process');
    execSync(`pdftoppm -r 60 -png ${JSON.stringify(out)} ${JSON.stringify(path.join(pngDir, 'page'))}`);
  }
  await browser.close();
  if (heights.some((r) => r.h > limit - 4)) process.exitCode = 2;
})();
