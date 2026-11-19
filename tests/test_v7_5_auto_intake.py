import sys,asyncio,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config,BUSINESS_ID,PRODUCT_ID
from store import connect
from purchaser_intake import import_membership,handle_queued_event
from clients import IntegrationError
import pytest

class Whop:
    def __init__(self,m, user=None):self.m=m;self.u=user if user is not None else {'email':'buyer@example.org'};self.lookups=0
    async def membership(self,mid):self.lookups+=1;return self.m
    async def user(self,uid):return self.u
class Engine:
    def __init__(self):self.calls=[]
    async def reconcile(self,cid):self.calls.append(cid)

@pytest.fixture
def fixture(tmp_path):
    cfg=Config(database_url='',require_database_url=False,db=str(tmp_path/'a.sqlite'))
    future=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=20)).isoformat().replace('+00:00','Z')
    m={'id':'mem_abc','user_id':'user_abc','account_id':BUSINESS_ID,'product_id':PRODUCT_ID,
       'plan_id':'plan_qSXeS0xoDapGU','status':'active','current_period_end':future}
    return cfg,m

def test_auto_import_before_oauth_and_crm_queued(fixture):
    cfg,m=fixture;whop=Whop(m)
    result=asyncio.run(import_membership(cfg,whop,'mem_abc'))
    assert result['state']=='created'
    with connect(cfg) as db:
        buyer=db.execute('SELECT * FROM customers').fetchone()
        assert buyer['whop_user_id']=='user_abc' and buyer['verified']==0 and buyer['buyer_email_verified']==0
        assert db.execute('SELECT status FROM crm_sync').fetchone()['status']=='pending'
        assert db.execute('SELECT COUNT(*) FROM licenses').fetchone()[0]==0
    assert asyncio.run(import_membership(cfg,whop,'mem_abc'))['state']=='updated'
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==1

def test_queued_event_processes_existing_and_new(fixture):
    cfg,m=fixture; whop=Whop(m);eng=Engine()
    ev={'object_id':'mem_abc'}
    assert asyncio.run(handle_queued_event(cfg,whop,eng,ev))=='processed'
    assert eng.calls==[1]
    assert asyncio.run(handle_queued_event(cfg,whop,eng,ev))=='processed'
    assert eng.calls==[1,1]

def test_payment_id_cannot_be_mapped_to_customer(fixture):
    cfg,m=fixture;whop=Whop(m);eng=Engine()
    assert asyncio.run(handle_queued_event(cfg,whop,eng,{'object_id':'pay_123'}))=='needs_mapping'
    assert whop.lookups==0 and not eng.calls

def test_wrong_product_never_imported(fixture):
    cfg,m=fixture;m['product_id']='prod_not_startuptrading';whop=Whop(m)
    assert asyncio.run(import_membership(cfg,whop,'mem_abc'))['state']=='ignored_other_product'
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==0

def test_missing_email_retries_instead_of_fake_contact(fixture):
    cfg,m=fixture;whop=Whop(m,user={})
    with pytest.raises(IntegrationError,match='buyer email unavailable'):
        asyncio.run(import_membership(cfg,whop,'mem_abc'))
    with connect(cfg) as db:assert db.execute('SELECT COUNT(*) FROM customers').fetchone()[0]==0

def test_canceled_does_not_generate_new_customer(fixture):
    cfg,m=fixture;m['status']='expired';whop=Whop(m)
    assert asyncio.run(import_membership(cfg,whop,'mem_abc'))['state']=='ignored_ineligible'

def test_membership_owner_change_never_overwrites(fixture):
    cfg,m=fixture;whop=Whop(m)
    asyncio.run(import_membership(cfg,whop,'mem_abc'))
    m['user_id']='user_attacker'
    with pytest.raises(IntegrationError,match='owner changed'):
        asyncio.run(import_membership(cfg,whop,'mem_abc'))

def test_no_trust_webhook_email(fixture):
    cfg,m=fixture;whop=Whop(m,{'email':'true@example.org'})
    asyncio.run(import_membership(cfg,whop,'mem_abc'))
    with connect(cfg) as db:assert db.execute('SELECT buyer_email FROM customers').fetchone()['buyer_email']=='true@example.org'
