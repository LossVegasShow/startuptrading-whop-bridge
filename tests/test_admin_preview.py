import sys,time,secrets
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from store import connect
from security import hash_token
import app as web

def test_preview_disabled_by_default(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'disabled.sqlite'))
    monkeypatch.setattr(web.cfg,'admin_test_enabled',False)
    monkeypatch.setattr(web.cfg,'admin_test_email','admin@example.com')
    monkeypatch.setattr(web.cfg,'admin_test_user_id','')
    with TestClient(web.app) as c:
        assert c.get('/admin-test/login').status_code==404
        assert c.get('/admin-test').status_code==404
        assert c.get('/').status_code==200
        assert b'Authorized admin preview' not in c.get('/').content

def test_admin_preview_requires_session_and_verified_exact_email(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'enabled.sqlite'))
    monkeypatch.setattr(web.cfg,'admin_test_enabled',True)
    monkeypatch.setattr(web.cfg,'admin_test_email','owner@example.com')
    monkeypatch.setattr(web.cfg,'admin_test_user_id','')
    monkeypatch.setattr(web.cfg,'allowed_test_email','nttest@example.com')
    assert web.preview_identity_matches('user_somebody','owner@example.com',True)
    assert not web.preview_identity_matches('user_somebody','owner@example.com',False)
    assert not web.preview_identity_matches('user_somebody','different@example.com',True)
    with TestClient(web.app) as c:
        assert c.get('/admin-test').status_code==403
        assert c.get('/').status_code==200
        assert b'Authorized admin preview' in c.get('/').content
        token=secrets.token_urlsafe(36)
        with connect(web.cfg) as db:
            db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',
                    (hash_token(token),'user_owner','owner@example.com',int(time.time())+3600))
        c.cookies.set('sut_admin_preview',token)
        r=c.get('/admin-test')
        assert r.status_code==200 and b'NO LIVE LICENSING' in r.content
        csrf=web.csrf(token)
        assert c.post('/admin-test/preview',data={'csrf_token':'wrong','path':'existing'}).status_code==403
        assert c.post('/admin-test/preview',data={'csrf_token':csrf,'path':'existing','nt_email':'other@example.com'}).status_code==403
        for path in ['existing','new']:
            r=c.post('/admin-test/preview',data={'csrf_token':csrf,'path':path,'nt_email':'nttest@example.com'})
            assert r.status_code==200
            assert b'no license was issued' in r.content
        with connect(web.cfg) as db:
            assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==0
            assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==0
        assert c.post('/admin-test/logout',data={'csrf_token':csrf},follow_redirects=False).status_code==303
        assert c.get('/admin-test').status_code==403
