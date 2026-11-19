"""Admin-only read-only membership resolution. Never changes customer or license data."""
import httpx
from config import BUSINESS_ID, PRODUCT_ID
from clients import membership_entitlement, membership_plan_id, membership_plan_conflict, normalize_membership, WhopClient, IntegrationError

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
                # Resolve documented variant_id first, then verified payment evidence.
                list_plan=membership_plan_id(item)
                source='list'
                if not list_plan and isinstance(item.get('id'),str) and item['id'].startswith('mem_'):
                    item=await WhopClient(cfg).resolve_membership(item)
                    source=item.get('plan_source','detail')
                item=normalize_membership(item)
                eligibility=membership_entitlement(item)
                plan=membership_plan_id(item)
                account=item.get('account') or {}
                product=item.get('product') or {}
                acct_id=item.get('account_id') or (account.get('id') if isinstance(account,dict) else None)
                prod_id=item.get('product_id') or (product.get('id') if isinstance(product,dict) else None)
                from config import PLANS
                if membership_plan_conflict(item): reason='plan_identity_conflict'
                elif not plan: reason='plan_missing_unverified'
                elif plan not in PLANS: reason='plan_not_allowlisted'
                elif membership_plan_conflict(item): reason='plan_identity_conflict'
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


async def verified_subscription_by_member(cfg, member_id, subscription_id, expected_user_id):
    """Fetch authoritative subscription via the SAME member_id-filtered API proven in diagnostics.

    This returns the authenticated record for intake, not a summary. Every identity,
    product and plan must match; uncertain pagination or ambiguous results fail closed.
    """
    if not all(isinstance(x, str) and len(x) <= 100 for x in (member_id, subscription_id, expected_user_id)):
        raise ValueError('Invalid membership identifiers')
    if not member_id.startswith('mber_') or not subscription_id.startswith('mem_') or not expected_user_id.startswith('user_'):
        raise ValueError('Use valid Whop member, subscription, and user IDs')
    if not cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY not configured')
    found=[]
    after=None
    async with httpx.AsyncClient(timeout=18) as client:
        for _ in range(20):
            params={'account_id':BUSINESS_ID,'member_id':member_id,'first':100}
            if after: params['after']=after
            response=await client.get('https://api.whop.com/api/v1/memberships',params=params,
                headers={'Authorization':'Bearer '+cfg.whop_api_key,'Api-Version-Date':cfg.whop_api_version})
            if response.status_code != 200: raise IntegrationError('Whop member membership lookup HTTP '+str(response.status_code))
            body=response.json()
            if not isinstance(body,dict) or not isinstance(body.get('data'),list):
                raise IntegrationError('Unexpected Whop membership response')
            for item in body['data']:
                if not isinstance(item,dict) or item.get('id') != subscription_id: continue
                if item.get('member_id') != member_id or item.get('user_id') != expected_user_id: continue
                account=item.get('account') or {}; product=item.get('product') or {}
                if (item.get('account_id') or (account.get('id') if isinstance(account,dict) else None)) != BUSINESS_ID:continue
                if (item.get('product_id') or (product.get('id') if isinstance(product,dict) else None)) != PRODUCT_ID:continue
                if not membership_plan_id(item): item=await WhopClient(cfg).resolve_membership(item)
                item=normalize_membership(item)
                if not membership_entitlement(item):continue
                found.append(item)
            page=body.get('page_info') or {}
            if not page.get('has_next_page'):
                if len(found)>1: raise IntegrationError('Conflicting matching membership rows')
                return found[0] if found else None
            cursor=page.get('end_cursor')
            if not cursor or cursor==after:raise IntegrationError('Incomplete Whop pagination')
            after=cursor
    raise IntegrationError('Membership list exceeded pagination limit')
