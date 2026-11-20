// Saves the last animated frame of every scene as a PNG, for a quick visual check.
//   node video/engine/preview.js <timeline.json> <out_dir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const tl = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), out = process.argv[3];
  fs.mkdirSync(out, { recursive: true });
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  const browser = await chromium.launch(proxy ? { proxy: { server: proxy } } : {});
  const page = await (await browser.newContext({ viewport: { width: tl.w, height: tl.h }, ignoreHTTPSErrors: true })).newPage();
  await page.goto('file://' + path.join(__dirname, 'scene.html'));
  await page.evaluate(() => window.ready);
  for (let i = 0; i < tl.scenes.length; i++) {
    await page.evaluate(sc => { window.SCENE = sc; }, { ...tl.scenes[i], w: tl.w, h: tl.h });
    await page.evaluate(t => window.draw(t), (tl.scenes[i].anim || 3) + 3);
    await page.screenshot({ path: path.join(out, 'scene-' + String(i).padStart(2, '0') + '.png') });
  }
  await browser.close();
})();
