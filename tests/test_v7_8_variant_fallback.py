import asyncio,datetime as dt
from types import SimpleNamespace
import pytest
from config import PLANS,BUSINESS_ID,PRODUCT_ID
from clients import membership_plan_id, membership_entitlement, membership_plan_conflict, WhopClient, IntegrationError
from member_lookup import resolve_member

PLAN=next(iter(PLANS))
BASE={'id':'mem_test','member_id':'mber_test','user_id':'user_test','account_id':BUSINESS_ID,'product_id':PRODUCT_ID,
 'status':'active','current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=10)).isoformat()}

class Response:
    status_code=200
    def __init__(self,body,status=200):self.body=body;self.status_code=status
    def json(self):return self.body

class FakeHTTP:
    calls=[]
    def __init__(self,**kw):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass
    async def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url.endswith('/memberships'):return Response({'data':[dict(BASE)],'page_info':{'has_next_page':False}})
        if url.endswith('/'+BASE['id']):return Response(dict(BASE))
        if url.endswith('/payments'):
            return Response({'data':[{'status':'paid','membership_id':BASE['id'],'account_id':BUSINESS_ID,'user_id':BASE['user_id'],
                    'line_items':[{'product_id':PRODUCT_ID,'variant_id':PLAN}]}], 'page_info':{'has_next_page':False}})
        raise AssertionError(url)

CFG=SimpleNamespace(whop_api_key='test',whop_api_version='2026-11-17-3')

def test_documented_variant_id_resolves():
    m={**BASE,'variant_id':PLAN}
    assert membership_plan_id(m)==PLAN
    assert membership_entitlement(m)['plan_id']==PLAN

def test_conflicting_variant_id_fail_closed():
    m={**BASE,'variant_id':PLAN,'plan_id':'plan_bad'}
    assert membership_plan_conflict(m)
    assert membership_entitlement(m) is None

def test_readonly_lookup_payment_fallback(monkeypatch):
    FakeHTTP.calls=[]
    monkeypatch.setattr('member_lookup.httpx.AsyncClient',FakeHTTP)
    monkeypatch.setattr('clients.httpx.AsyncClient',FakeHTTP)
    result=asyncio.run(resolve_member(CFG,BASE['member_id'],BASE['user_id']))
    assert result[0]['eligible_now'] and result[0]['plan_source']=='verified_payment'
    assert any(url.endswith('/payments') for url,_ in FakeHTTP.calls)

def test_payment_wrong_customer_rejected(monkeypatch):
    class Wrong(FakeHTTP):
        async def get(self,url,**kw):
            r=await super().get(url,**kw)
            if url.endswith('/payments'):r.body['data'][0]['user_id']='user_other'
            return r
    monkeypatch.setattr('clients.httpx.AsyncClient',Wrong)
    assert asyncio.run(WhopClient(CFG).payment_plan_for_membership(BASE)) is None

def test_payment_unapproved_variant_rejected(monkeypatch):
    class Wrong(FakeHTTP):
        async def get(self,url,**kw):
            r=await super().get(url,**kw)
            if url.endswith('/payments'):r.body['data'][0]['line_items'][0]['variant_id']='plan_unknown'
            return r
    monkeypatch.setattr('clients.httpx.AsyncClient',Wrong)
    assert asyncio.run(WhopClient(CFG).payment_plan_for_membership(BASE)) is None

def test_payment_conflict_requires_review(monkeypatch):
    class Conflict(FakeHTTP):
        async def get(self,url,**kw):
            r=await super().get(url,**kw)
            if url.endswith('/payments'):
                row=r.body['data'][0]
                r.body['data']=[row,{**row,'line_items':[{'product_id':PRODUCT_ID,'variant_id':list(PLANS)[1]}]}]
            return r
    monkeypatch.setattr('clients.httpx.AsyncClient',Conflict)
    with pytest.raises(IntegrationError,match='Conflicting'):
        asyncio.run(WhopClient(CFG).payment_plan_for_membership(BASE))
