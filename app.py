"""StartUpTrading integration: one member activation experience, separate secure licensing engine.
Works with a Whop link and verified buyer email; embedded Whop SSO adapter is NOT claimed.
"""
import asyncio,hashlib,hmac,json,os,secrets, smtplib,ssl,time,base64
from urllib.parse import urlencode
import httpx
from email.message import EmailMessage
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from config import Config,INDICATORS,EVENTS,PLANS
from store import connect,customer,audit,request_crm_sync
from engine import Engine
from clients import membership_entitlement,IntegrationError
from diagnostics import run_checks
from member_lookup import resolve_member, verified_subscription_by_member
from customer_communications import process_pending
import lifecycle
import returning_member
import attention
import alerts
import lifecycle_emails
from purchaser_intake import handle_queued_event, import_membership
from security import verify_webhook,hash_token,require_admin
import customer_errors
import email_templates

cfg=Config(); engine=Engine(cfg)
ROOT=Path(__file__).parent

CODES_PER_DAY=10

def purge_expired(db):
    """Delete expired sign-in state, sessions and invites (anyone can create OAuth state rows)."""
    now=int(time.time())
    for table in ('oauth_states','admin_test_oauth_states','sessions','admin_test_sessions'):
        db.execute(f'DELETE FROM {table} WHERE expires_at<?',(now,))
    db.execute('DELETE FROM invites WHERE expires_at<?',(now-86400*30,))

def issue_code(db,cid,purpose,email):
    now=int(time.time()); old=db.execute('SELECT requested_at FROM codes WHERE customer_id=? AND purpose=?',(cid,purpose)).fetchone()
    if old and now-old['requested_at']<60: raise HTTPException(429,'Wait a minute before requesting another code')
    # Daily cap: with 5 guesses per code, unlimited codes would still allow slow
    # guessing, and would let a member send code emails to any inbox repeatedly.
    sent=db.execute("SELECT COUNT(*) AS n FROM audit WHERE customer_id=? AND action='code_requested' AND details=? AND at>?",
                    (cid,purpose,now-86400)).fetchone()['n']
    if sent>=CODES_PER_DAY: raise HTTPException(429,'Too many codes requested today; try again tomorrow or contact support')
    code=f'{secrets.randbelow(1000000):06}'
    digest=hmac.new(cfg.admin_password.encode(),f'{cid}:{purpose}:{code}'.encode(),hashlib.sha256).hexdigest()
    db.execute('INSERT OR REPLACE INTO codes(customer_id,purpose,code_hash,target_email,expires_at,attempts,requested_at) VALUES(?,?,?,?,?,0,?)',
               (cid,purpose,digest,email,now+600,now))
    audit(db,cid,'code_requested',purpose)
    return code

def verify_code(db,cid,purpose,code):
    row=db.execute('SELECT * FROM codes WHERE customer_id=? AND purpose=?',(cid,purpose)).fetchone()
    if not row or row['expires_at']<time.time() or row['attempts']>=5: return False
    db.execute('UPDATE codes SET attempts=attempts+1 WHERE customer_id=? AND purpose=?',(cid,purpose))
    expected=hmac.new(cfg.admin_password.encode(),f'{cid}:{purpose}:{code}'.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,row['code_hash']): return False
    db.execute('DELETE FROM codes WHERE customer_id=? AND purpose=?',(cid,purpose))
    audit(db,cid,'code_verified',purpose)
    return True

def deliver_code(email,code):
    if cfg.debug_otp and cfg.public_base_url.startswith('http://127.0.0.1:'):
        print(f'LOCAL TEST OTP for {email}: {code}',flush=True)
        return
    if cfg.resend_api_key:
        if not cfg.resend_from:
            raise HTTPException(503,'Resend sender not configured. Please contact support.')
        # Render's free tier blocks common SMTP ports; HTTPS email delivery
        # works without opening network ports. The sender must be verified.
        payload={'from':cfg.resend_from,'to':[email],
                 'subject':f'{code} is your StartUpTrading activation code',
                 'text':f'Your StartUpTrading activation code is {code}. It expires in 10 minutes. If you did not request it, ignore this email.',
                 'html':email_templates.code_email(code,cfg.support_email)}
        try:
            with httpx.Client(timeout=12) as client:
                response=client.post('https://api.resend.com/emails',json=payload,
                    headers={'Authorization':'Bearer '+cfg.resend_api_key})
            if response.status_code not in (200,201,202):
                raise HTTPException(503,'Email delivery is temporarily unavailable')
        except httpx.RequestError:
            raise HTTPException(503,'Email delivery is temporarily unavailable')
        return
    if not all([cfg.smtp_host,cfg.smtp_from]): raise HTTPException(503,'Email service not configured. Please contact support.')
    msg=EmailMessage();msg['Subject']=f'{code} is your StartUpTrading activation code';msg['From']=cfg.smtp_from;msg['To']=email
    msg.set_content(f'Your StartUpTrading activation code is {code}. It expires in 10 minutes. If you did not request it, ignore this email.')
    msg.add_alternative(email_templates.code_email(code,cfg.support_email),subtype='html')
    try:
        if cfg.smtp_port==465:
            with smtplib.SMTP_SSL(cfg.smtp_host,cfg.smtp_port,timeout=12) as server:
                if cfg.smtp_username: server.login(cfg.smtp_username,cfg.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host,cfg.smtp_port,timeout=12) as server:
                server.starttls(context=ssl.create_default_context())
                if cfg.smtp_username: server.login(cfg.smtp_username,cfg.smtp_password)
                server.send_message(msg)
    except (OSError,smtplib.SMTPException): raise HTTPException(503,'Email delivery is temporarily unavailable')

def session_customer(request):
    token=request.cookies.get('sut_session','')
    if len(token)<30: raise HTTPException(403,'Use your private activation invitation')
    with connect(cfg) as db:
        row=db.execute('SELECT customer_id FROM sessions WHERE token_hash=? AND expires_at>?',(hash_token(token),int(time.time()))).fetchone()
        if not row: raise HTTPException(403,'Activation session has expired')
        c=customer(db,row['customer_id'])
    return c,token

def csrf(token): return hashlib.sha256(('csrf:'+token).encode()).hexdigest()
def check_csrf(request,token,provided):
    if not hmac.compare_digest(csrf(token),provided): raise HTTPException(403,'Invalid form security token')

def site_links():
    return {'support_email':cfg.support_email,'discord_url':cfg.discord_url,'checkout_url':cfg.checkout_url,
            'whop_hub_url':cfg.whop_hub_url,'setup_url':cfg.indicator_setup_url,
            'affiliate':cfg.affiliate_url or 'https://ninjatrader.com/'}

def page(request,template,status_code=200,**kw):
    return templates.TemplateResponse(request,template,{'site':site_links(),**kw},status_code=status_code)

def render_error(request,key,status):
    title,body,action=customer_errors.MESSAGES[key]
    return page(request,'error.html',status_code=status,status=status,key=key,title=title,body=body,action=action)

async def event_worker():
    # One worker process only (Render Docker default is one Uvicorn worker).
    # Durable queued events and periodic reconciliation recover from missed webhooks.
    while True:
        await asyncio.sleep(max(30,cfg.poll_seconds))
        try:
            with connect(cfg) as db:
                queue=[dict(r) for r in db.execute("SELECT * FROM webhook_events WHERE state IN ('queued','retry') ORDER BY received_at LIMIT 50")]
            for event in queue:
                try:
                    state=await handle_queued_event(cfg,engine.whop,engine,event)
                    with connect(cfg) as db:
                        db.execute('UPDATE webhook_events SET state=?,last_error=NULL WHERE webhook_id=?',
                                   (state,event['webhook_id']))
                except Exception as exc:
                    with connect(cfg) as db:
                        db.execute('UPDATE webhook_events SET state=?,last_error=? WHERE webhook_id=?',
                                   ('retry',str(exc)[:130],event['webhook_id']))
            with connect(cfg) as db:
                ids=[r['id'] for r in db.execute('SELECT id FROM customers ORDER BY updated_at ASC LIMIT 100').fetchall()]
            for cid in ids:
                try:await engine.reconcile(cid)
                except Exception as exc:
                    with connect(cfg) as db:audit(db,cid,'reconcile_retry_needed',str(exc)[:140])
            with connect(cfg) as db:
                purge_expired(db)
                lifecycle_emails.schedule_reminders(db)
            await process_pending(cfg)
            with connect(cfg) as db:issues=attention.find_issues(db,cfg)
            await alerts.notify(cfg,lambda:connect(cfg),issues)
        except Exception: pass

@asynccontextmanager
async def lifespan(app):
    with connect(cfg):pass
    task=asyncio.create_task(event_worker()) if cfg.run_reconciler else None
    yield
    if task:task.cancel()

app=FastAPI(title='StartUpTrading Licensing Bridge',docs_url=None,redoc_url=None,lifespan=lifespan)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')
templates=Jinja2Templates(directory=str(ROOT/'templates'))
customer_errors.install(app,lambda request,key,status:render_error(request,key,status))

# Paths that must keep answering on every hostname: Whop webhooks and the OAuth
# callback (Whop may still deliver to the old address during the switch), and
# health checks.
CANONICAL_EXEMPT=('/webhooks','/health','/oauth/callback')

def canonical_target(request):
    """URL on PUBLIC_BASE_URL to redirect to, or None to serve the request here."""
    base=cfg.public_base_url
    if not (cfg.canonical_redirect and base.startswith('https://')):return None
    if request.method not in ('GET','HEAD') or request.url.path.startswith(CANONICAL_EXEMPT):return None
    want=urlsplit(base).netloc.lower()
    host=request.headers.get('host','').lower()
    if not host or host==want:return None
    query=('?'+request.url.query) if request.url.query else ''
    return base+request.url.path+query

@app.middleware('http')
async def canonical_host(request,call_next):
    target=canonical_target(request)
    # 302, not 301: a permanent redirect would be cached by browsers and hard
    # to undo if the setting is ever changed.
    if target:return RedirectResponse(target,status_code=302)
    return await call_next(request)

@app.middleware('http')
async def secure_headers(request,call_next):
    resp=await call_next(request)
    resp.headers['Cache-Control']='no-store';resp.headers['Referrer-Policy']='no-referrer'
    resp.headers['X-Content-Type-Options']='nosniff';resp.headers['X-Frame-Options']='DENY'
    resp.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    resp.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=(), payment=()'
    if cfg.public_base_url.startswith('https://'):
        # Tell browsers to only ever use HTTPS for this host (not subdomains).
        resp.headers['Strict-Transport-Security']='max-age=31536000'
    return resp

@app.get('/health')
def health():
    return {'status':'ok','mode':'single_test_membership' if cfg.license_writes else 'observe_only',
            'whop_configured':bool(cfg.whop_api_key),'webhook_configured':bool(cfg.whop_webhook_secret),
            'ninjatrader_configured':bool(cfg.nt_cid and cfg.nt_sec), 'reconciler_enabled':cfg.run_reconciler,
            'public_host':urlsplit(cfg.public_base_url).netloc,'canonical_redirect':cfg.canonical_redirect}

@app.get('/',response_class=HTMLResponse)
def index(request:Request):
    return page(request,'index.html',indicators=INDICATORS,affiliate=cfg.affiliate_url,admin_preview_enabled=cfg.admin_test_enabled and preview_allowlist_configured())


def preview_allowlist_configured():
    return cfg.admin_test_user_id.startswith('user_') or ('@' in cfg.admin_test_email and len(cfg.admin_test_email)<255)

def preview_identity_matches(userid,email,email_verified):
    id_ok=cfg.admin_test_user_id.startswith('user_') and hmac.compare_digest(userid,cfg.admin_test_user_id)
    email_ok=bool('@' in cfg.admin_test_email and email_verified is True and
                  hmac.compare_digest(email,cfg.admin_test_email))
    return id_ok or email_ok

def admin_test_authorized(request:Request):
    # This independent preview session cannot be used as a paying customer session.
    if not cfg.admin_test_enabled or not preview_allowlist_configured():
        raise HTTPException(404, 'Admin preview disabled')
    token=request.cookies.get('sut_admin_preview','')
    if len(token)<30:
        raise HTTPException(403, 'Admin preview requires Whop sign-in')
    with connect(cfg) as db:
        row=db.execute('SELECT whop_user_id,verified_email FROM admin_test_sessions WHERE token_hash=? AND expires_at>?',
                       (hash_token(token),int(time.time()))).fetchone()
    if not row or not preview_identity_matches(row['whop_user_id'],row['verified_email'] or '',bool(row['verified_email'])):
        raise HTTPException(403, 'Admin preview session invalid')
    return token

@app.get('/admin-test/login')
def admin_test_login():
    if not (cfg.admin_test_enabled and preview_allowlist_configured()):
        raise HTTPException(404, 'Admin preview disabled')
    if not (cfg.whop_client_id and cfg.whop_client_secret):
        raise HTTPException(503, 'Whop OAuth not configured')
    state=secrets.token_urlsafe(32); verifier=secrets.token_urlsafe(40); nonce=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with connect(cfg) as db:
        db.execute('INSERT INTO admin_test_oauth_states(state_hash,verifier,nonce,expires_at) VALUES(?,?,?,?)',
                   (hash_token(state),verifier,nonce,int(time.time())+600))
    url='https://api.whop.com/oauth/authorize?'+urlencode({
        'response_type':'code','client_id':cfg.whop_client_id,
        'redirect_uri':cfg.public_base_url+'/oauth/callback',
        'scope':'openid profile email','state':state,'nonce':nonce,
        'code_challenge':challenge,'code_challenge_method':'S256'})
    return RedirectResponse(url,302)

@app.get('/admin-test/diagnostics')
async def admin_test_diagnostics(request:Request):
    # Allowlisted, OAuth-verified admin only. Read-only by construction.
    admin_test_authorized(request)
    results=await run_checks(cfg)
    return JSONResponse(results,headers={'Cache-Control':'no-store'})

@app.get('/admin-test/member-lookup')
async def admin_member_lookup(request:Request,member_id:str='',expected_user_id:str=''):
    # Read-only diagnostic for operator; do not return customer emails or secrets.
    admin_test_authorized(request)
    if not member_id:
        raise HTTPException(400,'Supply ?member_id=mber_...')
    try:
        matches=await resolve_member(cfg,member_id,expected_user_id)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except (IntegrationError,httpx.RequestError,ValueError):
        raise HTTPException(502,'Whop membership lookup unavailable; inspect private logs')
    with connect(cfg) as db:
        for row in matches:
            if not row['membership_id']:continue
            customer_row=db.execute('SELECT id,whop_user_id,verified,status FROM customers WHERE membership_id=?',
                                   (row['membership_id'],)).fetchone()
            row['customer_record_exists']=customer_row is not None
            row['account_link_verified']=bool(customer_row['verified']) if customer_row else False
            row['stored_whop_user_matches']=bool(customer_row and customer_row['whop_user_id']==expected_user_id) if expected_user_id else None
    return JSONResponse({'mode':'READ_ONLY','member_id':member_id,'results':matches,
        'note':'No customer record, email or license has been modified. A missing customer record is expected before intake.'},
        headers={'Cache-Control':'no-store'})


async def admin_intake_target(membership_id,expected_user_id,member_id):
    """Verify a specific subscription using the same Whop list route as the proven lookup.

    Some real memberships have a valid list `variant_id` while their direct-detail
    request fails; switching endpoints here previously broke verified intake.
    """
    if not isinstance(membership_id,str) or not membership_id.startswith('mem_') or len(membership_id)>100:
        raise HTTPException(400,'Enter an actual Whop subscription ID (mem_...)')
    if not isinstance(expected_user_id,str) or not expected_user_id.startswith('user_') or len(expected_user_id)>100:
        raise HTTPException(400,'Enter the expected Whop user ID (user_...)')
    try:
        # Use the exact member_id-filtered route that successfully verified this
        # customer. Never substitute the admin's OAuth identity for the buyer.
        if member_id:
            m=await verified_subscription_by_member(cfg,member_id,membership_id,expected_user_id)
        else:
            # Legacy intake callers retain the prior strict lookup; operators
            # should supply mber_ to use the confirmed working API route.
            m=await engine.whop.find_subscription_for_user(membership_id,expected_user_id)
    except (IntegrationError,httpx.RequestError) as exc:
        raise HTTPException(502,'Whop subscription listing unavailable; check Render logs') from exc
    if m is None:
        raise HTTPException(409,'Subscription not found for expected Whop user')
    from clients import membership_entitlement
    if not membership_entitlement(m):
        raise HTTPException(409,'Membership is not eligible for the approved StartUpTrading product and plan')
    return m

@app.get('/admin-test/intake',response_class=HTMLResponse)
async def admin_intake_form(request:Request,membership_id:str='',expected_user_id:str='',member_id:str=''):
    token=admin_test_authorized(request)
    # No mutation on GET; render existing admin session + double-submit protection.
    from html import escape
    safe_id=escape(membership_id,quote=True)
    safe_uid=escape(expected_user_id,quote=True)
    safe_member=escape(member_id,quote=True)
    html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Intake verification</title>
    <meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="font:16px system-ui;max-width:670px;margin:4rem auto;padding:1rem">
    <h1>StartUpTrading: purchaser intake verification</h1>
    <p>For a genuine approved Whop subscription only. This creates or checks the customer record in PostgreSQL.
    It never creates indicator licenses, verifies NinjaTrader identity, or sends an activation email.</p>
    <form method="post" action="/admin-test/intake">
      <label>Whop Member ID (mber_)<br><input name="member_id" required maxlength="100" value="{safe_member}" style="width:95%;padding:9px"></label><br><br>
      <label>Subscription ID (mem_)<br><input name="membership_id" required maxlength="100" value="{safe_id}" style="width:95%;padding:9px"></label><br><br>
      <label>Expected Whop user ID (user_)<br><input name="expected_user_id" required maxlength="100" value="{safe_uid}" style="width:95%;padding:9px"></label><br><br>
      <input type="hidden" name="csrf_token" value="{csrf(token)}">
      <button type="submit" style="padding:12px 18px;cursor:pointer">Verify membership and record intake</button>
    </form><p><a href="/admin-test">Back to admin preview</a></p></body></html>'''
    return HTMLResponse(html,headers={'Cache-Control':'no-store'})

@app.post('/admin-test/intake')
async def admin_intake_run(request:Request,csrf_token:str=Form(...),membership_id:str=Form(...),expected_user_id:str=Form(...),member_id:str=Form('')):
    token=admin_test_authorized(request)
    check_csrf(request,token,csrf_token)
    if cfg.license_writes:
        raise HTTPException(409,'Disable license writes before running purchaser intake verification')
    verified_membership=await admin_intake_target(membership_id,expected_user_id,member_id)
    try:
        # Real purchaser-intake path used by signed webhook processing. No license reconcile here.
        imported=await import_membership(cfg,engine.whop,membership_id,verified_membership=verified_membership)
    except (IntegrationError,httpx.RequestError) as exc:
        raise HTTPException(502,'Purchaser intake cannot complete: check Whop email access and server logs') from exc
    if imported.get('state') not in ('created','updated'):
        raise HTTPException(409,'Whop purchaser intake was not eligible to create a record')
    with connect(cfg) as db:
        row=db.execute('SELECT id,membership_id,whop_user_id,verified,buyer_email_verified,nt_email FROM customers WHERE membership_id=?',
                       (membership_id,)).fetchone()
        license_count=db.execute('SELECT COUNT(*) FROM licenses WHERE customer_id=?',(row['id'],)).fetchone()[0]
        crm=db.execute('SELECT status FROM crm_sync WHERE customer_id=?',(row['id'],)).fetchone()
    # Do not expose PII; this is a membership-data test, not customer account access.
    return JSONResponse({'mode':'INTAKE_ONLY','membership_id':membership_id,
        'result':imported['state'],'customer_record_exists':bool(row),
        'user_matches_expected':bool(row and row['whop_user_id']==expected_user_id),
        'ninjatrader_email_verified':bool(row and row['verified']),
        'buyer_email_verified':bool(row and row['buyer_email_verified']),
        'license_rows':license_count,'crm_outbox_status':crm['status'] if crm else None,
        'activation_email_sent_by_this_request':False,
        'notes':'Whop-eligible purchaser saved; customer must still complete authenticated onboarding and NinjaTrader email verification.'},
        headers={'Cache-Control':'no-store'})

@app.get('/admin-test',response_class=HTMLResponse)
def admin_test(request:Request):
    token=admin_test_authorized(request)
    return page(request,'admin_test.html',affiliate=cfg.affiliate_url,
                preview_email=cfg.allowed_test_email,csrf=csrf(token),
                email_test_ready=bool(cfg.resend_api_key and cfg.resend_from and cfg.admin_test_email and cfg.whop_client_secret),
                email_test_state=request.query_params.get('email_test',''))

@app.post('/admin-test/preview',response_class=HTMLResponse)
def admin_test_preview(request:Request,csrf_token:str=Form(...),path:str=Form(...),nt_email:str=Form('')):
    token=admin_test_authorized(request);check_csrf(request,token,csrf_token)
    if path not in ('existing','new'):raise HTTPException(400,'Unknown onboarding path')
    email=nt_email.strip().lower()
    if email and (len(email)>100 or '@' not in email or '.' not in email.rsplit('@',1)[-1]):
        raise HTTPException(400,'Invalid email')
    if cfg.allowed_test_email and email and not hmac.compare_digest(email,cfg.allowed_test_email):
        raise HTTPException(403,'Only the configured test email is permitted')
    return page(request,'admin_test.html',affiliate=cfg.affiliate_url,
                preview_email=cfg.allowed_test_email,csrf=csrf(token),path=path,
                email=email,preview_complete=True)


def admin_email_identity(request:Request):
    # Admin preview sessions are NOT customer sessions and grant no license access.
    admin_test_authorized(request)
    if not cfg.admin_test_email or not cfg.resend_api_key or not cfg.resend_from or not cfg.whop_client_secret:
        raise HTTPException(503,'Test email is not configured')
    token=request.cookies.get('sut_admin_preview','')
    with connect(cfg) as db:
        row=db.execute('SELECT whop_user_id,verified_email FROM admin_test_sessions WHERE token_hash=? AND expires_at>?',
                       (hash_token(token),int(time.time()))).fetchone()
    if not row or not row['verified_email'] or not hmac.compare_digest(row['verified_email'].lower(),cfg.admin_test_email):
        raise HTTPException(403,'Verified admin email is required for test delivery')
    return token,row['whop_user_id']

@app.post('/admin-test/email/send')
def admin_test_send_email(request:Request,csrf_token:str=Form(...)):
    token,userid=admin_email_identity(request);check_csrf(request,token,csrf_token)
    now=int(time.time())
    with connect(cfg) as db:
        old=db.execute('SELECT requested_at FROM admin_email_tests WHERE whop_user_id=?',(userid,)).fetchone()
        if old and now-int(old['requested_at'])<90:
            raise HTTPException(429,'Please wait 90 seconds before requesting another test code')
    code=f'{secrets.randbelow(1000000):06}'
    digest=hmac.new(cfg.whop_client_secret.encode(),f'admin-email-test:{userid}:{code}'.encode(),hashlib.sha256).hexdigest()
    # First attempt delivery; a delivery error cannot falsely record a sent test code.
    deliver_code(cfg.admin_test_email,code)
    with connect(cfg) as db:
        db.execute('INSERT INTO admin_email_tests(whop_user_id,code_hash,expires_at,attempts,requested_at,verified_at) VALUES(?,?,?,?,?,?) '
                   'ON CONFLICT(whop_user_id) DO UPDATE SET code_hash=excluded.code_hash,expires_at=excluded.expires_at,attempts=0,requested_at=excluded.requested_at,verified_at=NULL',
                   (userid,digest,now+600,0,now,None))
    return RedirectResponse('/admin-test?email_test=sent',303)

@app.post('/admin-test/email/verify')
def admin_test_verify_email(request:Request,csrf_token:str=Form(...),code:str=Form(...)):
    token,userid=admin_email_identity(request);check_csrf(request,token,csrf_token)
    now=int(time.time())
    if not (len(code)==6 and code.isdigit()):raise HTTPException(400,'Enter the six-digit verification code')
    with connect(cfg) as db:
        row=db.execute('SELECT code_hash,expires_at,attempts FROM admin_email_tests WHERE whop_user_id=?',(userid,)).fetchone()
        if not row or row['expires_at']<now or row['attempts']>=5:
            raise HTTPException(400,'Code expired or too many attempts')
        # Record the attempt, even when code does not match.
        db.execute('UPDATE admin_email_tests SET attempts=attempts+1 WHERE whop_user_id=?',(userid,))
        digest=hmac.new(cfg.whop_client_secret.encode(),f'admin-email-test:{userid}:{code}'.encode(),hashlib.sha256).hexdigest()
        valid=hmac.compare_digest(digest,row['code_hash'])
        if valid:
            db.execute('UPDATE admin_email_tests SET verified_at=?,code_hash=NULL WHERE whop_user_id=?',(now,userid))
    if not valid:raise HTTPException(400,'Incorrect verification code')
    return RedirectResponse('/admin-test?email_test=verified',303)

@app.post('/admin-test/logout')
def admin_test_logout(request:Request,csrf_token:str=Form(...)):
    token=admin_test_authorized(request);check_csrf(request,token,csrf_token)
    with connect(cfg) as db:
        db.execute('DELETE FROM admin_test_sessions WHERE token_hash=?',(hash_token(token),))
    response=RedirectResponse('/',303); response.delete_cookie('sut_admin_preview')
    return response

@app.get('/oauth/login')
def oauth_login():
    if not (cfg.whop_client_id and cfg.whop_client_secret):raise HTTPException(503,'Whop OAuth not configured')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(40);nonce=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with connect(cfg) as db:
        purge_expired(db)
        db.execute('INSERT INTO oauth_states(state_hash,verifier,nonce,expires_at) VALUES(?,?,?,?)',
                   (hash_token(state),verifier,nonce,int(time.time())+600))
    url='https://api.whop.com/oauth/authorize?'+urlencode({
        'response_type':'code','client_id':cfg.whop_client_id,
        'redirect_uri':cfg.public_base_url+'/oauth/callback',
        'scope':'openid profile email','state':state,'nonce':nonce,
        'code_challenge':challenge,'code_challenge_method':'S256'})
    return RedirectResponse(url,302)

@app.get('/oauth/callback')
async def oauth_callback(code:str='',state:str='',error:str=''):
    if error or not code or not state:raise HTTPException(400,'Whop sign-in declined or incomplete')
    with connect(cfg) as db:
        row=db.execute('SELECT verifier,nonce FROM oauth_states WHERE state_hash=? AND expires_at>?',(hash_token(state),int(time.time()))).fetchone()
        admin_preview=False
        if not row:
            row=db.execute('SELECT verifier,nonce FROM admin_test_oauth_states WHERE state_hash=? AND expires_at>?',
                           (hash_token(state),int(time.time()))).fetchone()
            admin_preview=bool(row)
        if not row:raise HTTPException(403,'Sign-in state expired')
        db.execute('DELETE FROM '+('admin_test_oauth_states' if admin_preview else 'oauth_states')+' WHERE state_hash=?',
                   (hash_token(state),))
        verifier,nonce=row['verifier'],row['nonce']
    async with httpx.AsyncClient(timeout=18) as client:
        r=await client.post('https://api.whop.com/oauth/token',json={
            'grant_type':'authorization_code','code':code,
            'redirect_uri':cfg.public_base_url+'/oauth/callback',
            'client_id':cfg.whop_client_id,'client_secret':cfg.whop_client_secret,
            'code_verifier':verifier})
        if r.status_code!=200:raise HTTPException(502,'Whop token exchange failed')
        tokens=r.json()
        if not tokens.get('access_token'):raise HTTPException(502,'Whop token missing')
        # Decode only the nonce claim for correlation; user identity comes from the authenticated userinfo endpoint.
        idtoken=tokens.get('id_token','')
        try:
            payload=idtoken.split('.')[1]
            claim=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            if not hmac.compare_digest(str(claim.get('nonce','')),nonce):raise ValueError('Nonce mismatch')
        except Exception:raise HTTPException(403,'Whop identity nonce verification failed')
        info=await client.get('https://api.whop.com/oauth/userinfo',headers={'Authorization':'Bearer '+tokens['access_token']})
    if info.status_code!=200:raise HTTPException(502,'Whop profile lookup failed')
    person=info.json();userid=person.get('sub','');email=str(person.get('email') or '').strip().lower()
    if not userid.startswith('user_') or '@' not in email:raise HTTPException(403,'Whop profile is missing required identity')
    if admin_preview:
        if not (cfg.admin_test_enabled and preview_identity_matches(userid,email,person.get('email_verified'))):
            raise HTTPException(403,'Whop account is not allowlisted for admin preview')
        token=secrets.token_urlsafe(36)
        with connect(cfg) as db:
            db.execute('INSERT INTO admin_test_sessions(token_hash,whop_user_id,verified_email,expires_at) VALUES(?,?,?,?)',
                       (hash_token(token),userid,email if person.get('email_verified') is True else None,int(time.time())+3600))
        response=RedirectResponse('/admin-test',303)
        response.set_cookie('sut_admin_preview',token,httponly=True,
             secure=not cfg.public_base_url.startswith('http://127.0.0.1:'),samesite='lax',max_age=3600)
        return response
    try: memberships=await engine.whop.memberships_for_user(userid)
    except IntegrationError:raise HTTPException(502,'Whop membership could not be checked')
    eligible=[membership_entitlement(m) for m in memberships]
    eligible=[m for m in eligible if m and m.get('user_id')==userid]
    if not eligible:raise HTTPException(403,'No eligible StartUpTrading membership found for this Whop user')
    ent=sorted(eligible,key=lambda x:x['paid_through'],reverse=True)[0]
    membership_id=ent['membership_id']
    with connect(cfg) as db:
        row=db.execute('SELECT * FROM customers WHERE membership_id=?',(membership_id,)).fetchone()
        if row and row['whop_user_id'] and row['whop_user_id']!=userid:raise HTTPException(409,'Membership identity conflict')
        if row:
            cid=row['id']
            db.execute('UPDATE customers SET whop_user_id=?,plan_id=?,paid_through=?,buyer_email_verified=CASE WHEN ? THEN 1 ELSE buyer_email_verified END,updated_at=? WHERE id=?',
                       (userid,ent['plan_id'],ent['paid_through'],person.get('email_verified') is True,int(time.time()),cid))
        else:
            cur=db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,plan_id,paid_through,status,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                           (membership_id,userid,email,1 if person.get('email_verified') is True else 0,ent['plan_id'],ent['paid_through'],
                            'buyer_verified' if person.get('email_verified') is True else 'invited',int(time.time())))
            cid=cur.lastrowid
        request_crm_sync(db,cid)
        # Whop states the email is verified; otherwise the existing buyer-email code remains required.
        if person.get('email_verified') is True and not row:
            audit(db,cid,'whop_verified_identity','OAuth userinfo and eligible membership')
        session=secrets.token_urlsafe(36)
        db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)',
                   (hash_token(session),cid,int(time.time())+86400*14))
    response=RedirectResponse('/onboarding',303)
    response.set_cookie('sut_session',session,httponly=True,
        secure=not cfg.public_base_url.startswith('http://127.0.0.1:'),samesite='lax',max_age=1209600)
    return response

def valid_invite(db,invite_token):
    return db.execute('SELECT customer_id FROM invites WHERE token_hash=? AND expires_at>? AND used_at IS NULL',
                      (hash_token(invite_token),int(time.time()))).fetchone()

@app.get('/activate/{invite_token}',response_class=HTMLResponse)
def invite_landing(request:Request,invite_token:str):
    # Opening the link must not use it up: email security scanners (Outlook Safe
    # Links, Gmail) fetch links automatically. The visitor confirms with a POST.
    with connect(cfg) as db:
        if not valid_invite(db,invite_token):raise HTTPException(404,'Invitation invalid or expired')
    return page(request,'invite_accept.html',token=invite_token)

@app.post('/activate/{invite_token}')
def accept_invite(request:Request,invite_token:str):
    with connect(cfg) as db:
        row=db.execute('SELECT customer_id FROM invites WHERE token_hash=? AND expires_at>? AND used_at IS NULL',(hash_token(invite_token),int(time.time()))).fetchone()
        if not row:raise HTTPException(404,'Invitation invalid or expired')
        db.execute('UPDATE invites SET used_at=? WHERE token_hash=?',(int(time.time()),hash_token(invite_token)))
        session=secrets.token_urlsafe(36)
        db.execute('INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES(?,?,?)',(hash_token(session),row['customer_id'],int(time.time())+86400*14))
    resp=RedirectResponse('/onboarding',status_code=303)
    resp.set_cookie('sut_session',session,httponly=True,secure=not cfg.public_base_url.startswith('http://127.0.0.1:'),samesite='lax',max_age=1209600)
    return resp

@app.get('/onboarding',response_class=HTMLResponse)
def onboarding(request:Request):
    c,token=session_customer(request)
    with connect(cfg) as db:
        licenses=[dict(r) for r in db.execute('SELECT * FROM licenses WHERE customer_id=? ORDER BY product_id',(c['id'],))]
    error=customer_errors.message_for(request.query_params.get('error',''))
    message=request.query_params.get('message','')
    return page(request,'onboarding.html',c=c,csrf=csrf(token),indicators=INDICATORS,licenses=licenses,
                affiliate=cfg.affiliate_url,error=error,message=message,view=onboarding_view(c,licenses))

ACTIVE_STATES={'created','renewed','unchanged'}
LICENSE_LABELS={'created':'Active','renewed':'Active','unchanged':'Active','expired':'Expired',
                'already_expired':'Expired','absent':'Not active','error':'Needs attention'}

def onboarding_view(c,licenses):
    """Work out which step the member is on and how to describe their indicators."""
    by_pid={int(l['product_id']):l for l in licenses}
    items=[]
    for pid,name in INDICATORS.items():
        row=by_pid.get(pid)
        state=row['state'] if row else None
        if state in ACTIVE_STATES: tone='ok'
        elif state=='error': tone='warn'
        elif state in ('expired','already_expired','absent'): tone='off'
        else: tone='wait'
        label=LICENSE_LABELS.get(state,'Activating' if c['verified'] else 'Waiting for step 2')
        items.append({'pid':pid,'name':name,'label':label,'tone':tone})
    if not c['buyer_email_verified']: step=1
    elif not c['verified'] and not c['nt_email']: step=2
    elif not c['verified']: step=3
    else: step=4
    all_active=all(i['tone']=='ok' for i in items)
    visual={1:1,2:2,3:2,4:3}[step]
    stepper=[]
    for n,label in enumerate(['Membership','NinjaTrader email','Indicators'],1):
        if n<visual or (n==3 and all_active and step==4):stepper.append((label,'done'))
        elif n==visual:stepper.append((label,'current'))
        else:stepper.append((label,''))
    return {'step':step,'visual_step':visual,'stepper':stepper,'indicators':items,'all_active':all_active,
            'ineligible':c['status']=='ineligible','code_pending':bool(c['nt_email'] and not c['verified'])}

@app.post('/onboarding/buyer-code')
def buyer_code(request:Request,csrf_token:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    with connect(cfg) as db: code=issue_code(db,c['id'],'buyer',c['buyer_email'])
    deliver_code(c['buyer_email'],code)
    return RedirectResponse('/onboarding?message=buyer_sent',303)

@app.post('/onboarding/buyer-verify')
def buyer_verify(request:Request,csrf_token:str=Form(...),code:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    with connect(cfg) as db:
        ok=verify_code(db,c['id'],'buyer',code)
        if ok:
            db.execute('UPDATE customers SET buyer_email_verified=1,status=?,updated_at=? WHERE id=?',('buyer_verified',int(time.time()),c['id']))
    # Raise only after the transaction commits, so the failed attempt is counted.
    if not ok:raise HTTPException(400,'Invalid or expired verification code')
    return RedirectResponse('/onboarding?message=buyer_verified',303)

@app.post('/onboarding/nt-code')
def nt_code(request:Request,csrf_token:str=Form(...),nt_email:str=Form(...),path:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    if not c['buyer_email_verified']:
        raise HTTPException(403,'Verify your Whop purchasing email first')
    email=nt_email.strip().lower()
    if len(email)>64 or '@' not in email or '.' not in email.rsplit('@',1)[-1]:raise HTTPException(400,'Valid NinjaTrader email required')
    if path not in ('existing','new'):raise HTTPException(400,'Invalid onboarding path')
    with connect(cfg) as db:
        # Once linked, self-service cannot silently detach licenses or switch accounts.
        # Support must first reconcile/revoke owned licenses through a reviewed process.
        if c['verified']:
            raise HTTPException(409,'NinjaTrader account already linked; contact support to change it')
        prior=db.execute('SELECT 1 FROM licenses WHERE customer_id=? LIMIT 1',(c['id'],)).fetchone()
        if prior:
            raise HTTPException(409,'Existing indicator licenses require support review before relinking')
        holder=returning_member.holder_of(db,email,c['id'])
        # A returning member (same Whop user, earlier membership) may reclaim their
        # own NinjaTrader link; the transfer itself is checked again at verify time.
        if holder and not returning_member.same_whop_user(holder,c):
            raise HTTPException(409,'That NinjaTrader email is linked to another account; contact support')
        db.execute('UPDATE customers SET nt_email=?,verified=0,onboarding_path=?,updated_at=? WHERE id=?',(email,path,int(time.time()),c['id']))
        code=issue_code(db,c['id'],'nt',email)
    deliver_code(email,code)
    return RedirectResponse('/onboarding?message=nt_sent',303)

@app.post('/onboarding/nt-verify')
async def nt_verify(request:Request,csrf_token:str=Form(...),code:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    # Returning member: if the email is held by this same Whop user's earlier
    # membership, confirm with Whop that it has ended BEFORE using up the code.
    with connect(cfg) as db:
        pending=db.execute('SELECT nt_email FROM customers WHERE id=?',(c['id'],)).fetchone()
        holder=returning_member.holder_of(db,pending['nt_email'],c['id']) if pending and pending['nt_email'] else None
    if holder:
        if not returning_member.same_whop_user(holder,c):
            raise HTTPException(409,'That NinjaTrader email is already linked')
        try:await returning_member.confirm_holder_ended(engine,holder)
        except returning_member.StillActiveElsewhere:
            raise HTTPException(409,'That NinjaTrader account is still active on another membership; contact support')
        except IntegrationError:
            raise HTTPException(502,'Whop membership could not be checked')
    if holder:
        # Hold the old record's sync lease so its reconcile can't run mid-transfer.
        try:
            with returning_member.HolderLease(engine,holder['id']):
                _nt_verify_link(c,code,holder)
        except returning_member.TransferBusy:
            raise HTTPException(409,'Wait a minute and try again: a license sync is in progress')
    else:
        _nt_verify_link(c,code,None)
    try:await engine.reconcile(c['id'])
    except IntegrationError as exc:
        with connect(cfg) as db:audit(db,c['id'],'reconcile_retry_needed',str(exc)[:140])
    return RedirectResponse('/onboarding?message=nt_verified',303)

def _nt_verify_link(c,code,expected_holder):
    with connect(cfg) as db:
        if not c['buyer_email_verified']:
            raise HTTPException(403,'Membership email must be verified first')
        current=db.execute('SELECT nt_email,verified FROM customers WHERE id=?',(c['id'],)).fetchone()
        if not current or not current['nt_email'] or current['verified']:
            raise HTTPException(409,'Account linking is not pending')
        holder=returning_member.holder_of(db,current['nt_email'],c['id'])
        # The holder must be exactly the one confirmed with Whop above (or none).
        if holder and (not expected_holder or holder['id']!=expected_holder['id']):
            raise HTTPException(409,'That NinjaTrader email is already linked')
        prior=db.execute('SELECT 1 FROM licenses WHERE customer_id=? LIMIT 1',(c['id'],)).fetchone()
        if prior:raise HTTPException(409,'Existing licenses require support review')
        code_row=db.execute('SELECT target_email FROM codes WHERE customer_id=? AND purpose=?',(c['id'],'nt')).fetchone()
        if not code_row or code_row['target_email']!=current['nt_email']:
            raise HTTPException(409,'Verification request does not match linked email')
        ok=verify_code(db,c['id'],'nt',code)
        if ok and holder:
            try:returning_member.transfer(db,holder['id'],c['id'],current['nt_email'])
            except IntegrationError as exc:raise HTTPException(409,str(exc))
        elif ok:
            db.execute('UPDATE customers SET verified=1,status=?,updated_at=? WHERE id=?',('pending',int(time.time()),c['id']))
            request_crm_sync(db,c['id'])
    # Raise only after the transaction commits, so the failed attempt is counted
    # (raising inside it rolled the attempt counter back, defeating the 5-try limit).
    if not ok:raise HTTPException(400,'Invalid or expired verification code')

@app.post('/onboarding/refresh')
async def customer_refresh(request:Request,csrf_token:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    try:await engine.reconcile(c['id'])
    except IntegrationError:pass
    return RedirectResponse('/onboarding?message=refreshed',303)

@app.get('/admin',response_class=HTMLResponse)
def admin(request:Request):
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    with connect(cfg) as db:
        customers=[dict(r) for r in db.execute('SELECT * FROM customers ORDER BY updated_at DESC LIMIT 250')]
        events=[dict(r) for r in db.execute('SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT 15')]
        audits=[dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 20')]
        licenses=[dict(r) for r in db.execute('SELECT * FROM licenses ORDER BY updated_at DESC LIMIT 60')]
        issues=attention.find_issues(db,cfg)
    return page(request,'admin.html',customers=customers,events=events,audits=audits,licenses=licenses,
                attention_count=len(issues),attention_high=any(i['severity']=='high' for i in issues),
                writes=cfg.license_writes,allow_email=cfg.allowed_test_email,allow_mem=cfg.allowed_test_membership,
                whop=bool(cfg.whop_api_key),nt=bool(cfg.nt_sec and cfg.nt_cid),base=cfg.public_base_url)

@app.post('/admin/invite',response_class=HTMLResponse)
async def admin_invite(request:Request,membership_id:str=Form(...),buyer_email:str=Form(...)):
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    membership_id=membership_id.strip();buyer_email=buyer_email.strip().lower()
    if len(buyer_email)>200 or '@' not in buyer_email:raise HTTPException(400,'Invalid email')
    m=await engine.whop.membership(membership_id)
    entitlement=membership_entitlement(m)
    if not entitlement:raise HTTPException(403,'Membership is not currently eligible; no invitation created')
    token=secrets.token_urlsafe(40)
    with connect(cfg) as db:
        row=db.execute('SELECT * FROM customers WHERE membership_id=?',(membership_id,)).fetchone()
        if row and row['buyer_email']!=buyer_email:raise HTTPException(409,'Buyer email differs from existing record; manual review required')
        if row:cid=row['id']
        else:
            cur=db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,buyer_email_verified,plan_id,paid_through,status,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                          (membership_id,m.get('user_id'),buyer_email,0,entitlement['plan_id'],entitlement['paid_through'],'invited',int(time.time())))
            cid=cur.lastrowid
        request_crm_sync(db,cid)
        db.execute('INSERT INTO invites(token_hash,customer_id,expires_at) VALUES(?,?,?)',(hash_token(token),cid,int(time.time())+86400*3))
        audit(db,cid,'invitation_created','Admin invitation; buyer email must be verified')
    url=cfg.public_base_url+'/activate/'+quote(token)
    return page(request,'invite.html',url=url,recipient=buyer_email)

@app.get('/admin/attention',response_class=HTMLResponse)
def admin_attention(request:Request):
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    with connect(cfg) as db:issues=attention.find_issues(db,cfg)
    return page(request,'admin_attention.html',issues=issues,
                alerts_on=alerts.valid_url(cfg.alert_webhook_url),worker_on=cfg.run_reconciler)

@app.get('/admin/lifecycle/{cid}')
async def admin_lifecycle(request:Request,cid:int):
    # Read-only: Whop membership GET + NinjaTrader license-list GET, no writes.
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    try:return JSONResponse(await lifecycle.snapshot(cfg,engine,cid))
    except IntegrationError as exc:raise HTTPException(404,str(exc))

@app.post('/admin/reconcile/{cid}')
async def admin_reconcile(request:Request,cid:int):
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    try:result=await engine.reconcile(cid)
    except IntegrationError as exc:result={'error':str(exc)}
    return page(request,'result.html',result=result)

@app.post('/webhooks/whop')
async def webhook(request:Request):
    if not cfg.whop_webhook_secret:raise HTTPException(503,'Webhook secret not configured')
    try:declared=int(request.headers.get('content-length','0'))
    except ValueError:raise HTTPException(400,'Invalid Content-Length')
    if declared>256*1024:raise HTTPException(413,'Oversized webhook')
    raw=await request.body()
    if len(raw)>256*1024:raise HTTPException(413,'Oversized webhook')
    if not verify_webhook(request.headers,raw,cfg.whop_webhook_secret):raise HTTPException(401,'Invalid webhook signature')
    try:event=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise HTTPException(400,'Invalid JSON')
    if not isinstance(event,dict) or not isinstance(event.get('type'),str):raise HTTPException(400,'Invalid webhook event')
    event_type=event['type'];mid=request.headers['webhook-id'];obj=event.get('data') or {}
    objid=(obj.get('membership_id') or ((obj.get('membership') or {}).get('id') if isinstance(obj.get('membership'),dict) else '') or (obj.get('id','') if event_type.startswith('membership.') else '')) if isinstance(obj,dict) else ''
    with connect(cfg) as db:
        cur=db.execute('INSERT OR IGNORE INTO webhook_events(webhook_id,event_type,object_id,received_at,state) VALUES(?,?,?,?,?)',
                       (mid,event_type[:120],str(objid)[:130],int(time.time()),'queued' if event_type in EVENTS else 'ignored'))
        duplicate=cur.rowcount==0
    # Durable event storage is immediate; reconciliation uses up-to-date Whop membership, not payload assumptions.
    return {'received':True,'duplicate':duplicate}

@app.post('/admin/handle-events')
async def handle_events(request:Request):
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    with connect(cfg) as db:
        items=[dict(r) for r in db.execute("SELECT * FROM webhook_events WHERE state='queued' ORDER BY received_at LIMIT 50")]
    outcomes=[]
    for item in items:
        try:
            state=await handle_queued_event(cfg,engine.whop,engine,item)
            with connect(cfg) as db:
                db.execute('UPDATE webhook_events SET state=?,last_error=NULL WHERE webhook_id=?',
                           (state,item['webhook_id']))
        except Exception as exc:
            with connect(cfg) as db:
                db.execute('UPDATE webhook_events SET state=?,last_error=? WHERE webhook_id=?',
                           ('retry',str(exc)[:130],item['webhook_id']))
        outcomes.append(item['webhook_id'])
    return page(request,'result.html',result={'processed_events':len(outcomes),'unmapped_payment_events':'Review webhook events if object IDs do not match membership IDs'})
