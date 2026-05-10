"""Runtime constants shared across modules — host/port, URL builders.

Centralizes the host/port lookup that was duplicated across app.py, the
_open_studio MCP tool, and start_studio.py.
"""
from __future__ import annotations

import os
from typing import NamedTuple


class Bind(NamedTuple):
    host: str
    port: int


def get_bind() -> Bind:
    """Return the host/port the server is (or will be) bound to."""
    return Bind(
        host=os.environ.get("PICASSO_HOST", "127.0.0.1"),
        port=int(os.environ.get("PICASSO_PORT", "8090")),
    )


def base_url() -> str:
    bind = get_bind()
    return f"http://{bind.host}:{bind.port}"


def studio_url(session_id: str | None = None, *, launch_nonce: str | None = None) -> str:
    url = base_url() + "/"
    qs = []
    if session_id:
        qs.append(f"session={session_id}")
    if launch_nonce:
        qs.append(f"launch={launch_nonce}")
    if qs:
        url += "?" + "&".join(qs)
    return url
