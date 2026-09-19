import json, threading, time, uuid
from pathlib import Path
import paramiko
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.auth.auth import get_current_user
from backend.db.engine import get_db, SessionLocal
from backend.db.models import Node
from backend.node.health import build_nodes_health
from backend.node.requests import NodeRequests
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
 node_ids:list[int]=Field(min_length=1); ssh_username:str='root'; ssh_password:str=Field(min_length=1,max_length=512); ssh_port:int=Field(22,ge=1,le=65535); canary_node_id:int|None=None
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
def ssh(node,user,password,port,script):
 c=paramiko.SSHClient()
 c.load_system_host_keys()
 c.load_host_keys(str(KNOWN_HOSTS))
 c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
 try:
  c.connect(node.address,port=port,username=user,password=password,timeout=20,allow_agent=False,look_for_keys=False)
  _,o,e=c.exec_command('bash -s',timeout=900);o.channel.sendall(script.encode());o.channel.shutdown_write();rc=o.channel.recv_exit_status();out=o.read().decode(errors='replace')+e.read().decode(errors='replace')
  if rc:raise RuntimeError(out[-1500:])
  return out
 finally:c.close()
SCRIPT='''set -Eeuo pipefail
. /opt/ov-node/.env
STAMP=$(date +%s); B=/opt/ov-node.rollback; N=/opt/ov-node.new.$STAMP
DOMAIN_PRESENT=0
rm -rf "$N"; mkdir -p "$N"
curl -fsSL --retry 3 https://api.github.com/repos/primeZdev/ov-node/releases/latest -o /tmp/ovrel.json
URL=$(sed -n 's/.*"tarball_url":[[:space:]]*"\\([^"]*\\)".*/\\1/p' /tmp/ovrel.json|head -1)
TAG=$(sed -n 's/.*"tag_name":[[:space:]]*"\\([^"]*\\)".*/\\1/p' /tmp/ovrel.json|head -1)
curl -fL --retry 3 "$URL" -o /tmp/ovnode.tgz; tar -xzf /tmp/ovnode.tgz -C "$N" --strip-components=1
cp /opt/ov-node/.env "$N/.env"
if [ -f /opt/ov-node/core/routers/domain_history.py ]; then
  DOMAIN_PRESENT=1
  install -D -m 640 /opt/ov-node/core/routers/domain_history.py "$N/core/routers/domain_history.py"
  if ! grep -q '^# PVNETWORK_DOMAIN_HISTORY_INCLUDE_V1$' "$N/core/routers/router.py"; then
    cat >> "$N/core/routers/router.py" <<'PVNETWORK_DOMAIN_INCLUDE'


# PVNETWORK_DOMAIN_HISTORY_INCLUDE_V1
from core.routers.domain_history import router as domain_history_router

router.include_router(domain_history_router)
PVNETWORK_DOMAIN_INCLUDE
  fi
fi
cd "$N"; /root/.local/bin/uv sync
rm -rf "$B"; cp -a /opt/ov-node "$B"; systemctl stop ov-node; rm -rf /opt/ov-node; mv "$N" /opt/ov-node
sed -i 's/host="127.0.0.1"/host="0.0.0.0"/' /opt/ov-node/main.py; echo "${TAG:-unknown}" >/opt/ov-node/VERSION
systemctl restart ov-node
ready=0
for i in $(seq 1 30);do curl -fsS http://127.0.0.1:${SERVICE_PORT:-9090}/openapi.json >/dev/null&&ready=1&&break;sleep 2;done
if [ "$ready" = 1 ] && [ "$DOMAIN_PRESENT" = 1 ]; then
  curl -fsS http://127.0.0.1:${SERVICE_PORT:-9090}/openapi.json | grep -q '/sync/local-domain-activity' || ready=0
  systemctl restart ov-domain-collector.service
  systemctl is-active --quiet ov-domain-collector.service || ready=0
  collector_capture_ready=0
  for collector_attempt in $(seq 1 15); do
    collector_pid="$(systemctl show ov-domain-collector.service -p MainPID --value)"
    if [[ "$collector_pid" =~ ^[0-9]+$ ]] && pgrep -P "$collector_pid" -a 2>/dev/null | grep -Fq 'tcpdump -Z root'; then
      collector_capture_ready=1
      break
    fi
    sleep 1
  done
  if [ "$collector_capture_ready" != 1 ]; then
    ready=0
  fi
fi
if [ "$ready" = 1 ]; then echo "${TAG:-latest}"; exit 0; fi
systemctl stop ov-node;rm -rf /opt/ov-node;mv "$B" /opt/ov-node;systemctl restart ov-node;exit 1
'''
def run(job,password):
 db=SessionLocal();job['state']='running';save(job)
 try:
  ids=job['node_ids'];canary=job.get('canary_node_id') or ids[0];order=[canary]+[x for x in ids if x!=canary]
  for pos,i in enumerate(order):
   if str(i) in job['completed']:continue
   n=db.query(Node).filter(Node.id==i).first()
   if not n:raise RuntimeError(f'Node {i} not found')
   n.maintenance=True;n.drain=True;n.last_upgrade_status='running';db.commit();job['stage']=f'upgrading:{n.name}';save(job)
   out=ssh(n,job['ssh_username'],password,job['ssh_port'],SCRIPT)
   info=NodeRequests(n.address,n.port,n.key,n.tunnel_address or n.address,n.protocol,n.ovpn_port).get_node_info()
   if not info or info.get('status')!='running':raise RuntimeError(f'Health check failed: {n.name}')
   n.version=(out.strip().splitlines()[-1] if out.strip() else 'latest')[:128];n.last_upgrade_at=int(time.time());n.last_upgrade_status='succeeded';n.maintenance=False;n.drain=False;db.commit();job['completed'][str(i)]='succeeded';save(job)
   if pos==0:job['stage']='canary_passed';save(job)
  job['state']='succeeded';job['stage']='complete';save(job)
 except Exception as e:
  db.rollback();job['state']='failed';job['error']=str(e)[:1500];save(job)
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
async def upgrade(q:Upgrade,u:dict=Depends(get_current_user)):
 admin(u);i=str(uuid.uuid4());j={'id':i,'state':'queued','stage':'queued','error':None,'node_ids':q.node_ids,'canary_node_id':q.canary_node_id,'ssh_username':q.ssh_username,'ssh_port':q.ssh_port,'completed':{},'created_at':int(time.time())};save(j)
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

ROLLBACK_SCRIPT = r'''set -Eeuo pipefail
test -d /opt/ov-node.rollback
. /opt/ov-node/.env
PORT="${SERVICE_PORT:-9090}"
CURRENT="/opt/ov-node.failed.$(date +%s)"
systemctl stop ov-node
mv /opt/ov-node "$CURRENT"
mv /opt/ov-node.rollback /opt/ov-node
systemctl daemon-reload
systemctl restart ov-node
ready=0
for i in $(seq 1 30); do
  if curl -fsS --max-time 5 \
    "http://127.0.0.1:${PORT}/openapi.json" >/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != 1 ]; then
  systemctl stop ov-node || true
  mv /opt/ov-node /opt/ov-node.rollback.failed
  mv "$CURRENT" /opt/ov-node
  systemctl restart ov-node
  exit 1
fi
rm -rf "$CURRENT"
cat /opt/ov-node/VERSION 2>/dev/null || echo rollback
'''

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

    node.maintenance = True
    node.drain = True
    node.last_upgrade_status = "rollback_running"
    db.commit()

    try:
        output = await __import__("asyncio").to_thread(
            ssh,
            node,
            request.ssh_username,
            request.ssh_password,
            request.ssh_port,
            ROLLBACK_SCRIPT,
        )
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
        node.maintenance = False
        node.drain = False
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
        raise HTTPException(502, str(exc)[:500])
    finally:
        request.ssh_password = ""
