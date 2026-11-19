import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from member_lookup import resolve_member

MEMBER='mber_1b6K65ghZrnuv'
USER='user_ibzJP8GE1TE32'

def test_lookup_strict_identifiers():
    cfg=SimpleNamespace(whop_api_key='fake',whop_api_version='2026-10-01')
    try: asyncio.run(resolve_member(cfg,'mem_this_is_a_subscription'))
    except ValueError: pass
    else: raise AssertionError('mber_ required')

def test_lookup_filters_and_checks_membership(monkeypatch):
    from config import BUSINESS_ID, PRODUCT_ID, PLANS
    import datetime as dt
    end=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=12)).isoformat()
    rows=[{'id':'mem_correct','member_id':MEMBER,'user_id':USER,'account_id':BUSINESS_ID,
           'product_id':PRODUCT_ID,'plan_id':next(iter(PLANS)),'status':'active',
           'current_period_end':end},
          {'id':'mem_other','member_id':'mber_other','account_id':BUSINESS_ID,'product_id':PRODUCT_ID}]
    class Response:
        status_code=200
        def json(self):return {'data':rows,'page_info':{'has_next_page':False}}
    class Client:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,*args,**kw):
            assert kw['params']['member_id']==MEMBER
            return Response()
    monkeypatch.setattr('member_lookup.httpx.AsyncClient',Client)
    cfg=SimpleNamespace(whop_api_key='fake',whop_api_version='2026-10-01')
    result=asyncio.run(resolve_member(cfg,MEMBER,USER))
    assert len(result)==1 and result[0]['membership_id']=='mem_correct'
    assert result[0]['eligible_now'] and result[0]['user_matches_expected']
