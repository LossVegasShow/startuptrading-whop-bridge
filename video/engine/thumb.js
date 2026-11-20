// Renders a thumbnail: node video/engine/thumb.js '<json params>' <out.png>
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const params = JSON.parse(process.argv[2]), out = process.argv[3];
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const u = new URL('file://' + path.join(__dirname, 'thumbnail.html'));
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
  await p.goto(u.toString()); await p.evaluate(() => window.ready);
  await p.screenshot({ path: out }); await b.close();
})();
