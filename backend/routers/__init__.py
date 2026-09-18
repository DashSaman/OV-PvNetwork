from backend.auth.auth import router as login_router
from .operations import router as operations_router
from .backups import router as backups_router
from .security import router as security_router
from .fleet import router as fleet_router
from .audit import router as audit_router
from .users import router as user_router
from .admins import router as admin_router
from .node import router as node_router
from .setting import router as setting_router
from .mirza import router as mirza_router
from .mirza_nodes import router as mirza_nodes_router
from .domain_activity import router as domain_activity_router
from .bandwidth import router as bandwidth_router

all_routers = [
    backups_router,
    operations_router,
    security_router,
    fleet_router,
    audit_router,
    login_router,
    user_router,
    setting_router,
    node_router,
    admin_router,
    mirza_router,
    mirza_nodes_router,
    domain_activity_router,
    bandwidth_router,
]
