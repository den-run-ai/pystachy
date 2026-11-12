const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  for (const [w, scheme] of [[1280, 'light'], [400, 'dark']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme, offline: true });
    const p = await ctx.newPage();
    const reqs = [], errs = [];
    p.on('request', (r) => { if (!r.url().startsWith('file:') && !r.url().startsWith('data:')) reqs.push(r.url()); });
    p.on('pageerror', (e) => errs.push(String(e)));
    p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto('file://' + process.argv[2]);
    await p.waitForTimeout(400);
    const svgs = await p.$$eval('svg', (s) => s.length);
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    const lede = await p.$eval('#takeaway', (e) => e.textContent.replace(/\s+/g, ' ').trim().slice(0, 120));
    console.log(`${w}px ${scheme}: svgs=${svgs} overflow=${overflow} network=${reqs.length} errors=${errs.length} | ${lede}`);
    if (w === 400) await p.screenshot({ path: process.argv[3], fullPage: false });
    await ctx.close();
  }
  await b.close();
})();
