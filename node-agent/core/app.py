from pathlib import Path
from fastapi import FastAPI
from core.routers import core_router
from core.config import settings
import asyncio
import contextlib


async def accounting_sampler():
    from core.service.user_managment import get_users_usage
    from core.logger import logger
    while True:
        try:await asyncio.to_thread(get_users_usage)
        except Exception:logger.warning('Durable accounting sample failed; retrying')
        await asyncio.sleep(1)


async def session_sampler():
    from core.service.sessions import synchronize
    from core.logger import logger
    while True:
        try:await asyncio.to_thread(synchronize)
        except Exception:logger.warning('Central session synchronization failed; retrying')
        await asyncio.sleep(15)


@contextlib.asynccontextmanager
async def lifespan(app):
    tasks=[]
    if settings.accounting_file:tasks.append(asyncio.create_task(accounting_sampler()))
    if settings.panel_url:tasks.append(asyncio.create_task(session_sampler()))
    try:yield
    finally:
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await task

api=FastAPI(title='PVNetwork Node',lifespan=lifespan,docs_url='/doc' if settings.doc else None,
            redoc_url=None,openapi_url='/openapi.json' if settings.doc else None)
api.include_router(core_router)


@api.middleware('http')
async def private_responses(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store, max-age=0'
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@api.get('/healthz')
async def health():
    return {'status':'ok','version':(Path(__file__).resolve().parents[1]/'VERSION').read_text().strip()}
