"""Bounded manual reconciliation for one registered node."""
import hashlib
from pathlib import Path
import subprocess
import sys
import threading

from backend.db.engine import SessionLocal
from backend.db.models import Node
from backend.node.deploy import new_deploy_job,host_deploy_lock,update_job,fail_job


def snapshot(node):
    return {'node_id':node.id,'address':node.address,'port':node.port,'name':node.name,
            'key_sha256':hashlib.sha256(node.key.encode()).hexdigest()}


def run(job,expected):
    lock=None
    try:
        lock=host_deploy_lock(expected['address'])
        if not lock.acquire(blocking=False):
            lock=None
            raise RuntimeError('Node operation is already running')
        with SessionLocal() as db:
            node=db.get(Node,expected['node_id'])
            if node is None or snapshot(node)!=expected:
                raise RuntimeError('Node identity changed; retry with its current configuration')
        job.state='running'
        update_job(job,10,'reconcile','Checking profiles for the selected node only')
        root=Path(__file__).resolve().parents[2]
        result=subprocess.run([sys.executable,str(root/'scripts/pvnetwork-node-user-reconcile.py'),
            '--node-id',str(expected['node_id'])],cwd=root,timeout=240,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode:
            raise RuntimeError('Selected node reconciliation failed; inspect private node diagnostics before retry')
        job.state='succeeded';job.error=None
        update_job(job,100,'complete','Selected node profiles verified','ok')
    except Exception:
        fail_job(job,RuntimeError('Selected node reconciliation did not complete; inspect node identity, connectivity and private diagnostics before retry'))
    finally:
        if lock is not None:lock.release()


def start(node):
    expected=snapshot(node)
    job=new_deploy_job(node.address)
    job.result={'operation':'node-reconcile','node_id':node.id}
    update_job(job,0,'queued','Selected node reconciliation queued')
    threading.Thread(target=run,args=(job,expected),daemon=True).start()
    return job.id
