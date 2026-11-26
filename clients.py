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
    # Whop resolves plan IDs case-insensitively and reports its canonical spelling.
    # Compare without case and return our canonical spelling for known plans.
    if len({v.casefold() for v in values})>1: return None
    return canonical_plan_id(values[0]) if values else None


def canonical_plan_id(value):
    from config import PLANS, COMMUNITY_PLAN_ID
    known={p.casefold():p for p in (*PLANS, COMMUNITY_PLAN_ID)}
    return known.get(str(value).casefold(),value)


def membership_plan_conflict(record):
    if not isinstance(record,dict):return False
    nested=record.get('plan')
    values=[record.get('variant_id'),record.get('plan_id'),
            nested.get('id') if isinstance(nested,dict) else None]
    vals=[v for v in values if isinstance(v,str) and v]
    return len({v.casefold() for v in vals})>1


def normalize_membership(record):
    """Retain original Whop identities; populate plan_id only if unambiguous."""
    if not isinstance(record,dict): return record
    result=dict(record)
    if not membership_plan_conflict(result) and not result.get('plan_id'):
        result['plan_id']=membership_plan_id(result)
    return result

# Billing period each approved plan must report. A record whose
# billing_period_days disagrees with its plan is never granted a rolling period.
PLAN_PERIOD_DAYS = {'plan_qSXeS0xoDapGU': 30, 'plan_B84PWlvXemyfX': 365}
# Keep at least this much runway on a rolling period so a license is never
# issued that lapses before the next reconcile can extend it.
ROLLING_MIN_RUNWAY = dt.timedelta(days=2)
EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def rolling_period_end(m, now=None):
    """End of the current billing period for an active membership that Whop
    reports WITHOUT any period timestamps, else None.

    Whop leaves current_period_start, current_period_end and expires_at null on
    some active memberships, for example a $0 promotional checkout
    (initial_price and renewal_price 0.00). Those members are genuinely active,
    so a null period must not lock them out, but a null period is also not a
    licence to grant open-ended access. Only this exact shape qualifies:

    - status is exactly 'active' (not trialing, canceling, past_due, ...),
    - no period or expiry timestamp at all (a present one always wins, and an
      unparseable one fails closed),
    - not cancelled and not set to cancel at period end,
    - billing_period_days matches the approved plan (30 monthly, 365 annual).

    The end is the next billing-period boundary counted from created_at (or
    the Unix epoch if Whop omits it). It is stable within a period, so
    reconciling repeatedly never rewrites licenses; it advances once per
    period, like a normal renewal. Whop's status stays authoritative: when the
    membership is cancelled or expires, status changes and access is revoked.
    """
    if not isinstance(m, dict) or m.get('status') != 'active':
        return None
    for key in ('current_period_start', 'current_period_end', 'expires_at'):
        if m.get(key) not in (None, ''):
            return None
    if m.get('cancel_at_period_end') not in (None, False):
        return None
    if m.get('canceled_at') not in (None, ''):
        return None
    days = m.get('billing_period_days')
    expected = PLAN_PERIOD_DAYS.get(membership_plan_id(m))
    if isinstance(days, bool) or not isinstance(days, int) or expected is None or days != expected:
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    period = dt.timedelta(days=days)
    anchor = parse_utc(m.get('created_at'))
    if m.get('created_at') not in (None, '') and anchor is None:
        return None
    if anchor is None or anchor > now:
        anchor = EPOCH
    end = anchor + period * ((now - anchor) // period + 1)
    if end - now < ROLLING_MIN_RUNWAY:
        end += period
    return end


def membership_entitlement(m, now=None):
    """Fail closed when authoritative state/period information is absent."""
    if not isinstance(m,dict): return None
    account = m.get('account') or {}
    accid = account.get('id') or m.get('account_id') or m.get('company_id')
    if accid != BUSINESS_ID: return None
    if (m.get('product_id') or (m.get('product') or {}).get('id')) != PRODUCT_ID: return None
    if membership_plan_id(m) not in PLANS: return None
    if membership_plan_conflict(m): return None
    status = m.get('status')
    # 'canceling' = cancelled at period end but still paid up; access is kept
    # until current_period_end, which is enforced below.
    if status not in ('active','trialing','canceling'): return None
    now = now or dt.datetime.now(dt.timezone.utc)
    end = parse_utc(m.get('current_period_end'))
    expires = parse_utc(m.get('expires_at'))
    if expires and (not end or expires < end): end = expires
    source = 'whop_period'
    if not end:
        # Never infer a period from plan duration EXCEPT for the narrow,
        # fully-validated shape in rolling_period_end (active, no timestamps).
        end = rolling_period_end(m, now)
        source = 'rolling_active'
    if not end or end <= now: return None
    return {'membership_id':m.get('id'), 'user_id':m.get('user_id'), 'plan_id':membership_plan_id(m),
            'status':status, 'paid_through':end.isoformat().replace('+00:00','Z'), 'period_source':source}

class WhopClient:
    def __init__(self,cfg:Config): self.cfg=cfg
    async def memberships_for_user(self,user_id):
        """Every StartUpTrading membership held by this Whop user.

        Whop's `/memberships?user_id=...` filter silently returns no rows in
        production (see V7_11_DEPLOY.md), which made every member sign-in fail
        with "no membership". Page the business/product list instead and match
        the user locally, exactly like find_subscription_for_user. A partial
        scan never counts: incomplete pagination fails closed.
        """
        if not self.cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY is not configured')
        if not isinstance(user_id,str) or not user_id.startswith('user_'): raise IntegrationError('Invalid Whop user identity')
        data=[]
        after=None
        async with httpx.AsyncClient(timeout=18) as client:
            for _ in range(50):
                params={'account_id':BUSINESS_ID,'product_id':PRODUCT_ID,'first':100}
                if after: params['after']=after
                r=await client.get('https://api.whop.com/api/v1/memberships',params=params,
                    headers={'Authorization':f'Bearer {self.cfg.whop_api_key}','Api-Version-Date':self.cfg.whop_api_version})
                if r.status_code!=200: raise IntegrationError(f'Whop membership listing HTTP {r.status_code}')
                val=r.json()
                page=val.get('data') if isinstance(val,dict) else None
                if not isinstance(page,list): raise IntegrationError('Unexpected Whop membership list response')
                data.extend(m for m in page if isinstance(m,dict) and m.get('user_id')==user_id)
                info=val.get('page_info') or {}
                if not info.get('has_next_page'): break
                cursor=info.get('end_cursor')
                if not cursor or cursor==after: raise IntegrationError('Whop membership list pagination incomplete')
                after=cursor
            else:
                raise IntegrationError('Whop membership list exceeded safe pagination limit')
        resolved=[]
        for record in data:
            if isinstance(record,dict) and str(record.get('id','')).startswith('mem_') and not membership_plan_id(record):
                record=await self.resolve_membership(record)
            resolved.append(normalize_membership(record))
        return resolved
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
        detail=await self.membership(record['id'])
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

    async def member(self, member_id):
        """Whop Members API record (GET /api/v1/members/{mber_...}).

        This is where Whop exposes the customer's email (top-level `email`, with
        the key's member-email read permission). The caller must still bind the
        record to a verified membership; see purchaser_intake.member_api_email.
        """
        if not self.cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY is not configured')
        if not isinstance(member_id,str) or not member_id.startswith('mber_') or len(member_id)>100:
            raise IntegrationError('Invalid Whop member ID')
        async with httpx.AsyncClient(timeout=18) as client:
            r = await client.get(f'https://api.whop.com/api/v1/members/{member_id}',
                headers={'Authorization':f'Bearer {self.cfg.whop_api_key}','Api-Version-Date':self.cfg.whop_api_version})
        if r.status_code != 200: raise IntegrationError(f'Whop member lookup HTTP {r.status_code}')
        data=r.json()
        record=data.get('data',data) if isinstance(data,dict) else None
        if not isinstance(record,dict): raise IntegrationError('Unexpected Whop member response')
        return record

    async def membership(self, membership_id):
        if not self.cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY is not configured')
        if not membership_id.startswith('mem_'): raise IntegrationError('Invalid membership ID')
        async with httpx.AsyncClient(timeout=18) as client:
            r = await client.get(f'https://api.whop.com/api/v1/memberships/{membership_id}',
                headers={'Authorization':f'Bearer {self.cfg.whop_api_key}','Api-Version-Date':self.cfg.whop_api_version})
        if r.status_code != 200: raise IntegrationError(f'Whop membership lookup HTTP {r.status_code}')
        data=r.json()
        return normalize_membership(data.get('data',data) if isinstance(data,dict) else data)

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
                r=await client.post(self.cfg.nt_auth_url,json={
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
