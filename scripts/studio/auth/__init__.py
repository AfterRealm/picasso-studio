"""Auth subpackage — token storage, launch nonces, request middleware.

Three concerns kept in their own modules so each is testable in isolation:
- `tokens` — on-disk persistence + per-OS perm tightening.
- `nonces` — bounded TTL store for one-time launch nonces.
- `middleware` — pure-ASGI bearer/Host/Origin enforcement (does NOT use
  BaseHTTPMiddleware — that breaks SSE + MCP streaming).

Top-level re-exports cover the symbols actually used by the rest of the
codebase. Internal helpers (TOKEN_DIR, PUBLIC_PATHS, _origin_host) stay
in their submodules.
"""
from __future__ import annotations

from .middleware import AuthMiddleware, allowed_hosts_for
from .nonces import mint_launch_nonce, redeem_launch_nonce
from .tokens import load_or_create_token

__all__ = [
    "AuthMiddleware",
    "allowed_hosts_for",
    "load_or_create_token",
    "mint_launch_nonce",
    "redeem_launch_nonce",
]
