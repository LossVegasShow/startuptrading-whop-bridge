import base64,hashlib,hmac,time
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
    try:
        decoded=base64.b64decode(auth[6:],validate=True).decode('utf-8')
        username,provided=decoded.split(':',1)
    except Exception:raise HTTPException(401,'Invalid credentials',headers={'WWW-Authenticate':'Basic'})
    if not (hmac.compare_digest(username,'admin') and hmac.compare_digest(provided,password)):
        raise HTTPException(401,'Invalid credentials',headers={'WWW-Authenticate':'Basic'})
    return True
