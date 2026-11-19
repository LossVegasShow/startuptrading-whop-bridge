import asyncio, datetime as dt, sys, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from config import Config, BUSINESS_ID, PRODUCT_ID, PLANS
from security import hash_token
from store import connect

MID='mem_real_list_only'; USER='user_real_list_only'

def member(uid=USER, plan=None):
    return {'id':MID,'user_id':uid,'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,
            'variant_id':plan or next(iter(PLANS)),'status':'active',
            'current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=7)).isoformat()}

class ListOnlyWhop:
    async def memberships_for_user(self,uid):
        return [member()] if uid==USER else []
    async def membership(self,mid):
        raise AssertionError('Direct membership endpoint must not be called in admin intake')
    async def user(self,uid):return {'email':'confirmed-buyer@example.org'}


def setup(tmp_path,monkeypatch):
    cfg=Config(database_url='',require_database_url=False,db=str(tmp_path/'test.sqlite'),license_writes=False,
               admin_test_enabled=True,admin_test_user_id=USER)
    monkeypatch.setattr(app,'cfg',cfg)
    monkeypatch.setattr(app.engine,'whop',ListOnlyWhop())
    token='z'*40
    with connect(cfg) as db:
        db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',
                   (hash_token(token),USER,None,int(time.time())+3600))
    client=TestClient(app.app);client.cookies.set('sut_admin_preview',token)
    return client,cfg,{'csrf_token':app.csrf(token),'membership_id':MID,'expected_user_id':USER}

def test_list_record_used_when_detail_unavailable(tmp_path,monkeypatch):
    client,cfg,data=setup(tmp_path,monkeypatch)
    r=client.post('/admin-test/intake',data=data)
    assert r.status_code==200,r.text
    assert r.json()['customer_record_exists'] is True
    assert r.json()['license_rows']==0
    r2=client.post('/admin-test/intake',data=data)
    assert r2.json()['result']=='updated'
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==1

def test_user_mismatch_fails_without_write(tmp_path,monkeypatch):
    client,cfg,data=setup(tmp_path,monkeypatch);data['expected_user_id']='user_someone_else'
    r=client.post('/admin-test/intake',data=data)
    assert r.status_code==409
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==0

def test_ineligible_plan_fails_without_write(tmp_path,monkeypatch):
    client,cfg,data=setup(tmp_path,monkeypatch)
    class WrongPlan(ListOnlyWhop):
        async def memberships_for_user(self,uid):return [member(plan='plan_wrong')]
    monkeypatch.setattr(app.engine,'whop',WrongPlan())
    r=client.post('/admin-test/intake',data=data)
    assert r.status_code==409
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==0
