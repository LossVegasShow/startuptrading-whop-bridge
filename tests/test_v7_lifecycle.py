import asyncio, sys, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config,PRODUCT_ID, PLANS, BUSINESS_ID, INDICATORS
from store import connect
from engine import Engine
from clients import IntegrationError

class FakeWhop:
    def __init__(self):self.status='active';self.period=10
    async def membership(self,mid):
        return {'id':mid,'account':{'id':BUSINESS_ID},'user_id':'user_test','product_id':PRODUCT_ID,
                'variant_id':next(iter(PLANS)),'status':self.status,
                'current_period_end':(datetime.now(timezone.utc)+timedelta(days=self.period)).isoformat()}
class FakeNinja:
    def __init__(self):self.data={pid:[] for pid in INDICATORS};self.created=[];self.updated=[]
    async def licenses(self,pid):return [dict(x) for x in self.data[pid]]
    async def create(self,pid,email,end):
        lid=pid+10000;self.data[pid].append({'id':lid,'email':email,'expirationDateUTC':end});self.created.append(pid);return lid
    async def update(self,pid,lid,email,end):
        row=next(r for r in self.data[pid] if r['id']==lid);row['expirationDateUTC']=end
        self.updated.append((pid,end));return lid

def setup(tmp_path):
    cfg=Config(db=str(tmp_path/'test.db'),license_writes=True,allowed_test_email='test@example.com',
               allowed_test_membership='mem_test',nt_username='user',nt_password='pass',nt_cid='c',nt_sec='s')
    with connect(cfg) as db:
        db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,nt_email,verified,status,updated_at) VALUES(?,?,?,?,?,?,?)',
                   ('mem_test','user_test','buyer@example.com','test@example.com',1,'pending',int(time.time())))
    engine=Engine(cfg);engine.whop=FakeWhop();engine.nt=FakeNinja()
    return engine,cfg

def test_full_lifecycle(tmp_path):
    e,cfg=setup(tmp_path)
    first=asyncio.run(e.reconcile(1));assert first['writes']==3;assert len(e.nt.created)==3
    second=asyncio.run(e.reconcile(1));assert second['writes']==0;assert len(e.nt.created)==3
    e.whop.period=30;third=asyncio.run(e.reconcile(1));assert third['writes']==3;assert len(e.nt.updated)==3
    e.whop.status='canceling';e.whop.period=30
    assert asyncio.run(e.reconcile(1))['writes']==0 # cancel at period end retains access
    e.whop.status='expired';out=asyncio.run(e.reconcile(1))
    assert out['status']=='ineligible' and out['writes']==3
    assert all(r['expirationDateUTC']<datetime.now(timezone.utc).isoformat() for rows in e.nt.data.values() for r in rows)
    assert asyncio.run(e.reconcile(1))['writes']==0
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==3

def test_do_not_touch_preexisting_license(tmp_path):
    e,cfg=setup(tmp_path)
    # Still active but ending before the membership: never modified (an already-expired
    # license is adopted instead; see tests/test_owned_separately.py).
    e.nt.data[2067].append({'id':222,'email':'test@example.com','expirationDateUTC':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    try:asyncio.run(e.reconcile(1));assert False,'expected incomplete sync'
    except IntegrationError:pass
    assert len(e.nt.created)==2
    assert not any(p==2067 for p,_ in e.nt.updated)
    with connect(cfg) as db:assert db.execute('SELECT * FROM licenses WHERE product_id=2067').fetchone() is None

def test_allowlist_and_unverified_block_writes(tmp_path):
    e,cfg=setup(tmp_path)
    with connect(cfg) as db:db.execute('UPDATE customers SET verified=0 WHERE id=1')
    assert asyncio.run(e.reconcile(1))['writes']==0
    cfg.allowed_test_membership='mem_wrong'
    with connect(cfg) as db:db.execute('UPDATE customers SET verified=1 WHERE id=1')
    assert asyncio.run(e.reconcile(1))['writes']==0
    assert not e.nt.created

def test_identity_conflict_blocks_changes(tmp_path):
    e,cfg=setup(tmp_path)
    orig=e.whop.membership
    async def wrong(mid):
        m=await orig(mid);m['user_id']='user_other';return m
    e.whop.membership=wrong
    try:asyncio.run(e.reconcile(1));assert False
    except IntegrationError:pass
    assert not e.nt.created

def test_lease_guards_parallel_processing(tmp_path):
    e,cfg=setup(tmp_path)
    assert e.acquire(1,'first')
    assert not e.acquire(1,'second')
    e.release(1,'first')
    assert e.acquire(1,'second')
    e.release(1,'second')
