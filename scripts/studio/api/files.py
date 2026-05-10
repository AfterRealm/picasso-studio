"""Authenticated file-serving + font enumeration.

Replaces the old `app.mount("/sessions_files", StaticFiles(...))` which
exposed the entire sessions_data tree. Every request goes through the
auth middleware and through `relative_to(sess.dir.resolve())` so a path
traversal can't escape the session directory.
"""
from __future__ import annotations

import functools

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..paths import UnsafePathError, safe_session_id
from ..sessions import get_session

router = APIRouter()


@router.get("/sessions_files/{sid}/{filename}")
async def serve_session_file(sid: str, filename: str):
    """Serve a file out of the session's directory.

    Returns a uniform 404 for every failure mode so an attacker can't
    distinguish "bad sid" from "bad filename" from "file missing" via
    timing or response codes.
    """
    not_found = HTTPException(404, "not found")
    try:
        safe_session_id(sid)
    except UnsafePathError:
        raise not_found from None
    sess = get_session(sid)
    if sess is None:
        raise not_found
    if "/" in filename or "\\" in filename or filename.startswith(".."):
        raise not_found
    candidate = sess.dir / filename
    try:
        resolved = candidate.resolve()
        resolved.relative_to(sess.dir.resolve())
    except (OSError, ValueError):
        raise not_found from None
    if not resolved.is_file():
        raise not_found
    return FileResponse(
        resolved,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@functools.lru_cache(maxsize=1)
def _font_list() -> list[str]:
    try:
        from matplotlib import font_manager
        return sorted({f.name for f in font_manager.fontManager.ttflist})
    except Exception:  # noqa: BLE001 — matplotlib import / enumeration is best-effort
        return ["Arial", "Times New Roman", "Courier New", "Verdana", "Georgia", "Tahoma"]


@router.get("/api/fonts")
async def api_list_fonts() -> list[str]:
    """Return a sorted list of font family names available on this machine.
    UI fallback for browsers without window.queryLocalFonts() (Firefox, Safari)."""
    return _font_list()
