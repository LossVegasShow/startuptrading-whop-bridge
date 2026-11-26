"""The sales page's visual layer (design_fx): decorative only, switchable, and it
never replaces real content with invented claims."""
import json
import re
import shutil
import subprocess

import pytest

from test_sales_site import SITE, load_build

CFG = json.loads((SITE / 'site.config.json').read_text())


def render(name='sales', **kw):
    return load_build().render(dict(CFG, **kw), name)[0]


def test_fx_only_on_the_sales_page_and_switchable():
    on = render()
    assert 'class="sut sut-fx"' in on and '<canvas class="sut-hero-fx"' in on and 'Market.prototype' in on
    off = render(design_fx='')
    assert 'class="sut"' in off and '<canvas class="sut-hero-fx"' not in off and 'Market.prototype' not in off
    # Checkout, tracking and the approved hero copy are identical either way.
    for marker in ('data-whop-checkout-plan-id', 'data-member-cta="hero"', "Jack's tools.<br>Your charts.", 'sutAttribution'):
        assert marker in on and marker in off
    for page in ('free_tools', 'calculator', 'tv_atr', 'welcome', 'setup'):
        assert 'Market.prototype' not in render(page), page


def test_no_placeholders_and_no_invented_testimonials():
    html = render()
    assert 'class="sut-ph' not in html and 'goes here' not in html
    assert 'What members say' not in html          # no quotes until real, permissioned ones exist
    # Illustrations are labelled as such.
    assert html.count('>Illustration<') == 2 and 'Channel preview' in html


def test_contract_specs_are_correct():
    specs = {s: (t, v, p) for s, _, t, v, p in load_build().CONTRACTS}
    assert specs['ES'] == ('0.25', '12.50', '50') and specs['MES'] == ('0.25', '1.25', '5')
    assert specs['NQ'] == ('0.25', '5.00', '20') and specs['MNQ'] == ('0.25', '0.50', '2')
    assert specs['CL'] == ('0.01', '10.00', '1,000') and specs['GC'] == ('0.10', '10.00', '100')
    for s, (t, v, p) in specs.items():               # tick value = tick size × $ per point
        assert abs(float(t) * float(p.replace(',', '')) - float(v)) < 1e-9, s


def test_real_captures_replace_the_illustrations():
    html = render(scanner_media_url='https://cdn.example/scan.mp4', atr_media_url='https://cdn.example/atr.webp')
    assert '<video class="sut-media" src="https://cdn.example/scan.mp4" muted loop playsinline preload="none" data-autoplay' in html
    assert '<img class="sut-media" src="https://cdn.example/atr.webp"' in html
    markup = re.sub(r'<script.*?</script>', '', html, flags=re.S)
    assert 'class="sut-scan-row"' not in markup and 'data-fx-chart="bracket"' not in markup


DRIVER = r"""
const {chromium} = require('playwright'); const fs = require('fs');
const [htmlFile, outFile] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); const out = {};
  for (const motion of ['no-preference', 'reduce']) {
    const p = await b.newPage({reducedMotion: motion}); const errors = [];
    p.on('pageerror', e => errors.push(e.message));
    await p.route(/^https?:/, r => r.abort());
    await p.goto('file://' + htmlFile); await p.waitForTimeout(1500);
    const read = () => p.evaluate(() => ['n','stop','per','used'].map(k => document.querySelector('[data-o="'+k+'"]').textContent));
    const set = (v) => p.evaluate(v => { const i = document.querySelector('[data-k="atr"]'); i.value = v; i.dispatchEvent(new Event('input', {bubbles: true})); }, v);
    const r = {start: await read()};
    await set('24'); r.atr24 = await read();
    await set('40'); await p.selectOption('[data-k="pv"]', '50'); r.zero = await read();
    r.note = await p.evaluate(() => document.querySelector('[data-o="note"]').textContent);
    r.drawn = await p.evaluate(() => { const c = document.querySelector('.sut-hero-fx'); return c.width > 0 && c.height > 0; });
    r.revealed = await p.evaluate(() => document.querySelector('#pricing [data-reveal]') !== null);
    r.errors = errors; out[motion] = r; await p.close();
  }
  await b.close(); fs.writeFileSync(outFile, JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def test_atr_demo_math_and_canvas_in_browser(tmp_path):
    node = shutil.which('node')
    if not node or subprocess.run([node, '-e', "require('playwright')"], capture_output=True, cwd=tmp_path).returncode:
        pytest.skip('node + playwright needed')
    page = tmp_path / 'index.html'
    page.write_text(load_build().render(CFG, 'sales')[1])
    (tmp_path / 'd.js').write_text(DRIVER)
    subprocess.run([node, str(tmp_path / 'd.js'), str(page), str(tmp_path / 'o.json')], check=True, cwd=tmp_path, timeout=90)
    out = json.loads((tmp_path / 'o.json').read_text())
    for motion, r in out.items():
        assert r['errors'] == [], motion
        # $180 on MES with a 1.5 × ATR stop: 3 contracts at ATR 8, 1 at ATR 24 (the site's own example).
        assert r['start'] == ['3', '12.00 pts', '$60', '$180'], motion
        assert r['atr24'] == ['1', '36.00 pts', '$180', '$180'], motion
        assert r['zero'][0] == '0' and 'Skip the trade' in r['note'], motion
        assert r['drawn'], motion
