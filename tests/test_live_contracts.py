"""Published API shape checks: no external services or credentials needed."""
import asyncio,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config,PLANS,BUSINESS_ID,PRODUCT_ID
from clients import membership_entitlement,NinjaClient,IntegrationError

def test_whop_documented_membership_fields():
    m={'id':'mem_test','account':{'id':BUSINESS_ID},'user_id':'user_test',
       'product_id':PRODUCT_ID,'plan_id':next(iter(PLANS)), 'status':'active',
       'cancel_at_period_end':True,
       'current_period_end':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}
    assert membership_entitlement(m)['plan_id']==m['plan_id']
    m['status']='expired'
    assert membership_entitlement(m) is None

def test_ninja_documented_vendor_contract():
    nt=NinjaClient(Config())
    calls=[]
    async def fake_call(method,path,payload=None):
        calls.append((method,path,payload))
        if method=='GET':return {'2067':{'licenses':[]}}
        if method=='POST':return [90001]
        if method=='PATCH':return 90001
    nt.call=fake_call
    async def check():
        assert await nt.licenses(2067)==[]
        assert await nt.create(2067,'member@example.com','2027-01-01T00:00:00Z')==90001
        assert await nt.update(2067,90001,'member@example.com','2027-02-01T00:00:00Z')==90001
    asyncio.run(check())
    assert calls[0][:2]==('GET','/v1/licenses/vendor')
    assert calls[1][1]=='/v1/licenses/vendor' and calls[1][2]['productIds']==[2067]
    assert calls[2][1]=='/v1/licenses/vendor/90001'

def test_vendor_missing_product_fails_closed():
    nt=NinjaClient(Config())
    async def fake_call(*args,**kwargs): return {}
    nt.call=fake_call
    try:asyncio.run(nt.licenses(2067))
    except IntegrationError:pass
    else:raise AssertionError('Missing vendor product must fail closed')
