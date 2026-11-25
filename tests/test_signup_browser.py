"""The optional GoHighLevel sign-up form in a real browser, offline.

The page is built as GoHighLevel serves it: the site-wide header code
(dist/site-tracking.html) plus a page embed, so tracking.js runs twice. GoHighLevel
is replaced by a fake form that posts the same window messages the real one does
(checked against link.msgsndr.com/js/form_embed.js and the form's own code):
  "iframeLoaded" when loaded, then on a successful submission
  ["set-sticky-contacts", "_ud", ...] and
  ["set-sticky-contacts", "embedded_iframe_<iframe id>", "<iframe id>", ...].
Nothing is sent to GoHighLevel."""
import json
import shutil
import subprocess

import pytest

from test_sales_site import SITE, load_build

FORM = 'https://api.leadconnectorhq.com/widget/form/TEST123'

DRIVER = r"""
const {chromium} = require('playwright');
const [html, outPath] = [process.argv[2], process.argv[3]];
const fs = require('fs');
const FAKE_FORM = `<!doctype html><body style="margin:0;background:#141922;height:500px">
<script>
  window.addEventListener('message', function (e) {
    if (e.data === 'submit') {
      var iframeId = 'inline-TEST123';
      parent.postMessage(['set-sticky-contacts', '_ud', '{}', 'loc', 'fp'], '*');
      parent.postMessage(['set-sticky-contacts', 'embedded_iframe_' + iframeId, iframeId, 'loc', 'fp'], '*');
      parent.postMessage(['set-sticky-contacts', 'embedded_iframe_' + iframeId, iframeId, 'loc', 'fp'], '*');
    }
  });
  window.addEventListener('message', function (e) {
    if (typeof e.data === 'number') parent.postMessage('[iFrameSizer]inline-TEST123:' + e.data + ':354:mutationObserver', '*');
  });
  parent.postMessage(['iframeLoaded'], '*');
  parent.postMessage('[iFrameSizer]inline-TEST123:500:354:init', '*');
</script></body>`;
(async () => {
  const b = await chromium.launch();
  const out = {};
  for (const width of [390, 1280]) {
    const p = await b.newPage({viewport: {width, height: 800}});
    const embedLoads = [];
    await p.route('**/*', r => {
      const u = r.request().url();
      if (u.startsWith('https://page.test/')) return r.fulfill({contentType: 'text/html', body: html});
      if (u.includes('/widget/form/')) return r.fulfill({contentType: 'text/html', body: FAKE_FORM});
      if (u.includes('/js/form_embed.js')) { embedLoads.push(u); return r.fulfill({contentType: 'text/javascript', body: ''}); }
      return r.abort();
    });
    await p.goto('https://page.test/tools?utm_source=youtube&utm_medium=social&utm_campaign=risk_lab&a=jackaff');
    await p.waitForTimeout(300);
    const before = await p.evaluate(() => document.querySelector('iframe[data-ghl-form]').getAttribute('src'));
    await p.evaluate(() => document.querySelector('#subscribe').scrollIntoView());
    await p.waitForFunction(() => !!document.querySelector('iframe[data-ghl-form]').getAttribute('src'));
    await p.waitForTimeout(500);
    const src = await p.evaluate(() => document.querySelector('iframe[data-ghl-form]').getAttribute('src'));
    const frame = p.frames().find(f => f.url().includes('/widget/form/'));
    // A fake success message from the page itself must not count.
    await p.evaluate(() => window.postMessage(['set-sticky-contacts', 'embedded_iframe_inline-TEST123', 'inline-TEST123'], '*'));
    await frame.evaluate(() => window.postMessage('submit', '*'));
    await frame.evaluate(() => window.postMessage('submit', '*'));
    await p.waitForTimeout(400);
    // Sizing: the form's own reports (load, validation messages, then the short thank-you).
    const heightAt = async n => { await frame.evaluate(v => window.postMessage(v, '*'), n); await p.waitForTimeout(150);
      return p.evaluate(() => document.querySelector('iframe[data-ghl-form]').getBoundingClientRect().height); };
    const sizes = {load: await p.evaluate(() => document.querySelector('iframe[data-ghl-form]').getBoundingClientRect().height),
                   validation: await heightAt(720), thanks: await heightAt(180)};
    const events = await p.evaluate(() => dataLayer.map(e => e.event));
    const subscribe = await p.evaluate(() => dataLayer.filter(e => e.event === 'email_subscribe'));
    const box = await p.evaluate(() => {
      const r = document.querySelector('iframe[data-ghl-form]').getBoundingClientRect();
      return {width: r.width, height: r.height, docWidth: document.documentElement.scrollWidth, vw: innerWidth};
    });
    out[width] = {before, src, events, subscribe, embedLoads: embedLoads.length, box, sizes};
    await p.close();
  }
  await b.close();
  fs.writeFileSync(outPath, JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def _run(tmp_path, name):
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    probe = subprocess.run([node, '-e', "require('playwright')"], capture_output=True, cwd=tmp_path)
    if probe.returncode:
        pytest.skip('playwright not installed')
    b = load_build()
    cfg = json.loads((SITE / 'site.config.json').read_text())
    cfg['ghl_subscribe_form_url'] = FORM
    embed = b.render(cfg, name)[0]
    html = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + b.site_tracking_snippet() + '</head><body>' + embed + '</body></html>')
    (tmp_path / 'driver.js').write_text(DRIVER)
    out = tmp_path / 'out.json'
    subprocess.run([node, str(tmp_path / 'driver.js'), html, str(out)], check=True, cwd=tmp_path, timeout=120)
    return json.loads(out.read_text())


@pytest.mark.parametrize('name,interest', [('tv_atr', 'tradingview'), ('calculator', 'calculators'),
                                           ('free_tools', 'free-tools')])
def test_signup_form_in_browser(tmp_path, name, interest):
    for width, r in _run(tmp_path, name).items():
        # Not loaded until the reader scrolls near it; GoHighLevel's script loaded once.
        assert r['before'] is None, width
        assert r['embedLoads'] == 1, width
        # Attribution reaches the form's URL (= its hidden fields' query keys).
        assert f'source_page={name}' in r['src'] and f'interest={interest}' in r['src']
        for part in ('affiliate=jackaff', 'first_utm_source=youtube', 'last_utm_source=youtube',
                     'first_utm_medium=social', 'first_utm_campaign=risk_lab'):
            assert part in r['src'], (width, part)
        # Both copies of tracking.js ran, yet each page event fired once.
        assert r['events'].count('sut_attribution') == 1, r['events']
        assert r['events'].count('free_tool_view') == 1, r['events']
        # Two successful submissions' worth of messages and a fake from the page: one sign-up.
        assert len(r['subscribe']) == 1, r['subscribe']
        s = r['subscribe'][0]
        assert s['source_page'] == name and s['interest'] == interest and s['form_id'] == 'TEST123'
        assert s['first_touch']['utm_source'] == 'youtube' and s['affiliate'] == 'jackaff'
        # Fits the screen: no sideways scrolling on a phone.
        assert r['box']['docWidth'] <= r['box']['vw'], (width, r['box'])
        # The iframe follows the form's reported height plus the margin GHL leaves out,
        # growing for validation messages and shrinking for the thank-you message.
        pad = 24
        assert r['sizes'] == {'load': 500 + pad, 'validation': 720 + pad, 'thanks': 180 + pad}, r['sizes']
