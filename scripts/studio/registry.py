"""Op registry — single source of truth for all image operations.

Each op is a function that takes (session_id, **params) and mutates the session's
current image. Ops are registered once and exposed to BOTH the MCP server (so
Claude can call them) and the FastAPI HTTP layer (so the web UI buttons can call
them). One source of truth, two surfaces.

Usage:

    from picasso_studio.registry import register_op

    @register_op(
        category="filter",
        label="Sepia",
        description="Warm, vintage tone — converts the image to sepia.",
        params={},
    )
    def sepia(session_id: str) -> dict:
        ...
        return {"output_path": new_path}
"""
from __future__ import annotations

import functools
import logging
import os
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("picasso_studio.ops")

# When PICASSO_DEBUG=1, op error responses include the full Python traceback.
# Off by default to keep error messages readable in chat.
_DEBUG = os.environ.get("PICASSO_DEBUG", "").lower() in ("1", "true", "yes")


@dataclass
class OpDef:
    """Metadata + function for one image operation."""
    name: str
    func: Callable
    category: str
    label: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)
    """Param schema. Keys are param names, values are dicts like
    {'type': 'int', 'default': 1024, 'min': 1, 'max': 8192, 'help': '...'}.
    Used for both UI controls and MCP tool argument descriptions."""
    interactive: dict[str, Any] | None = None
    """Optional UI hint for direct-on-canvas interaction. Shape:
    {'type': 'rect', 'params': ['left','top','right','bottom']} — UI shows a draggable rect overlay
    {'type': 'text', 'params': {'x':'x','y':'y','text':'text','font':'font','size':'size','color':'color'}} — text modal + draggable overlay
    {'type': 'point', 'params': ['x','y']} — single click-to-place point
    When set, clicking the op enters an on-canvas mode instead of opening the popover."""


OP_REGISTRY: dict[str, OpDef] = {}


def register_op(
    *,
    category: str,
    label: str,
    description: str,
    params: dict[str, Any] | None = None,
    interactive: dict[str, Any] | None = None,
) -> Callable:
    """Decorator that registers an op into OP_REGISTRY.

    The op function is wrapped in a uniform error handler — any uncaught
    exception during execution is converted to `{"error": "<class>: <msg>"}`
    so MCP / HTTP callers always get a structured response instead of a 500.
    Errors are also logged with full traceback for server-side debugging."""
    def wrap(func: Callable) -> Callable:
        @functools.wraps(func)
        def safe(*args: Any, **kwargs: Any) -> dict:
            try:
                result = func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                log.exception("op %s failed", func.__name__)
                err: dict = {
                    "error": f"{type(exc).__name__}: {exc}",
                    "op": func.__name__,
                }
                if _DEBUG:
                    err["trace"] = traceback.format_exc()
                return err
            if not isinstance(result, dict):
                return {
                    "error": f"op returned non-dict: {type(result).__name__}",
                    "op": func.__name__,
                }
            return result

        OP_REGISTRY[func.__name__] = OpDef(
            name=func.__name__,
            func=safe,
            category=category,
            label=label,
            description=description,
            params=params or {},
            interactive=interactive,
        )
        ops_by_category.cache_clear()  # type: ignore[attr-defined]
        ops_shape.cache_clear()        # type: ignore[attr-defined]
        return safe
    return wrap


@functools.lru_cache(maxsize=1)
def ops_shape() -> dict[str, list[dict]]:
    """JSON-ready shape served at /api/ops, cached and centrally invalidated.

    Lives in registry.py so the cache and the canonical shape stay
    co-located with the data. `register_op` clears it the same way it
    clears `ops_by_category`. Previous versions had a sibling cache in
    app.py wired through a one-listener pubsub — this is the same thing
    without the indirection.
    """
    out: dict[str, list[dict]] = {}
    for cat, ops_list in ops_by_category().items():
        out[cat] = [
            {
                "name": o.name,
                "label": o.label,
                "description": o.description,
                "params": o.params,
                "interactive": o.interactive,
            }
            for o in ops_list
        ]
    return out


@functools.lru_cache(maxsize=1)
def ops_by_category() -> dict[str, list[OpDef]]:
    """Group ops by category for UI rendering. Cached — registry is frozen
    after import in practice; the @register_op decorator clears this on any
    new registration so dynamic op loading still works."""
    out: dict[str, list[OpDef]] = {}
    for op in OP_REGISTRY.values():
        out.setdefault(op.category, []).append(op)
    return out
