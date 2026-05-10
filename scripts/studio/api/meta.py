"""Public meta endpoints: liveness probe + browser token handshake.

These are the only routes intentionally exempt from the auth middleware
(`PUBLIC_PATHS` in `auth.middleware`). Keep payloads minimal —
unauthenticated info leaks (versions, deployment fingerprint) start here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..auth import redeem_launch_nonce

router = APIRouter()

# The browser stores the token in two places:
# - sessionStorage, used by JS for the `Authorization: Bearer …` header on
#   `fetch()` calls.
# - A cookie (HttpOnly, SameSite=Strict), used implicitly by EventSource
#   and `<img src=…>` since neither lets us set custom headers.
# Both are accepted by AuthMiddleware. The cookie is SameSite=Strict so a
# malicious page cannot trigger an authenticated request via embed/img/etc;
# the middleware's Host + Origin check is the second belt.
TOKEN_COOKIE_NAME = "picasso_token"


@router.get("/health")
async def health() -> dict:
    """Unauthenticated liveness probe — used by start_studio.py port check.

    Intentionally minimal: any extra metadata here is unauthenticated info
    leak (version targeting, deployment fingerprinting). Authenticated
    diagnostics live elsewhere.
    """
    return {"ok": True}


def make_token_handshake_router(token: str) -> APIRouter:
    """Build the /token-handshake route bound to the running token."""
    r = APIRouter()

    @r.get("/token-handshake")
    async def token_handshake(launch: str):
        """Exchange a one-time launch nonce (minted by `open_studio` /
        start_studio.py) for the persistent bearer token.

        Sets the token as both a JSON body field (for JS / sessionStorage)
        AND an HttpOnly cookie so EventSource and `<img>` requests carry
        auth automatically.

        Public (no token required) — but the nonce is single-use and
        expires after 5 minutes, so a malicious page that doesn't have a
        fresh nonce can't get the token.
        """
        if not redeem_launch_nonce(launch):
            raise HTTPException(401, "invalid or already-redeemed launch nonce")
        resp = JSONResponse({"token": token})
        resp.set_cookie(
            key=TOKEN_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="strict",
            secure=False,  # localhost-only — TLS isn't on the table
            path="/",
            max_age=60 * 60 * 24,  # 24h; restart of the server rotates anyway
        )
        return resp

    return r
