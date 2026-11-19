import sys, asyncio, secrets, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from store import connect
from security import hash_token
import app as web
import diagnostics


def test_diagnostics_requires_oauth_admin(tmp_path,monkeypatch):
    monkeypatch.setattr(web.cfg,'db',str(tmp_path/'diag.sqlite'))
    monkeypatch.setattr(web.cfg,'database_url','')
    monkeypatch.setattr(web.cfg,'require_database_url',False)
    monkeypatch.setattr(web.cfg,'admin_test_enabled',True)
    monkeypatch.setattr(web.cfg,'admin_test_email','owner@example.com')
    monkeypatch.setattr(web.cfg,'admin_test_user_id','')
    with TestClient(web.app) as client:
        assert client.get('/admin-test/diagnostics').status_code==403
        token=secrets.token_urlsafe(36)
        with connect(web.cfg) as db:
            db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',
                (hash_token(token),'user_owner','owner@example.com',int(time.time())+300))
        client.cookies.set('sut_admin_preview',token)
        async def fake(cfg):return {'release':'v7.3','mode':'READ_ONLY'}
        monkeypatch.setattr(web,'run_checks',fake)
        response=client.get('/admin-test/diagnostics')
        assert response.status_code==200
        assert response.json()['mode']=='READ_ONLY'
        assert response.headers.get('cache-control')=='no-store'


def test_read_only_aggregation(monkeypatch):
    class C:database_url='postgres://example';license_writes=False;whop_webhook_secret='a'
    async def whop(cfg):return {'status':'pass'}
    async def ninja(cfg):return {'status':'pass'}
    monkeypatch.setattr(diagnostics,'check_postgres',lambda cfg:{'status':'pass'})
    monkeypatch.setattr(diagnostics,'check_whop',whop)
    monkeypatch.setattr(diagnostics,'check_ninja',ninja)
    result=asyncio.run(diagnostics.run_checks(C()))
    assert result['mode']=='READ_ONLY'
    assert result['database']['status']=='pass'
    assert result['webhook']['status']=='configured'


def test_missing_configs_do_not_connect(monkeypatch):
    class C:database_url='';whop_api_key='';nt_username='';nt_password='';nt_cid='';nt_sec=''
    assert diagnostics.check_postgres(C())['status']=='fail'
    assert asyncio.run(diagnostics.check_whop(C()))['status']=='fail'
    assert asyncio.run(diagnostics.check_ninja(C()))['status']=='fail'
