"""Session CRUD + undo/redo/clear/jump + SSE event stream.

Cursor-only mutations (undo/redo/clear/jump) emit `cursor_changed` events;
op application (which lives in op_service) emits `op_entry_appended`.
That keeps SSE consumers from probing the same event type for two shapes.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from ..events import GLOBAL_HUB, HUB
from ..paths import MAX_INPUT_BYTES, UnsafePathError, safe_ext, safe_input_path
from ..sessions import create_session, get_session, list_sessions

router = APIRouter()


@router.post("/api/sessions")
async def api_create_session(image: UploadFile = File(...)) -> dict:
    # Bound the upload so a multi-GB POST can't OOM the process.
    data = await image.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise HTTPException(413, f"upload exceeds {MAX_INPUT_BYTES // (1024*1024)} MB cap")
    ext = safe_ext((image.filename or "upload.png").rsplit(".", 1)[-1])
    try:
        sess = await asyncio.to_thread(create_session, data, ext)
    except UnsafePathError as exc:
        raise HTTPException(415, str(exc)) from exc
    return sess.to_dict()


@router.post("/api/sessions/from-path")
async def api_create_session_from_path(req: Request) -> dict:
    """Create a session from a path already on this box.

    Same final state as the multipart upload at `/api/sessions`, but skips
    the round-trip when the caller already has the file locally (the chat
    agent, CLI tools, scripts). The path is validated against the workspace
    allowlist by `safe_input_path` and pillow-verified before any bytes are
    persisted into the sessions store.
    """
    try:
        body = await req.json()
    except Exception as exc:
        raise HTTPException(400, "JSON body required") from exc
    raw = (body or {}).get("path")
    if not raw or not isinstance(raw, str):
        raise HTTPException(400, "'path' field required (absolute path to an image inside the workspace)")
    try:
        resolved = safe_input_path(raw)
    except UnsafePathError as exc:
        raise HTTPException(415, str(exc)) from exc
    data = resolved.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise HTTPException(413, f"file exceeds {MAX_INPUT_BYTES // (1024*1024)} MB cap")
    ext = safe_ext(resolved.suffix.lstrip(".") or "png")
    try:
        sess = await asyncio.to_thread(create_session, data, ext)
    except UnsafePathError as exc:
        raise HTTPException(415, str(exc)) from exc
    return sess.to_dict()


@router.get("/api/sessions")
async def api_list_sessions() -> list[dict]:
    return [s.to_dict() for s in list_sessions()]


@router.get("/api/sessions/{sid}")
async def api_get_session(sid: str) -> dict:
    sess = get_session(sid)
    if sess is None:
        raise HTTPException(404, f"unknown session {sid}")
    return sess.to_dict()


@router.post("/api/sessions/{sid}/undo")
async def api_undo(sid: str) -> dict:
    sess = get_session(sid)
    if sess is None:
        raise HTTPException(404, f"unknown session {sid}")
    if sess.cursor >= 0:
        sess.cursor -= 1
        sess.save()
        await sess.notify({"type": "cursor_changed", "session": sess.to_dict()})
    return sess.to_dict()


@router.post("/api/sessions/{sid}/redo")
async def api_redo(sid: str) -> dict:
    sess = get_session(sid)
    if sess is None:
        raise HTTPException(404, f"unknown session {sid}")
    if sess.cursor < len(sess.history) - 1:
        sess.cursor += 1
        sess.save()
        await sess.notify({"type": "cursor_changed", "session": sess.to_dict()})
    return sess.to_dict()


@router.post("/api/sessions/{sid}/clear")
async def api_clear(sid: str) -> dict:
    sess = get_session(sid)
    if sess is None:
        raise HTTPException(404, f"unknown session {sid}")
    sess.history = []
    sess.cursor = -1
    sess.save()
    await sess.notify({"type": "cursor_changed", "session": sess.to_dict()})
    return sess.to_dict()


@router.post("/api/sessions/{sid}/jump/{step}")
async def api_jump(sid: str, step: int) -> dict:
    """Move the session cursor. step=-1 means 'show the original image'."""
    sess = get_session(sid)
    if sess is None:
        raise HTTPException(404, f"unknown session {sid}")
    sess.cursor = max(-1, min(len(sess.history) - 1, step))
    sess.save()
    await sess.notify({"type": "cursor_changed", "session": sess.to_dict()})
    return sess.to_dict()


@router.get("/api/events")
async def api_global_events() -> StreamingResponse:
    """Process-wide SSE channel for cross-session UI signals.

    Currently emits `session_created` whenever a session is created (HTTP
    upload OR MCP `create_session`). Lets any open GUI tab offer to switch
    to a freshly-created session — the per-session SSE channel doesn't
    help here because nobody's subscribed to a brand-new session yet.
    """
    queue = GLOBAL_HUB.subscribe()

    async def gen():
        try:
            yield "data: {\"type\": \"hello\"}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            GLOBAL_HUB.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/sessions/{sid}/events")
async def api_session_events(sid: str) -> StreamingResponse:
    """SSE stream — push live updates to the UI when ops are applied."""
    sess = get_session(sid)
    if sess is None:
        raise HTTPException(404, f"unknown session {sid}")
    queue = HUB.subscribe(sid)
    if queue is None:
        raise HTTPException(429, "too many subscribers for this session")

    async def gen():
        try:
            yield f"data: {json.dumps({'type': 'hello', 'session': sess.to_dict()})}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            HUB.unsubscribe(sid, queue)

    return StreamingResponse(gen(), media_type="text/event-stream")
