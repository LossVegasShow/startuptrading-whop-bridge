import base64,hashlib,hmac,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config,PRODUCT_ID,PLANS,BUSINESS_ID,INDICATORS
from clients import membership_entitlement
from security import verify_webhook,hash_token
from store import connect,audit
from engine import Engine
from datetime import datetime,timedelta,timezone


def make_member(status='active',product=PRODUCT_ID,plan=list(PLANS)[0],future=True):
    end=(datetime.now(timezone.utc)+(timedelta(days=5) if future else -timedelta(days=1))).isoformat().replace('+00:00','Z')
    return {'id':'mem_test','account':{'id':BUSINESS_ID},'user_id':'user_test','product_id':product,
            'plan_id':plan,'status':status,'current_period_end':end,'expires_at':None}

def test_eligible_monthly_and_annual():
    for plan in PLANS:
        ent=membership_entitlement(make_member(plan=plan))
        assert ent and ent['plan_id']==plan

def test_scheduled_cancel_retains_access():
    m=make_member(status='active');m['cancel_at_period_end']=True
    assert membership_entitlement(m)

def test_bad_status_or_product_fails_closed():
    assert not membership_entitlement(make_member(status='expired'))
    assert not membership_entitlement(make_member(status='past_due'))
    assert not membership_entitlement(make_member(product='prod_unrelated'))
    assert not membership_entitlement(make_member(plan='plan_unrelated'))
    assert not membership_entitlement(make_member(future=False))

def test_missing_period_fails_closed():
    m=make_member();m['current_period_end']=None
    assert membership_entitlement(m) is None

def test_signature_verification():
    secret='ws_example';raw=b'{"type":"membership.activated"}';ts=str(int(time.time()));mid='evt_example'
    value=base64.b64encode(hmac.new(secret.encode(),f'{mid}.{ts}.'.encode()+raw,hashlib.sha256).digest()).decode()
    heads={'webhook-id':mid,'webhook-timestamp':ts,'webhook-signature':'v1,'+value}
    assert verify_webhook(heads,raw,secret)
    assert not verify_webhook(heads,raw+b'changed',secret)
    assert not verify_webhook(heads,raw,'incorrect')
    assert not verify_webhook({**heads,'webhook-timestamp':str(int(ts)-400)},raw,secret)

def test_store_persists(tmp_path):
    cfg=Config(db=str(tmp_path/'test.sqlite3'))
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,buyer_email,updated_at) VALUES(?,?,?)',('mem_test','buyer@example.com',int(time.time())))
        audit(db,1,'test','safe')
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==1
        assert db.execute('SELECT action FROM audit').fetchone()[0]=='test'

def test_license_writes_require_both_allowlist_matches():
    cfg=Config(license_writes=True,allowed_test_email='test@example.com',allowed_test_membership='mem_test')
    eng=Engine(cfg)
    assert eng.allowed({'nt_email':'test@example.com','membership_id':'mem_test','verified':1})
    assert not eng.allowed({'nt_email':'other@example.com','membership_id':'mem_test'})
    assert not eng.allowed({'nt_email':'test@example.com','membership_id':'mem_other'})
    cfg.license_writes=False
    assert not Engine(cfg).allowed({'nt_email':'test@example.com','membership_id':'mem_test'})

def test_correct_ninja_products():
    assert set(INDICATORS)=={2067,2071,2205}

def test_hashed_tokens():
    assert hash_token('private-link')==hashlib.sha256(b'private-link').hexdigest()
    assert hash_token('private-link')!=hash_token('another')

def test_web_ui_and_security(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import app as web
    web.cfg.db=str(tmp_path/'web.sqlite')
    web.cfg.admin_password='a-very-long-test-password'
    web.cfg.whop_client_id='';web.cfg.whop_client_secret=''
    with TestClient(web.app) as client:
        assert client.get('/health').status_code==200
        assert client.get('/').status_code==200
        assert b'Activate' in client.get('/').content  # V2: member access separated from sales
        assert client.get('/admin').status_code==401
        assert client.post('/webhooks/whop',json={'type':'membership.activated'}).status_code==503
        assert client.get('/oauth/login').status_code==503
        assert client.get('/onboarding').status_code==403

def test_engine_reconciles_one_allowlisted_test_account(tmp_path):
    import asyncio
    from store import customer
    class FakeWhop:
        async def membership(self,mid): return make_member()
    class FakeNT:
        def __init__(self):self.created=[];self.updated=[]
        async def licenses(self,pid):return []
        async def create(self,pid,email,end):
            self.created.append((pid,email,end));return pid+100000
        async def update(self,*args):self.updated.append(args);return 1
    cfg=Config(db=str(tmp_path/'integration.sqlite3'),license_writes=True,
               allowed_test_email='test@example.com',allowed_test_membership='mem_test',
                   nt_username='test',nt_password='test',nt_cid='test',nt_sec='test')
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,nt_email,verified,status,updated_at) VALUES(?,?,?,?,?,?,?)',
                   ('mem_test','user_test','buyer@example.com','test@example.com',1,'verified',int(time.time())))
    e=Engine(cfg);e.whop=FakeWhop();e.nt=FakeNT()
    result=asyncio.run(e.reconcile(1))
    assert result['status']=='eligible' and len(e.nt.created)==3
    assert {x[0] for x in e.nt.created}==set(INDICATORS)
    with connect(cfg) as db:
        assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==3
