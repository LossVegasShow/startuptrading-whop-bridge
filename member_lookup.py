"""Admin-only read-only membership resolution. Never changes customer or license data."""
import httpx
from config import BUSINESS_ID, PRODUCT_ID
from clients import membership_entitlement, membership_plan_id, normalize_membership, IntegrationError

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
                # Whop list results may omit plan_id. Resolve details using the
                # membership's authoritative mem_ ID before checking entitlement.
                list_plan=membership_plan_id(item)
                source='list'
                if not list_plan and isinstance(item.get('id'),str) and item['id'].startswith('mem_'):
                    detail_response=await client.get('https://api.whop.com/api/v1/memberships/'+item['id'],
                        headers={'Authorization':'Bearer '+cfg.whop_api_key,
                                 'Api-Version-Date':cfg.whop_api_version})
                    if detail_response.status_code!=200:
                        raise IntegrationError('Whop membership detail HTTP '+str(detail_response.status_code))
                    detail=detail_response.json()
                    detail=detail.get('data',detail) if isinstance(detail,dict) else detail
                    if not isinstance(detail,dict) or detail.get('id')!=item['id']:
                        raise IntegrationError('Whop membership detail identity mismatch')
                    for identity in ('user_id','account_id','member_id','product_id'):
                        if item.get(identity) and detail.get(identity) and item[identity]!=detail[identity]:
                            raise IntegrationError('Whop membership detail identity conflict')
                    item={**item,**{k:v for k,v in detail.items() if v is not None}}
                    source='detail'
                item=normalize_membership(item)
                eligibility=membership_entitlement(item)
                plan=membership_plan_id(item)
                account=item.get('account') or {}
                product=item.get('product') or {}
                acct_id=item.get('account_id') or (account.get('id') if isinstance(account,dict) else None)
                prod_id=item.get('product_id') or (product.get('id') if isinstance(product,dict) else None)
                from config import PLANS
                if not plan: reason='plan_missing_unverified'
                elif plan not in PLANS: reason='plan_not_allowlisted'
                elif item.get('plan_id') and isinstance(item.get('plan'),dict) and item['plan'].get('id') and item['plan_id']!=item['plan']['id']: reason='plan_identity_conflict'
                elif not eligibility: reason='status_or_paid_period_not_eligible'
                else: reason='eligible'
                found.append({'membership_id':item.get('id'),'status':item.get('status'),
                    'plan_id':plan,'plan_source':source,'eligibility_reason':reason,'period_end':item.get('current_period_end'),
                    'eligible_now':bool(eligibility),
                    'user_matches_expected':(item.get('user_id')==expected_user_id) if expected_user_id else None})
            info=body.get('page_info') or {}
            if not info.get('has_next_page'): return found
            new_after=info.get('end_cursor')
            if not new_after or new_after==after: raise IntegrationError('Whop membership pagination cursor missing')
            after=new_after
    raise IntegrationError('Too many Whop membership pages; lookup incomplete')
