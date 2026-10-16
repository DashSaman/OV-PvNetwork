"""Main-administrator manual operations bound to one registered node."""
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db.models import Node
from backend.node import reconcile
from backend.node.deploy import get_deploy_job
from backend.schema.output import ResponseModel

router=APIRouter(prefix='/nodes',tags=['Node operations'])


def authorized(node_id,user,db):
    if user.get('type')!='main_admin':raise HTTPException(403,'Main administrator access is required')
    node=db.get(Node,node_id)
    if node is None:raise HTTPException(404,'Node not found')
    return node


@router.post('/{node_id}/reconcile',status_code=202,response_model=ResponseModel)
def reconcile_node(node_id:int,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    node=authorized(node_id,user,db)
    return ResponseModel(success=True,msg='Selected node reconciliation queued',data={'job_id':reconcile.start(node),'node_id':node.id})


@router.get('/{node_id}/reconcile/{job_id}',response_model=ResponseModel)
def reconcile_status(node_id:int,job_id:str,user:dict=Depends(get_current_user),db:Session=Depends(get_db)):
    authorized(node_id,user,db)
    job=get_deploy_job(job_id)
    if not job or job.get('result')!={'operation':'node-reconcile','node_id':node_id}:
        raise HTTPException(404,'Selected node reconciliation job not found')
    return ResponseModel(success=True,msg='Selected node reconciliation status',data=job)
