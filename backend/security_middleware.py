import ipaddress,json,time
from collections import defaultdict,deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from backend.db.engine import SessionLocal
from backend.db.models import SecuritySettings
_hits=defaultdict(deque);_cache={'at':0,'v':None}
EXEMPT_PREFIXES=(
 '/api/integrations/mirza/',
 '/api/nodes/public-health/',
)
def cfg():
 now=time.time()
 if _cache['v'] and now-_cache['at']<10:return _cache['v']
 db=SessionLocal()
 try:
  r=db.query(SecuritySettings).filter(SecuritySettings.id==1).first();v={'rate':bool(r and r.rate_limit_enabled),'limit':int(r.rate_limit_per_minute if r else 120),'allow':bool(r and r.ip_allowlist_enabled),'cidrs':json.loads(r.allowed_cidrs if r else '[]')}
 finally:db.close()
 _cache.update(at=now,v=v);return v
class SecurityMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  if not request.url.path.startswith('/api'):return await call_next(request)
  if request.method in {'OPTIONS','HEAD'} or request.url.path.startswith(EXEMPT_PREFIXES):
   return await call_next(request)
  c=cfg();forward=request.headers.get('x-forwarded-for','');ip=forward.split(',')[0].strip() if forward else (request.client.host if request.client else '')
  if c['allow'] and request.url.path!='/api/login':
   try:ok=any(ipaddress.ip_address(ip) in ipaddress.ip_network(x,strict=False) for x in c['cidrs'])
   except Exception:ok=False
   if not ok:return JSONResponse({'detail':'IP is not allowed'},403)
  if c['rate']:
   k=ip;q=_hits[k];now=time.time()
   while q and q[0]<now-60:q.popleft()
   if len(q)>=c['limit']:return JSONResponse({'detail':'Rate limit exceeded'},429,headers={'Retry-After':'60'})
   q.append(now)
  return await call_next(request)

class ApiScopeMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  auth=request.headers.get('authorization','')
  if not auth.lower().startswith('bearer ovp_'):return await call_next(request)
  import hashlib,json,time
  from backend.db.models import ApiToken
  raw=auth.split(' ',1)[1];db=SessionLocal()
  try:
   row=db.query(ApiToken).filter(ApiToken.token_hash==hashlib.sha256(raw.encode()).hexdigest(),ApiToken.revoked_at.is_(None)).first()
   if not row or (row.expires_at and row.expires_at<=int(time.time())):return JSONResponse({'detail':'Invalid API token'},401)
   scopes=set(json.loads(row.scopes));path=request.url.path;write=request.method not in {'GET','HEAD','OPTIONS'}
   area='settings'
   if '/users' in path:area='users'
   elif '/nodes' in path or '/fleet' in path:area='nodes'
   elif '/audit' in path:area='audit'
   required=f'{area}:{"write" if write else "read"}'
   if required not in scopes:return JSONResponse({'detail':f'Missing scope: {required}'},403)
  finally:db.close()
  return await call_next(request)
