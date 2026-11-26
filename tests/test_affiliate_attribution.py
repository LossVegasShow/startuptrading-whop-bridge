"""Whop affiliate attribution on the startuptrading.com homepage (the sales page; /join still works) (sales-site/src/affiliate.js).

Affiliates send customers to startuptrading.com/join?a=CODE. The code must reach
BOTH embedded checkouts (monthly and annual) and every Whop checkout link, survive
navigation and return visits, and never change the plan, price or return URL.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_sales_site import SITE, load_build, rendered

NOW = 1_800_000_000_000  # ms


def node_eval(tmp_path, body):
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    src = (SITE / 'src' / 'affiliate.js').read_text()
    core = src.split('/*aff-core*/')[1].split('/*end-aff-core*/')[0]
    script = tmp_path / 'aff.js'
    script.write_text(core + '\nconsole.log(JSON.stringify(' + body + '));')
    return json.loads(subprocess.run([node, str(script)], capture_output=True, text=True, check=True).stdout)


def test_codes_are_cleaned(tmp_path):
    out = node_eval(tmp_path, "['jack_t', 'Trader.Bob-1', ' x ', '', '<script>', 'a b', 'x'.repeat(65), null, '-lead']"
                              ".map(sutAffClean)")
    assert out == ['jack_t', 'Trader.Bob-1', 'x', '', '', '', '', '', '']


def test_url_code_is_saved_for_30_days_and_latest_wins(tmp_path):
    first, again, later, expired, newer, junk = node_eval(tmp_path, f"""[
      sutAffPick('?a=alice&utm_source=yt', null, {NOW}),
      sutAffPick('', JSON.stringify({{code:'alice', exp:{NOW}+1000}}), {NOW}),
      sutAffPick('?utm_source=x', JSON.stringify({{code:'alice', exp:{NOW}+29*86400000}}), {NOW}),
      sutAffPick('', JSON.stringify({{code:'alice', exp:{NOW}-1}}), {NOW}),
      sutAffPick('?a=bob', JSON.stringify({{code:'alice', exp:{NOW}+1000}}), {NOW}),
      sutAffPick('?a=%3Cbad%3E', JSON.stringify({{code:'alice', exp:{NOW}+1000}}), {NOW})
    ]""")
    assert first['code'] == 'alice' and json.loads(first['save']) == {'code': 'alice', 'exp': NOW + 30 * 86400000}
    assert again == {'code': 'alice', 'save': None}            # remembered on a later page view
    assert later['code'] == 'alice'
    assert expired == {'code': '', 'save': None}               # after 30 days, nothing
    assert newer['code'] == 'bob' and json.loads(newer['save'])['code'] == 'bob'   # most recent affiliate
    assert junk == {'code': 'alice', 'save': None}             # invalid ?a= ignored, keeps the saved one


def test_corrupt_storage_is_ignored(tmp_path):
    assert node_eval(tmp_path, "sutAffPick('', '{not json', 1)") == {'code': '', 'save': None}


def test_only_checkout_and_join_links_are_decorated(tmp_path):
    out = node_eval(tmp_path, """[
      sutAffDecorate('https://whop.com/checkout/plan_qSXeS0xoDapGU/', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://whop.com/checkout/plan_B84PWlvXemyfX/?utm_source=x', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://startuptrading.com/join', 'alice', 'www.startuptrading.com'),
      sutAffDecorate('https://startuptrading.com/join#pricing', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://whop.com/startuptrading/', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://whop.com/checkout/plan_qSXeS0xoDapGU/?a=bob', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://startuptrading.com/indicators', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://activate.startuptrading.com/', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://example.com/checkout/x', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://whop.com/checkout/plan_qSXeS0xoDapGU/', '', 'startuptrading.com'),
      sutAffDecorate('not a url', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://startuptrading.com/', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://startuptrading.com/#pricing', 'alice', 'startuptrading.com'),
      sutAffDecorate('https://startuptrading.com/free-tools', 'alice', 'startuptrading.com')
    ]""")
    assert out[0] == 'https://whop.com/checkout/plan_qSXeS0xoDapGU/?a=alice'
    assert out[1] == 'https://whop.com/checkout/plan_B84PWlvXemyfX/?utm_source=x&a=alice'
    assert out[2] == 'https://startuptrading.com/join?a=alice'
    assert out[3] == 'https://startuptrading.com/join?a=alice#pricing'
    assert out[4] == 'https://whop.com/startuptrading/?a=alice'
    assert out[5].endswith('?a=bob')                           # an explicit affiliate is never replaced
    assert out[6:11] == ['https://startuptrading.com/indicators', 'https://activate.startuptrading.com/',
                         'https://example.com/checkout/x', 'https://whop.com/checkout/plan_qSXeS0xoDapGU/', 'not a url']
    # The homepage is the sales page, so links to it carry the affiliate too (/join is kept for old links).
    assert out[11:] == ['https://startuptrading.com/?a=alice', 'https://startuptrading.com/?a=alice#pricing',
                        'https://startuptrading.com/free-tools']


def test_page_script_runs_affiliate_capture_before_the_checkout_code():
    _, embed, _ = rendered(embed='true')
    script = embed.split('<script>\n', 1)[1].split('</script>', 1)[0]
    assert script.index('window.SUT_AFFILIATE = pick.code') < script.index('data-whop-checkout-affiliate-code')
    # The Whop loader comes after, so the attribute is set before the checkouts mount.
    assert embed.index('data-whop-checkout-affiliate-code') < embed.index('js.whop.com/static/checkout/loader.js')


def test_both_plans_get_the_code_and_keep_their_return_url():
    cfg, embed, _ = rendered(embed='true')
    mounts = re.findall(r'<div data-whop-checkout-plan-id="([^"]+)"([^>]*)>', embed)
    assert {p for p, _ in mounts} == {'plan_qSXeS0xoDapGU', 'plan_B84PWlvXemyfX'}
    for _, attrs in mounts:
        assert f'data-whop-checkout-return-url="{cfg["thank_you_url"]}"' in attrs
    # The script sets the code on EVERY mount (a loop over all of them), nothing else.
    assert "querySelectorAll('.sut [data-whop-checkout-plan-id]')" in embed
    assert "setAttribute('data-whop-checkout-affiliate-code', aff)" in embed
    assert 'data-whop-checkout-return-url' not in embed.split('<script>', 1)[1]


def test_hosted_checkout_links_carry_the_code_when_embed_is_off():
    cfg = json.loads((SITE / 'site.config.json').read_text())
    cfg['embed_checkout'] = ''
    embed, _ = load_build().render(cfg, 'sales')
    assert "if (aff && !url.searchParams.has('a')) url.searchParams.set('a', aff);" in embed


def test_ghl_site_wide_snippet_is_built_and_current():
    snippet = (SITE / 'dist' / 'affiliate-tracking.html').read_text()
    assert snippet == load_build().affiliate_snippet()
    assert snippet.startswith('<!-- StartUpTrading: Whop affiliate attribution') and '<script>' in snippet
    assert 'window.SUT_AFFILIATE' in snippet and 'whop-checkout-return-url' not in snippet
