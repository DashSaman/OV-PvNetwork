import json, threading, time, uuid
from pathlib import Path
import paramiko
from backend.security_ssh import configure_ssh_client
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.auth.auth import get_current_user
from backend.db.engine import get_db, SessionLocal
from backend.db.models import Node
from backend.node.health import build_nodes_health
from backend.node.requests import NodeRequests
from backend.node.deploy import (
 router_capability_install_script as _router_capability_install_script,
)
from backend.schema.output import ResponseModel
router=APIRouter(prefix='/fleet',tags=['Fleet'])
JOBDIR=Path('/opt/pvnetwork-panel/data/fleet-jobs'); JOBDIR.mkdir(parents=True,exist_ok=True); JOBDIR.chmod(0o700)
KNOWN_HOSTS=Path('/opt/pvnetwork-panel/data/fleet_known_hosts')
KNOWN_HOSTS.parent.mkdir(parents=True,exist_ok=True)
KNOWN_HOSTS.touch(mode=0o600,exist_ok=True)
KNOWN_HOSTS.chmod(0o600)
_ACTIVE_JOBS=set()
_ACTIVE_JOBS_LOCK=threading.Lock()

def _job_is_active(job_id):
 with _ACTIVE_JOBS_LOCK:
  return job_id in _ACTIVE_JOBS

class Control(BaseModel):
 drain:bool|None=None; maintenance:bool|None=None; weight:int|None=Field(None,ge=0,le=1000)
class Upgrade(BaseModel):
 node_ids:list[int]=Field(min_length=1); ssh_username:str='root'; ssh_password:str=Field(min_length=1,max_length=512); ssh_port:int=Field(22,ge=1,le=65535); canary_node_id:int|None=None; ssh_fingerprints:dict[int,str]=Field(default_factory=dict)
class Retry(BaseModel): ssh_password:str=Field(min_length=1,max_length=512)
def admin(u):
 if u['type']!='main_admin':raise HTTPException(403,'Main administrator required')
def save(j):
 t=JOBDIR/(j['id']+'.tmp');t.write_text(json.dumps(j,ensure_ascii=False));t.chmod(0o600);t.replace(JOBDIR/(j['id']+'.json'))
def load(i):
 try:return json.loads((JOBDIR/(i+'.json')).read_text())
 except Exception:return None
def score(x):
 if x.get('health') in {'offline','disabled'}:return 0
 v=100-float(x.get('cpu_usage') or 0)*.35-float(x.get('memory_usage') or 0)*.30-min(float(x.get('api_latency_ms') or 0)/40,20)-min(float(x.get('central_active_sessions') or 0),15)
 if x.get('drain'):v-=20
 if x.get('maintenance'):v=0
 return max(0,min(100,round(v)))
@router.get('/',response_model=ResponseModel)
async def fleet(db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 admin(u); data=await build_nodes_health(db); rows={n.id:n for n in db.query(Node).all()}
 for x in data:
  n=rows.get(x['id']); x['maintenance']=bool(n.maintenance); x['version']=n.version; x['last_upgrade_at']=n.last_upgrade_at; x['last_upgrade_status']=n.last_upgrade_status; x['health_score']=score(x); n.health_score=x['health_score']
  if n.maintenance:x['eligible_for_new_connections']=False;x['administrative_state']='maintenance'
 db.commit();return ResponseModel(success=True,msg='Fleet status',data=data)
@router.put('/{node_id}/control',response_model=ResponseModel)
async def control(node_id:int,q:Control,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 admin(u);n=db.query(Node).filter(Node.id==node_id).first()
 if not n:raise HTTPException(404,'Node not found')
 if q.drain is not None:n.drain=q.drain
 if q.maintenance is not None:n.maintenance=q.maintenance;n.drain=q.maintenance or n.drain
 if q.weight is not None:n.weight=q.weight
 db.commit();return ResponseModel(success=True,msg='Node control updated',data={'id':n.id,'drain':n.drain,'maintenance':n.maintenance,'weight':n.weight})
def ssh(node, user, password, port, script, expected_fingerprint=None):
    client = paramiko.SSHClient()
    configure_ssh_client(
        client,
        expected_fingerprint=expected_fingerprint,
    )
    try:
        client.connect(
            node.address,
            port=port,
            username=user,
            password=password,
            timeout=20,
            allow_agent=False,
            look_for_keys=False,
        )
        # Fixed command; the deployment script is sent on stdin.
        _, stdout, stderr = client.exec_command(
            "bash -s",
            timeout=900,
        )  # nosec B601
        stdout.channel.sendall(script.encode())
        stdout.channel.shutdown_write()
        rc = stdout.channel.recv_exit_status()
        output = (
            stdout.read().decode(errors="replace")
            + stderr.read().decode(errors="replace")
        )
        if rc:
            raise RuntimeError(output[-1500:])
        return output
    finally:
        client.close()

def router_capability_install_script(node_root='/opt/ov-node'):
 return _router_capability_install_script(node_root)

def build_upgrade_script():
 raise ValueError('Legacy updates require explicit Adopt Existing Node with a verified native source bundle')


def is_native(node):
 from backend.node import tls
 return node.key.startswith(tls.KEY_PREFIX) or tls.has_trust(node.address,node.port) or bool(tls.binding(node.address,node.port))


def native_operation(node,action,user,password,port,fingerprint):
 from backend.node.native_deploy import agent_operation
 return agent_operation(action=action,host=node.address,ssh_port=port,username=user,password=password,fingerprint=fingerprint)

def require_verified_nodes(db,ids,canary=None):
 if not ids or (canary is not None and canary not in ids):
  raise ValueError('Canary must be one of the requested nodes')
 for node_id in ids:
  node=db.query(Node).filter(Node.id==node_id).first()
  if not node:raise ValueError('Requested node not found')
  if not is_native(node):
   raise ValueError('Legacy fleet operations require explicit Adopt Existing Node before verified native upgrade or rollback')

def run(job,password):
 db=SessionLocal();job['state']='running';save(job)
 try:
  ids=list(dict.fromkeys(job['node_ids']));canary=job.get('canary_node_id') or (ids[0] if ids else None)
  require_verified_nodes(db,ids,canary)
  order=[canary]+[x for x in ids if x!=canary]
  for pos,i in enumerate(order):
   if str(i) in job['completed']:continue
   n=db.query(Node).filter(Node.id==i).first()
   if not n:raise RuntimeError(f'Node {i} not found')
   prior_flags=(n.maintenance,n.drain)
   n.last_upgrade_status='running';db.commit();job['stage']=f'upgrading:{n.name}';save(job)
   fingerprint=job.get('ssh_fingerprints',{}).get(str(i))
   from backend.version import __version__
   current=NodeRequests(n.address,n.port,n.key,n.tunnel_address or n.address,n.protocol,n.ovpn_port).get_node_info()
   result={'version':__version__,'changed':False} if current.get('version')==__version__ else native_operation(n,'upgrade',job['ssh_username'],password,job['ssh_port'],fingerprint)
   out=result['version']
   info=NodeRequests(n.address,n.port,n.key,n.tunnel_address or n.address,n.protocol,n.ovpn_port).get_node_info()
   if not info or info.get('status')!='running':raise RuntimeError(f'Health check failed: {n.name}')
   n.version=(out.strip().splitlines()[-1] if out.strip() else 'unknown')[:128];n.last_upgrade_at=int(time.time());n.last_upgrade_status='succeeded';n.maintenance,n.drain=prior_flags;db.commit();job['completed'][str(i)]='succeeded';save(job)
   if pos==0:job['stage']='canary_passed';save(job)
  job['state']='succeeded';job['stage']='complete';save(job)
 except Exception as e:
  db.rollback();job['state']='failed';message=str(e).replace(password,'[REDACTED]') if password else str(e)
  for known in db.query(Node).filter(Node.id.in_(job['node_ids'])).all():message=message.replace(known.key,'[REDACTED]')
  job['error']=message[:1500];save(job)
 finally:
  password=''
  db.close()
  with _ACTIVE_JOBS_LOCK:
   _ACTIVE_JOBS.discard(job['id'])

def launch(job,password):
 with _ACTIVE_JOBS_LOCK:
  if job['id'] in _ACTIVE_JOBS:
   return False
  _ACTIVE_JOBS.add(job['id'])
 try:
  threading.Thread(target=run,args=(job,password),daemon=True).start()
  return True
 except Exception:
  with _ACTIVE_JOBS_LOCK:
   _ACTIVE_JOBS.discard(job['id'])
  raise
@router.post('/upgrade',response_model=ResponseModel)
async def upgrade(q:Upgrade,u:dict=Depends(get_current_user),db:Session=Depends(get_db)):
  admin(u)
  try:require_verified_nodes(db,q.node_ids,q.canary_node_id)
  except ValueError as exc:raise HTTPException(409,str(exc)) from None
  i=str(uuid.uuid4());j={'id':i,'state':'queued','stage':'queued','error':None,'node_ids':q.node_ids,'canary_node_id':q.canary_node_id,'ssh_username':q.ssh_username,'ssh_port':q.ssh_port,'ssh_fingerprints':{str(k):v for k,v in q.ssh_fingerprints.items()},'completed':{},'created_at':int(time.time())};save(j)
  if not launch(j,q.ssh_password):raise HTTPException(409,'Job is already running')
  return ResponseModel(success=True,msg='Canary upgrade started',data={'job_id':i})
@router.get('/jobs/{job_id}',response_model=ResponseModel)
async def job(job_id:str,u:dict=Depends(get_current_user)):
 admin(u);j=load(job_id)
 if not j:raise HTTPException(404,'Job not found')
 if j.get('state')=='running' and not _job_is_active(job_id):
  j['state']='failed';j['stage']='interrupted';j['error']='Panel service restarted while this job was running. Retry is available.';save(j)
 return ResponseModel(success=True,msg='Fleet job',data=j)
@router.post('/jobs/{job_id}/retry',response_model=ResponseModel)
async def retry(job_id:str,q:Retry,u:dict=Depends(get_current_user)):
 admin(u);j=load(job_id)
 if not j:raise HTTPException(404,'Job not found')
 if j['state']=='running' and _job_is_active(job_id):raise HTTPException(409,'Job is running')
 if j['state']=='running':
  j['state']='failed';j['stage']='interrupted';j['error']='Previous execution was interrupted'
 j['state']='queued';j['error']=None;save(j)
 if not launch(j,q.ssh_password):raise HTTPException(409,'Job is already running')
 return ResponseModel(success=True,msg='Retry started',data={'job_id':job_id})

# PVNETWORK_FINAL_FLEET_ROLLBACK_V1
class RollbackRequest(BaseModel):
    ssh_username: str = "root"
    ssh_password: str = Field(min_length=1, max_length=512)
    ssh_port: int = Field(22, ge=1, le=65535)
    ssh_fingerprint: str | None = Field(default=None, max_length=160)

@router.post("/{node_id}/rollback", response_model=ResponseModel)
async def rollback_node(
    node_id: int,
    request: RollbackRequest,
    db: Session = Depends(get_db),
    u: dict = Depends(get_current_user),
):
    admin(u)
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(404, "Node not found")

    if not is_native(node):
        request.ssh_password=''
        raise HTTPException(409,'Legacy rollback requires a verified native lifecycle; use explicit Adopt Existing Node first')
    prior_flags=(node.maintenance,node.drain)
    node.last_upgrade_status = "rollback_running"
    db.commit()

    try:
        result=await __import__('asyncio').to_thread(native_operation,node,'rollback-agent',request.ssh_username,request.ssh_password,request.ssh_port,request.ssh_fingerprint)
        output=result['version']
        info = await __import__("asyncio").to_thread(
            NodeRequests(
                node.address,
                node.port,
                node.key,
                node.tunnel_address or node.address,
                node.protocol,
                node.ovpn_port,
            ).get_node_info
        )
        if not info or info.get("status") != "running":
            raise RuntimeError("Health check after rollback failed")

        node.version = (
            output.strip().splitlines()[-1]
            if output.strip() else "rollback"
        )[:128]
        node.last_upgrade_status = "rolled_back"
        node.last_upgrade_at = int(time.time())
        node.maintenance,node.drain=prior_flags
        db.commit()

        return ResponseModel(
            success=True,
            msg="Node rollback completed",
            data={
                "node_id": node.id,
                "version": node.version,
            },
        )
    except Exception as exc:
        db.rollback()
        node = db.query(Node).filter(Node.id == node_id).first()
        node.last_upgrade_status = "rollback_failed"
        db.commit()
        message=str(exc)
        for secret in [request.ssh_password,node.key]:
            if secret:message=message.replace(secret,'[REDACTED]')
        raise HTTPException(502, message[:500])
    finally:
        request.ssh_password = ""
