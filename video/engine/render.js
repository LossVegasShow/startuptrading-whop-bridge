// Captures the animated frames of every scene in a timeline.
//   node video/engine/render.js <timeline.json>
// timeline: { w, h, fps, frames_dir, scenes: [{ ...scene params, anim: seconds }] }
// Writes <frames_dir>/s000/f00000.jpg ... (only the animated part; build.py holds the last frame).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const tl = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  const browser = await chromium.launch(proxy ? { proxy: { server: proxy } } : {});
  const ctx = await browser.newContext({ viewport: { width: tl.w, height: tl.h }, deviceScaleFactor: 1, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto('file://' + path.join(__dirname, 'scene.html'));
  await page.evaluate(() => window.ready);
  const fontsOk = await page.evaluate(() => document.fonts.check('700 40px Geist'));
  console.log('brand font loaded:', fontsOk);
  for (let i = 0; i < tl.scenes.length; i++) {
    const s = tl.scenes[i], dir = path.join(tl.frames_dir, 's' + String(i).padStart(3, '0'));
    fs.mkdirSync(dir, { recursive: true });
    await page.evaluate(sc => { window.SCENE = sc; }, { ...s, w: tl.w, h: tl.h });
    const n = Math.max(1, Math.round(s.anim * tl.fps));
    for (let f = 0; f < n; f++) {
      await page.evaluate(t => window.draw(t), f / tl.fps);
      await page.screenshot({ path: path.join(dir, 'f' + String(f).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 92 });
    }
    process.stdout.write(`scene ${i + 1}/${tl.scenes.length} (${n} frames)\n`);
  }
  await browser.close();
})();
