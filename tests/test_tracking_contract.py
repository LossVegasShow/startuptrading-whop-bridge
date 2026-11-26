"""The contract between tracking.js, the dataLayer payload, the GTM container's
variables and the GA4 user properties, run in a real browser in the order
GoHighLevel uses: the page embed runs in the body first, the site-wide header code
is injected after the page loads.

Regression for 2026-11-26: a stale /free-tools embed (pre-channel tracking.js) ran
first, claimed sut_attribution, and GTM saw first_channel / last_channel undefined.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_sales_site import SITE, load_build

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = json.loads((ROOT / 'growth' / 'gtm' / 'startuptrading-gtm-container.json').read_text())['containerVersion']
VARS = {v['name']: v for v in CONTAINER['variable']}
QA = '?utm_source=qa&utm_medium=test&utm_campaign=gtm_check'
STALE = (ROOT / 'tests' / 'fixtures' / 'stale_free_tools_embed_script.js').read_text()


def dlv_names():
    return {v['parameter'][2]['value'] for v in CONTAINER['variable'] if v['type'] == 'v'}


def test_every_gtm_data_layer_variable_is_emitted_by_tracking_js():
    src = (SITE / 'src' / 'tracking.js').read_text()
    for name in dlv_names():
        assert re.search(r'\b' + name + r'\s*:', src), f'GTM reads {name!r} but tracking.js never pushes it'
    # The two user-property keys are top-level fields of every event, including sut_attribution.
    assert 'first_channel: (attr.first || {}).channel' in src and 'last_channel: (sutLatest(attr) || {}).channel' in src
    up = VARS['GA4 user properties']['parameter'][0]['value']
    assert '{{DLV - first_channel}}' in up and '{{DLV - last_channel}}' in up
    google = next(t for t in CONTAINER['tag'] if t['type'] == 'googtag')
    assert any(m['map'][1]['value'] == '{{GA4 user properties}}'
               for p in google['parameter'] if p.get('key') == 'configSettingsTable' for m in p['list'])


DRIVER = r"""
const {chromium} = require('playwright');
const fs = require('fs');
const [htmlPath, outPath] = process.argv.slice(2);
const cases = JSON.parse(fs.readFileSync(htmlPath, 'utf8'));
(async () => {
  const b = await chromium.launch(); const out = {};
  for (const c of cases) {
    const ctx = await b.newContext(); const p = await ctx.newPage();
    await p.route('**/*', r => {
      const u = r.request().url();
      if (u.startsWith('https://startuptrading.com/')) return r.fulfill({contentType: 'text/html', body: c.html});
      return r.fulfill({contentType: 'text/javascript', body: ''});
    });
    if (c.seed) { await p.goto('https://startuptrading.com/seed'); await p.evaluate(s => localStorage.setItem('sut_attr', s), c.seed); }
    await p.goto('https://startuptrading.com' + c.path);
    await p.waitForFunction(() => window.__headerDone === true, null, {timeout: 10000});
    out[c.name] = await p.evaluate(() => dataLayer.filter(e => e && e.event === 'sut_attribution'));
    await ctx.close();
  }
  await b.close(); fs.writeFileSync(outPath, JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def ghl_page(embed_script_html, header_html):
    """Body embed first; header code injected after load, as GoHighLevel does."""
    header_js = json.dumps(re.findall(r'<script>(.*?)</script>', header_html, re.S))
    return ('<!doctype html><html><head><meta charset="utf-8"></head><body>' + embed_script_html +
            '<script>window.addEventListener("load", function () { var parts = ' + header_js + ';'
            ' parts.forEach(function (js) { var s = document.createElement("script"); s.textContent = js;'
            ' document.head.appendChild(s); }); window.__headerDone = true; });</script></body></html>')


EXISTING = json.dumps({'first': {'at': 1795598154937, 'utm_source': 'chatgpt.com', 'channel': 'ai_referral'},
                       'last': {'at': 1795653722235, 'utm_source': 'qa', 'utm_medium': 'test', 'utm_campaign': 'gtm_check'}})


@pytest.fixture(scope='module')
def results(tmp_path_factory):
    node = shutil.which('node')
    tmp = tmp_path_factory.mktemp('contract')
    if not node or subprocess.run([node, '-e', "require('playwright')"], capture_output=True, cwd=tmp).returncode:
        pytest.skip('node + playwright needed')
    b = load_build()
    cfg = json.loads((SITE / 'site.config.json').read_text())
    header = b.site_tracking_snippet(cfg)
    current_embed = b.render(cfg, 'free_tools')[0]
    stale_embed = '<div class="sut" data-page="free_tools" data-tool-id="free-tools-directory"></div><script>' + STALE + '</script>'
    cases = [
        {'name': 'fresh_current', 'path': '/free-tools' + QA, 'html': ghl_page(current_embed, header)},
        {'name': 'existing_current', 'path': '/free-tools' + QA, 'html': ghl_page(current_embed, header), 'seed': EXISTING},
        {'name': 'fresh_stale', 'path': '/free-tools' + QA, 'html': ghl_page(stale_embed, header)},
        {'name': 'existing_stale', 'path': '/free-tools' + QA, 'html': ghl_page(stale_embed, header), 'seed': EXISTING},
    ]
    (tmp / 'cases.json').write_text(json.dumps(cases))
    (tmp / 'driver.js').write_text(DRIVER)
    subprocess.run([node, str(tmp / 'driver.js'), str(tmp / 'cases.json'), str(tmp / 'out.json')], check=True, cwd=tmp, timeout=120)
    return json.loads((tmp / 'out.json').read_text())


def user_properties(event):
    """Evaluate the container's own GA4 user-properties variable against a dataLayer event."""
    js = VARS['GA4 user properties']['parameter'][0]['value']
    for name in ('first_channel', 'last_channel'):
        js = js.replace('{{DLV - ' + name + '}}', json.dumps(event.get(name)) if name in event else 'undefined')
    out = subprocess.run([shutil.which('node'), '-e', f'console.log(JSON.stringify(({js})()))'], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.parametrize('case,first,last', [
    ('fresh_current', 'other_referral', 'other_referral'),
    ('existing_current', 'ai_referral', 'other_referral'),
])
def test_current_scripts_satisfy_the_contract(results, case, first, last):
    events = results[case]
    assert len(events) == 1, 'sut_attribution must be pushed exactly once per page'
    e = events[0]
    assert (e['first_channel'], e['last_channel']) == (first, last)
    assert e['first_touch']['channel'] == first and e['last_touch']['channel'] == last
    assert user_properties(e) == {'first_channel': first, 'last_channel': last}


@pytest.mark.parametrize('case', ['fresh_stale', 'existing_stale'])
def test_a_stale_embed_reproduces_the_reported_failure(results, case):
    """Documents the root cause: the old embed runs first and its payload has no channels."""
    events = results[case]
    assert len(events) == 1 and 'first_channel' not in events[0] and 'channel' not in events[0]['last_touch']
    assert user_properties(events[0]) == {'first_channel': 'unknown', 'last_channel': 'unknown'}


def test_live_checker_flags_a_stale_embed():
    sys.path.insert(0, str(ROOT / 'growth' / 'gtm'))
    import check_live
    b = load_build()
    cfg = json.loads((SITE / 'site.config.json').read_text())
    repo = (SITE / 'src' / 'tracking.js').read_text()
    # GoHighLevel's page data escapes '<' (as \u003C), so </script> never appears inside it.
    nuxt = json.dumps([b.site_tracking_snippet(cfg)]).replace('<', '\\u003C')
    good = b.render(cfg, 'free_tools')[0] + f'<script type="application/json" id="__NUXT_DATA__">{nuxt}</script>'
    bad = f'<script>{STALE}</script><script type="application/json" id="__NUXT_DATA__">{nuxt}</script>'
    assert {s for _, s, _ in check_live.analyze(good, repo)} == {'current'}
    assert [(w, s) for w, s, _ in check_live.analyze(bad, repo)] == [('page body (embed)', 'stale'),
                                                                     ('injected (header code)', 'current')]
