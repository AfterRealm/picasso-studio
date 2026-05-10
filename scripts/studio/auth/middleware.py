"""Pure-ASGI auth middleware for Picasso Studio.

CRITICAL: this middleware MUST stay pure-ASGI. Starlette's
BaseHTTPMiddleware buffers streaming response bodies before passing them
back to the client, which silently breaks both:

- The SSE endpoint at `/api/sessions/{sid}/events` (clients see no events
  until the connection closes — i.e., the live UI updates we ship don't).
- FastMCP's streamable-HTTP transport mounted at `/mcp` (chunked replies
  get buffered, and the MCP client times out waiting for the stream).

A pure-ASGI middleware operates on `(scope, receive, send)` directly and
never touches the response body. Starlette / FastAPI consume it via
`app.add_middleware(...)` exactly the same way as the BaseHTTPMiddleware
form, but without the buffering hazard.

Auth policy:
- Public paths (PUBLIC_PATHS) skip every check — health probe + token
  handshake bootstrap.
- Everything else requires a valid `Authorization: Bearer <token>` (or
  `X-Picasso-Token`), an exact-match Host header, and (when present) a
  same-origin `Origin`/`Referer`.
- Comparison is constant-time so a timing oracle can't fish out the
  bearer token.
"""
from __future__ import annotations

import json
import logging
import secrets
from typing import Iterable
from urllib.parse import urlsplit

from starlette.types import ASGIApp

log = logging.getLogger("picasso_studio.auth.middleware")

# Routes that stay open: liveness probe + token handshake bootstrap +
# the index HTML itself (no per-user data; the app served from it must be
# able to load before it can call /token-handshake to redeem its nonce).
# EXACT match only — no startswith — so a future `/healthcheck-debug`
# doesn't silently inherit unauthenticated status.
PUBLIC_PATHS = frozenset({"/", "/health", "/token-handshake"})

# Public path PREFIXES — narrow set, intentional. /static carries the JS
# and CSS the browser needs to bootstrap; without it the index page loads
# but stays blank. Auth still gates every /api/* call the JS makes.
PUBLIC_PREFIXES = ("/static/",)


def _origin_host(value: str | None) -> str | None:
    """Return host:port of an Origin / Referer header (or None)."""
    if not value:
        return None
    try:
        parts = urlsplit(value)
        return parts.netloc or None
    except ValueError:
        return None


def _header(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> str | None:
    for k, v in headers:
        if k.lower() == name:
            try:
                return v.decode("latin-1")
            except UnicodeDecodeError:
                return None
    return None


def _cookie(headers: Iterable[tuple[bytes, bytes]], name: str) -> str | None:
    """Pull a single cookie value out of the request's Cookie header."""
    raw = _header(headers, b"cookie")
    if not raw:
        return None
    for piece in raw.split(";"):
        k, _, v = piece.strip().partition("=")
        if k == name:
            return v.strip()
    return None


async def _reject(scope: dict, send, *, status: int, body: dict) -> None:
    """Reject with a status-appropriate response for either http or websocket scope.

    Sending HTTP messages on a websocket scope raises in uvicorn — so for
    websocket we issue a pre-handshake close with an HTTP-style status code
    in the WS close-code namespace (4000 + status).
    """
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 4000 + status})
        return
    payload = json.dumps(body).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode("ascii")),
        ],
    })
    await send({"type": "http.response.body", "body": payload})


def allowed_hosts_for(host: str, port: int) -> set[str]:
    """All host:port pairs that count as 'us' for the Host header check.

    IPv6 Host headers are bracketed (`[::1]:port`) — that's the form
    browsers and curl actually send. The bare `::1` form is ambiguous as
    a Host header (the trailing port digits look like another hextet) so
    we don't include it.
    """
    aliases = {host}
    if host in ("127.0.0.1", "0.0.0.0"):
        aliases.update({"127.0.0.1", "localhost", "[::1]"})
    elif host == "localhost":
        aliases.update({"127.0.0.1", "localhost"})
    return {f"{h}:{port}" for h in aliases}


class AuthMiddleware:
    """Pure-ASGI bearer-token + Host/Origin enforcement.

    Use exactly like a BaseHTTPMiddleware:
        app.add_middleware(AuthMiddleware, token=..., allowed_hosts=...)

    But unlike BaseHTTPMiddleware, this does not wrap the response into an
    intermediate buffer; streaming responses pass through untouched.
    """

    def __init__(self, app: ASGIApp, *, token: str, allowed_hosts: Iterable[str]) -> None:
        self.app = app
        self._token = token
        self._allowed_hosts = frozenset(h.lower() for h in allowed_hosts)

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])

        # Host check — DNS-rebinding guard.
        host = (_header(headers, b"host") or "").lower()
        if host not in self._allowed_hosts:
            await _reject(scope, send, status=403,
                          body={"error": "host header rejected (DNS-rebinding guard)"})
            return

        # Origin/Referer check — same-origin or no-origin only.
        origin = _origin_host(_header(headers, b"origin")) or _origin_host(_header(headers, b"referer"))
        if origin is not None and origin.lower() not in self._allowed_hosts:
            await _reject(scope, send, status=403,
                          body={"error": "cross-origin request rejected"})
            return

        # Token check — accept (in priority order):
        #   1. Authorization: Bearer <token>  — preferred, set by JS fetch
        #   2. X-Picasso-Token: <token>       — alternative for MCP clients
        #   3. picasso_token cookie           — implicit auth for EventSource
        #                                       and <img> (which can't set
        #                                       headers); set by /token-handshake
        auth_header = _header(headers, b"authorization") or ""
        if auth_header.lower().startswith("bearer "):
            presented = auth_header[7:].strip()
        else:
            presented = (_header(headers, b"x-picasso-token") or "").strip()
        if not presented:
            presented = _cookie(headers, "picasso_token") or ""
        if not presented or not secrets.compare_digest(presented, self._token):
            # Log presented length (NOT the value) so misconfigured clients
            # can be diagnosed without leaking the real or attempted token.
            log.info("rejected bearer token of length %d on %s", len(presented), path)
            await _reject(scope, send, status=401,
                          body={"error": "missing or invalid bearer token"})
            return

        await self.app(scope, receive, send)
