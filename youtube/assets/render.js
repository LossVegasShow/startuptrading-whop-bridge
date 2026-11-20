// Renders every asset in renders.json to PNG in youtube/assets/out/.
//   NODE_PATH=$(npm root -g) node youtube/assets/render.js
// Each entry: { "out": "file.png", "page": "thumbnail.html", "params": {...}, "w": 1280, "h": 720, "transparent": false }
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const dir = __dirname;
  const jobs = JSON.parse(fs.readFileSync(path.join(dir, 'renders.json'), 'utf8'));
  fs.mkdirSync(path.join(dir, 'out'), { recursive: true });
  const browser = await chromium.launch();
  for (const job of jobs) {
    const page = await browser.newPage({ viewport: { width: job.w, height: job.h }, deviceScaleFactor: 1 });
    // Brand fonts come from Google Fonts in OBS; offline renders fall back to Inter.
    await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
    const url = new URL('file://' + path.join(dir, job.page));
    for (const [k, v] of Object.entries(job.params || {})) url.searchParams.set(k, String(v));
    await page.goto(url.toString());
    await page.waitForTimeout(150);
    await page.screenshot({ path: path.join(dir, 'out', job.out), omitBackground: !!job.transparent });
    await page.close();
    console.log('rendered', job.out);
  }
  await browser.close();
})();
