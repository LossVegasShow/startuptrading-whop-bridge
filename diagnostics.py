"""Read-only operator diagnostics. No customer records, credentials or account emails in responses."""
import asyncio
import httpx
from config import INDICATORS, BUSINESS_ID
from store import connect
from clients import NinjaClient


def check_postgres(cfg):
    if not cfg.database_url:
        return {'status':'fail','reason':'DATABASE_URL is missing; hosted SQLite is not durable'}
    try:
        with connect(cfg) as db:
            db.execute('SELECT COUNT(*) AS n FROM customers').fetchone()
            db.execute('SELECT COUNT(*) AS n FROM licenses').fetchone()
            db.execute('SELECT COUNT(*) AS n FROM webhook_events').fetchone()
        return {'status':'pass','note':'PostgreSQL connection and schema queries succeeded'}
    except Exception:
        return {'status':'fail','reason':'Database unavailable or schema mismatch; inspect private Render logs'}


async def check_whop(cfg):
    if not cfg.whop_api_key:
        return {'status':'fail','reason':'WHOP_API_KEY missing'}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r=await client.get('https://api.whop.com/api/v1/memberships',
                params={'account_id':BUSINESS_ID,'first':1},
                headers={'Authorization':'Bearer '+cfg.whop_api_key,'Api-Version-Date':cfg.whop_api_version})
        if r.status_code!=200:
            return {'status':'fail','reason':f'Whop membership list HTTP {r.status_code}'}
        payload=r.json()
        if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
            return {'status':'fail','reason':'Unexpected Whop membership list JSON shape'}
        return {'status':'pass','note':'Whop API key can list memberships (not a paid-member entitlement test)'}
    except (httpx.RequestError,ValueError,TypeError):
        return {'status':'fail','reason':'Whop connection or response problem'}


async def check_ninja(cfg):
    if not all((cfg.nt_username,cfg.nt_password,cfg.nt_cid,cfg.nt_sec)):
        return {'status':'fail','reason':'NinjaTrader vendor API credentials incomplete'}
    try:
        nt=NinjaClient(cfg)
        result=await nt.call('GET','/v1/products/me')
        if not isinstance(result,list):
            return {'status':'fail','reason':'Unexpected NinjaTrader vendor products response'}
        available=set()
        for product in result:
            if isinstance(product,dict):
                value=product.get('productId')
            else:
                value=product
            try:available.add(int(value))
            except (ValueError,TypeError):pass
        expected=set(INDICATORS)
        missing=sorted(expected-available)
        if missing:
            return {'status':'fail','reason':'Vendor access authenticated but expected products are missing','missing_product_ids':missing}
        return {'status':'pass','note':'Vendor authentication succeeded and every membership product ID is accessible','product_ids':sorted(expected)}
    except Exception:
        return {'status':'fail','reason':'NinjaTrader vendor authentication, connection or response failed; inspect private Render logs'}


async def run_checks(cfg):
    # Whop & NinjaTrader requests use GET only; no license write endpoints can be called.
    db=await asyncio.to_thread(check_postgres,cfg)
    whop,nt=await asyncio.gather(check_whop(cfg),check_ninja(cfg))
    webhook={'status':'configured' if cfg.whop_webhook_secret else 'missing',
             'note':'Signing secret present, but webhook delivery/signature not verified by this check' if cfg.whop_webhook_secret else 'WHOP_WEBHOOK_SECRET missing'}
    return {'release':'v7.3','mode':'READ_ONLY','license_writes_enabled':bool(cfg.license_writes),
            'database':db,'whop':whop,'ninjatrader':nt,'webhook':webhook,
            'limitations':['No customer account or membership link is created or tested',
                           'No emails or NinjaTrader licenses are created, renewed or expired',
                           'A successful check does not prove webhook delivery or full customer activation']}
