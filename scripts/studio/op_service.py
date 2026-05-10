"""Single op invocation path used by both MCP and HTTP surfaces.

Before this module existed, MCP-side and HTTP-side op invocation each
implemented their own pre/post logic — and they drifted: HTTP truncated the
redo branch and emitted SSE notifications; MCP did neither. So an op called
from Claude wouldn't refresh the GUI canvas, and `record_op` was running its
own truncation on top of the HTTP-side one (duplicate work).

`apply_op` is the one place where 'run a registered op against a session'
lives. Both surfaces call it. Behavior is identical regardless of caller.

Threading model: image ops are CPU-bound and frequently long-running
(animate_*, gif_* loops). Routing them through asyncio's default executor
shares a pool with EVERY other to_thread call in the process — uploads,
matplotlib font enumeration, anything else — so a 5-second animate would
back up unrelated work. We give image ops their own bounded executor so
they queue against each other but leave the default pool free for short
infrastructure work.

Race-safety on incremental SSE: two concurrent ops on the same session
used to make `apply_op` look up `sess.history[-1]` after the await, which
could return the OTHER op's entry. We use a contextvar (set by record_op
inside the executor thread, copied across run_in_executor) so each
apply_op coroutine sees its own appended entry.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from .registry import OP_REGISTRY
from .sessions import SESSIONS_ROOT, get_session, take_recorded_entry

log = logging.getLogger("picasso_studio.op_service")

# Bounded pool sized to CPU count. Pillow releases the GIL during many
# native operations so threads (not processes) parallelize meaningfully on
# the C-side; for pure-Python frame loops the GIL caps real parallelism but
# keeps the system responsive instead of one op blocking everything.
_MAX_OP_WORKERS = max(2, (os.cpu_count() or 4))
_OP_EXECUTOR: ThreadPoolExecutor | None = None


def get_op_executor() -> ThreadPoolExecutor:
    """Lazily construct the dedicated image-op executor."""
    global _OP_EXECUTOR
    if _OP_EXECUTOR is None:
        _OP_EXECUTOR = ThreadPoolExecutor(
            max_workers=_MAX_OP_WORKERS,
            thread_name_prefix="picasso-op",
        )
    return _OP_EXECUTOR


def shutdown_op_executor() -> None:
    """Drain pending op work and free the executor. Called from lifespan."""
    global _OP_EXECUTOR
    if _OP_EXECUTOR is not None:
        _OP_EXECUTOR.shutdown(wait=True)
        _OP_EXECUTOR = None


async def apply_op(op_name: str, session_id: str, params: dict[str, Any]) -> dict:
    """Run a registered op against a session, returning its result dict.

    Handles:
    - Validating session exists.
    - Off-loading the (synchronous, CPU-bound) op work to the dedicated
      image-op executor so the asyncio event loop keeps serving SSE +
      MCP + other endpoints, AND so unrelated to_thread calls don't
      starve when an op is slow.
    - Emitting an INCREMENTAL SSE 'op_entry_appended' event on success
      with the entry the op just recorded (race-safe via contextvar) +
      cursor flags. UI subscribers apply the delta locally.

    Note: the op's own decorator (`register_op`) already wraps it in error
    handling, so exceptions surface as `{'error': ...}` dicts from the op
    itself; we never need to catch broadly here. record_op (called inside
    the op) already truncates the redo branch on its own — DO NOT pre-
    truncate here, that was the duplicate-work bug.
    """
    op = OP_REGISTRY.get(op_name)
    if op is None:
        return {"error": f"unknown op: {op_name}", "op": op_name}
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}", "op": op_name}

    loop = asyncio.get_running_loop()
    executor = get_op_executor()

    # Run inside a fresh contextvars.Context so the recorded-entry slot is
    # isolated to this single op call — concurrent apply_op calls against
    # the same session each see their own entry, not each other's.
    ctx = contextvars.copy_context()

    def _run() -> dict:
        return ctx.run(partial(op.func, session_id=session_id, **params))

    result = await loop.run_in_executor(executor, _run)
    entry = ctx.run(take_recorded_entry)

    if isinstance(result, dict) and "error" not in result:
        await sess.notify({
            "type": "op_entry_appended",
            "result": result,
            "entry": entry.to_dict(SESSIONS_ROOT) if entry is not None else None,
            "cursor": sess.cursor,
            "can_undo": sess.cursor >= 0,
            "can_redo": sess.cursor < len(sess.history) - 1,
        })
    return result
