import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.operations.daily_checks import enforce_user_limits, check_user_used_traffic
from backend.config import config
from backend.routers import all_routers
from backend.routers.sub import router as subscription_router
from backend.routers.push import router as push_router
from backend.routers.anyconnect import (
    router as anyconnect_router,
    integration_router as anyconnect_integration_router,
)
from backend.version import __version__
from backend.operations.history import record_usage_history
from backend.audit import AuditMiddleware
from backend.security_middleware import (
    ApiScopeMiddleware,
    SecurityHeadersMiddleware,
    SecurityMiddleware,
)


api = FastAPI(
    title="PVNetwork API",
    description="API for managing PVNetwork Panel",
    version=__version__,
    docs_url="/doc" if config.DOC else None,
    redoc_url="/redoc" if config.DOC else None,
    openapi_url="/openapi.json" if config.DOC else None,
)

frontend_build_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

api.mount(
    f"/{config.URLPATH}/assets",
    StaticFiles(directory=os.path.join(frontend_build_path, "assets")),
    name="assets",
)

api.add_middleware(ApiScopeMiddleware)
api.add_middleware(SecurityMiddleware)
api.add_middleware(AuditMiddleware)
api.add_middleware(SecurityHeadersMiddleware)

cors_origins = [
    item.strip()
    for item in (config.CORS_ORIGINS or "").split(",")
    if item.strip()
]
if cors_origins:
    api.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def start_scheduler():
    """This function starts the scheduler for every 5 minutes tasks"""
    scheduler = AsyncIOScheduler()
    # PVNETWORK_FAILOPEN_EVENTLOOP_V1
    # Usage sync and limit enforcement run only through
    # ov-usage-sync.timer. Do not run blocking node I/O
    # inside Uvicorn's single asyncio event loop.

    scheduler.add_job(record_usage_history, CronTrigger(minute="*/30"), id="usage_history", replace_existing=True)

    scheduler.start()


@api.on_event("startup")
async def startup_event():
    start_scheduler()


for router in all_routers:
    api.include_router(prefix="/api", router=router)

api.include_router(subscription_router)
api.include_router(push_router)
api.include_router(prefix="/api", router=anyconnect_router)
api.include_router(
    prefix="/api",
    router=anyconnect_integration_router,
)


@api.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok", "version": __version__}


@api.get(f"/{config.URLPATH}/{{path:path}}")
@api.get(f"/{config.URLPATH}")
async def serve_react():
    index_path = os.path.join(frontend_build_path, "index.html")
    return FileResponse(index_path)
