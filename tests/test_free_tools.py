"""Free tools library: /free-tools, the TradingView companion page, nav gating,
optional sign-up, structured data and analytics. Everything is built from
sales-site/tools.json and site.config.json."""
import json
import re
import shutil
import subprocess

import pytest

from test_sales_site import SITE, load_build

CFG = json.loads((SITE / 'site.config.json').read_text())
TOOLS = json.loads((SITE / 'tools.json').read_text())


def page(name, **overrides):
    cfg = dict(CFG)
    cfg.update(overrides)
    return load_build().render(cfg, name)[0]


def markup(embed):
    """The page's HTML without scripts (script comments mention button names)."""
    return re.sub(r'<script.*?</script>', '', embed, flags=re.S)


def ld(embed):
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', embed, re.S).group(1))


def text_of(embed):
    return re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', embed.split('<footer')[0], flags=re.S)


# --- Registry -----------------------------------------------------------------------

def test_registry_is_valid():
    cats = TOOLS['categories']
    assert list(cats)[0] == 'all' and {'tradingview', 'ninjatrader', 'calculators', 'education'} <= set(cats)
    ids = [t['id'] for t in TOOLS['tools']]
    assert len(ids) == len(set(ids)) == 3
    for t in TOOLS['tools']:
        assert t['status'] in ('available', 'coming_soon')
        assert set(t['categories']) <= set(cats) - {'all'}
        url = CFG[t['page']]                          # every page is a config URL...
        assert url.startswith('https://startuptrading.com/')   # ...on startuptrading.com
        if t.get('external_url'):
            assert t['external_url'] in CFG


def test_directory_renders_every_tool_and_filter():
    embed = page('free_tools')
    for t in TOOLS['tools']:
        assert f'data-tool-id="{t["id"]}"' in embed and t['name'].replace('&', '&amp;') in embed
        assert f'href="{CFG[t["page"]]}"' in embed
    for key in TOOLS['categories']:
        assert f'data-filter="{key}"' in embed
    # Education has no tools yet: an empty-state note, not a dead link.
    assert 'data-empty-for="education"' in embed
    assert '<div class="sut-filters" role="group" aria-label="Filter tools" hidden>' in embed   # shown by JS


def test_tradingview_link_only_once_published():
    embed = page('free_tools', tv_atr_script_url='')
    assert 'tradingview.com' not in embed and 'Coming soon to TradingView' in embed
    url = 'https://www.tradingview.com/script/abc123-ATR-Position-Size-Stop-Planner/'
    embed = page('free_tools', tv_atr_script_url=url)
    assert f'href="{url}"' in embed and 'data-outbound="tradingview"' in embed


def test_companion_page():
    embed = page('tv_atr', tv_atr_script_url='')
    assert 'tradingview.com' not in embed and 'sut-btn-disabled' in embed
    assert f'href="{CFG["calculator_url"]}"' in embed and f'href="{CFG["free_indicator_url"]}"' in embed
    for heading in ('The method', 'Worked examples', 'Install', 'Know the limits', 'Related free resources'):
        assert heading in embed
    # The worked example matches the script's arithmetic: 1.5 x 4.00 = 6 pts, x $50 = $300, $500 -> 1 contract.
    assert '6.00-point stop (24 ticks)' in embed and '<b>1 contract</b>' in embed and '<b>8 contracts</b>' in embed
    url = 'https://www.tradingview.com/script/abc123/'
    embed = page('tv_atr', tv_atr_script_url=url)
    assert f'href="{url}"' in embed and 'Open on TradingView' in embed


# --- Navigation and gating -----------------------------------------------------------

def nav(embed):
    return re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)', embed.split('</header>')[0])


def test_sales_nav_has_every_item_and_anchors_exist():
    embed = page('sales')
    labels = [label for _, label in nav(embed)]
    assert labels == ['Technology', 'Free Tools', 'Education', 'Community', 'About Jack', 'Become a Member']
    for href, _ in nav(embed):
        if href.startswith('#'):
            assert f'id="{href[1:]}"' in embed, href


def test_free_pages_do_not_link_to_the_gated_offer():
    for name in ('free_tools', 'tv_atr', 'calculator'):
        embed = markup(page(name, membership_open=''))
        assert CFG['sales_page_url'] not in embed, name
        assert 'Become a Member' not in embed, name


def test_free_pages_link_to_the_offer_once_open():
    embed = page('free_tools', membership_open='true')
    hrefs = dict((label, href) for href, label in nav(embed))
    assert hrefs['Technology'] == CFG['sales_page_url'] + '#indicators'
    assert hrefs['Become a Member'] == CFG['sales_page_url'] + '#pricing'
    assert 'See the membership' in embed


def test_education_uses_learn_page_when_it_exists():
    assert dict((l, h) for h, l in nav(page('sales')))['Education'] == '#room'
    learn = 'https://startuptrading.com/learn'
    assert dict((l, h) for h, l in nav(page('sales', learn_url=learn)))['Education'] == learn
    assert dict((l, h) for h, l in nav(page('free_tools', learn_url=learn)))['Education'] == learn


def test_no_internal_links_to_unknown_pages():
    known = {v for k, v in CFG.items() if isinstance(v, str) and v.startswith('https://startuptrading.com')}
    known |= {CFG['site_url'] + '/'}
    for name in ('sales', 'free_tools', 'tv_atr', 'calculator', 'welcome', 'setup'):
        embed = page(name)
        for href in re.findall(r'href="(https://startuptrading\.com[^"#?]*)', embed):
            assert href in known or href.rstrip('/') in known, (name, href)


# --- Optional sign-up ---------------------------------------------------------------

def test_signup_absent_until_configured_and_never_required():
    for name in ('free_tools', 'tv_atr', 'calculator'):
        assert 'id="subscribe"' not in page(name, ghl_subscribe_form_url=''), name
    form = 'https://api.leadconnectorhq.com/widget/form/TEST123'
    embed = page('tv_atr', ghl_subscribe_form_url=form)
    assert f'src="{form}?source_page=tv_atr&amp;interest=tradingview"' in embed
    assert 'never need an email' in embed and 'Unsubscribe anytime' in embed
    # The calculator works without the form: its inputs are outside the sign-up section.
    calc = page('calculator', ghl_subscribe_form_url=form)
    assert calc.index('id="sut-size"') < calc.index('id="subscribe"')


# --- SEO ------------------------------------------------------------------------------

def test_structured_data_for_new_pages():
    d = {g['@type']: g for g in ld(page('free_tools'))['@graph']}
    assert {'CollectionPage', 'BreadcrumbList', 'Organization'} <= set(d)
    assert [i['name'] for i in d['CollectionPage']['mainEntity']['itemListElement']] == [t['name'] for t in TOOLS['tools']]
    d = {g['@type']: g for g in ld(page('tv_atr'))['@graph']}
    assert d['SoftwareApplication']['offers']['price'] == '0' and 'downloadUrl' not in d['SoftwareApplication']
    d = {g['@type']: g for g in ld(page('tv_atr', tv_atr_script_url='https://www.tradingview.com/script/x/'))['@graph']}
    assert d['SoftwareApplication']['downloadUrl'] == 'https://www.tradingview.com/script/x/'


def test_new_pages_are_indexable_and_unique():
    b = load_build()
    titles = [p[3] for p in b.PAGES.values()]
    descs = [p[4] for p in b.PAGES.values()]
    assert len(set(titles)) == len(titles) and len(set(descs)) == len(descs)
    for name in ('free_tools', 'tv_atr'):
        _, full = b.render(CFG, name)
        assert 'noindex' not in full


@pytest.mark.parametrize('name', ['free_tools', 'tv_atr'])
def test_new_pages_pass_phrase_rules(name):
    from marketing import compliance
    assert compliance.check_text(text_of(page(name))) == []


# --- Analytics ------------------------------------------------------------------------

def test_tracking_hooks_present():
    assert 'data-tool-id="atr-position-size-planner"' in page('tv_atr')
    calc = markup(page('calculator'))
    assert 'data-tool-id="futures-position-size-calculator"' in calc and calc.count('data-tool-use') == 2
    sales = markup(page('sales'))
    assert sales.count('data-member-cta=') >= 3 and 'id="checkout"' in sales
    # The site-wide snippet is current and carries both affiliate capture and analytics.
    snippet = (SITE / 'dist' / 'site-tracking.html').read_text()
    assert snippet == load_build().site_tracking_snippet()
    assert 'window.SUT_AFFILIATE' in snippet and "push('sut_attribution')" in snippet


def node_eval(tmp_path, body):
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    src = (SITE / 'src' / 'tracking.js').read_text()
    core = src.split('/*track-core*/')[1].split('/*end-track-core*/')[0]
    script = tmp_path / 't.js'
    script.write_text(core + '\nconsole.log(JSON.stringify(' + body + '));')
    return json.loads(subprocess.run([node, str(script)], capture_output=True, text=True, check=True).stdout)


def test_attribution_first_and_last_touch(tmp_path):
    utm, ref, internal, direct, first_kept = node_eval(tmp_path, """[
      sutTouch('?utm_source=tradingview&utm_medium=signature&x=1', '', 'startuptrading.com', 1),
      sutTouch('', 'https://www.youtube.com/watch?v=1', 'startuptrading.com', 2),
      sutTouch('', 'https://startuptrading.com/free-tools', 'startuptrading.com', 3),
      sutTouch('', '', 'startuptrading.com', 4),
      sutAttribution(JSON.stringify({first:{utm_source:'tradingview',at:1}}), {utm_source:'youtube.com',utm_medium:'referral',at:2})
    ]""")
    assert utm == {'at': 1, 'utm_source': 'tradingview', 'utm_medium': 'signature'}
    assert ref == {'at': 2, 'utm_source': 'youtube.com', 'utm_medium': 'referral'}
    assert internal is None and direct is None
    assert first_kept['first']['utm_source'] == 'tradingview' and first_kept['last']['utm_source'] == 'youtube.com'
