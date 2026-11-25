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
    embed = page('free_tools', tv_atr_script_url='', tv_profile_url='')
    assert 'tradingview.com' not in markup(embed)   # the analytics script knows the host name
    url = 'https://www.tradingview.com/script/abc123-ATR-Position-Size-Stop-Planner/'
    embed = page('free_tools', tv_atr_script_url=url)
    assert f'href="{url}"' in embed and 'data-outbound="tradingview"' in embed


def test_published_script_is_live_everywhere():
    # Published by Jack on TradingView (Nov 2026): the config, registry and script agree.
    assert CFG['tv_atr_script_url'].startswith('https://www.tradingview.com/script/ZBt4abLo-')
    assert CFG['tv_profile_url'] == 'https://www.tradingview.com/u/Jack_Gleason/'
    planner = next(t for t in TOOLS['tools'] if t['id'] == 'atr-position-size-planner')
    assert planner['status'] == 'available' and planner['status_label'] == 'Free on TradingView'
    pine = (SITE.parent / 'growth' / 'tradingview' / 'atr-position-size-planner.pine').read_text()
    assert '// (c) Jack_Gleason' in pine and '{TradingView username}' not in pine
    for name in ('free_tools', 'tv_atr'):
        embed = page(name)
        assert f'href="{CFG["tv_atr_script_url"]}"' in embed and 'Coming soon' not in embed
    assert 'Follow Jack on TradingView' in page('tv_atr')


def test_companion_page():
    embed = page('tv_atr', tv_atr_script_url='', tv_profile_url='')
    assert 'tradingview.com' not in markup(embed) and 'sut-btn-disabled' in embed
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

FORM = 'https://api.leadconnectorhq.com/widget/form/TEST123'


def test_signup_absent_until_configured_and_never_required():
    for name in ('free_tools', 'tv_atr', 'calculator'):
        assert 'id="subscribe"' not in page(name, ghl_subscribe_form_url=''), name
        # A URL that isn't a GHL form embed is ignored rather than rendered broken.
        assert 'id="subscribe"' not in page(name, ghl_subscribe_form_url='https://example.com/x'), name
    # The calculator works without the form: its inputs are outside the sign-up section.
    calc = page('calculator', ghl_subscribe_form_url=FORM)
    assert calc.index('id="sut-size"') < calc.index('id="subscribe"')


@pytest.mark.parametrize('name,interest,tool', [
    ('free_tools', 'free-tools', 'free-tools-directory'),
    ('tv_atr', 'tradingview', 'atr-position-size-planner'),
    ('calculator', 'calculators', 'futures-position-size-calculator'),
])
def test_signup_embed_is_ghl_inline_form_with_attribution_hooks(name, interest, tool):
    embed = page(name, ghl_subscribe_form_url=FORM)
    section = re.search(r'<section[^>]*id="subscribe".*?</section>', embed, re.S).group(0)
    iframe = re.search(r'<iframe[^>]*>', section).group(0)
    # No src in the HTML: tracking.js adds the attribution parameters, then sets it once.
    assert ' src=' not in iframe and f'data-sut-src="{FORM}"' in iframe
    for attr in (f'data-source-page="{name}"', f'data-interest="{interest}"', f'data-tool-id="{tool}"',
                 'id="inline-TEST123"', 'data-form-id="TEST123"', 'data-layout-iframe-id="inline-TEST123"',
                 'data-cookie-consent="true"', 'data-cookie-consent-provider="auto"', 'data-ghl-form'):
        assert attr in iframe, attr
    # Lazy loading stops GoHighLevel's embed from ever showing the form.
    assert 'loading="lazy"' not in iframe
    # The form has its own headline and description: no second headline here.
    assert '<h2' not in section and '<h3' not in section
    assert 'works without an email' in section and 'Optional' in section
    # Usable without JavaScript.
    assert '<noscript>' in section and f'{FORM}?source_page={name}' in section
    # GoHighLevel's script is loaded by tracking.js, never twice from the markup.
    assert 'form_embed.js"></script>' not in embed


def test_resource_template_gets_the_form():
    b = load_build()
    b.PAGES['resource_demo'] = ('_resource-template.html', 'x.html', 'x-embed.html', 'Demo resource', 'Demo.')
    try:
        cfg = dict(CFG, ghl_subscribe_form_url=FORM)
        embed = b.render(cfg, 'resource_demo')[0]
    finally:
        del b.PAGES['resource_demo']
    assert 'id="subscribe"' in embed and 'data-interest="education"' in embed
    assert 'data-tool-id="RESOURCE_ID"' in embed


# --- SEO ------------------------------------------------------------------------------

def test_structured_data_for_new_pages():
    d = {g['@type']: g for g in ld(page('free_tools'))['@graph']}
    assert {'CollectionPage', 'BreadcrumbList', 'Organization'} <= set(d)
    assert [i['name'] for i in d['CollectionPage']['mainEntity']['itemListElement']] == [t['name'] for t in TOOLS['tools']]
    d = {g['@type']: g for g in ld(page('tv_atr', tv_atr_script_url=''))['@graph']}
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
      sutAttribution(JSON.stringify({first:{utm_source:'tradingview',at:1}}), sutTouch('', 'https://youtube.com/x', 'startuptrading.com', 2), 'startuptrading.com', 2)
    ]""")
    assert utm == {'at': 1, 'utm_source': 'tradingview', 'utm_medium': 'signature', 'channel': 'tradingview'}
    assert ref == {'at': 2, 'utm_source': 'youtube', 'utm_medium': 'referral', 'referrer_host': 'youtube.com', 'channel': 'youtube'}
    assert internal is None
    assert direct == {'at': 4, 'direct': True, 'utm_source': '(direct)', 'utm_medium': '(none)', 'channel': 'direct'}
    assert first_kept['first']['utm_source'] == 'tradingview' and first_kept['last']['utm_source'] == 'youtube'


def test_form_params_carry_first_and_latest_touch(tmp_path):
    params, empty = node_eval(tmp_path, """[
      sutFormParams({first:{utm_source:'youtube',utm_medium:'social',utm_campaign:'risk_lab',utm_content:'s25',at:1},
                     last:{utm_source:'tradingview',utm_medium:'social',at:2}}, 'jackaff',
                    {source_page:'tv_atr', interest:'tradingview', tool_id:'atr-position-size-planner'}),
      sutFormParams({}, '', {source_page:'calculator'})
    ]""")
    assert params == {
        'source_page': 'tv_atr', 'interest': 'tradingview', 'tool_id': 'atr-position-size-planner',
        'affiliate': 'jackaff',
        'first_utm_source': 'youtube', 'first_utm_medium': 'social', 'first_utm_campaign': 'risk_lab',
        'first_utm_content': 's25', 'last_utm_source': 'tradingview', 'last_utm_medium': 'social'}
    # Standard utm_* keys are never overwritten: GoHighLevel's own attribution reads those.
    assert not any(k.startswith('utm_') for k in params)
    assert empty == {'source_page': 'calculator'}


def test_only_ghl_success_message_counts_as_a_signup(tmp_path):
    results = node_eval(tmp_path, """[
      sutFormSubmitted(['set-sticky-contacts', 'embedded_iframe_inline-X', 'inline-X', 'loc', 'fp'], 'inline-X'),
      sutFormSubmitted(['set-sticky-contacts', '_ud', '{}', 'loc', 'fp'], 'inline-X'),
      sutFormSubmitted(['set-sticky-contacts', 'embedded_iframe_inline-Y', 'inline-Y'], 'inline-X'),
      sutFormSubmitted(['iframeLoaded'], 'inline-X'),
      sutFormSubmitted(['fetch-query-params', '', 'loc'], 'inline-X'),
      sutFormSubmitted('[iFrameSizer]inline-X:519:390:init', 'inline-X'),
      sutFormSubmitted({0: 'set-sticky-contacts', 1: 'embedded_iframe_inline-X'}, 'inline-X'),
      sutFormSubmitted(['set-sticky-contacts', 'embedded_iframe_'], '')
    ]""")
    assert results == [True, False, False, False, False, False, False, False]


# --- Flagship positioning: SEO spec (titles, descriptions, H1s, canonicals, author) ----

SEO_SPEC = {
    'tv_atr': ('Free TradingView Futures Position Size & Risk Indicator',
               'Free TradingView indicator for ATR position sizing, prop firm drawdown planning, micro futures '
               'comparison and visual trade risk management.',
               'Free futures risk & position size indicator for TradingView.'),
    'calculator': ('Free Futures Position Size Calculator | ES, NQ, MES, MNQ',
                   'Calculate futures contract size, ATR stops and estimated trade risk for ES, NQ, MES and MNQ. '
                   'Free prop firm risk planner. No sign-up required.',
                   'Free futures position size calculator & prop firm risk planner.'),
    'free_tools': ('Free Futures Trading Tools & Indicators | StartUpTrading',
                   'Explore free TradingView indicators, NinjaTrader tools, futures position size calculators '
                   'and risk management resources from StartUpTrading.',
                   'Free trading technology for futures traders.'),
}


@pytest.mark.parametrize('name', list(SEO_SPEC))
def test_titles_descriptions_and_h1_follow_the_spec(name):
    import html as h
    title, desc, h1 = SEO_SPEC[name]
    _, _, _, b_title, b_desc = load_build().PAGES[name]
    assert (b_title, b_desc) == (title, desc)
    embed = page(name)
    found = re.search(r'<h1>(.*?)</h1>', embed, re.S).group(1)
    assert ' '.join(h.unescape(re.sub(r'<[^>]+>', ' ', found)).split()).lower() == h1.lower()
    assert embed.count('<h1>') == 1


@pytest.mark.parametrize('name,key', [('tv_atr', 'tv_atr_page_url'), ('calculator', 'calculator_url'),
                                      ('free_tools', 'free_tools_url')])
def test_canonical_url_in_standalone_pages(name, key):
    _, full = load_build().render(CFG, name)
    assert full.count('rel="canonical"') == 1 and f'<link rel="canonical" href="{CFG[key]}">' in full


def test_members_pages_have_no_canonical_and_stay_noindex():
    for name in ('welcome', 'setup'):
        _, full = load_build().render(CFG, name)
        assert 'rel="canonical"' not in full and 'noindex' in full


def test_author_attribution_is_visible_and_in_structured_data():
    embed = page('tv_atr')
    assert 'By Jack Gleason.' in embed
    app = next(g for g in ld(embed)['@graph'] if g['@type'] == 'SoftwareApplication')
    assert app['author'] == {'@type': 'Person', 'name': 'Jack Gleason'}
    assert app['name'] == 'StartUpTrading Futures Risk Planner'
    assert app['alternateName'] == 'Futures Position Size Calculator - ATR & Prop Firm Risk'
    assert 'Futures Position Size Calculator - ATR &amp; Prop Firm Risk' in embed      # install step


def test_one_tracking_bundle_per_page():
    for name in ('sales', 'free_tools', 'tv_atr', 'calculator'):
        embed = page(name)
        assert embed.count('function sutTouch(') == 1 and embed.count('function sutAffPick(') == 1, name


def test_ghl_resizer_height_is_read_only_for_our_iframe(tmp_path):
    r = node_eval(tmp_path, """[
      sutSizerHeight('[iFrameSizer]inline-X:542:664:mutationObserver', 'inline-X'),
      sutSizerHeight('[iFrameSizer]inline-X:654.5:354:init', 'inline-X'),
      sutSizerHeight('[iFrameSizer]inline-Y:542:664:init', 'inline-X'),
      sutSizerHeight('[iFrameSizer]inline-XY:542:664:init', 'inline-X'),
      sutSizerHeight(['set-sticky-contacts'], 'inline-X'),
      sutSizerHeight('[iFrameSizer]inline-X:abc:1:init', 'inline-X'),
      sutSizerHeight('[iFrameSizer]inline-X:542:664:init', ''),
      SUT_FORM_PAD
    ]""")
    assert r[:7] == [542, 654.5, None, None, None, None, None]
    # GoHighLevel's measurement misses the form's 10px top margin on desktop.
    assert r[7] >= 10


def test_form_space_reserved_only_until_sized():
    css = (SITE / 'src' / 'styles.css').read_text()
    assert '.sut-sub-form:not([data-sut-sized]) { min-height: 519px; }' in css
    # Never clip the form by hiding its overflow.
    rule = re.search(r'\.sut-sub-form \{[^}]*\}', css).group(0)
    assert 'overflow' not in rule and 'scrolling' not in (SITE / 'build.py').read_text().split('def subscribe_html')[1].split('def membership_note_html')[0]
