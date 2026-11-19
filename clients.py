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
    """Accept plan identity from direct membership responses or embedded plan.

    Never infer a plan from price, billing interval, product, or membership status.
    Conflicting identities fail closed.
    """
    if not isinstance(record, dict): return None
    direct=record.get('plan_id')
    embedded=record.get('plan')
    nested=embedded.get('id') if isinstance(embedded,dict) else None
    if direct and nested and direct != nested: return None
    return direct or nested


def normalize_membership(record):
    """Normalize verified field shapes; preserve conflicts so entitlement fails closed."""
    if not isinstance(record,dict): return record
    result=dict(record)
    plan=record.get('plan')
    if not record.get('plan_id') and isinstance(plan,dict):
        result['plan_id']=plan.get('id')
    return result

def membership_entitlement(m):
    """Fail closed when authoritative state/period information is absent."""
    if not isinstance(m,dict): return None
    account = m.get('account') or {}
    accid = account.get('id') or m.get('account_id') or m.get('company_id')
    if accid != BUSINESS_ID: return None
    if (m.get('product_id') or (m.get('product') or {}).get('id')) != PRODUCT_ID: return None
    if membership_plan_id(m) not in PLANS: return None
    if m.get('plan_id') and isinstance(m.get('plan'),dict) and m['plan'].get('id') and m['plan_id'] != m['plan']['id']: return None
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
    async def memberships_for_user(self,user_id):
        if not self.cfg.whop_api_key: raise IntegrationError('WHOP_API_KEY is not configured')
        if not user_id.startswith('user_'): raise IntegrationError('Invalid Whop user identity')
        async with httpx.AsyncClient(timeout=18) as client:
            r=await client.get('https://api.whop.com/api/v1/memberships',
                params={'account_id':BUSINESS_ID,'user_id':user_id,'product_id':PRODUCT_ID,'first':100},
                headers={'Authorization':f'Bearer {self.cfg.whop_api_key}','Api-Version-Date':self.cfg.whop_api_version})
        if r.status_code!=200: raise IntegrationError(f'Whop membership listing HTTP {r.status_code}')
        val=r.json()
        data=val.get('data',[])
        if not isinstance(data,list): raise IntegrationError('Unexpected Whop membership list response')
        # A list response can be partial. Fetch detail only when plan identity is absent.
        resolved=[]
        for record in data:
            if isinstance(record,dict) and record.get('id','').startswith('mem_') and not membership_plan_id(record):
                detail=await self.membership(record['id'])
                if isinstance(detail,dict):
                    for identity in ('id','user_id','account_id','product_id','member_id'):
                        if record.get(identity) and detail.get(identity) and record[identity]!=detail[identity]:
                            raise IntegrationError('Whop membership detail identity conflict')
                    record={**record,**{k:v for k,v in detail.items() if v is not None}}
            resolved.append(normalize_membership(record))
        return resolved
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
