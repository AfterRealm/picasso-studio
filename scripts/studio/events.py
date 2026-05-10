"""Per-session event hub — keeps SSE transport out of the Session model.

Session used to hold a `list[asyncio.Queue]` of subscribers directly, which
leaked the SSE/asyncio transport concern into the domain model. The hub
keeps that coupling out: Session.notify() forwards to the hub, and the SSE
endpoint subscribes/unsubscribes here. Sessions stay testable without an
event loop.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

log = logging.getLogger("picasso_studio.events")

MAX_SUBSCRIBERS_PER_SESSION = 8
QUEUE_MAX_EVENTS = 64


class SessionEventHub:
    """Per-session subscriber list, keyed by session id."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, sid: str) -> asyncio.Queue | None:
        """Open a subscriber queue for the session. None if cap reached."""
        bucket = self._queues[sid]
        if len(bucket) >= MAX_SUBSCRIBERS_PER_SESSION:
            return None
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_EVENTS)
        bucket.append(q)
        return q

    def unsubscribe(self, sid: str, queue: asyncio.Queue) -> None:
        bucket = self._queues.get(sid, [])
        try:
            bucket.remove(queue)
        except ValueError:
            pass
        if not bucket:
            self._queues.pop(sid, None)

    def publish(self, sid: str, event: dict) -> None:
        """Push an event to every live subscriber of this session."""
        bucket = self._queues.get(sid)
        if not bucket:
            return
        dead: list[asyncio.Queue] = []
        for q in list(bucket):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("dropping event for session %s; subscriber queue full", sid)
                dead.append(q)
        for q in dead:
            try:
                bucket.remove(q)
            except ValueError:
                pass


# Global broadcast channel — events that any GUI tab should hear regardless
# of which session it's bound to (e.g. "a new session was created via MCP,
# do you want to switch?"). Same shape as SessionEventHub but with a single
# bucket.
class GlobalEventHub:
    """Process-wide pub/sub for cross-session UI events."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_EVENTS)
        self._queues.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        try:
            self._queues.remove(queue)
        except ValueError:
            pass

    def publish(self, event: dict) -> None:
        dead: list[asyncio.Queue] = []
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("dropping global event; subscriber queue full")
                dead.append(q)
        for q in dead:
            try:
                self._queues.remove(q)
            except ValueError:
                pass


# Single process-wide hubs.
HUB = SessionEventHub()
GLOBAL_HUB = GlobalEventHub()
