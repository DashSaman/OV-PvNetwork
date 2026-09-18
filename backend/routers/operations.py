import asyncio,time
from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db.models import User,Node,UserNode,UsageHistory,ActiveSession,AuditLog
from backend.node.requests import NodeRequests
from backend.node.health import build_nodes_health
from backend.schema.output import ResponseModel
router=APIRouter(prefix='/operations',tags=['Operations'])
def main(u):
 if u['type']!='main_admin':raise HTTPException(403,'Main administrator required')
class Bulk(BaseModel):user_uuids:list[str]=Field(min_length=1,max_length=1000);action:str
class Transfer(BaseModel):source_node_id:int;target_node_id:int;user_uuids:list[str]|None=None
def client(n):return NodeRequests(n.address,n.port,n.key,n.tunnel_address or n.address,n.protocol,n.ovpn_port)
@router.get('/dashboard',response_model=ResponseModel)
async def dashboard(db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);users=db.query(User);nodes=await build_nodes_health(db);now=date.today();data={'users_total':users.count(),'users_active':users.filter(User.is_active.is_(True)).count(),'users_expired':users.filter(User.expiry_date<now).count(),'online_sessions':db.query(ActiveSession).count(),'nodes_total':len(nodes),'nodes_healthy':sum(x.get('health')=='healthy' for x in nodes),'nodes_degraded':sum(x.get('health')=='degraded' for x in nodes),'nodes_offline':sum(x.get('health')=='offline' for x in nodes),'allocated_bytes':int(db.query(func.coalesce(func.sum(User.total),0)).scalar() or 0),'used_bytes':int(db.query(func.coalesce(func.sum(User.used),0)).scalar() or 0)};return ResponseModel(success=True,msg='Operations dashboard',data=data)
@router.get('/users/{uuid}/history',response_model=ResponseModel)
async def history(uuid:str,days:int=Query(30,ge=1,le=365),db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);cut=int(time.time())-days*86400;rows=db.query(UsageHistory).filter(UsageHistory.user_uuid==uuid,UsageHistory.sampled_at>=cut).order_by(UsageHistory.sampled_at).all();return ResponseModel(success=True,msg='Usage history',data=[{'used':x.used,'total':x.total,'sampled_at':x.sampled_at} for x in rows])
@router.post('/users/bulk',response_model=ResponseModel)
async def bulk(q:Bulk,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u)
 if q.action not in {'activate','deactivate','reset_usage'}:raise HTTPException(422,'Invalid bulk action')
 rows=db.query(User).filter(User.uuid.in_(q.user_uuids)).all();done=[];failed=[]
 for x in rows:
  try:
   if q.action=='reset_usage':x.used=0;x.last_node_usage=0
   else:
    active=q.action=='activate';x.is_active=active
    ns=db.query(Node).join(UserNode,UserNode.node_id==Node.id).filter(UserNode.user_uuid==x.uuid).all()
    for n in ns:
     if not await asyncio.to_thread(client(n).change_user_status,x.name,active):raise RuntimeError(n.name)
   done.append(x.uuid)
  except Exception as e:failed.append({'uuid':x.uuid,'error':str(e)[:200]})
 db.commit();return ResponseModel(success=not failed,msg='Bulk operation completed',data={'completed':done,'failed':failed})
@router.post('/users/transfer',response_model=ResponseModel)
async def transfer(q:Transfer,db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);src=db.query(Node).filter_by(id=q.source_node_id).first();dst=db.query(Node).filter_by(id=q.target_node_id).first()
 if not src or not dst or src.id==dst.id:raise HTTPException(422,'Invalid nodes')
 query=db.query(User).join(UserNode,UserNode.user_uuid==User.uuid).filter(UserNode.node_id==src.id)
 if q.user_uuids:query=query.filter(User.uuid.in_(q.user_uuids))
 done=[];failed=[]
 for x in query.all():
  try:
   if not await asyncio.to_thread(client(dst).create_user,x.name):raise RuntimeError('Target create failed')
   if not db.query(UserNode).filter_by(user_uuid=x.uuid,node_id=dst.id).first():db.add(UserNode(user_uuid=x.uuid,node_id=dst.id))
   old=db.query(UserNode).filter_by(user_uuid=x.uuid,node_id=src.id).first()
   if old:db.delete(old)
   done.append(x.uuid)
  except Exception as e:failed.append({'uuid':x.uuid,'error':str(e)[:200]})
 db.commit();return ResponseModel(success=not failed,msg='Transfer completed',data={'completed':done,'failed':failed})
@router.get('/audit',response_model=ResponseModel)
async def audit(limit:int=Query(200,ge=1,le=500),db:Session=Depends(get_db),u:dict=Depends(get_current_user)):
 main(u);rows=db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all();return ResponseModel(success=True,msg='Audit',data=[{'id':x.id,'actor':x.actor,'action':x.action,'resource':x.resource,'success':x.success,'status_code':x.status_code,'ip_address':x.ip_address,'duration_ms':x.duration_ms,'created_at':x.created_at} for x in rows])

# OV_AUTOMATIC_REBALANCE_V1
class RebalanceRequest(BaseModel):
    execute: bool = False
    source_node_id: int | None = None
    target_node_id: int | None = None
    limit: int = Field(25, ge=1, le=500)
    source_score_max: int = Field(45, ge=0, le=100)
    target_score_min: int = Field(70, ge=0, le=100)

async def _rebalance_data(q: RebalanceRequest, db: Session):
    health_rows = await build_nodes_health(db)
    health = {
        int(row["id"]): row
        for row in health_rows
        if row.get("id") is not None
    }
    nodes = {
        node.id: node
        for node in db.query(Node).all()
    }
    counts = dict(
        db.query(
            UserNode.node_id,
            func.count(UserNode.user_uuid),
        )
        .group_by(UserNode.node_id)
        .all()
    )

    def node_score(node_id):
        row = health.get(node_id, {})
        return int(
            row.get("health_score")
            or nodes[node_id].health_score
            or 0
        )

    if q.source_node_id:
        source = nodes.get(q.source_node_id)
    else:
        candidates = [
            node for node in nodes.values()
            if counts.get(node.id, 0) > 0 and (
                node.maintenance
                or node.drain
                or health.get(node.id, {}).get("health")
                   in {"offline", "degraded"}
                or node_score(node.id) <= q.source_score_max
            )
        ]
        source = min(
            candidates,
            key=lambda node: (
                node_score(node.id),
                -counts.get(node.id, 0),
            ),
            default=None,
        )

    if not source:
        return {
            "needed": False,
            "reason": "No overloaded or unhealthy source node",
        }

    if q.target_node_id:
        target = nodes.get(q.target_node_id)
    else:
        candidates = [
            node for node in nodes.values()
            if node.id != source.id
            and node.status
            and not node.drain
            and not node.maintenance
            and health.get(node.id, {}).get("health") == "healthy"
            and node_score(node.id) >= q.target_score_min
        ]
        target = max(
            candidates,
            key=lambda node: (
                node_score(node.id),
                node.weight,
                -counts.get(node.id, 0),
            ),
            default=None,
        )

    if not target:
        raise HTTPException(
            409,
            "No healthy target node has enough health score",
        )

    rows = (
        db.query(User)
        .join(UserNode, UserNode.user_uuid == User.uuid)
        .filter(UserNode.node_id == source.id)
        .order_by(User.used.desc())
        .limit(q.limit)
        .all()
    )

    plan = {
        "needed": bool(rows),
        "source": {
            "id": source.id,
            "name": source.name,
            "score": node_score(source.id),
            "users": counts.get(source.id, 0),
        },
        "target": {
            "id": target.id,
            "name": target.name,
            "score": node_score(target.id),
            "users": counts.get(target.id, 0),
        },
        "users": [
            {"uuid": row.uuid, "name": row.name}
            for row in rows
        ],
    }

    if not q.execute:
        return plan

    completed = []
    failed = []
    target_client = client(target)

    for row in rows:
        try:
            created = await asyncio.to_thread(
                target_client.create_user,
                row.name,
            )
            if not created:
                raise RuntimeError("Target user creation failed")

            exists = (
                db.query(UserNode)
                .filter_by(
                    user_uuid=row.uuid,
                    node_id=target.id,
                )
                .first()
            )
            if not exists:
                db.add(
                    UserNode(
                        user_uuid=row.uuid,
                        node_id=target.id,
                    )
                )

            old = (
                db.query(UserNode)
                .filter_by(
                    user_uuid=row.uuid,
                    node_id=source.id,
                )
                .first()
            )
            if old:
                db.delete(old)

            db.commit()
            completed.append(row.uuid)
        except Exception as exc:
            db.rollback()
            failed.append({
                "uuid": row.uuid,
                "error": str(exc)[:250],
            })

    plan["completed"] = completed
    plan["failed"] = failed
    return plan

@router.post("/rebalance", response_model=ResponseModel)
async def rebalance(
    request: RebalanceRequest,
    db: Session = Depends(get_db),
    u: dict = Depends(get_current_user),
):
    main(u)
    data = await _rebalance_data(request, db)
    return ResponseModel(
        success=not data.get("failed"),
        msg=(
            "Automatic rebalance executed"
            if request.execute
            else "Automatic rebalance plan generated"
        ),
        data=data,
    )
