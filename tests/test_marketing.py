"""Server-side marketing attribution and revenue (marketing.py, the webhook, the
activation hand-off and the admin dashboard)."""
import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import acquisition
from config import Config
from store import connect

PW = 'a-long-admin-password-for-tests'
BASE = 'https://activate.example.com'
SECRET = 'ws_marketing_test'


def cfg_for(tmp_path, **kw):
    base = dict(db=str(tmp_path / 'm.db'), database_url='', require_database_url=False, admin_password=PW,
                public_base_url=BASE, whop_webhook_secret=SECRET)
    base.update(kw)
    return Config(**base)


def payment(pid='pay_1', mem='mem_a', status='paid', total='99.00', reason='subscription_create', updated='2026-11-20T10:00:00Z',
            paid='2026-11-20T10:00:00Z', refunded='0.00', **extra):
    p = {'id': pid, 'membership_id': mem, 'status': status, 'substatus': status, 'billing_reason': reason,
         'currency': 'usd', 'total': {'amount': total, 'currency': 'usd'}, 'usd_total': {'amount': total, 'currency': 'usd'},
         'refunded_amount': {'amount': refunded, 'currency': 'usd'}, 'paid_at': paid, 'created_at': paid,
         'updated_at': updated, 'variant_id': 'plan_qSXeS0xoDapGU', 'product_id': 'prod_x', 'promo_code_id': None,
         'checkout_origin': 'https://startuptrading.com', 'checkout_surface': 'embedded_checkout',
         # Personal fields Whop sends that must never be stored:
         'customer_email': 'buyer@example.com', 'customer_phone': '+15550000', 'ip_address': '203.0.113.9',
         'user_agent': 'Mozilla', 'user': {'id': 'user_1', 'email': 'buyer@example.com'},
         'billing_address': {'line1': '1 Main St'}, 'payment_instrument': {'last4': '4242'}}
    p.update(extra)
    return p


# --- Hand-off ------------------------------------------------------------------------

def test_handoff_is_validated_and_never_personal():
    got = acquisition.parse_handoff({'sut_fs': 'youtube', 'sut_fm': 'social', 'sut_fch': 'youtube', 'sut_fl': '/free-tools',
                                   'sut_ft': '1764000000000', 'sut_ls': 'buyer@example.com', 'sut_lch': 'not_a_channel',
                                   'sut_vid': 'zz', 'sut_aff': 'jack aff<script>', 'sut_fc': 'risk_lab'})
    assert got == {'first_source': 'youtube', 'first_medium': 'social', 'first_channel': 'youtube',
                   'first_landing': '/free-tools', 'first_at': 1764000000, 'first_campaign': 'risk_lab'}
    assert acquisition.read_cookie(acquisition.cookie_value(got)) == got
    assert acquisition.read_cookie('not json') == {} and acquisition.read_cookie('x' * 3000) == {}


def test_attribution_is_stored_once_per_membership(tmp_path):
    cfg = cfg_for(tmp_path)
    with connect(cfg) as db:
        assert acquisition.record_attribution(db, 'mem_a', 1, {'first_channel': 'youtube', 'first_source': 'youtube'})
        # A later sign-in from another source never overwrites the original acquisition.
        assert not acquisition.record_attribution(db, 'mem_a', 1, {'first_channel': 'instagram', 'first_source': 'instagram'})
        assert not acquisition.record_attribution(db, 'not_a_mem', 1, {'first_channel': 'youtube'})
        row = dict(db.execute('SELECT * FROM customer_attribution').fetchone())
    assert row['first_channel'] == 'youtube' and row['method'] == 'activation_link'


def test_activation_page_keeps_the_handoff_in_a_cookie(tmp_path, monkeypatch):
    import app
    monkeypatch.setattr(app, 'cfg', cfg_for(tmp_path))
    with TestClient(app.app, base_url=BASE) as c:
        r = c.get('/?sut_fs=chatgpt&sut_fm=referral&sut_fch=ai_referral&sut_vid=a1b2c3d4e5f6a1b2c3d4e5f6')
        assert r.status_code == 200
        cookie = r.cookies.get(acquisition.ATTR_COOKIE)
        assert acquisition.read_cookie(cookie)['first_channel'] == 'ai_referral'
        assert 'httponly' in r.headers['set-cookie'].lower()
        assert acquisition.ATTR_COOKIE not in c.get('/').headers.get('set-cookie', '')


# --- Payments ------------------------------------------------------------------------

def test_payment_rows_keep_no_personal_data():
    row = acquisition.payment_row(payment())
    assert row['total'] == 99.0 and row['membership_id'] == 'mem_a' and row['billing_reason'] == 'subscription_create'
    blob = json.dumps(row)
    for pii in ('buyer@example.com', '+15550000', '203.0.113.9', 'Mozilla', '1 Main St', '4242', 'user_1'):
        assert pii not in blob
    assert acquisition.payment_row({'id': 'nope'}) is None


def test_payments_are_idempotent_and_order_safe(tmp_path):
    cfg = cfg_for(tmp_path)
    with connect(cfg) as db:
        assert acquisition.record_payment(db, payment(updated='2026-11-20T10:00:00Z'), 'webhook:payment.succeeded')
        assert acquisition.record_payment(db, payment(updated='2026-11-20T10:00:00Z'), 'webhook:payment.succeeded')  # retry
        assert acquisition.record_payment(db, payment(updated='2026-11-21T10:00:00Z', refunded='99.00', substatus='refunded'), 'api_refresh')
        # An older copy arriving late never replaces the newer one.
        assert not acquisition.record_payment(db, payment(updated='2026-11-19T10:00:00Z'), 'webhook:payment.succeeded')
        rows = db.execute('SELECT * FROM payments').fetchall()
    assert len(rows) == 1 and rows[0]['refunded_amount'] == 99.0 and rows[0]['substatus'] == 'refunded'


def signed(body, mid='msg_1'):
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    sig = base64.b64encode(hmac.new(SECRET.encode(), f'{mid}.{ts}.'.encode() + raw, hashlib.sha256).digest()).decode()
    return raw, {'webhook-id': mid, 'webhook-timestamp': ts, 'webhook-signature': 'v1,' + sig, 'content-type': 'application/json'}


def test_signed_payment_webhook_records_revenue_once(tmp_path, monkeypatch):
    import app
    cfg = cfg_for(tmp_path)
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE) as c:
        raw, heads = signed({'id': 'msg_1', 'type': 'payment.succeeded', 'data': payment()})
        assert c.post('/webhooks/whop', content=raw, headers=heads).json() == {'received': True, 'duplicate': False}
        assert c.post('/webhooks/whop', content=raw, headers=heads).json()['duplicate'] is True
        bad_raw, bad_heads = signed({'id': 'msg_2', 'type': 'payment.succeeded', 'data': payment(pid='pay_forged')}, 'msg_2')
        bad_heads['webhook-signature'] = 'v1,forged'
        assert c.post('/webhooks/whop', content=bad_raw, headers=bad_heads).status_code == 401
    with connect(cfg) as db:
        assert [r['id'] for r in db.execute('SELECT id FROM payments')] == ['pay_1']


# --- Reporting -----------------------------------------------------------------------

def seed(cfg):
    with connect(cfg) as db:
        members = [('mem_yt', 'eligible', 1, 'youtube'), ('mem_ig', 'eligible', 1, 'instagram'),
                   ('mem_promo', 'eligible', 1, 'youtube'), ('mem_none', 'ineligible', 0, None),
                   ('mem_qa', 'eligible', 1, 'youtube')]
        for i, (mem, status, verified, ch) in enumerate(members, 1):
            db.execute('INSERT INTO customers(id,membership_id,whop_user_id,buyer_email,nt_email,verified,status,updated_at) '
                       'VALUES(?,?,?,?,?,?,?,?)', (i, mem, 'u', f'b{i}@example.com', f'nt{i}@example.com', verified, status, 1))
            db.execute('INSERT INTO audit(at,customer_id,action,details) VALUES(?,?,?,?)', (1764000000 + i, i, 'seen', ''))
            if ch:
                acquisition.record_attribution(db, mem, i, {'first_channel': ch, 'first_source': ch, 'first_medium': 'social',
                                                          'first_campaign': 'risk_lab', 'first_landing': '/free-tools',
                                                          'last_channel': 'tradingview', 'last_source': 'tradingview'})
        for i in (1, 2):
            for pid in (2067, 2071):
                db.execute("INSERT INTO licenses(customer_id,product_id,license_id,expiration,state,updated_at) VALUES(?,?,?,?,?,?)",
                           (i, pid, 100 + pid, 'x', 'created', 1))
        acquisition.record_payment(db, payment('pay_yt1', 'mem_yt'), 'w')
        acquisition.record_payment(db, payment('pay_yt2', 'mem_yt', reason='subscription_cycle', paid='2026-12-20T10:00:00Z',
                                             updated='2026-12-20T10:00:00Z'), 'w')
        acquisition.record_payment(db, payment('pay_ig', 'mem_ig', total='495.00', refunded='495.00'), 'w')
        acquisition.record_payment(db, payment('pay_promo', 'mem_promo', total='0.00'), 'w')
        acquisition.record_payment(db, payment('pay_fail', 'mem_promo', status='failed', total='99.00'), 'w')
        acquisition.record_payment(db, payment('pay_qa', 'mem_qa', total='99.00'), 'w')


def test_report_counts_verified_revenue_by_channel(tmp_path):
    cfg = cfg_for(tmp_path, marketing_exclude_memberships='mem_qa')
    seed(cfg)
    with connect(cfg) as db:
        r = acquisition.report(cfg, db)
    t = r['totals']
    assert t['excluded'] == 1 and t['subscribers'] == 4
    assert t['paying'] == 2 and t['promo_only'] == 1          # $0 promo is never a paying customer
    assert t['revenue'] == 99 + 99 + 495 and t['refunds'] == 495 and t['net_revenue'] == 198
    assert t['renewal_revenue'] == 99 and t['initial_revenue'] == 99 + 495
    assert t['failed_payments'] == 1 and t['refunded_payments'] == 1
    assert t['activated'] == 2 and t['activation_rate'] == 50.0
    assert t['churned'] == 1 and t['attribution_rate'] == 75.0
    assert t['mrr'] == 99                                     # the refunded annual payment adds nothing
    ch = {x['channel']: x for x in r['channels']}
    assert ch['youtube']['net_revenue'] == 198 and ch['youtube']['subscribers'] == 2 and ch['youtube']['ltv'] == 198
    assert ch['instagram']['net_revenue'] == 0 and ch['unknown']['subscribers'] == 1
    assert r['channels'][0]['channel'] == 'youtube'


def test_report_filters_and_latest_touch(tmp_path):
    cfg = cfg_for(tmp_path, marketing_exclude_emails='nt5@example.com')
    seed(cfg)
    with connect(cfg) as db:
        last = acquisition.report(cfg, db, basis='last')
        yt = acquisition.report(cfg, db, channel='youtube')
        dec = acquisition.report(cfg, db, start=1764000000 + 100, end=None)
        paid = acquisition.report(cfg, db, traffic='paid')
    assert {x['channel'] for x in last['channels']} == {'tradingview', 'unknown'}
    assert yt['totals']['subscribers'] == 2 and yt['totals']['excluded'] == 1
    assert dec['totals']['subscribers'] == 0          # nobody first seen after the start date
    assert paid['totals']['subscribers'] == 0


def test_dashboard_and_link_generator_need_admin(tmp_path, monkeypatch):
    import app
    cfg = cfg_for(tmp_path)
    seed(cfg)
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE) as c:
        assert c.get('/admin/marketing').status_code == 401
        html = c.get('/admin/marketing', auth=('admin', PW)).text
        assert 'Marketing performance' in html and 'YouTube' in html and 'Verified' in html and 'GA4' in html
        html = c.get('/admin/marketing?channel=youtube&basis=last&start=2025-01-01&end=bad', auth=('admin', PW)).text
        assert 'Acquisition channels (latest touch)' in html
        assert c.get('/admin/campaign-links').status_code == 401
        assert 'Campaign link generator' in c.get('/admin/campaign-links', auth=('admin', PW)).text
        assert c.get('/static/campaign-links.js').status_code == 200
