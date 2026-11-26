"""The free StartUpTrading Community product (Discord) and the annual plan ID fix.

Guarantees: community members never receive indicator licenses, never become
customers, never count as paid subscribers or revenue, can upgrade to the paid
membership, and paid functionality is unchanged."""
import asyncio
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

import acquisition
import purchaser_intake
from clients import membership_entitlement, membership_plan_id
from config import BUSINESS_ID, PRODUCT_ID, PLANS, COMMUNITY_PRODUCT_ID, COMMUNITY_PLAN_ID
from store import connect
from test_marketing import cfg_for, payment, seed
from test_sales_site import SITE, load_build

ANNUAL = 'plan_B84PWlvXemyfX'     # Whop's canonical spelling (verified via the API)


def paid(plan, **kw):
    end = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat().replace('+00:00', 'Z')
    m = {'id': 'mem_paid', 'account': {'id': BUSINESS_ID}, 'user_id': 'user_a', 'product_id': PRODUCT_ID,
         'variant_id': plan, 'status': 'active', 'current_period_end': end, 'expires_at': None}
    m.update(kw)
    return m


def community(**kw):
    m = {'id': 'mem_comm', 'account': {'id': BUSINESS_ID}, 'user_id': 'user_a', 'product_id': COMMUNITY_PRODUCT_ID,
         'variant_id': COMMUNITY_PLAN_ID, 'status': 'active', 'created_at': '2026-11-26T10:00:00Z',
         'current_period_end': None, 'expires_at': None}
    m.update(kw)
    return m


# --- Annual plan ID ---------------------------------------------------------------------

def test_annual_plan_uses_whops_canonical_id_and_matches_any_case():
    assert ANNUAL in PLANS and 'plan_B84PWLvXemyFX' not in PLANS
    for spelling in (ANNUAL, 'plan_B84PWLvXemyFX', ANNUAL.lower()):
        ent = membership_entitlement(paid(spelling))
        assert ent and ent['plan_id'] == ANNUAL, spelling
    assert membership_plan_id({'variant_id': 'plan_b84pwlvxemyfx', 'plan': {'id': ANNUAL}}) == ANNUAL
    # Genuinely different plans still conflict.
    assert membership_plan_id({'variant_id': ANNUAL, 'plan': {'id': 'plan_qSXeS0xoDapGU'}}) is None
    cfg = json.loads((SITE / 'site.config.json').read_text())
    assert ANNUAL in cfg['checkout_url_annual']


# --- Community: never licensed, never a customer ------------------------------------------

def test_community_membership_is_never_entitled_to_licenses():
    assert membership_entitlement(community()) is None
    assert not purchaser_intake.is_target_membership(community())
    # Even if someone put the free plan on the paid product, it isn't a paid plan.
    assert membership_entitlement(community(product_id=PRODUCT_ID)) is None
    assert COMMUNITY_PRODUCT_ID != PRODUCT_ID and COMMUNITY_PLAN_ID not in PLANS


class FakeWhop:
    def __init__(self, m): self.m = m
    async def membership(self, mid): return dict(self.m)
    async def resolve_membership(self, m): return m


def test_community_webhook_records_member_only(tmp_path):
    cfg = cfg_for(tmp_path)
    result = asyncio.run(purchaser_intake.import_membership(cfg, FakeWhop(community()), 'mem_comm'))
    assert result == {'state': 'community_member'}
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) AS n FROM customers').fetchone()['n'] == 0
        assert db.execute('SELECT COUNT(*) AS n FROM message_outbox').fetchone()['n'] == 0
        row = dict(db.execute('SELECT * FROM community_members').fetchone())
    assert row['membership_id'] == 'mem_comm' and row['whop_user_id'] == 'user_a' and row['status'] == 'active'

    class Engine:
        async def reconcile(self, cid): raise AssertionError('community members are never reconciled')
    state = asyncio.run(purchaser_intake.handle_queued_event(cfg, FakeWhop(community()), Engine(), {'object_id': 'mem_comm'}))
    assert state == 'community_member'


def test_other_products_are_still_ignored(tmp_path):
    cfg = cfg_for(tmp_path)
    other = community(product_id='prod_somethingelse')
    assert asyncio.run(purchaser_intake.import_membership(cfg, FakeWhop(other), 'mem_comm')) == {'state': 'ignored_other_product'}


# --- Community: never revenue, upgrades counted -------------------------------------------

def test_community_payments_are_never_revenue_or_ga4_purchases(tmp_path):
    cfg = cfg_for(tmp_path, ga4_measurement_id='G-S0PT1NK0FK', ga4_api_secret='s')
    seed(cfg)
    with connect(cfg) as db:
        before = acquisition.report(cfg, db)['totals']
        # A $0 community checkout, and (defensively) a non-zero one on the community product.
        acquisition.record_payment(db, payment('pay_c0', 'mem_comm', total='0.00', product_id=COMMUNITY_PRODUCT_ID), 'w')
        acquisition.record_payment(db, payment('pay_c1', 'mem_yt', total='5.00', product_id=COMMUNITY_PRODUCT_ID,
                                               paid='2026-11-21T10:00:00Z', updated='2026-11-21T10:00:00Z'), 'w')
        after = acquisition.report(cfg, db)['totals']
        acquisition.record_ga_client(db, 'mem_yt', '1234567890.1764000000', 'ga_cookie')
        txids = [e[2]['params'].get('transaction_id') for e in acquisition.pending_ga_events(cfg, db)]
    assert after['revenue'] == before['revenue'] and after['paying'] == before['paying']
    assert 'pay_c0' not in txids and 'pay_c1' not in txids


def test_upgrade_from_community_to_paid_is_counted(tmp_path):
    cfg = cfg_for(tmp_path)
    seed(cfg)            # paid customers: mem_yt (user 'u', paid $99 + $99 renewal) etc.
    with connect(cfg) as db:
        db.execute("UPDATE customers SET whop_user_id='user_upgraded' WHERE membership_id='mem_yt'")
        acquisition.record_community_member(db, community(id='mem_c1', user_id='user_upgraded'))
        acquisition.record_community_member(db, community(id='mem_c2', user_id='user_never_paid'))
        acquisition.record_community_member(db, {'id': 'mem_x', 'product_id': 'prod_other', 'user_id': 'user_z'})
        r = acquisition.community_report(db)
    assert r['joined'] == 2 and r['upgraded'] == 1 and r['upgrade_rate'] == 50.0
    assert r['upgraded_revenue'] == 198          # the upgraded member's paid revenue ($99 + $99 renewal)
    # Webhook retries don't double count.
    with connect(cfg) as db:
        acquisition.record_community_member(db, community(id='mem_c1', user_id='user_upgraded', status='canceled'))
        assert acquisition.community_report(db)['joined'] == 2


def test_upgrading_member_can_still_activate_paid_tools():
    """The paid entitlement only looks at the paid membership; a community membership
    for the same Whop user changes nothing."""
    assert membership_entitlement(paid('plan_qSXeS0xoDapGU', user_id='user_a'))
    assert membership_entitlement(community(user_id='user_a')) is None


# --- Site and GTM ---------------------------------------------------------------------------

def test_free_pages_offer_the_free_community():
    b = load_build()
    cfg = json.loads((SITE / 'site.config.json').read_text())
    assert cfg['community_join_url'] == f'https://whop.com/checkout/{COMMUNITY_PLAN_ID}/'
    for name in ('free_tools', 'calculator', 'tv_atr'):
        embed = b.render(cfg, name)[0]
        assert f'data-community-cta="{name}"' in embed and 'Join the free Discord' in embed, name
    import re
    markup = lambda h: re.sub(r'<script.*?</script>', '', h, flags=re.S)
    sales = markup(b.render(cfg, 'sales')[0])
    for place in ('hero', 'pricing', 'faq', 'footer'):
        assert f'data-community-cta="{place}"' in sales, place
    # Free entry to the Discord; the trade room stays paid.
    assert 'Free Discord community</th><td class="yes">✓</td><td class="yes">✓</td>' in sales
    assert 'Members-only trade room with Jack</th><td class="no">—</td><td class="yes">✓</td>' in sales
    assert 'Private Discord' not in sales
    for name in ('welcome', 'setup'):          # members' pages: already in the community
        assert 'data-community-cta' not in markup(b.render(cfg, name)[0]), name
    assert 'data-community-cta' not in markup(b.render(dict(cfg, community_join_url=''), 'free_tools')[0])


def test_gtm_container_maps_community_events():
    c = json.loads((SITE.parent / 'growth' / 'gtm' / 'startuptrading-gtm-container.json').read_text())['containerVersion']
    blob = json.dumps(c)
    assert 'community_join_click' in blob and 'join_group' in blob and '{{DLV - group_id}}' in blob


DRIVER = r"""
const {chromium} = require('playwright'); const fs = require('fs');
const [htmlFile, outFile] = process.argv.slice(2); const html = fs.readFileSync(htmlFile, 'utf8');
(async () => {
  const b = await chromium.launch(); const out = {};
  for (const [name, q] of [['click', ''], ['joined', '?community=joined'], ['joined_again', '?community=joined']]) {
    const ctx = name === 'joined_again' ? out._ctx : await b.newContext(); if (name === 'joined') out._ctx = ctx;
    const p = await ctx.newPage();
    await p.route('**/*', r => r.request().url().startsWith('https://startuptrading.com/') ?
      r.fulfill({contentType: 'text/html', body: html}) : r.fulfill({contentType: 'text/javascript', body: ''}));
    await p.goto('https://startuptrading.com/futures-position-size-calculator' + q);
    await p.waitForTimeout(300);
    if (name === 'click') {
      await p.evaluate(() => document.addEventListener('click', e => e.preventDefault(), true));
      await p.fill('#sut-size input[name=risk]', '750'); await p.waitForTimeout(100);
      await p.fill('#sut-prop input[name=dd]', '2500'); await p.waitForTimeout(100);
      await p.click('a[data-community-cta]');
    }
    out[name] = await p.evaluate(() => dataLayer.filter(e => e && e.event && !/^gtm/.test(e.event)));
  }
  delete out._ctx; await b.close(); fs.writeFileSync(outFile, JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def test_community_events_and_clean_parameters_in_browser(tmp_path):
    node = shutil.which('node')
    if not node or subprocess.run([node, '-e', "require('playwright')"], capture_output=True, cwd=tmp_path).returncode:
        pytest.skip('node + playwright needed')
    b = load_build()
    cfg = json.loads((SITE / 'site.config.json').read_text())
    html = '<!doctype html><html><head><meta charset="utf-8"></head><body>' + b.render(cfg, 'calculator')[0] + '</body></html>'
    (tmp_path / 'page.html').write_text(html)
    (tmp_path / 'd.js').write_text(DRIVER)
    subprocess.run([node, str(tmp_path / 'd.js'), str(tmp_path / 'page.html'), str(tmp_path / 'o.json')], check=True, cwd=tmp_path, timeout=90)
    out = json.loads((tmp_path / 'o.json').read_text())
    ev = {e['event']: e for e in out['click']}
    assert ev['community_join_click'].get('placement') == 'calculator'
    # tool_use no longer carries the previous event's calculator.
    tool_use = [e for e in out['click'] if e['event'] == 'tool_use'][0]
    assert tool_use.get('calculator') is None and tool_use['tool_id'] == 'futures-position-size-calculator'
    assert sorted(e.get('calculator') for e in out['click'] if e['event'] == 'calculation_complete') == ['position_size', 'prop_firm']
    # The post-join event: once per browser, never on a reload or repeat visit.
    assert [e['event'] for e in out['joined']].count('community_join') == 1
    assert [e for e in out['joined'] if e['event'] == 'community_join'][0]['group_id'] == 'startuptrading_community'
    assert [e['event'] for e in out['joined_again']].count('community_join') == 0
