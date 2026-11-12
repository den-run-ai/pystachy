const { chromium } = require('playwright');
(async () => {
  const [sel, out, w, theme] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +(w || 1100), height: 900 } });
  await p.goto('file://' + __dirname + '/harness.html');
  if (theme === 'dark') await p.evaluate(() => { document.documentElement.classList.add('dark'); dash._runAll(); });
  await p.waitForTimeout(200);
  await p.locator(sel).screenshot({ path: out });
  await b.close();
})();
