"""Picasso Studio — FastAPI + FastMCP composition root.

Two surfaces over one OP_REGISTRY:
- Web UI (HTTP) — humans click toolbar buttons, /api/ops/* endpoints
- MCP server   — Claude calls the ops as tools, mounted at /mcp

This file just wires the pieces together:
- `auth/`        — pure-ASGI bearer-token middleware + handshake nonces.
- `api/sessions` — REST routes for session CRUD + SSE.
- `api/files`    — authenticated file-serving + font enumeration.
- `api/meta`     — public health probe + token handshake.
- `mcp_tools`    — hand-written MCP tools (setup / config / sessions).
- `transport`    — auto-registration of OP_REGISTRY entries against
                   both MCP and FastAPI.
- `op_service`   — single apply_op() service shared by both surfaces.
- `paths`        — Pillow safety + workspace allowlist.

NOTE: do NOT add `from __future__ import annotations` here. FastMCP's
tool decorator inspects the wrapped function's annotations with
`eval_str=True`, which would try to resolve dynamically-created Model
names against module globals (they live in local scope) and NameError
at startup.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP

from .api import files as api_files
from .api import meta as api_meta
from .api import sessions as api_sessions
from .auth import AuthMiddleware, allowed_hosts_for, load_or_create_token
# Side-effect: importing ops package populates OP_REGISTRY
from . import mcp_tools, ops  # noqa: F401
from .op_service import shutdown_op_executor
from .paths import configure_pillow
from .registry import OP_REGISTRY, ops_by_category
from .runtime import get_bind
from .sessions import list_sessions, restore_from_disk
from .transport import register_all_ops

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("picasso_studio")

STATIC_DIR = Path(__file__).parent / "static"

mcp = FastMCP("picasso-studio", streamable_http_path="/")

# Per-launch bearer token. Generated fresh on first run, stored at
# ~/.picasso_studio/token. Required on every authenticated request.
TOKEN = load_or_create_token()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Apply Pillow safety settings (decompression-bomb cap) here rather than
    # at import time so other in-process code isn't surprised.
    configure_pillow()
    # Restore any sessions that were saved to disk before the previous
    # shutdown. Used to run at module import time (which made the package
    # unimportable in tests).
    restore_from_disk()
    # Bridge FastMCP's lifespan into FastAPI's — Starlette doesn't propagate
    # a mounted sub-app's lifespan, so without this the MCP session manager
    # never initializes and POSTs return 500.
    async with mcp.session_manager.run():
        yield
    # Flush any debounced session writes on shutdown so we don't lose state.
    for sess in list_sessions():
        sess.flush()
    # Drain the dedicated image-op executor.
    shutdown_op_executor()


app = FastAPI(title="Picasso Studio", version="0.1.0", lifespan=lifespan)

_BIND = get_bind()
app.add_middleware(
    AuthMiddleware,
    token=TOKEN,
    allowed_hosts=allowed_hosts_for(_BIND.host, _BIND.port),
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers — keep app.py thin; each surface lives in its own module.
app.include_router(api_meta.router)
app.include_router(api_meta.make_token_handshake_router(TOKEN))
app.include_router(api_sessions.router)
app.include_router(api_files.router)

# Hand-written MCP tools (setup / config / session lifecycle / open_studio).
mcp_tools.register(mcp)

# Auto-registered op tools + endpoints.
register_all_ops(app, mcp)

# FastMCP exposes a Starlette app at /mcp by default for streamable-http.
# We mount its asgi app under /mcp so a single uvicorn serves both surfaces.
app.mount("/mcp", mcp.streamable_http_app())


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/ops")
async def api_list_ops() -> dict:
    """Return the op registry shape for the UI to render buttons.

    Cache + invalidation live in `registry.ops_shape()` — single source
    of truth, automatically cleared when an op registers (no listener
    plumbing required).
    """
    from .registry import ops_shape
    return ops_shape()


def main() -> None:
    import uvicorn

    bind = get_bind()
    log.info("starting picasso-studio on %s:%s", bind.host, bind.port)
    log.info("registered %d ops in %d categories",
             len(OP_REGISTRY), len(ops_by_category()))
    uvicorn.run(app, host=bind.host, port=bind.port, log_level="info")


if __name__ == "__main__":
    main()
