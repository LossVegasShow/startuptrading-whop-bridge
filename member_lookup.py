"""Admin-only read-only membership resolution. Never changes customer or license data."""
import httpx
from config import BUSINESS_ID, PRODUCT_ID
from clients import membership_entitlement, IntegrationError

async def resolve_member(cfg, member_id, expected_user_id=''):
    if not member_id.startswith('mber_') or len(member_id)>100:
        raise ValueError('Use a Whop Member ID beginning mber_')
    if expected_user_id and (not expected_user_id.startswith('user_') or len(expected_user_id)>100):
        raise ValueError('Expected user ID must begin user_')
    if not cfg.whop_api_key:
        raise IntegrationError('Whop API key not configured')
    found=[]
    after=None
    async with httpx.AsyncClient(timeout=18) as client:
        for _ in range(10):
            params={'account_id': BUSINESS_ID, 'member_id': member_id, 'first':100}
            if after: params['after']=after
            response=await client.get('https://api.whop.com/api/v1/memberships',
                params=params,headers={'Authorization':'Bearer '+cfg.whop_api_key,
                                        'Api-Version-Date':cfg.whop_api_version})
            if response.status_code!=200:
                raise IntegrationError('Whop member membership lookup HTTP '+str(response.status_code))
            body=response.json()
            if not isinstance(body,dict) or not isinstance(body.get('data'),list):
                raise IntegrationError('Unexpected Whop membership list response')
            for item in body['data']:
                if not isinstance(item,dict): continue
                if item.get('member_id') != member_id: continue
                if (item.get('account_id') or (item.get('account') or {}).get('id')) != BUSINESS_ID: continue
                if (item.get('product_id') or (item.get('product') or {}).get('id')) != PRODUCT_ID: continue
                eligibility=membership_entitlement(item)
                found.append({'membership_id':item.get('id'),'status':item.get('status'),
                    'plan_id':item.get('plan_id'),'period_end':item.get('current_period_end'),
                    'eligible_now':bool(eligibility),
                    'user_matches_expected':(item.get('user_id')==expected_user_id) if expected_user_id else None})
            info=body.get('page_info') or {}
            if not info.get('has_next_page'): return found
            new_after=info.get('end_cursor')
            if not new_after or new_after==after: raise IntegrationError('Whop membership pagination cursor missing')
            after=new_after
    raise IntegrationError('Too many Whop membership pages; lookup incomplete')
