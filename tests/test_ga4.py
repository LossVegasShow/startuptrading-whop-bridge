"""GTM / GA4 integration: the importable container, where GTM loads, consent,
GA client id hand-off, verified server events (Measurement Protocol) and the GA4
Data API connector for the dashboard."""
import asyncio
import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import acquisition
import ga4_data
from store import connect
from test_free_tools import node_eval
from test_marketing import cfg_for, payment, seed, PW, BASE
from test_sales_site import SITE, load_build

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = json.loads((ROOT / 'growth' / 'gtm' / 'startuptrading-gtm-container.json').read_text())['containerVersion']


# --- The importable GTM container ------------------------------------------------------

def test_container_is_current():
    import importlib.util
    spec = importlib.util.spec_from_file_location('bc', ROOT / 'growth' / 'gtm' / 'build_container.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.build()['containerVersion'] == CONTAINER, 'run python growth/gtm/build_container.py'


def test_container_references_resolve():
    names = {v['name'] for v in CONTAINER['variable']} | {b['name'] for b in CONTAINER['builtInVariable']} | {'_event'}
    blob = json.dumps(CONTAINER)
    for ref in set(re.findall(r'\{\{([^}]+)\}\}', blob)):
        assert ref in names, ref
    trig = {t['triggerId'] for t in CONTAINER['trigger']} | {'2147479573'}
    for t in CONTAINER['tag']:
        assert set(t['firingTriggerId']) <= trig, t['name']
    assert CONTAINER['container']['publicId'] == 'GTM-NXZL43PP'
    assert {v['name']: v for v in CONTAINER['variable']}['GA4 measurement ID']['parameter'][0]['value'] == 'G-S0PT1NK0FK'


def test_container_one_page_view_and_no_browser_purchase():
    tags = {t['name']: t for t in CONTAINER['tag']}
    google = [t for t in CONTAINER['tag'] if t['type'] == 'googtag']
    assert len(google) == 1 and google[0]['tagFiringOption'] == 'ONCE_PER_LOAD'
    blob = json.dumps(CONTAINER)
    assert 'purchase' not in blob and 'sut_purchase' not in blob
    # Every tracked activity is wired.
    events = {'free_tool_view', 'tool_use', 'calculation_complete', 'email_subscribe', 'checkout_view',
              'checkout_return', 'file_download', 'free_tool_select', 'checkout_intent', 'outbound_click'}
    assert all(e in blob for e in events)
    assert {'GA4 - select_content (free tool)', 'GA4 - select_promotion (membership CTA)', 'GA4 - tradingview_click'} <= set(tags)
    lookup = {v['name']: v for v in CONTAINER['variable']}['GA4 event name']
    pairs = {m['map'][0]['value']: m['map'][1]['value'] for m in lookup['parameter'][2]['list']}
    assert pairs == {'email_subscribe': 'generate_lead', 'checkout_view': 'begin_checkout'}


def test_container_sends_no_personal_data():
    blob = json.dumps(CONTAINER).lower().replace('email_subscribe', '')   # the event name itself
    for bad in ('email', 'affiliate', 'first_touch', 'last_touch', 'nt_email', 'buyer', 'license'):
        assert bad not in blob, bad
    clean = {v['name']: v for v in CONTAINER['variable']}['Page location (clean)']['parameter'][0]['value']
    assert "'/activate/(token)'" in clean and 'utm_source' in clean


# --- Where GTM loads --------------------------------------------------------------------

def test_gtm_only_in_site_wide_header_not_in_page_embeds():
    b = load_build()
    head, body = b.site_tracking_snippet(), b.site_tracking_body_snippet()
    assert head.count("window.SUT_GTM_ID = 'GTM-NXZL43PP'") == 1 and 'googletagmanager.com/gtm.js' in head
    assert head.index('SUT_GTM_ID') < head.index('SUT_AFF_KEY')            # consent defaults + GTM first
    assert 'ns.html?id=GTM-NXZL43PP' in body
    assert (SITE / 'dist' / 'site-tracking.html').read_text() == head
    assert (SITE / 'dist' / 'site-tracking-body.html').read_text() == body
    cfg = json.loads((SITE / 'site.config.json').read_text())
    for name in b.PAGES:
        assert 'googletagmanager' not in b.render(cfg, name)[0], name
    assert "analytics_storage: 'denied', region:" in head and "ad_storage: 'denied'" in head


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    import app
    cfg = cfg_for(tmp_path, gtm_container_id='GTM-NXZL43PP')
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE) as c:
        yield c, cfg


def test_activation_pages_load_gtm_admin_pages_never(app_client):
    c, cfg = app_client
    r = c.get('/')
    assert '<script src="/static/gtm.js" data-gtm="GTM-NXZL43PP"></script>' in r.text
    csp = r.headers['content-security-policy']
    assert "script-src 'self' https://www.googletagmanager.com" in csp and 'google-analytics.com' in csp
    admin = c.get('/admin/marketing', auth=('admin', PW))
    assert 'gtm.js' not in admin.text and 'googletagmanager' not in admin.headers['content-security-policy']
    assert c.get('/static/gtm.js').status_code == 200


def test_no_gtm_without_a_container(tmp_path, monkeypatch):
    import app
    monkeypatch.setattr(app, 'cfg', cfg_for(tmp_path))
    with TestClient(app.app, base_url=BASE) as c:
        r = c.get('/')
    assert 'gtm.js' not in r.text and 'googletagmanager' not in r.headers['content-security-policy']


# --- GA client id hand-off ---------------------------------------------------------------

def test_ga_client_id_from_cookie_and_handoff(tmp_path):
    js = node_eval(tmp_path, """[sutGaClientId('foo=1; _ga=GA1.1.1234567890.1764000000; x=2'), sutGaClientId('_ga=bad'),
        sutHandoff({first:{utm_source:'youtube',channel:'youtube'}}, '', '', '1234567890.1764000000').sut_gcid]""")
    assert js == ['1234567890.1764000000', '', '1234567890.1764000000']
    assert acquisition.ga_client_from_cookie('GA1.1.1234567890.1764000000') == '1234567890.1764000000'
    assert acquisition.ga_client_from_cookie('GA1.1.<script>') == ''
    cfg = cfg_for(tmp_path)
    with connect(cfg) as db:
        assert acquisition.record_ga_client(db, 'mem_a', '1234567890.1764000000', 'ga_cookie')
        assert not acquisition.record_ga_client(db, 'mem_a', '999999.1764000001', 'handoff')   # kept once
        assert not acquisition.record_ga_client(db, 'mem_b', 'not-an-id', 'handoff')
        # The hand-off never writes the GA id into the attribution table.
        assert acquisition.record_attribution(db, 'mem_c', 3, {'ga_client_id': '1.1764000000', 'first_channel': 'youtube'})


# --- Verified server events (Measurement Protocol) -----------------------------------------

class FakeResp:
    def __init__(self, code): self.status_code = code


def test_server_events_purchase_refund_activation_once(tmp_path):
    cfg = cfg_for(tmp_path, marketing_exclude_memberships='mem_qa', ga4_measurement_id='G-S0PT1NK0FK', ga4_api_secret='s3cret')
    seed(cfg)
    now = int(time.time())
    with connect(cfg) as db:
        for mem in ('mem_yt', 'mem_ig', 'mem_promo', 'mem_qa'):
            acquisition.record_ga_client(db, mem, '1234567890.1764000000', 'ga_cookie')
        db.execute("UPDATE customers SET status='ineligible' WHERE membership_id='mem_ig'")
    sent = []

    async def post(url, body):
        sent.append((url, body))
        return FakeResp(204)
    n = asyncio.run(acquisition.ga_sync(cfg, connect, post=post, now=now))
    names = sorted(b['events'][0]['name'] for _, b in sent)
    # mem_yt: 2 purchases (initial + renewal); mem_ig: purchase + full refund; $0 promo and QA: nothing.
    assert names.count('purchase') == 3 and names.count('refund') == 1
    assert names.count('activation_complete') == 2 and names.count('ninjatrader_linked') == 3
    assert names.count('subscription_cancel') == 1 and n == len(sent)
    blob = json.dumps([b for _, b in sent])
    for pii in ('example.com', 'buyer', '203.0.113.9', '4242', 'Main St'):
        assert pii not in blob
    purchases = [b['events'][0]['params'] for _, b in sent if b['events'][0]['name'] == 'purchase']
    assert {p['purchase_type'] for p in purchases} == {'initial', 'renewal'}
    assert all(p['transaction_id'].startswith('pay_') and p['currency'] == 'USD' for p in purchases)
    assert all('api_secret=s3cret' in u and 'measurement_id=G-S0PT1NK0FK' in u for u, _ in sent)
    # Webhook retries, worker restarts: nothing is sent twice.
    sent.clear()
    assert asyncio.run(acquisition.ga_sync(cfg, connect, post=post, now=now)) == 0 and sent == []


def test_unattributed_buyer_waits_then_counts_anonymously(tmp_path):
    cfg = cfg_for(tmp_path, ga4_measurement_id='G-S0PT1NK0FK', ga4_api_secret='s')
    with connect(cfg) as db:
        acquisition.record_payment(db, payment('pay_x', 'mem_x', paid='2026-11-20T10:00:00Z'), 'w')
        db.execute("UPDATE payments SET received_at=?", (1764000000,))
        assert acquisition.pending_ga_events(cfg, db, now=_ts('2026-11-20T12:00:00Z')) == []
        later = acquisition.pending_ga_events(cfg, db, now=_ts('2026-11-24T12:00:00Z'))
    assert [e[2]['name'] for e in later] == ['purchase'] and later[0][1] == acquisition._anon_client('mem_x')


def _ts(iso):
    return acquisition._ts(iso)


def test_no_server_events_without_secret(tmp_path):
    cfg = cfg_for(tmp_path)
    seed(cfg)
    assert asyncio.run(acquisition.ga_sync(cfg, connect, post=lambda u, b: None)) == 0


# --- GA4 Data API connector -----------------------------------------------------------------

def report(dims, mets):
    return {'rows': [{'dimensionValues': [{'value': d} for d in ds], 'metricValues': [{'value': str(m)} for m in ms]}
                     for ds, ms in zip(dims, mets)]}


FAKE = {
    'totals': report([[]], [[1200, 900, 1500, 800]]),
    'channels': report([['youtube'], ['ai_referral']], [[400, 500], [100, 120]]),
    'channel_events': report([['youtube', 'generate_lead'], ['youtube', 'tool_use'], ['ai_referral', 'generate_lead']],
                             [[20], [300], [5]]),
    'landing': report([['/futures-position-size-calculator']], [[700, 600, 30]]),
    'devices': report([['mobile'], ['desktop']], [[700], [500]]),
    'countries': report([['United States']], [[800]]),
    'default_channels': report([['Organic Search']], [[300, 250]]),
}


def fake_post(url, body):
    name = next(k for k, v in ga4_data._requests('30daysAgo', 'today').items() if v == body)

    class R:
        status_code = 200
        def json(self): return FAKE[name]

    async def go(): return R()
    return go()


def test_ga4_connector_summarizes_and_caches(tmp_path):
    cfg = cfg_for(tmp_path, ga4_property_id='123456789', ga4_service_account_json='{"client_email":"x","private_key":"y"}')
    data = asyncio.run(ga4_data.cached(cfg, connect, '30daysAgo', 'today', post=fake_post))
    assert data['totals']['users'] == 1200 and data['returning_users'] == 300 and data['leads'] == 25
    assert data['channels']['youtube'] == {'users': 400, 'sessions': 500, 'leads': 20}
    assert data['funnel']['tool_use'] == 300 and data['devices'] == {'mobile': 700, 'desktop': 500}
    again = asyncio.run(ga4_data.cached(cfg, connect, '30daysAgo', 'today', post=lambda u, b: 1 / 0))
    assert again['totals']['users'] == 1200            # served from the cache, no API call


def test_ga4_not_configured_is_reported_not_faked(tmp_path, monkeypatch):
    import app
    cfg = cfg_for(tmp_path)
    seed(cfg)
    monkeypatch.setattr(app, 'cfg', cfg)
    with TestClient(app.app, base_url=BASE) as c:
        html = c.get('/admin/marketing', auth=('admin', PW)).text
    assert 'not connected' in html and 'GA4_PROPERTY_ID' in html


def test_dashboard_shows_ga4_numbers_when_connected(tmp_path, monkeypatch):
    import app
    cfg = cfg_for(tmp_path, ga4_property_id='123456789', ga4_service_account_json='{"client_email":"x","private_key":"y"}')
    seed(cfg)
    monkeypatch.setattr(app, 'cfg', cfg)

    async def fake_cached(cfg_, connect_, start, end, post=None, now=None):
        return ga4_data.summarize(FAKE) | {'errors': {}, 'fetched_at': 1}
    monkeypatch.setattr(app.ga4_data, 'cached', fake_cached)
    with TestClient(app.app, base_url=BASE) as c:
        html = c.get('/admin/marketing', auth=('admin', PW)).text
    assert '<b>connected</b>' in html and '1,200' in html and 'Mixed sources' in html
    assert '/futures-position-size-calculator' in html and 'mobile 700' in html


def test_service_account_jwt_is_signed_rs256():
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import serialization, hashes
    import base64
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    tok = ga4_data._jwt('sa@proj.iam.gserviceaccount.com', pem, 'https://oauth2.googleapis.com/token', 1000)
    h, b, s = tok.split('.')
    pad = lambda x: x + '=' * (-len(x) % 4)
    claims = json.loads(base64.urlsafe_b64decode(pad(b)))
    assert claims['scope'].endswith('analytics.readonly') and claims['exp'] == 4600
    key.public_key().verify(base64.urlsafe_b64decode(pad(s)), f'{h}.{b}'.encode(), padding.PKCS1v15(), hashes.SHA256())
