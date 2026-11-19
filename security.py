import base64,hashlib,hmac,threading,time
from urllib.parse import urlsplit
from fastapi import HTTPException, Request

def verify_webhook(headers,raw:bytes,secret:str,now=None):
    mid=headers.get('webhook-id','');ts=headers.get('webhook-timestamp','');sig=headers.get('webhook-signature','')
    if not secret or not mid or len(mid)>200 or not ts or not sig: return False
    try:
        if abs((time.time() if now is None else now)-int(ts))>300: return False
    except (ValueError,OverflowError): return False
    expected=base64.b64encode(hmac.new(secret.encode(),mid.encode()+b'.'+ts.encode()+b'.'+raw,hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(part[3:],expected) for part in sig.split() if part.startswith('v1,'))

def hash_token(token):return hashlib.sha256(token.encode()).hexdigest()

class LoginThrottle:
    """Brute-force protection for the admin login (single-process, in memory).

    After `per_client` failed attempts from one client within `window` seconds,
    that client is locked out for the rest of the window. `global_limit` failures
    from all clients together lock admin login for everyone, which stops an
    attacker rotating IP addresses. Successful logins don't clear the global count.
    """
    def __init__(self,per_client=10,global_limit=50,window=900):
        self.per_client,self.global_limit,self.window=per_client,global_limit,window
        self.fails={};self.lock=threading.Lock()
    def _recent(self,key,now):
        times=[t for t in self.fails.get(key,[]) if now-t<self.window]
        self.fails[key]=times
        return times
    def blocked(self,client,now=None):
        now=time.time() if now is None else now
        with self.lock:
            return len(self._recent(client,now))>=self.per_client or len(self._recent('*',now))>=self.global_limit
    def failure(self,client,now=None):
        now=time.time() if now is None else now
        with self.lock:
            for key in (client,'*'):
                self._recent(key,now).append(now)
    def success(self,client):
        with self.lock:
            self.fails.pop(client,None)

admin_throttle=LoginThrottle()

def client_key(request:Request):
    # Render's proxy appends the real client address as the LAST X-Forwarded-For
    # entry; earlier entries can be forged by the client.
    fwd=request.headers.get('x-forwarded-for','')
    if fwd.strip():return fwd.split(',')[-1].strip()[:64]
    return (request.client.host if request.client else 'unknown')[:64]

def require_admin(request:Request,password,base_url=None):
    if request.method not in ("GET","HEAD") and base_url:
        origin=request.headers.get("origin","")
        ref=request.headers.get("referer","")
        expected=urlsplit(base_url)
        candidate=urlsplit(origin or ref)
        if not candidate.scheme or (candidate.scheme,candidate.netloc)!=(expected.scheme,expected.netloc):
            raise HTTPException(403,"Invalid administration request origin")
    auth=request.headers.get('authorization','')
    if not password: raise HTTPException(503,'Configure ADMIN_PASSWORD first')
    if not auth.startswith('Basic '):raise HTTPException(401,'Admin login required',headers={'WWW-Authenticate':'Basic realm="StartUpTrading Admin"'})
    client=client_key(request)
    if admin_throttle.blocked(client):
        raise HTTPException(429,'Too many failed admin logins; try again in 15 minutes',headers={'Retry-After':'900'})
    try:
        decoded=base64.b64decode(auth[6:],validate=True).decode('utf-8')
        username,provided=decoded.split(':',1)
    except Exception:
        admin_throttle.failure(client)
        raise HTTPException(401,'Invalid credentials',headers={'WWW-Authenticate':'Basic'})
    # Compare both fields every time (no short-circuit) to keep timing uniform.
    user_ok=hmac.compare_digest(username.encode(),b'admin')
    pass_ok=hmac.compare_digest(provided.encode(),password.encode())
    if not (user_ok and pass_ok):
        admin_throttle.failure(client)
        raise HTTPException(401,'Invalid credentials',headers={'WWW-Authenticate':'Basic'})
    admin_throttle.success(client)
    return True
