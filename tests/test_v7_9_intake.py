import asyncio,datetime as dt,sys,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config,BUSINESS_ID,PRODUCT_ID,PLANS
from store import connect
from security import hash_token
import app

MEM='mem_verified_intake'
USER='user_verified_intake'

class Whop:
    def __init__(self,m):self.m=m
    async def membership(self,id):return self.m
    async def memberships_for_user(self,userid):return [self.m] if userid==self.m.get("user_id") else []
    async def user(self,id):return {'email':'whopbuyer@example.org'}
    async def resolve_membership(self,m):return m

def setup(tmp_path,monkeypatch):
    cfg=Config(database_url='',require_database_url=False,db=str(tmp_path/'intake.sqlite'),license_writes=False,admin_test_enabled=True,admin_test_user_id=USER)
    monkeypatch.setattr(app,'cfg',cfg)
    monkeypatch.setattr(app.engine,'whop',Whop({'id':MEM,'user_id':USER,'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,'variant_id':next(iter(PLANS)),'status':'active','current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=10)).isoformat()}))
    token='a'*40
    with connect(cfg) as db:
        db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',(hash_token(token),USER,None,int(time.time())+3600))
    client=TestClient(app.app)
    client.cookies.set('sut_admin_preview',token)
    return client,cfg

def test_intake_creates_exactly_one_customer_and_zero_licenses(tmp_path,monkeypatch):
    client,cfg=setup(tmp_path,monkeypatch)
    form=client.get('/admin-test/intake',params={'membership_id':MEM,'expected_user_id':USER})
    assert form.status_code==200 and MEM in form.text
    params={'membership_id':MEM,'expected_user_id':USER,'csrf_token':app.csrf('a'*40)}
    first=client.post('/admin-test/intake',data=params)
    assert first.status_code==200,first.text
    assert first.json()['result']=='created'
    assert first.json()['customer_record_exists'] is True
    assert first.json()['license_rows']==0
    assert first.json()['crm_outbox_status']=='pending'
    again=client.post('/admin-test/intake',data=params)
    assert again.status_code==200 and again.json()['result']=='updated'
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM message_outbox').fetchone()[0]==0

def test_wrong_whop_user_fails_without_data_mutation(tmp_path,monkeypatch):
    client,cfg=setup(tmp_path,monkeypatch)
    r=client.post('/admin-test/intake',data={'membership_id':MEM,'expected_user_id':'user_wrong','csrf_token':app.csrf('a'*40)})
    assert r.status_code==409
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==0

def test_writes_enabled_prohibits_intake_test(tmp_path,monkeypatch):
    client,cfg=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(cfg,'license_writes',True)
    r=client.post('/admin-test/intake',data={'membership_id':MEM,'expected_user_id':USER,'csrf_token':app.csrf('a'*40)})
    assert r.status_code==409

def test_intake_requires_auth_and_csrf(tmp_path,monkeypatch):
    client,cfg=setup(tmp_path,monkeypatch)
    r=client.post('/admin-test/intake',data={'membership_id':MEM,'expected_user_id':USER,'csrf_token':'wrong'})
    assert r.status_code==403
    client.cookies.clear()
    r=client.get('/admin-test/intake')
    assert r.status_code==403
