from fastapi.testclient import TestClient
from config import Config
from store import connect, track_funnel_event
import app as web
from pathlib import Path


def test_public_page_hides_admin_and_unverified_content(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'v2.sqlite'))
    monkeypatch.setattr(web.cfg,'whop_checkout_url','')
    monkeypatch.setattr(web.cfg,'admin_test_enabled',True)
    with TestClient(web.app) as client:
        page=client.get('/')
        assert page.status_code==200
        for name in ('ATR Order Automation','Trend Scanner and Momentum Selector','TSMS & Fibs'):
            assert name in page.text or name.replace('&','&amp;') in page.text
        assert '/admin-test' not in page.text
        assert 'VERIFIED SCREENSHOT PENDING' in page.text
        assert client.get('/checkout').status_code==503
        assert client.get('/activate',follow_redirects=False).headers['location']=='/oauth/login'
        assert client.get('/admin').status_code in (401,503)


def test_checkout_only_redirects_to_whop_and_tracks(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'funnel.sqlite'))
    monkeypatch.setattr(web.cfg,'whop_checkout_url','https://whop.com/checkout/example')
    with TestClient(web.app) as client:
        assert client.get('/').status_code==200
        result=client.get('/checkout',follow_redirects=False)
        assert result.status_code==303
        assert result.headers['location']=='https://whop.com/checkout/example'
    with connect(web.cfg) as db:
        names=[r['event_name'] for r in db.execute('SELECT event_name FROM funnel_events').fetchall()]
    assert 'visitor' in names and 'checkout_initiated' in names


def test_checkout_rejects_external_redirect(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'guard.sqlite'))
    for url in ('https://whop.com.evil.example/buy','javascript:alert(1)', 'http://whop.com/buy', 'https://evil.example'):
        monkeypatch.setattr(web.cfg,'whop_checkout_url',url)
        with TestClient(web.app) as client:
            assert client.get('/checkout').status_code==503


def test_verified_conversion_event_is_idempotent(tmp_path):
    cfg=Config(db=str(tmp_path/'unique.sqlite'))
    with connect(cfg) as db:
        track_funnel_event(db,'conversion_confirmed','membership:mem_abc')
        track_funnel_event(db,'conversion_confirmed','membership:mem_abc')
    with connect(cfg) as db:
        assert db.execute("SELECT COUNT(*) AS n FROM funnel_events WHERE event_name='conversion_confirmed'").fetchone()['n']==1


def test_member_page_access_and_confirmation_rule_static():
    source=(Path(__file__).resolve().parents[1]/'templates'/'activate.html').read_text()
    assert 'ns.licenses_count==3' in source
    assert "c.status=='eligible'" in source
    assert "('created','renewed','unchanged')" in source
    assert 'Email verification proves control of the inbox' in source
