from __future__ import annotations

import re
from time import time as epoch_time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from backend.panel_runtime_settings import load_transition_state

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def _valid_state(state) -> bool:
    if not isinstance(state, dict):
        return False
    old_path = state.get("old_path")
    new_path = state.get("new_path")
    expires = state.get("redirect_expires_at")
    if not isinstance(old_path, str) or not _SEGMENT_RE.fullmatch(old_path):
        return False
    if not isinstance(new_path, str) or not _SEGMENT_RE.fullmatch(new_path):
        return False
    if old_path.casefold() == new_path.casefold():
        return False
    return isinstance(expires, (int, float))


class PanelPathTransitionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        state = load_transition_state()
        if _valid_state(state) and epoch_time() < float(state["redirect_expires_at"]):
            old_prefix = "/" + state["old_path"]
            path = request.url.path
            if path == old_prefix or path.startswith(old_prefix + "/"):
                suffix = path[len(old_prefix):]
                target = "/" + state["new_path"] + suffix
                if request.url.query:
                    target += "?" + request.url.query
                return RedirectResponse(target, status_code=307)
        return await call_next(request)
