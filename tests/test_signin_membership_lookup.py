"""Member sign-in finds memberships without Whop's unreliable user_id filter.

In production `/memberships?user_id=...` returned no rows for a real, active
member, so the OAuth sign-in showed "We couldn't find an active membership".
memberships_for_user now pages the business/product list and matches locally.
"""
import asyncio, datetime as dt, sys
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clients import WhopClient, IntegrationError, membership_entitlement
from config import Config, BUSINESS_ID, PRODUCT_ID, PLANS

UID='user_bN8EFSrzs4Lqz'; MID='mem_T1AdJRcFkJNNSk'


def membership(uid=UID, mid=MID, **extra):
    m={'id':mid,'user_id':uid,'member_id':'mber_test','account_id':BUSINESS_ID,'product_id':PRODUCT_ID,
       'variant_id':next(iter(PLANS)),'status':'active',
       'current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=30)).isoformat()}
    m.update(extra)
    return m


def run(handler, uid=UID):
    real=httpx.AsyncClient
    factory=lambda **kw: real(transport=httpx.MockTransport(handler),**kw)
    with patch('clients.httpx.AsyncClient',side_effect=factory):
        return asyncio.run(WhopClient(Config(whop_api_key='test-key')).memberships_for_user(uid))


def test_does_not_rely_on_the_user_id_filter():
    seen=[]
    def handler(req):
        seen.append(req.url.params)
        # Simulate production: the user filter would return nothing.
        if 'user_id' in req.url.params:
            return httpx.Response(200,json={'data':[],'page_info':{'has_next_page':False}})
        return httpx.Response(200,json={'data':[membership('user_someone_else','mem_other'),membership()],
                                        'page_info':{'has_next_page':False}})
    got=run(handler)
    assert [m['id'] for m in got]==[MID]
    assert membership_entitlement(got[0])['membership_id']==MID
    assert all('user_id' not in p for p in seen)
    assert seen[0].get('account_id')==BUSINESS_ID and seen[0].get('product_id')==PRODUCT_ID


def test_pages_until_the_member_is_found():
    def handler(req):
        if not req.url.params.get('after'):
            return httpx.Response(200,json={'data':[membership('user_a','mem_a')],
                                            'page_info':{'has_next_page':True,'end_cursor':'c1'}})
        assert req.url.params['after']=='c1'
        return httpx.Response(200,json={'data':[membership()],'page_info':{'has_next_page':False}})
    assert [m['id'] for m in run(handler)]==[MID]


def test_other_users_memberships_are_never_returned():
    def handler(req):
        return httpx.Response(200,json={'data':[membership('user_a','mem_a'),membership('user_b','mem_b')],
                                        'page_info':{'has_next_page':False}})
    assert run(handler)==[]


def test_incomplete_pagination_fails_closed():
    def handler(req):
        return httpx.Response(200,json={'data':[membership()],'page_info':{'has_next_page':True}})
    with pytest.raises(IntegrationError,match='pagination'):
        run(handler)


def test_http_error_fails_closed():
    with pytest.raises(IntegrationError):
        run(lambda req: httpx.Response(500,json={}))


def test_plan_is_still_resolved_when_the_list_omits_it():
    def handler(req):
        if req.url.path.endswith('/memberships/'+MID):
            return httpx.Response(200,json=membership())
        rec=membership(); rec.pop('variant_id')
        return httpx.Response(200,json={'data':[rec],'page_info':{'has_next_page':False}})
    got=run(handler)
    assert got[0]['plan_id']==next(iter(PLANS)) and membership_entitlement(got[0])


def test_invalid_user_identity_is_rejected():
    with pytest.raises(IntegrationError):
        run(lambda req: httpx.Response(200,json={'data':[]}),uid='not-a-user')
