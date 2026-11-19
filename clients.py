"""Only server-side clients; secrets never flow to the browser."""
import asyncio
import datetime as dt
import httpx
from config import Config, BUSINESS_ID, PRODUCT_ID, PLANS

class IntegrationError(Exception): pass

def parse_utc(s):
    if not s: return None
    try: return dt.datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(dt.timezone.utc)
    except (ValueError, TypeError): return None

def membership_plan_id(record):
    """Resolve Whop's plan/variant ID, refusing contradictory identities.

    Current Whop membership API names the purchased plan `variant_id`.
    Older API responses may call it `plan_id` or include `plan.id`.
    Never infer a plan from price, product, email, or membership status.
    """
    if not isinstance(record, dict): return None
    embedded=record.get('plan')
    values=[record.get('variant_id'),record.get('plan_id'),
            embedded.get('id') if isinstance(embedded,dict) else None]
    values=[v for v in values if isinstance(v,str) and v]
    if len(set(values))>1: return None
    return values[0] if values else None


def membership_plan_conflict(record):
    if not isinstance(record,dict):return False
    nested=record.get('plan')
    values=[record.get('variant_id'),record.get('plan_id'),
            nested.get('id') if isinstance(nested,dict) else None]
    vals=[v for v in values if isinstance(v,str) and v]
    return len(set(vals))>1


def normalize_membership(record):
    """Retain original Whop identities; populate plan_id only if unambiguous."""
    if not isinstance(record,dict): return record
    result=dict(record)
    if not membership_plan_conflict(result) and not result.get('plan_id'):
        result['plan_id']=membership_plan_id(result)
    return result

def membership_entitlement(m):
    """Fail closed when authoritative state/period information is absent."""
    if not isinstance(m,dict): return None
    account = m.get('account') or {}
    accid = account.get('id') or m.get('account_id') or m.get('company_id')
    if accid != BUSINESS_ID: return None
    if (m.get('product_id') or (m.get('product') or {}).get('id')) != PRODUCT_ID: return None
    if membership_plan_id(m) not in PLANS: return None
    if membership_plan_conflict(m): return None
    status = m.get('status')
    if status not in ('active','trialing'): return None
    end = parse_utc(m.get('current_period_end'))
    expires = parse_utc(m.get('expires_at'))
    if expires and (not end or expires < end): end = expires
    now = dt.datetime.now(dt.timezone.utc)
    if not end or end <= now: return None
    # Never infer a future billing period from plan duration.
    return {'membership_id':m.get('id'), 'user_id':m.get('user_id'), 'plan_id':membership_plan_id(m),
            'status':status, 'paid_through':end.isoformat().replace('+00:00','Z')}

class WhopClient:
    def __init__(self,cfg:Config): self.cfg=cfg
    async def business_membership_list(self):
        """One complete, authoritative list query used by OAuth, intake and reconciliation.

        Whop has returned no rows for otherwise valid `user_id` filters in live tests.
        Do NOT depend on server-side user filtering for access decisions. Fail closed
        on incomplete pagination rather than incorrectly rejecting or changing access.
        """
        if not self.cfg.whop_api_key:
            raise IntegrationError('WHOP_API_KEY is not configured')
        items=[]; cursor=None; seen=set()
        async with httpx.AsyncClient(timeout=18) as client:
            for _ in range(50):
                params={'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,'first':100}
                if cursor:params['after']=cursor
                r=await client.get('https://api.whop.com/api/v1/memberships',params=params,
                    headers={'Authorization':f'Bearer {self.cfg.whop_api_key}',
                             'Api-Version-Date':self.cfg.whop_api_version})
                if r.status_code!=200:
                    raise IntegrationError(f'Whop membership list HTTP {r.status_code}')
                try: payload=r.json()
                except ValueError as exc: raise IntegrationError('Invalid Whop membership JSON') from exc
                if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
                    raise IntegrationError('Unexpected Whop membership list response')
                for raw in payload['data']:
                    if not isinstance(raw,dict):continue
                    record=normalize_membership(raw)
                    account=record.get('account') or {}; product=record.get('product') or {}
                    if not isinstance(account,dict) or not isinstance(product,dict):continue
                    if (record.get('account_id') or account.get('id'))!=BUSINESS_ID:continue
                    if (record.get('product_id') or product.get('id'))!=PRODUCT_ID:continue
                    mid=record.get('id')
                    if not isinstance(mid,str) or not mid.startswith('mem_'):continue
                    if mid in seen:raise IntegrationError('Duplicate membership ID across Whop pages')
                    seen.add(mid);items.append(record)
                info=payload.get('page_info') or {}
                if not isinstance(info,dict):raise IntegrationError('Invalid Whop pagination')
                if not info.get('has_next_page'):return items
                nxt=info.get('end_cursor')
                if not isinstance(nxt,str) or not nxt or nxt==cursor:
                    raise IntegrationError('Incomplete Whop membership pagination')
                cursor=nxt
        raise IntegrationError('Whop membership list exceeded safe page limit')

    async def memberships_for_user(self,user_id):
        if not isinstance(user_id,str) or not user_id.startswith('user_'):
            raise IntegrationError('Invalid Whop user identity')
        items=await self.business_membership_list()
        result=[r for r in items if r.get('user_id')==user_id]
        # Detail API is a fallback for missing plan data, NOT a routine additional call.
        return [await self.resolve_membership(r) if not membership_plan_id(r) else r for r in result]

    async def authoritative_membership(self,membership_id,expected_user_id=None):
        if not isinstance(membership_id,str) or not membership_id.startswith('mem_'):
            raise IntegrationError('Invalid Whop membership ID')
        matches=[r for r in await self.business_membership_list() if r.get('id')==membership_id]
        if len(matches)!=1:raise IntegrationError('Whop subscription not found uniquely in completed list')
        record=matches[0]
        if expected_user_id and record.get('user_id')!=expected_user_id:
            raise IntegrationError('Whop membership owner mismatch')
        if not membership_plan_id(record):record=await self.resolve_membership(record)
        return record

    async def find_subscription_for_user(self, membership_id, expected_user_id):
        """Find an exact subscription without trusting Whop's `user_id` list filter.

        The member-based lookup can succeed when `/memberships?user_id=...`
        silently returns no rows. Page the business/product membership list and
        match both IDs locally. Never use a partial scan to establish eligibility.
        """
        if not self.cfg.whop_api_key:
            raise IntegrationError('WHOP_API_KEY is not configured')
        if not (isinstance(membership_id,str) and membership_id.startswith('mem_')
                and isinstance(expected_user_id,str) and expected_user_id.startswith('user_')):
            raise IntegrationError('Invalid Whop membership or user identity')
        after = None
        matches = []
        # The bounded loop fails closed if Whop refuses to finish pagination.
        async with httpx.AsyncClient(timeout=18) as client:
            for _ in range(50):
                params = {'account_id': BUSINESS_ID, 'product_id': PRODUCT_ID, 'first': 100}
                if after: params['after'] = after
                response = await client.get('https://api.whop.com/api/v1/memberships',
                    params=params, headers={'Authorization': f'Bearer {self.cfg.whop_api_key}',
                                            'Api-Version-Date': self.cfg.whop_api_version})
                if response.status_code != 200:
                    raise IntegrationError(f'Whop membership list HTTP {response.status_code}')
                payload = response.json()
                if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
                    raise IntegrationError('Unexpected Whop membership list response')
                for item in payload['data']:
                    if not isinstance(item,dict) or item.get('id') != membership_id: continue
                    if item.get('user_id') != expected_user_id: continue
                    acc = item.get('account') or {}
                    prod = item.get('product') or {}
                    if (item.get('account_id') or (acc.get('id') if isinstance(acc,dict) else None)) != BUSINESS_ID: continue
                    if (item.get('product_id') or (prod.get('id') if isinstance(prod,dict) else None)) != PRODUCT_ID: continue
                    matches.append(normalize_membership(item))
                page = payload.get('page_info') or {}
                if not page.get('has_next_page'):
                    if len(matches) > 1:
                        raise IntegrationError('Conflicting duplicate Whop subscription rows')
                    return matches[0] if matches else None
                cursor = page.get('end_cursor')
                if not cursor or cursor == after:
                    raise IntegrationError('Whop membership list pagination incomplete')
                after = cursor
        raise IntegrationError('Whop membership list exceeded safe pagination limit')

    async def payment_plan_for_membership(self, membership):
        """Fallback: identify an eligible plan through a PAID, matching Whop payment.

        No plan is inferred from amount or billing period. Membership/product/user
        identity must match; ambiguous or refunded evidence fails closed.
        """
        mid=membership.get('id') if isinstance(membership,dict) else None
        uid=membership.get('user_id') if isinstance(membership,dict) else None
        if not isinstance(mid,str) or not mid.startswith('mem_') or not uid:
            return None
        headers={'Authorization':f'Bearer {self.cfg.whop_api_key}',
                 'Api-Version-Date':self.cfg.whop_api_version}
        async with httpx.AsyncClient(timeout=18) as client:
            response=await client.get('https://api.whop.com/api/v1/payments',
                params={'account_id':BUSINESS_ID,'membership_id':mid,'status':'paid','first':100},
                headers=headers)
        if response.status_code in (401,403):
            raise IntegrationError('Whop payment:basic:read permission required for plan fallback')
        if response.status_code!=200:
            raise IntegrationError(f'Whop payment lookup HTTP {response.status_code}')
        body=response.json()
        if not isinstance(body,dict) or not isinstance(body.get('data'),list):
            raise IntegrationError('Unexpected Whop payments response')
        # Pagination can hide a newer plan; do not infer from incomplete pages.
        if (body.get('page_info') or {}).get('has_next_page'):
            raise IntegrationError('Whop payment history paginated; plan fallback requires complete history')
        plans=set()
        from config import PLANS
        for p in body['data']:
            if not isinstance(p,dict):continue
            if p.get('status')!='paid':continue
            if p.get('membership_id')!=mid or p.get('account_id')!=BUSINESS_ID:continue
            if p.get('user_id')!=uid:continue
            if p.get('refunded_at') or p.get('auto_refunded') or p.get('disputed_at'):continue
            for line in p.get('line_items') or []:
                if not isinstance(line,dict) or line.get('product_id')!=PRODUCT_ID:continue
                variant=line.get('variant_id')
                if variant and variant in PLANS:plans.add(variant)
                elif variant:plans.add('unapproved:'+str(variant))
        # Do not select a plan when different matching payments conflict.
        if len(plans)>1:raise IntegrationError('Conflicting purchased variants in Whop payment history')
        return next(iter(plans)) if plans and next(iter(plans)) in PLANS else None

    async def resolve_membership(self, record):
        """Detail -> documented variant_id -> verified payment fallback."""
        if not isinstance(record,dict) or not str(record.get('id','')).startswith('mem_'):
            return record
        detail=await self.membership_detail(record['id'])
        if not isinstance(detail,dict) or detail.get('id')!=record['id']:
            raise IntegrationError('Whop membership detail identity mismatch')
        for key in ('id','user_id','account_id','member_id','product_id','variant_id','plan_id'):
            if record.get(key) and detail.get(key) and record[key]!=detail[key]:
                raise IntegrationError('Whop membership detail identity conflict: '+key)
        merged={**record,**{k:v for k,v in detail.items() if v is not None}}
        if membership_plan_conflict(merged):
            raise IntegrationError('Whop membership contains conflicting plan identities')
        plan=membership_plan_id(merged)
        if not plan:
            plan=await self.payment_plan_for_membership(merged)
            if plan:
                merged['plan_id']=plan
                merged['plan_source']='verified_payment'
        else:
            merged['plan_source']='membership_detail'
        return normalize_membership(merged)

    async def user(self,user_id):
        if not self.cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY is not configured')
        if not user_id.startswith('user_'): raise IntegrationError('Invalid Whop user ID')
        async with httpx.AsyncClient(timeout=18) as client:
            r=await client.get(f'https://api.whop.com/api/v1/users/{user_id}',
                headers={'Authorization':f'Bearer {self.cfg.whop_api_key}',
                         'Api-Version-Date':self.cfg.whop_api_version})
        if r.status_code!=200: raise IntegrationError(f'Whop user lookup HTTP {r.status_code}')
        val=r.json()
        return val.get('data',val) if isinstance(val,dict) else val

    async def membership_detail(self, membership_id):
        if not self.cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY is not configured')
        if not membership_id.startswith('mem_'): raise IntegrationError('Invalid membership ID')
        async with httpx.AsyncClient(timeout=18) as client:
            r = await client.get(f'https://api.whop.com/api/v1/memberships/{membership_id}',
                headers={'Authorization':f'Bearer {self.cfg.whop_api_key}','Api-Version-Date':self.cfg.whop_api_version})
        if r.status_code != 200: raise IntegrationError(f'Whop membership lookup HTTP {r.status_code}')
        data=r.json()
        return normalize_membership(data.get('data',data) if isinstance(data,dict) else data)

    async def membership(self, membership_id):
        return await self.authoritative_membership(membership_id)

class NinjaClient:
    def __init__(self,cfg:Config):
        self.cfg=cfg; self.token=None; self.user_id=None; self.expires=dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        self.lock=asyncio.Lock()
    async def authorization(self):
        if not all([self.cfg.nt_username,self.cfg.nt_password,self.cfg.nt_cid,self.cfg.nt_sec]):
            raise IntegrationError('NinjaTrader credentials are incomplete')
        async with self.lock:
            if self.token and dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=8)<self.expires:
                return f'Bearer {self.user_id} {self.cfg.nt_username} {self.token}'
            async with httpx.AsyncClient(timeout=20) as client:
                r=await client.post('https://demo.tradovateapi.com/v1/auth/accesstokenrequest',json={
                    'name':self.cfg.nt_username,'password':self.cfg.nt_password,
                    'appId':self.cfg.nt_app_id,'appVersion':self.cfg.nt_app_version,
                    'cid':self.cfg.nt_cid,'sec':self.cfg.nt_sec})
            if r.status_code!=200: raise IntegrationError(f'NinjaTrader authentication HTTP {r.status_code}; no automatic login retry')
            val=r.json()
            if not val.get('accessToken') or not val.get('userId'):
                raise IntegrationError('NinjaTrader authentication did not return token/userId; check approval or retry window')
            self.token=val['accessToken']; self.user_id=val['userId']
            self.expires=parse_utc(val.get('expirationTime')) or dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=75)
            return f'Bearer {self.user_id} {self.cfg.nt_username} {self.token}'
    async def call(self,method,path,payload=None):
        authorization=await self.authorization()
        async with httpx.AsyncClient(timeout=25) as client:
            r=await client.request(method,'https://ecosystemapi.ninjatrader.com'+path,
                headers={'Authorization':authorization},json=payload)
        if r.status_code!=200: raise IntegrationError(f'NinjaTrader {method} HTTP {r.status_code}')
        val=r.json()
        if val.get('errorText'): raise IntegrationError('NinjaTrader API reported: '+str(val['errorText'])[:160])
        return val.get('result')
    async def licenses(self,product_id):
        result=await self.call('GET','/v1/licenses/vendor')
        if not isinstance(result,dict): raise IntegrationError('Unexpected NinjaTrader grouped license response')
        group=result.get(str(int(product_id)))
        if group is None: raise IntegrationError('Vendor does not own this NinjaTrader product or it is not visible')
        rows=group.get('licenses') if isinstance(group,dict) else None
        if not isinstance(rows,list): raise IntegrationError('Unexpected NinjaTrader product licenses')
        return rows
    async def create(self,product_id,email,end):
        result=await self.call('POST','/v1/licenses/vendor',{'license':{'email':email,'expirationDateUTC':end},'productIds':[int(product_id)]})
        if not isinstance(result,list) or len(result)!=1 or not isinstance(result[0],int):
            raise IntegrationError('Unexpected NinjaTrader creation response')
        return result[0]
    async def update(self,product_id,license_id,email,end):
        result=await self.call('PATCH',f'/v1/licenses/vendor/{int(license_id)}',
            {'product':{'email':email,'expirationDateUTC':end}})
        if not isinstance(result,int): raise IntegrationError('Unexpected NinjaTrader update response')
        return result
