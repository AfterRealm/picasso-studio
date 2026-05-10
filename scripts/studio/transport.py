"""Auto-registration of every OP_REGISTRY entry as both an MCP tool and a
FastAPI POST endpoint.

Pulled out of app.py so the wiring concern (per-op create_model + dual
binding) lives separately from FastAPI app construction. `register_all_ops`
is called once during app construction; FastAPI does not support adding
new routes after uvicorn starts serving, so this MUST run at app build
time — not in lifespan.

NOTE: do NOT add `from __future__ import annotations` here. FastMCP's
tool decorator inspects the wrapped function's annotations with
`eval_str=True`, which would try to resolve dynamically-created Model
names against module globals (they live in local scope) and NameError
at startup.
"""
import asyncio
import base64
import inspect
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
from pydantic import create_model

from .config import get_mode
from .op_service import apply_op
from .registry import OP_REGISTRY

log = logging.getLogger("picasso_studio.transport")


# Extension → MCP-compatible raster mime. SVG is intentionally absent —
# MCP ImageContent is raster-only, so vectorize results are returned as
# the plain dict (no inline render).
_INLINE_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
}


async def _wrap_op_result(result: Any) -> Any:
    """In inline mode, attach the image as ImageContent so it renders in chat.
    In gui mode (or unset), return the plain dict — browser is the canvas.
    MCP-side only; HTTP returns the raw dict and SSE carries the raw entry.

    The disk read + base64 encode happen in a worker thread so a multi-MB
    animated WebP doesn't block the event loop while encoding.
    """
    if not isinstance(result, dict) or "error" in result:
        return result
    if get_mode() != "inline":
        return result
    output_path = result.get("output_path")
    if not output_path:
        return result

    ext = Path(output_path).suffix.lstrip(".").lower()
    mime = _INLINE_MIME.get(ext)
    if mime is None:
        return result

    def _encode() -> str | None:
        try:
            img_bytes = Path(output_path).read_bytes()
        except OSError:
            return None
        return base64.b64encode(img_bytes).decode("ascii")

    b64 = await asyncio.to_thread(_encode)
    if b64 is None:
        return result
    return [
        TextContent(type="text", text=json.dumps(result)),
        ImageContent(type="image", data=b64, mimeType=mime),
    ]


def _register_op_as_mcp(mcp: FastMCP, op_name: str) -> None:
    """Wrap a registered op as an MCP tool. Done once per op at startup."""
    op = OP_REGISTRY[op_name]

    sig = inspect.signature(op.func)
    fields: dict[str, Any] = {"session_id": (str, ...)}
    for pname, pmeta in op.params.items():
        ptype = {"int": int, "float": float, "str": str, "bool": bool}.get(
            pmeta.get("type", "str"), str
        )
        if "default" in pmeta:
            default: Any = pmeta["default"]
        else:
            sig_param = sig.parameters.get(pname)
            if sig_param is not None and sig_param.default is not inspect.Parameter.empty:
                default = sig_param.default
            else:
                default = ...
        fields[pname] = (ptype, default)

    model_name = "".join(part.capitalize() for part in op_name.split("_")) + "Args"
    Model = create_model(model_name, **fields)  # type: ignore[arg-type]

    @mcp.tool(name=op_name, description=op.description)
    async def _tool(args: Model):  # type: ignore[valid-type]
        kwargs = args.model_dump()
        sid = kwargs.pop("session_id", "")
        result = await apply_op(op_name, sid, kwargs)
        return await _wrap_op_result(result)


def _register_op_as_http(app: FastAPI, op_name: str) -> None:
    """Wrap a registered op as a POST /api/ops/<name> endpoint."""

    async def _endpoint(req: Request):
        body = await req.json()
        sid = body.get("session_id")
        if not sid:
            raise HTTPException(400, "session_id required")
        params = {k: v for k, v in body.items() if k != "session_id"}
        result = await apply_op(op_name, sid, params)
        return JSONResponse(result)

    _endpoint.__name__ = f"op_{op_name}"
    app.post(f"/api/ops/{op_name}", name=f"op_{op_name}")(_endpoint)


def register_all_ops(app: FastAPI, mcp: FastMCP) -> None:
    """Bind every op in OP_REGISTRY to both MCP and FastAPI surfaces.

    Wrapped in a function (rather than the bare for-loop the previous
    version had) so tests can construct a fresh app without auto-binding
    every op, and so a future change to registration order is one edit
    instead of grepping for the loop.

    Note: FastAPI does not support adding new routes after uvicorn starts
    serving, so this MUST run at app construction time — not in lifespan.
    """
    for op_name in OP_REGISTRY:
        _register_op_as_mcp(mcp, op_name)
        _register_op_as_http(app, op_name)
