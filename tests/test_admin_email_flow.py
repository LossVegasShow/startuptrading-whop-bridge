import secrets,time
from fastapi.testclient import TestClient
from store import connect
from security import hash_token
import app as web

def test_restricted_email_flow(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'email.db'))
    monkeypatch.setattr(web.cfg,'database_url','')
    monkeypatch.setattr(web.cfg,'require_database_url',False)
    monkeypatch.setattr(web.cfg,'admin_test_enabled',True)
    monkeypatch.setattr(web.cfg,'admin_test_email','operator@example.com')
    monkeypatch.setattr(web.cfg,'admin_test_user_id','')
    monkeypatch.setattr(web.cfg,'resend_api_key','re_example')
    monkeypatch.setattr(web.cfg,'resend_from','onboarding@resend.dev')
    monkeypatch.setattr(web.cfg,'whop_client_secret','sample-private-signing-key')
    delivered={}
    monkeypatch.setattr(web,'deliver_code',lambda email,code:delivered.update(email=email,code=code))
    token=secrets.token_urlsafe(36)
    with TestClient(web.app) as c:
        assert c.post('/admin-test/email/send',data={'csrf_token':'bad'}).status_code==403
        with connect(web.cfg) as db:
            db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',(hash_token(token),'user_verified','operator@example.com',int(time.time())+3600))
        c.cookies.set('sut_admin_preview',token)
        csrf=web.csrf(token)
        assert c.post('/admin-test/email/send',data={'csrf_token':csrf},follow_redirects=False).status_code==303
        assert delivered['email']=='operator@example.com'
        assert c.post('/admin-test/email/send',data={'csrf_token':csrf}).status_code==429
        assert c.post('/admin-test/email/verify',data={'csrf_token':csrf,'code':'000000'},follow_redirects=False).status_code==400 or delivered['code']=='000000'
        assert c.post('/admin-test/email/verify',data={'csrf_token':csrf,'code':delivered['code']},follow_redirects=False).status_code==303
        with connect(web.cfg) as db:
            row=db.execute('SELECT verified_at,code_hash FROM admin_email_tests WHERE whop_user_id=?',('user_verified',)).fetchone()
            assert row['verified_at'] and row['code_hash'] is None
            assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==0

def test_email_requires_server_configuration(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'disabled.db'))
    monkeypatch.setattr(web.cfg,'database_url','')
    monkeypatch.setattr(web.cfg,'require_database_url',False)
    monkeypatch.setattr(web.cfg,'admin_test_enabled',True)
    monkeypatch.setattr(web.cfg,'admin_test_email','operator@example.com')
    monkeypatch.setattr(web.cfg,'admin_test_user_id','')
    monkeypatch.setattr(web.cfg,'resend_api_key','')
    token=secrets.token_urlsafe(36)
    with TestClient(web.app) as c:
        with connect(web.cfg) as db:
            db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',(hash_token(token),'user_verified','operator@example.com',int(time.time())+3600))
        c.cookies.set('sut_admin_preview',token)
        assert c.post('/admin-test/email/send',data={'csrf_token':web.csrf(token)}).status_code==503
