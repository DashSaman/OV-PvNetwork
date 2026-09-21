from __future__ import annotations

import asyncio
import time

from backend.db.engine import db_session
from backend.logger import logger
from backend.user_rename.engine import run_rename_job
from backend.user_rename.repository import claim_runnable_job


def run_once() -> str | None:
    with db_session() as db:
        job = claim_runnable_job(db)
        if job is None:
            return None
        job_id = job.id
        job.updated_at = int(time.time())
        db.commit()
    try:
        return asyncio.run(run_rename_job(job_id))
    except Exception:
        logger.exception("User rename worker failed for job %s", job_id)
        return "error"
