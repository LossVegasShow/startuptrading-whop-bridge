import asyncio, datetime as dt, sys
from pathlib import Path
from unittest.mock import patch
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import Config,BUSINESS_ID,PRODUCT_ID,PLANS
from member_lookup import verified_subscription_by_member
from clients import IntegrationError

MID='mem_cBxTHc4Aun0q90'; MEMBER='mber_1b6K65ghZrnuv'; UID='user_ibzJP8GE1TE32'
def row(**kw):
    r={'id':MID,'member_id':MEMBER,'user_id':UID,'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,
       'variant_id':next(iter(PLANS)),'status':'active','current_period_end':(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=5)).isoformat()}
    r.update(kw);return r

def lookup(handler):
    real=httpx.AsyncClient
    with patch('member_lookup.httpx.AsyncClient',side_effect=lambda **kw: real(transport=httpx.MockTransport(handler),**kw)):
        return asyncio.run(verified_subscription_by_member(Config(whop_api_key='test'),MEMBER,MID,UID))

def test_uses_proven_member_id_filter_and_returns_full_verified_record():
    def handler(req):
        assert req.url.params.get('member_id')==MEMBER
        assert 'user_id' not in req.url.params
        return httpx.Response(200,json={'data':[row()],'page_info':{'has_next_page':False}})
    assert lookup(handler)['user_id']==UID

def test_reject_other_user_and_wrong_plan():
    for wrong in (row(user_id='user_other'),row(variant_id='plan_wrong')):
        assert lookup(lambda req:httpx.Response(200,json={'data':[wrong], 'page_info':{'has_next_page':False}})) is None

def test_paginates_until_exact_match():
    def handler(req):
        if not req.url.params.get('after'):
            return httpx.Response(200,json={'data':[row(id='mem_other')], 'page_info':{'has_next_page':True,'end_cursor':'next'}})
        return httpx.Response(200,json={'data':[row()], 'page_info':{'has_next_page':False}})
    assert lookup(handler)['id']==MID

def test_refuses_incomplete_pagination():
    try:lookup(lambda req:httpx.Response(200,json={'data':[],'page_info':{'has_next_page':True}}))
    except IntegrationError:pass
    else:raise AssertionError('Must refuse incomplete Whop list')
