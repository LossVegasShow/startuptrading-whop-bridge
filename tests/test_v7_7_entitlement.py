import asyncio
import datetime as dt
from types import SimpleNamespace
from clients import membership_plan_id, membership_entitlement
from config import BUSINESS_ID, PRODUCT_ID, PLANS
from member_lookup import resolve_member

PLAN=next(iter(PLANS))
BASE={'id':'mem_example123','member_id':'mber_example123','user_id':'user_example123',
      'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,'status':'active',
      'current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=7)).isoformat()}

def test_nested_plan_is_validated():
    record={**BASE,'plan':{'id':PLAN}}
    assert membership_plan_id(record)==PLAN
    assert membership_entitlement(record)['plan_id']==PLAN

def test_missing_or_unapproved_plan_never_activates():
    assert membership_entitlement(BASE) is None
    assert membership_entitlement({**BASE,'plan':{'id':'plan_other'}}) is None

def test_conflicting_plan_fails_closed():
    record={**BASE,'plan_id':PLAN,'plan':{'id':'plan_other'}}
    assert membership_entitlement(record) is None


def test_lookup_gets_detail_when_list_omits_plan(monkeypatch):
    class Response:
        status_code=200
        def __init__(self,body):self.body=body
        def json(self):return self.body
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,**kwargs):
            if url.endswith('/memberships'):
                return Response({'data':[BASE], 'page_info':{'has_next_page':False}})
            assert url.endswith('/'+BASE['id'])
            return Response({'data':{**BASE,'plan':{'id':PLAN}}})
    monkeypatch.setattr('member_lookup.httpx.AsyncClient',Client)
    result=asyncio.run(resolve_member(SimpleNamespace(whop_api_key='fake',whop_api_version='2026-11-17'),BASE['member_id'],BASE['user_id']))
    assert result[0]['eligible_now'] is True
    assert result[0]['plan_id']==PLAN
    assert result[0]['plan_source']=='membership_detail'
    assert result[0]['eligibility_reason']=='eligible'
