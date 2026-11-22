const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const files = process.argv.slice(3);
  const imgs = files.map((f) => 'data:image/png;base64,' + fs.readFileSync(f).toString('base64'));
  const html = '<body style="margin:0;background:#888;display:flex;flex-wrap:wrap;gap:6px;padding:6px">' + imgs.map((s) => `<img src="${s}" style="width:300px;background:#fff">`).join('') + '</body>';
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1250, height: 800 } });
  await p.setContent(html); await p.waitForTimeout(200);
  await p.screenshot({ path: process.argv[2], fullPage: true }); await b.close();
})();
