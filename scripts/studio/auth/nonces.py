"""Single-use launch nonces — bridges the persistent bearer token to the
local browser without the token ever traveling on a URL of any other page.

Nonces have a TTL and a max-size cap so a misbehaving caller (or a prompt-
injected loop on `open_studio`) can't grow process RSS unboundedly.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict

NONCE_TTL_SECONDS = 5 * 60
NONCE_MAX_ENTRIES = 64


class NonceStore:
    """Thread-safe bounded TTL store for one-time launch nonces.

    OrderedDict gives O(1) insertion + O(1) FIFO eviction; explicit per-call
    sweep prunes expired entries on every mint and redeem so we don't hold
    forever-stale tokens even if traffic stops.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = NONCE_TTL_SECONDS,
        max_entries: int = NONCE_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, float] = OrderedDict()

    def _sweep_expired(self, now: float) -> None:
        # OrderedDict is insertion-ordered; once we hit a non-expired entry
        # we know everything after it is younger.
        cutoff = now - self._ttl
        while self._entries:
            nonce, ts = next(iter(self._entries.items()))
            if ts >= cutoff:
                break
            self._entries.popitem(last=False)

    def mint(self) -> str:
        nonce = secrets.token_urlsafe(24)
        with self._lock:
            now = time.monotonic()
            self._sweep_expired(now)
            while len(self._entries) >= self._max:
                self._entries.popitem(last=False)
            self._entries[nonce] = now
        return nonce

    def redeem(self, nonce: str) -> bool:
        with self._lock:
            now = time.monotonic()
            self._sweep_expired(now)
            ts = self._entries.pop(nonce, None)
        return ts is not None


# Process-wide singleton for the FastAPI app + MCP tools.
STORE = NonceStore()


def mint_launch_nonce() -> str:
    return STORE.mint()


def redeem_launch_nonce(nonce: str) -> bool:
    return STORE.redeem(nonce)
