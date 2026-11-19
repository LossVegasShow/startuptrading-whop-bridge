'''Optional GoHighLevel CRM and post-activation email processing.
No CRM calls without both GHL settings; no activation emails before all three
licenses are recorded and a setup guide URL is configured.
'''
import json
import time
from urllib.parse import urlparse
import httpx
from store import connect, customer
from config import INDICATORS, PLANS

API='https://services.leadconnectorhq.com'

def crm_enabled(cfg):
    return bool(cfg.ghl_api_key and cfg.ghl_location_id)

def email_enabled(cfg):
    return bool(cfg.resend_api_key and cfg.resend_from and valid_guide_url(cfg.indicator_setup_url))

def valid_guide_url(url):
    try:
        u=urlparse(url)
        return u.scheme=='https' and bool(u.hostname) and not u.username and not u.password
    except ValueError:return False

def build_contact(c,cfg):
    data={'locationId':cfg.ghl_location_id, 'email':c['buyer_email'], 'source':'StartUpTrading / Whop'}
    # GHL custom fields are opt-in. Do not overwrite arbitrary existing fields/tags.
    field_values={
        'whop_user_id':c.get('whop_user_id') or '',
        'whop_membership_id':c['membership_id'],
        'subscription_plan':PLANS.get(c.get('plan_id'),'Unknown'),
        'membership_status':c.get('status') or '',
        'ninjatrader_email':c.get('nt_email') if c.get('verified') else '',
        'activation_status':('active' if c.get('status')=='eligible' and c.get('activated') else
                              'linked' if c.get('verified') else 'awaiting_link'),
        'paid_through':c.get('paid_through') or ''}
    try: mapping=json.loads(cfg.ghl_custom_fields_json or '{}')
    except (TypeError,ValueError):mapping={}
    if isinstance(mapping,dict):
        fields=[{'id':v,'field_value':str(field_values[k] or '')} for k,v in mapping.items()
                if k in field_values and isinstance(v,str) and v.strip()]
        if fields:data['customFields']=fields
    return data

async def sync_crm(cfg,cid):
    if not crm_enabled(cfg):return 'not_configured'
    with connect(cfg) as db:
        row=db.execute('SELECT * FROM crm_sync WHERE customer_id=?',(cid,)).fetchone()
        c=customer(db,cid)
        if not c or not row:return 'not_found'
        row=dict(row)
        licenses=db.execute('SELECT product_id,license_id,expiration FROM licenses WHERE customer_id=?',(cid,)).fetchall()
        active={int(r['product_id']) for r in licenses if r['license_id'] and r['expiration']==c['paid_through']}
        c['activated']=active==set(INDICATORS) and bool(c['verified']) and c['status']=='eligible'
    data=build_contact(c,cfg)
    headers={'Authorization':'Bearer '+cfg.ghl_api_key,'Version':'2021-07-28','Content-Type':'application/json'}
    url=f'{API}/contacts/{row["contact_id"]}' if row['contact_id'] else f'{API}/contacts/upsert'
    method='PUT' if row['contact_id'] else 'POST'
    if row['contact_id']:data.pop('locationId',None)
    try:
        async with httpx.AsyncClient(timeout=18) as client:
            resp=await client.request(method,url,json=data,headers=headers)
        if resp.status_code not in (200,201):raise RuntimeError(f'GoHighLevel HTTP {resp.status_code}')
        content=resp.json()
        contact=content.get('contact') or {}
        contact_id=contact.get('id') or row['contact_id']
        if not contact_id:raise RuntimeError('GoHighLevel response missing contact ID')
        with connect(cfg) as db:
            # Compare-and-swap: an update that arrived during the API request remains pending.
            db.execute('''UPDATE crm_sync SET contact_id=?,synced_revision=?,
                status=CASE WHEN revision=? THEN 'synced' ELSE 'pending' END,
                attempts=0,next_attempt_at=0,last_error=NULL,updated_at=? WHERE customer_id=?''',
                (contact_id,row['revision'],row['revision'],int(time.time()),cid))
        return 'synced'
    except (httpx.HTTPError,ValueError,RuntimeError) as exc:
        with connect(cfg) as db:
            db.execute('''UPDATE crm_sync SET status='retry',attempts=attempts+1,
                next_attempt_at=?,last_error=?,updated_at=? WHERE customer_id=?''',
                (int(time.time())+min(3600,60*2**min(row['attempts'],6)),str(exc)[:180],int(time.time()),cid))
        return 'retry'


def activation_message(c,cfg):
    lines=['Your StartUpTrading NinjaTrader Indicators Are Ready!', '',
           'Your StartUpTrading indicator licenses have been activated for the NinjaTrader email: '+c['nt_email'], '',
           'Your indicators:']
    lines.extend('- '+name for name in INDICATORS.values())
    lines += ['', 'Getting started:',
        '1. Install or open NinjaTrader Desktop and sign in with your own NinjaTrader account.',
        '2. Follow the StartUpTrading setup instructions for the indicator download/import and chart configuration:',
        cfg.indicator_setup_url,
        '3. If your indicators do not appear, contact StartUpTrading support before purchasing another subscription.',
        '', 'Your access is tied to your active StartUpTrading Whop membership.',
        'Linked account email: '+c['nt_email']]
    if cfg.support_email:lines += ['Support: '+cfg.support_email]
    return '\n'.join(lines)

async def send_activation_email(cfg,cid):
    if not email_enabled(cfg):return 'not_configured'
    with connect(cfg) as db:
        row=db.execute("SELECT * FROM message_outbox WHERE customer_id=? AND kind='activation'",(cid,)).fetchone()
        c=customer(db,cid)
        if not row or not c or row['status']=='sent':return 'not_pending'
        row=dict(row)
        if row['status'] not in ('pending','retry'):return 'not_pending'
        # Recheck licensing and membership state before triggering an actual email.
        if c['status']!='eligible' or not c['verified'] or row['target_email']!=c['nt_email']:
            return 'blocked'
        rows=db.execute('SELECT product_id,license_id,expiration FROM licenses WHERE customer_id=?',(cid,)).fetchall()
        if {int(x['product_id']) for x in rows if x['license_id'] and x['expiration']==c['paid_through']}!=set(INDICATORS):return 'blocked'
        result=db.execute("UPDATE message_outbox SET status='sending',updated_at=? WHERE customer_id=? AND kind='activation' AND status IN ('pending','retry')",
                          (int(time.time()),cid))
        if result.rowcount!=1:return 'not_pending'
    # Stable provider idempotency key reduces duplicates after HTTP timeout/restart.
    headers={'Authorization':'Bearer '+cfg.resend_api_key,'Idempotency-Key':f'sut-activation-{cid}-v1'}
    payload={'from':cfg.resend_from,'to':[c['nt_email']],
        'subject':'Your StartUpTrading NinjaTrader indicators are ready',
        'text':activation_message(c,cfg)}
    try:
        async with httpx.AsyncClient(timeout=18) as client:
            resp=await client.post('https://api.resend.com/emails',headers=headers,json=payload)
        if resp.status_code not in (200,201,202):raise RuntimeError(f'Resend HTTP {resp.status_code}')
        message_id=resp.json().get('id')
        if not message_id:raise RuntimeError('Resend response missing message ID')
        with connect(cfg) as db:
            db.execute("UPDATE message_outbox SET status='sent',provider_message_id=?,last_error=NULL,updated_at=? WHERE customer_id=? AND kind='activation'",
                       (message_id,int(time.time()),cid))
        return 'sent'
    except (httpx.HTTPError,ValueError,RuntimeError) as exc:
        with connect(cfg) as db:
            db.execute('''UPDATE message_outbox SET status='retry',attempts=attempts+1,
                next_attempt_at=?,last_error=?,updated_at=? WHERE customer_id=? AND kind='activation' ''',
                (int(time.time())+min(3600,60*2**min(row['attempts'],6)),str(exc)[:180],int(time.time()),cid))
        return 'retry'

async def process_pending(cfg,limit=30):
    '''Called by existing single reconciler worker; no customer-facing new endpoints.'''
    now=int(time.time())
    with connect(cfg) as db:
        # Recover interrupted Resend requests using the same provider idempotency key.
        db.execute("UPDATE message_outbox SET status='retry' WHERE status='sending' AND updated_at<?",(now-600,))
        crm=[r['customer_id'] for r in db.execute("SELECT customer_id FROM crm_sync WHERE status IN ('pending','retry') AND next_attempt_at<=? LIMIT ?",(now,limit))] if crm_enabled(cfg) else []
        emails=[r['customer_id'] for r in db.execute("SELECT customer_id FROM message_outbox WHERE status IN ('pending','retry') AND next_attempt_at<=? LIMIT ?",(now,limit))] if email_enabled(cfg) else []
    for cid in crm:
        await sync_crm(cfg,cid)
    for cid in emails:
        await send_activation_email(cfg,cid)
    return {'crm_checked':len(crm),'email_checked':len(emails)}
