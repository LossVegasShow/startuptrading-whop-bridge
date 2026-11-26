"""The homepage (startuptrading.com/) is the membership sales page. /join serves the same
page for old links. Logo and Home links go to the root; canonical, Open Graph and
structured data name the root; GTM classifies both as the membership sales page."""
import json
import re
import shutil
import subprocess

import pytest

from test_sales_site import SITE, load_build

CFG = json.loads((SITE / 'site.config.json').read_text())
ROOT = 'https://startuptrading.com/'


def render(name, **kw):
    return load_build().render(dict(CFG, **kw), name)


def test_config_points_the_sales_page_at_the_root():
    assert CFG['sales_page_url'] == ROOT and 'join_url' not in CFG
    assert CFG['membership_open'] == ''            # purchasing stays gated until acceptance tests pass


def test_sales_page_canonical_og_and_structured_data_name_the_root():
    embed, full = render('sales')[:2]
    assert f'<link rel="canonical" href="{ROOT}">' in full
    assert f'<meta property="og:url" content="{ROOT}">' in full
    assert '/join' not in full.split('<body')[0]
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', embed, re.S).group(1))
    app = {g['@type']: g for g in ld['@graph']}['SoftwareApplication']
    assert app['url'] == ROOT and all(o['url'] == ROOT + '#pricing' for o in app['offers'])
    assert '/join' not in json.dumps(ld)


@pytest.mark.parametrize('name', ['sales', 'free_tools', 'calculator', 'tv_atr', 'welcome', 'setup'])
def test_no_page_links_to_join_and_the_logo_goes_home(name):
    embed = render(name)[0]
    hrefs = re.findall(r'href="([^"]+)"', re.sub(r'<script.*?</script>', '', embed, flags=re.S))
    assert not [h for h in hrefs if '/join' in h], name
    logo = re.search(r'<a class="sut-logo"[^>]*href="([^"]+)"', embed)
    if logo:
        assert logo.group(1) in ('#top', ROOT), (name, logo.group(1))


def test_membership_ctas_point_at_the_homepage_once_open():
    for name in ('free_tools', 'calculator', 'tv_atr'):
        embed = render(name, membership_open='true')[0]
        assert f'href="{ROOT}#pricing"' in embed, name


def test_gtm_classifies_root_and_join_as_the_sales_page():
    node = shutil.which('node')
    if not node:
        pytest.skip('node needed')
    c = json.loads((SITE.parent / 'growth' / 'gtm' / 'startuptrading-gtm-container.json').read_text())['containerVersion']
    js = {v['name']: v for v in c['variable']}['Page type']['parameter'][0]['value']
    cases = {('startuptrading.com', '/'): 'membership_sales', ('startuptrading.com', '/join'): 'membership_sales',
             ('startuptrading.com', '/join/'): 'membership_sales', ('startuptrading.com', '/free-tools'): 'free_tools_directory',
             ('startuptrading.com', '/futures-position-size-calculator'): 'free_tool',
             ('startuptrading.com', '/tradingview/atr-position-size-planner'): 'free_tool',
             ('startuptrading.com', '/welcome'): 'post_checkout', ('startuptrading.com', '/setup'): 'member_setup',
             ('activate.startuptrading.com', '/onboarding'): 'activation'}
    for (host, path), want in cases.items():
        src = '(' + js.replace('{{Page Hostname}}', json.dumps(host)).replace('{{Page Path}}', json.dumps(path)) + ')()'
        assert subprocess.run([node, '-p', src], capture_output=True, text=True).stdout.strip() == want, path
    tags = {t['name']: t for t in c['tag']}
    blob = json.dumps(tags['GA4 - Google tag (page view)'])
    assert '"content_group"' in blob and '{{Page type}}' in blob
    assert all('page_type' in json.dumps(t) for t in c['tag'] if t['type'] == 'gaawe')


def test_affiliate_script_decorates_root_and_join():
    js = (SITE / 'src' / 'affiliate.js').read_text()
    assert r'/^\/(join\/?)?$/' in js
