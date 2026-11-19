import pytest
import httpx
from unittest.mock import patch
from clients import WhopClient, IntegrationError
from config import Config, BUSINESS_ID,PRODUCT_ID

def member(mid,uid):
    return {'id':mid,'user_id':uid,'member_id':'mber_abc','account_id':BUSINESS_ID,
            'product_id':PRODUCT_ID,'variant_id':'plan_qSXeS0xoDapGU',
            'status':'active','current_period_end':'2099-12-02T14:41:58Z'}

@pytest.mark.asyncio
async def test_single_source_user_and_membership():
    called=[]
    def route(req):
        called.append(str(req.url))
        assert 'user_id=' not in str(req.url)
        if 'after=next' in str(req.url):
            return httpx.Response(200,json={'data':[member('mem_b','user_b')],'page_info':{'has_next_page':False}})
        return httpx.Response(200,json={'data':[member('mem_a','user_a')], 'page_info':{'has_next_page':True,'end_cursor':'next'}})
    actual=httpx.AsyncClient
    def fake(*a,**kw):return actual(*a,transport=httpx.MockTransport(route),**kw)
    with patch('clients.httpx.AsyncClient',fake):
        client=WhopClient(Config(whop_api_key='test'))
        user=await client.memberships_for_user('user_b')
        detail=await client.membership('mem_b')
    assert len(user)==1 and user[0]['id']=='mem_b'
    assert detail['user_id']=='user_b'
    assert len(called)==4

@pytest.mark.asyncio
async def test_incomplete_pagination_blocks_entitlement():
    def route(req):return httpx.Response(200,json={'data':[], 'page_info':{'has_next_page':True}})
    actual=httpx.AsyncClient
    with patch('clients.httpx.AsyncClient',lambda *a,**kw:actual(*a,transport=httpx.MockTransport(route),**kw)):
        with pytest.raises(IntegrationError,match='pagination'):
            await WhopClient(Config(whop_api_key='test')).memberships_for_user('user_test')

@pytest.mark.asyncio
async def test_owner_mismatch_fails_closed():
    def route(req):return httpx.Response(200,json={'data':[member('mem_a','user_a')], 'page_info':{'has_next_page':False}})
    actual=httpx.AsyncClient
    with patch('clients.httpx.AsyncClient',lambda *a,**kw:actual(*a,transport=httpx.MockTransport(route),**kw)):
        with pytest.raises(IntegrationError,match='owner mismatch'):
            await WhopClient(Config(whop_api_key='test')).authoritative_membership('mem_a','user_b')
