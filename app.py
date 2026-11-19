"""StartUpTrading integration: one member activation experience, separate secure licensing engine.
Works with a Whop link and verified buyer email; embedded Whop SSO adapter is NOT claimed.
"""
import asyncio,hashlib,hmac,json,os,secrets, smtplib,ssl,time,base64
from urllib.parse import urlencode
import httpx
from email.message import EmailMessage
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from config import Config,INDICATORS,EVENTS,PLANS
from store import connect,customer,audit
from engine import Engine
from clients import membership_entitlement,IntegrationError
from security import verify_webhook,hash_token,require_admin

cfg=Config(); engine=Engine(cfg)
ROOT=Path(__file__).parent

def issue_code(db,cid,purpose,email):
    now=int(time.time()); old=db.execute('SELECT requested_at FROM codes WHERE customer_id=? AND purpose=?',(cid,purpose)).fetchone()
    if old and now-old['requested_at']<60: raise HTTPException(429,'Wait a minute before requesting another code')
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
    if not all([cfg.smtp_host,cfg.smtp_from]): raise HTTPException(503,'Email service not configured. Please contact support.')
    msg=EmailMessage();msg['Subject']='StartUpTrading activation verification';msg['From']=cfg.smtp_from;msg['To']=email
    msg.set_content(f'Your StartUpTrading activation code is {code}. It expires in 10 minutes. If you did not request it, ignore this email.')
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

def page(request,template,**kw):
    return templates.TemplateResponse(request,template,kw)

async def event_worker():
    # Single-instance helper; for production use one dedicated worker/process and durable jobs.
    while True:
        await asyncio.sleep(max(30,cfg.poll_seconds))
        try:
            with connect(cfg) as db:
                queue=[dict(r) for r in db.execute("SELECT * FROM webhook_events WHERE state IN ('queued','retry') ORDER BY received_at LIMIT 50")]
            for event in queue:
                with connect(cfg) as db:
                    matched=db.execute('SELECT id FROM customers WHERE membership_id=?',(event['object_id'],)).fetchone()
                    if not matched:
                        db.execute('UPDATE webhook_events SET state=? WHERE webhook_id=?',('needs_mapping',event['webhook_id']))
                        continue
                    event_cid=matched['id']
                try:
                    await engine.reconcile(event_cid)
                    with connect(cfg) as db:
                        db.execute('UPDATE webhook_events SET state=?,last_error=NULL WHERE webhook_id=?',('processed',event['webhook_id']))
                except Exception as exc:
                    with connect(cfg) as db:
                        db.execute('UPDATE webhook_events SET state=?,last_error=? WHERE webhook_id=?',('retry',str(exc)[:130],event['webhook_id']))
            with connect(cfg) as db:
                ids=[r['id'] for r in db.execute('SELECT id FROM customers ORDER BY updated_at ASC LIMIT 100').fetchall()]
            for cid in ids:
                try:await engine.reconcile(cid)
                except Exception as exc:
                    with connect(cfg) as db:audit(db,cid,'reconcile_retry_needed',str(exc)[:140])
        except Exception: pass

@asynccontextmanager
async def lifespan(app):
    with connect(cfg):pass
    task=asyncio.create_task(event_worker()) if os.getenv('RUN_RECONCILER','false').lower()=='true' else None
    yield
    if task:task.cancel()

app=FastAPI(title='StartUpTrading Licensing Bridge',docs_url=None,redoc_url=None,lifespan=lifespan)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')
templates=Jinja2Templates(directory=str(ROOT/'templates'))

@app.middleware('http')
async def secure_headers(request,call_next):
    resp=await call_next(request)
    resp.headers['Cache-Control']='no-store';resp.headers['Referrer-Policy']='no-referrer'
    resp.headers['X-Content-Type-Options']='nosniff';resp.headers['X-Frame-Options']='DENY'
    resp.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return resp

@app.get('/health')
def health():
    return {'status':'ok','mode':'test_email_allowlist' if cfg.license_writes else 'observe_only',
            'whop_configured':bool(cfg.whop_api_key),'webhook_configured':bool(cfg.whop_webhook_secret),
            'ninjatrader_configured':bool(cfg.nt_cid and cfg.nt_sec)}

@app.get('/',response_class=HTMLResponse)
def index(request:Request):
    return page(request,'index.html',affiliate=cfg.affiliate_url)


@app.get('/oauth/login')
def oauth_login():
    if not (cfg.whop_client_id and cfg.whop_client_secret):raise HTTPException(503,'Whop OAuth not configured')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(40);nonce=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with connect(cfg) as db:
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
        if not row:raise HTTPException(403,'Sign-in state expired')
        db.execute('DELETE FROM oauth_states WHERE state_hash=?',(hash_token(state),))
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
            db.execute('UPDATE customers SET whop_user_id=?,plan_id=?,paid_through=?,updated_at=? WHERE id=?',
                       (userid,ent['plan_id'],ent['paid_through'],int(time.time()),cid))
        else:
            cur=db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,plan_id,paid_through,status,updated_at) VALUES(?,?,?,?,?,?,?)',
                           (membership_id,userid,email,ent['plan_id'],ent['paid_through'],
                            'buyer_verified' if person.get('email_verified') is True else 'invited',int(time.time())))
            cid=cur.lastrowid
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

@app.get('/activate/{invite_token}')
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
    return page(request,'onboarding.html',c=c,csrf=csrf(token),indicators=INDICATORS,licenses=licenses,affiliate=cfg.affiliate_url)

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
        if not verify_code(db,c['id'],'buyer',code):raise HTTPException(400,'Invalid or expired verification code')
        db.execute('UPDATE customers SET status=?,updated_at=? WHERE id=?',('buyer_verified',int(time.time()),c['id']))
    return RedirectResponse('/onboarding?message=buyer_verified',303)

@app.post('/onboarding/nt-code')
def nt_code(request:Request,csrf_token:str=Form(...),nt_email:str=Form(...),path:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    if c['status'] not in ('buyer_verified','eligible','ineligible','pending','verified') and not c['verified']:
        raise HTTPException(403,'Verify your Whop purchasing email first')
    email=nt_email.strip().lower()
    if len(email)>64 or '@' not in email or '.' not in email.rsplit('@',1)[-1]:raise HTTPException(400,'Valid NinjaTrader email required')
    if path not in ('existing','new'):raise HTTPException(400,'Invalid onboarding path')
    with connect(cfg) as db:
        conflict=db.execute('SELECT id FROM customers WHERE nt_email=? AND id!=? AND verified=1',(email,c['id'])).fetchone()
        if conflict:raise HTTPException(409,'That NinjaTrader email is linked to another account; contact support')
        db.execute('UPDATE customers SET nt_email=?,verified=0,onboarding_path=?,updated_at=? WHERE id=?',(email,path,int(time.time()),c['id']))
        code=issue_code(db,c['id'],'nt',email)
    deliver_code(email,code)
    return RedirectResponse('/onboarding?message=nt_sent',303)

@app.post('/onboarding/nt-verify')
async def nt_verify(request:Request,csrf_token:str=Form(...),code:str=Form(...)):
    c,token=session_customer(request);check_csrf(request,token,csrf_token)
    with connect(cfg) as db:
        if not verify_code(db,c['id'],'nt',code):raise HTTPException(400,'Invalid or expired verification code')
        db.execute('UPDATE customers SET verified=1,status=?,updated_at=? WHERE id=?',('pending',int(time.time()),c['id']))
    try:await engine.reconcile(c['id'])
    except IntegrationError:pass # maintain pending state for admin inspection
    return RedirectResponse('/onboarding?message=nt_verified',303)

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
    return page(request,'admin.html',customers=customers,events=events,audits=audits,licenses=licenses,
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
            cur=db.execute('INSERT INTO customers(membership_id,whop_user_id,buyer_email,plan_id,paid_through,status,updated_at) VALUES(?,?,?,?,?,?,?)',
                          (membership_id,m.get('user_id'),buyer_email,entitlement['plan_id'],entitlement['paid_through'],'invited',int(time.time())))
            cid=cur.lastrowid
        db.execute('INSERT INTO invites(token_hash,customer_id,expires_at) VALUES(?,?,?)',(hash_token(token),cid,int(time.time())+86400*3))
        audit(db,cid,'invitation_created','Admin invitation; buyer email must be verified')
    url=cfg.public_base_url+'/activate/'+quote(token)
    return page(request,'invite.html',url=url,recipient=buyer_email)

@app.post('/admin/reconcile/{cid}')
async def admin_reconcile(request:Request,cid:int):
    require_admin(request,cfg.admin_password,cfg.public_base_url)
    try:result=await engine.reconcile(cid)
    except IntegrationError as exc:result={'error':str(exc)}
    return page(request,'result.html',result=result)

@app.post('/webhooks/whop')
async def webhook(request:Request):
    if not cfg.whop_webhook_secret:raise HTTPException(503,'Webhook secret not configured')
    raw=await request.body()
    if len(raw)>256*1024:raise HTTPException(413,'Oversized webhook')
    if not verify_webhook(request.headers,raw,cfg.whop_webhook_secret):raise HTTPException(401,'Invalid webhook signature')
    try:event=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise HTTPException(400,'Invalid JSON')
    if not isinstance(event,dict) or not isinstance(event.get('type'),str):raise HTTPException(400,'Invalid webhook event')
    event_type=event['type'];mid=request.headers['webhook-id'];obj=event.get('data') or {}
    objid=obj.get('id','') if isinstance(obj,dict) else ''
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
        with connect(cfg) as db:
            matched=[r['id'] for r in db.execute('SELECT id FROM customers WHERE membership_id=?',(item['object_id'],))]
        for cid in matched:
            try:await engine.reconcile(cid)
            except Exception as exc:
                with connect(cfg) as db:db.execute('UPDATE webhook_events SET state=?,last_error=? WHERE webhook_id=?',('retry',str(exc)[:130],item['webhook_id']))
                break
        else:
            with connect(cfg) as db:
                db.execute('UPDATE webhook_events SET state=? WHERE webhook_id=?',('processed' if matched else 'needs_mapping',item['webhook_id']))
        outcomes.append(item['webhook_id'])
    return page(request,'result.html',result={'processed_events':len(outcomes),'unmapped_payment_events':'Review webhook events if object IDs do not match membership IDs'})
