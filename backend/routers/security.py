import hashlib,ipaddress,json,secrets,time,urllib.parse
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db.models import SecuritySettings,PrincipalSecurity,ApiToken
from backend.schema.output import ResponseModel
from backend.security_core import new_totp_secret,verify_totp,enc,dec
router=APIRouter(prefix='/security',tags=['Security'])
SCOPES={'users:read','users:write','nodes:read','nodes:write','settings:read','settings:write','audit:read'}
def main(u):
 if u['type']!='main_admin':raise HTTPException(403,'Main administrator required')
class SettingsIn(BaseModel):rate_limit_enabled:bool=True;rate_limit_per_minute:int=Field(120,ge=10,le=10000);ip_allowlist_enabled:bool=False;allowed_cidrs:list[str]=[]
class TotpCode(BaseModel):code:str=Field(min_length=6,max_length=6)
class TokenIn(BaseModel):name:str=Field(min_length=1,max_length=128);scopes:list[str];expires_at:int|None=None
@router.get('/',response_model=ResponseModel)
async def get(db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);r=db.query(SecuritySettings).filter_by(id=1).first();p=db.query(PrincipalSecurity).filter_by(username=u['username'],principal_type=u['type']).first();tokens=db.query(ApiToken).order_by(ApiToken.id.desc()).all()
 return ResponseModel(success=True,msg='Security settings',data={'rate_limit_enabled':r.rate_limit_enabled,'rate_limit_per_minute':r.rate_limit_per_minute,'ip_allowlist_enabled':r.ip_allowlist_enabled,'allowed_cidrs':json.loads(r.allowed_cidrs),'totp_enabled':bool(p and p.totp_enabled),'tokens':[{'id':x.id,'name':x.name,'prefix':x.token_prefix,'scopes':json.loads(x.scopes),'expires_at':x.expires_at,'revoked_at':x.revoked_at,'last_used_at':x.last_used_at} for x in tokens]})
@router.put('/',response_model=ResponseModel)
async def put(q:SettingsIn,request:Request,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u)
 try:nets=[ipaddress.ip_network(x,strict=False) for x in q.allowed_cidrs]
 except ValueError as exc:raise HTTPException(422,f'Invalid CIDR: {exc}') from exc
 if q.ip_allowlist_enabled:
  if not nets:raise HTTPException(422,'Allowlist cannot be enabled without at least one CIDR')
  forwarded=request.headers.get('x-forwarded-for','');client_ip=forwarded.split(',')[0].strip() if forwarded else (request.client.host if request.client else '')
  try:included=any(ipaddress.ip_address(client_ip) in network for network in nets)
  except ValueError:included=False
  if not included:raise HTTPException(422,'Your current IP must be included before enabling the allowlist')
 r=db.query(SecuritySettings).filter_by(id=1).first();r.rate_limit_enabled=q.rate_limit_enabled;r.rate_limit_per_minute=q.rate_limit_per_minute;r.ip_allowlist_enabled=q.ip_allowlist_enabled;r.allowed_cidrs=json.dumps(q.allowed_cidrs);r.updated_at=int(time.time());db.commit();return ResponseModel(success=True,msg='Security settings saved',data=None)
@router.post('/totp/setup',response_model=ResponseModel)
async def setup(db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);s=new_totp_secret();p=db.query(PrincipalSecurity).filter_by(username=u['username'],principal_type=u['type']).first()
 if not p:p=PrincipalSecurity(username=u['username'],principal_type=u['type']);db.add(p)
 p.totp_secret_encrypted=enc(s);p.totp_enabled=False;p.updated_at=int(time.time());db.commit();uri='otpauth://totp/'+urllib.parse.quote('PVNetwork:'+u['username'])+'?'+urllib.parse.urlencode({'secret':s,'issuer':'PVNetwork'});return ResponseModel(success=True,msg='TOTP setup',data={'secret':s,'uri':uri})
@router.post('/totp/confirm',response_model=ResponseModel)
async def confirm(q:TotpCode,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);p=db.query(PrincipalSecurity).filter_by(username=u['username'],principal_type=u['type']).first();s=dec(p.totp_secret_encrypted) if p else None
 if not s or not verify_totp(s,q.code):raise HTTPException(422,'Invalid TOTP code')
 p.totp_enabled=True;db.commit();return ResponseModel(success=True,msg='TOTP enabled',data=None)
@router.delete('/totp',response_model=ResponseModel)
async def disable(q:TotpCode,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);p=db.query(PrincipalSecurity).filter_by(username=u['username'],principal_type=u['type']).first();s=dec(p.totp_secret_encrypted) if p else None
 if not s or not verify_totp(s,q.code):raise HTTPException(422,'Invalid TOTP code')
 p.totp_enabled=False;p.totp_secret_encrypted=None;db.commit();return ResponseModel(success=True,msg='TOTP disabled',data=None)
@router.post('/tokens',response_model=ResponseModel)
async def token(q:TokenIn,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u)
 if not q.scopes or any(x not in SCOPES for x in q.scopes):raise HTTPException(422,'Invalid scopes')
 raw='pvn_'+secrets.token_urlsafe(36);x=ApiToken(name=q.name,token_prefix=raw[:12],token_hash=hashlib.sha256(raw.encode()).hexdigest(),scopes=json.dumps(q.scopes),expires_at=q.expires_at,created_at=int(time.time()),created_by=u['username']);db.add(x);db.commit();db.refresh(x);return ResponseModel(success=True,msg='Token created; copy it now',data={'id':x.id,'token':raw})
@router.delete('/tokens/{token_id}',response_model=ResponseModel)
async def revoke(token_id:int,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);x=db.query(ApiToken).filter_by(id=token_id).first()
 if not x:raise HTTPException(404,'Token not found')
 x.revoked_at=int(time.time());db.commit();return ResponseModel(success=True,msg='Token revoked',data=None)
