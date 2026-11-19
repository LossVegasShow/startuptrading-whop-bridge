import asyncio, datetime as dt, sys
from pathlib import Path
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clients import WhopClient, IntegrationError, membership_entitlement
from config import Config, BUSINESS_ID, PRODUCT_ID, PLANS

MID='mem_cBxTHc4Aun0q90'; UID='user_ibzJP8GE1TE32'

def membership(uid=UID,mid=MID, plan=None):
    return {'id':mid,'user_id':uid,'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,
            'variant_id':plan or next(iter(PLANS)), 'status':'active',
            'current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=8)).isoformat()}

def mock_client(handler):
    real=httpx.AsyncClient
    return lambda **kwargs: real(transport=httpx.MockTransport(handler),**kwargs)

def run(handler,mid=MID,uid=UID):
    cfg=Config(whop_api_key='test-key')
    with patch('clients.httpx.AsyncClient',side_effect=mock_client(handler)):
        return asyncio.run(WhopClient(cfg).find_subscription_for_user(mid,uid))

def test_unfiltered_list_resolves_member_when_user_filter_is_unreliable():
    def handler(req):
        assert 'user_id' not in req.url.params
        assert req.url.params.get('account_id')==BUSINESS_ID
        return httpx.Response(200,json={'data':[membership()], 'page_info':{'has_next_page':False}})
    got=run(handler)
    assert got['id']==MID and membership_entitlement(got)

def test_pagination_and_strict_matching():
    def handler(req):
        if not req.url.params.get('after'):
            return httpx.Response(200,json={'data':[membership('user_other')], 'page_info':{'has_next_page':True,'end_cursor':'abc'}})
        assert req.url.params.get('after')=='abc'
        return httpx.Response(200,json={'data':[membership()], 'page_info':{'has_next_page':False}})
    assert run(handler)['user_id']==UID

def test_wrong_user_cannot_match():
    def handler(req):return httpx.Response(200,json={'data':[membership('user_wrong')], 'page_info':{'has_next_page':False}})
    assert run(handler) is None

def test_incomplete_pagination_fails_closed():
    def handler(req):return httpx.Response(200,json={'data':[], 'page_info':{'has_next_page':True}})
    try:run(handler)
    except IntegrationError as exc:assert 'pagination' in str(exc)
    else:raise AssertionError('Should reject incomplete list')
