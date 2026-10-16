"""Main-admin node backups and same-node recovery through pinned SSH."""
import re
import secrets
import threading
import time

from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field,model_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

from backend.auth.auth import get_current_user
from backend.db.engine import get_db,SessionLocal
from backend.db.models import Node
from backend.node import archive_store as store,archive_transport as transport,native_deploy
from backend.node.deploy import new_deploy_job,get_deploy_job,host_deploy_lock,update_job,fail_job
from backend.schema.output import ResponseModel

router=APIRouter(prefix='/nodes',tags=['Node archives'])
UPLOAD_LIMIT=60*1024**2


class Credentials(BaseModel):
    ssh_port:int=Field(default=22,ge=1,le=65535)
    ssh_username:str=Field(default='root',pattern=r'^[a-zA-Z_][a-zA-Z0-9_-]{0,63}$')
    ssh_password:str|None=Field(default=None,max_length=512)
    ssh_private_key:str|None=Field(default=None,max_length=32768)
    ssh_key_passphrase:str|None=Field(default=None,max_length=512)
    ssh_fingerprint:str|None=Field(default=None,max_length=160)

    @model_validator(mode='after')
    def authenticated(self):
        if not self.ssh_password and not self.ssh_private_key:raise ValueError('SSH password or private key required')
        return self


class Restore(Credentials):
    archive_id:str=Field(pattern='^[a-f0-9]{24}$')
    offline:bool=Field(default=False,strict=True)
    start_recovered:bool=Field(default=False,strict=True)
    confirm_downtime:bool=Field(default=False,strict=True)

    @model_validator(mode='after')
    def explicit_recovery(self):
        if self.offline and not self.confirm_downtime:raise ValueError('Offline recovery requires explicit downtime confirmation')
        if self.start_recovered and not self.offline:raise ValueError('Starting recovered services requires offline recovery')
        return self


def authorized(node_id,user,db):
    if user.get('type')!='main_admin':raise HTTPException(403,'Main administrator access is required')
    node=db.get(Node,node_id)
    if node is None:raise HTTPException(404,'Node not found')
    return node


def receipt(identity,node,ready=False):
    try:return store.load(identity,node) if ready else store.bound(identity,node)
    except (OSError,ValueError,TypeError,KeyError):raise HTTPException(404,'Private archive unavailable or expired') from None


def public_entry(entry):
    return {'archive_id':entry['id'],'sha256':entry.get('sha256'),'size':entry.get('size'),
            'expires_at':entry['expires_at'],'node_id':entry['binding']['node_id']}


def run(job,identity,action,credentials):
    client=None;lock=None;cleanup_pending=False
    try:
        with SessionLocal() as db:
            entry=store.read(identity);node=db.get(Node,entry['binding']['node_id'])
            if node is None or store.binding(node)!=entry['binding']:raise ValueError('Node identity changed')
            address=node.address
        lock=host_deploy_lock(address)
        if not lock.acquire(blocking=False):lock=None;raise ValueError('Node operation is already running')
        if action=='restore':
            with store.open_verified(entry):pass
        job.state='running';update_job(job,3,'ssh','Connecting with verified SSH host identity')
        client=native_deploy.connect(address,credentials['ssh_port'],credentials['ssh_username'],
            credentials.get('ssh_password'),credentials.get('ssh_private_key'),credentials.get('ssh_key_passphrase'),credentials.get('ssh_fingerprint'))
        username=credentials['ssh_username']
        # Only fixed stage labels are persisted; raw native paths, replies and secrets stay private.
        report=lambda progress,stage,_message,level='info':update_job(job,min(90,progress),stage,'Native node '+stage,level)
        hidden=[credentials.get('ssh_password'),credentials.get('ssh_private_key'),credentials.get('ssh_key_passphrase')]
        if action=='backup':
            update_job(job,10,'backup','Creating and verifying native node backup')
            native=native_deploy.archive_operation(client=client,username=username,action='backup',report=report,secret_values=hidden)
            update_job(job,92,'download','Receiving private backup and checking SHA256')
            transport.download_archive(client,username,native,store.path(entry));store.seal(entry)
            if entry['sha256']!=native['sha256'] or entry['size']!=native['size']:raise ValueError('Backup receipt mismatch')
        elif action=='restore':
            update_job(job,10,'upload','Transferring verified private archive')
            upload_id=secrets.token_hex(12)
            entry['remote_upload_id']=upload_id;store.store(entry)
            uploaded=transport.upload_archive(client,username,store.path(entry),upload_id)
            native_deploy.archive_operation(client=client,username=username,action='restore',upload_id=upload_id,
                archive_sha256=entry['sha256'],offline=credentials.get('offline',False),
                start_recovered=credentials.get('start_recovered',False),report=report,secret_values=hidden)
            try:transport.remove_upload(client,username,uploaded)
            except Exception:cleanup_pending=True
        else:
            native_deploy.archive_operation(client=client,username=username,action='recover-data',report=report,secret_values=hidden)
        job.state='succeeded';job.result={**public_entry(entry),'operation':action,'state':'complete','private_staging_retained':cleanup_pending}
        update_job(job,100,'complete','Native node '+action+' verified','ok')
    except Exception as exc:
        # Paramiko's fingerprint is public trust material; arbitrary exception text is not.
        observed=re.search(r'Observed fingerprint: (SHA256:[A-Za-z0-9+/]{43})',str(exc))
        message=('SSH host identity needs verification. Observed fingerprint: '+observed.group(1)) if observed else 'Node archive operation failed; inspect private node diagnostics and recover pending transactions before retry'
        fail_job(job,RuntimeError(message))
    finally:
        if client is not None:client.close()
        if lock is not None:lock.release()
        for key in ('ssh_password','ssh_private_key','ssh_key_passphrase'):credentials[key]=''


def start(node,entry,action,credentials):
    with store.locked():
        current=store.bound(entry['id'],node)
        prior=get_deploy_job(current.get('job_id',''))
        if prior and prior['state'] in {'queued','running'}:raise HTTPException(409,'This archive operation is already running')
        job=new_deploy_job(node.address);current.update(job_id=job.id,operation=action,expires_at=int(time.time())+store.TTL);store.store(current)
    threading.Thread(target=run,args=(job,entry['id'],action,credentials.model_dump()),daemon=True).start()
    return ResponseModel(success=True,msg='Node archive operation queued',data={'archive_id':entry['id'],'job_id':job.id})


@router.post('/{node_id}/archives/backup',status_code=202,response_model=ResponseModel)
def backup(node_id:int,credentials:Credentials,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db)
    try:entry=store.create(node,'backup')
    except (OSError,ValueError):raise HTTPException(409,'Private archive storage is unavailable or full') from None
    return start(node,entry,'backup',credentials)


@router.post('/{node_id}/archives/upload',status_code=201,response_model=ResponseModel)
async def upload(node_id:int,request:Request,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db)
    if request.headers.get('content-type','').split(';')[0]!='application/octet-stream':raise HTTPException(415,'Send the archive as application/octet-stream')
    try:length=int(request.headers.get('content-length','0'))
    except ValueError:raise HTTPException(400,'Invalid archive length') from None
    if length<0 or length>UPLOAD_LIMIT:raise HTTPException(413,'Archive upload limit is 60 MiB')
    try:
        entry=await run_in_threadpool(store.create,node,'upload');total=0
        with store.receiving(entry) as handle:
            async for chunk in request.stream():
                total+=len(chunk)
                if total>UPLOAD_LIMIT:raise HTTPException(413,'Archive upload limit is 60 MiB')
                await run_in_threadpool(handle.write,chunk)
            if total==0 or (length and total!=length):raise HTTPException(400,'Archive upload is empty or incomplete')
        await run_in_threadpool(store.seal,entry)
    except (OSError,ValueError):raise HTTPException(409,'Private archive storage is unavailable or verification failed') from None
    return ResponseModel(success=True,msg='Private archive uploaded',data=public_entry(entry))


@router.post('/{node_id}/archives/restore',status_code=202,response_model=ResponseModel)
def restore(node_id:int,credentials:Restore,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db);entry=receipt(credentials.archive_id,node,ready=True)
    return start(node,entry,'restore',credentials)


@router.post('/{node_id}/archives/recover',status_code=202,response_model=ResponseModel)
def recover(node_id:int,credentials:Credentials,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db)
    try:entry=store.create(node,'recovery')
    except (OSError,ValueError):raise HTTPException(409,'Private archive storage is unavailable or full') from None
    return start(node,entry,'recover-data',credentials)


@router.get('/{node_id}/archives/{identity}/status',response_model=ResponseModel)
def status(node_id:int,identity:str,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db);entry=receipt(identity,node)
    job=get_deploy_job(entry.get('job_id',''))
    if not job:raise HTTPException(404,'Node archive job not found')
    return ResponseModel(success=True,msg='Node archive status',data=job)


@router.get('/{node_id}/archives/{identity}/download')
def download(node_id:int,identity:str,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db);entry=receipt(identity,node,ready=True)
    try:handle=store.open_verified(entry)
    except (OSError,ValueError):raise HTTPException(409,'Private archive verification failed') from None
    def chunks():
        try:
            for chunk in iter(lambda:handle.read(65536),b''):yield chunk
        finally:handle.close()
    return StreamingResponse(chunks(),media_type='application/gzip',headers={'Cache-Control':'no-store',
        'Content-Length':str(entry['size']),'X-Content-Type-Options':'nosniff',
        'Content-Disposition':f'attachment; filename="pvnetwork-node-{node.id}-{identity}.tar.gz"'},background=BackgroundTask(handle.close))


@router.delete('/{node_id}/archives/{identity}',response_model=ResponseModel)
def discard(node_id:int,identity:str,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db)
    with store.locked():
        entry=receipt(identity,node,ready=True);job=get_deploy_job(entry.get('job_id',''))
        if job and job['state'] in {'queued','running'}:raise HTTPException(409,'This archive operation is still running')
        try:store.discard(entry)
        except (OSError,ValueError):raise HTTPException(409,'Changed archive material was preserved') from None
    return ResponseModel(success=True,msg='Private controller copy removed',data=None)
