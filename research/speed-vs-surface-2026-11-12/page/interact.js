const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1100, height: 900 } });
  const errors = [];
  p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  p.on('pageerror', (e) => errors.push(String(e)));
  await p.goto('file://' + __dirname + '/harness.html');
  for (const v of ['pass_language', 'upstream_compiled']) {
    await p.selectOption('#trajectory-x', v);
    await p.waitForTimeout(150);
    const label = await p.$eval('#trajectory svg', (s) => [...s.querySelectorAll('text')].map((t) => t.textContent).find((t) => t.endsWith('→')));
    console.log(v, '->', label);
  }
  await p.selectOption('#blockers-scope', 'all');
  await p.waitForTimeout(150);
  const ends = await p.$$eval('#blockers svg text.pz-strong', (ts) => ts.map((t) => t.textContent));
  console.log('blockers(all) end labels:', ends.join(' | '));
  const marks = await p.$$eval('[data-source][data-field]', (els) => els.length);
  const overlay = await p.$eval('#overlay-table tbody', (t) => t.rows.length);
  console.log('marked values:', marks, 'overlay rows:', overlay, 'errors:', errors);
  await p.locator('#trajectory-section').screenshot({ path: __dirname + '/traj-upstream.png' });
  await b.close();
})();
