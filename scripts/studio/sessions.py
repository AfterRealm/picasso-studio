"""Per-session state for the editor.

A session = one image the user is editing, plus its op history. Each session
has a directory on disk (`sessions_data/<id>/`) holding the original upload
plus all intermediate frames, and an in-memory state dict tracking the current
image and history.

SSE subscribers used to live on the Session itself, which leaked the asyncio
transport into the domain model. They're now in `events.HUB`, addressed by
session id; Session.notify() forwards there.
"""
from __future__ import annotations

import contextvars
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from .events import HUB
from .paths import SID_RE, UnsafePathError, assert_within, safe_ext, verify_image_bytes

log = logging.getLogger("picasso_studio.sessions")

SESSIONS_ROOT = Path(__file__).parent / "sessions_data"
SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)

# Bound how often a single session rewrites its session.json. Many ops in a
# row used to fsync the entire history list per call.
_SAVE_DEBOUNCE_SECONDS = 1.0


@dataclass
class HistoryEntry:
    op: str
    params: dict
    output_path: str
    ts: float = field(default_factory=time.time)
    note: str = ""  # human-readable label for the UI
    size: int = 0   # bytes; cached at write time so to_dict() can skip stat()

    def to_dict(self, root: Path) -> dict:
        """Serialize to the wire shape used by SSE + Session.to_dict.

        Single source of truth — when HistoryEntry grows a field, every
        consumer (SSE incremental events, full session snapshots) gets it
        for free. Previously op_service had its own inline serialization
        that drifted.
        """
        try:
            output_rel = str(Path(self.output_path).relative_to(root))
        except (ValueError, OSError):
            output_rel = self.output_path
        return {
            "op": self.op,
            "params": self.params,
            "output": output_rel,
            "ts": self.ts,
            "note": self.note,
            "size": self.size,
        }


@dataclass
class Session:
    id: str
    dir: Path
    original: Path
    original_size: int = 0
    history: list[HistoryEntry] = field(default_factory=list)
    cursor: int = -1  # -1 = original; 0..len(history)-1 = at that step
    _last_save: float = field(default=0.0, repr=False)
    _save_pending: bool = field(default=False, repr=False)

    @property
    def current_image(self) -> Path:
        if self.cursor < 0 or self.cursor >= len(self.history):
            return self.original
        return Path(self.history[self.cursor].output_path)

    def current_size(self) -> int:
        if self.cursor < 0 or self.cursor >= len(self.history):
            return self.original_size
        return self.history[self.cursor].size

    def to_dict(self) -> dict:
        cur = self.current_image
        return {
            "id": self.id,
            "current_image": str(cur.relative_to(SESSIONS_ROOT)),
            "original": str(self.original.relative_to(SESSIONS_ROOT)),
            "size": self.current_size(),
            "cursor": self.cursor,
            "can_undo": self.cursor >= 0,
            "can_redo": self.cursor < len(self.history) - 1,
            "history": [h.to_dict(SESSIONS_ROOT) for h in self.history],
        }

    async def notify(self, event: dict) -> None:
        """Push an SSE event to all live subscribers via the hub."""
        HUB.publish(self.id, event)

    def _serialize(self) -> dict:
        return {
            "id": self.id,
            "original": self.original.name,
            "original_size": self.original_size,
            "cursor": self.cursor,
            "history": [
                {"op": h.op, "params": h.params, "output": Path(h.output_path).name,
                 "ts": h.ts, "note": h.note, "size": h.size}
                for h in self.history
            ],
        }

    def save(self) -> None:
        """Persist session metadata to disk, debounced.

        Many ops in a row (the common case) collapse into a single write.
        On heavy contention the actual disk write is deferred to a background
        sync via flush(); the file always reflects the most recent state at
        most _SAVE_DEBOUNCE_SECONDS after the last call.
        """
        now = time.monotonic()
        if now - self._last_save < _SAVE_DEBOUNCE_SECONDS:
            self._save_pending = True
            return
        self._write_now()

    def flush(self) -> None:
        """Force any pending debounced write to disk now."""
        if self._save_pending:
            self._write_now()

    def _write_now(self) -> None:
        meta = self._serialize()
        try:
            (self.dir / "session.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8",
            )
            self._last_save = time.monotonic()
            self._save_pending = False
        except OSError as exc:
            log.warning("failed to save session %s: %s", self.id, exc)


class SessionStore:
    """In-memory map of session_id → Session.

    Pulled out of a bare module-level dict so tests can construct a fresh
    store with a temp `sessions_root`, and so a future scope-change (e.g.
    per-user stores) doesn't require a codebase-wide find/replace.

    The module-level functions (`get_session`, `list_sessions`,
    `create_session`, `record_op`, `restore_from_disk`) operate on a
    process-wide default store for backward compatibility.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, sid: str) -> Session | None:
        if not isinstance(sid, str) or not SID_RE.match(sid):
            return None
        return self._sessions.get(sid)

    def all(self) -> list[Session]:
        return list(self._sessions.values())

    def add(self, sess: Session) -> None:
        self._sessions[sess.id] = sess


# Process-wide default store. Tests / future per-scope work can construct
# their own via SessionStore(); the module-level functions below all
# delegate here.
_default_store = SessionStore()


# Backward-compatibility shim — old code reaches `_sessions` directly in a
# few places. Prefer `_default_store` going forward.
_sessions = _default_store._sessions  # noqa: SLF001 — same dict, two names


def restore_from_disk() -> int:
    """Rebuild Sessions from `sessions_data/`. Call once at server startup.

    Used to run at import time, which made the module unimportable in tests
    and tied import order to the filesystem. Call from FastAPI's lifespan
    instead.
    """
    if not SESSIONS_ROOT.exists():
        return 0
    restored = 0
    sroot_resolved = SESSIONS_ROOT.resolve()
    for sdir in SESSIONS_ROOT.iterdir():
        if not sdir.is_dir():
            continue
        meta_path = sdir / "session.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                continue
            sid = meta.get("id", "")
            if not isinstance(sid, str) or not SID_RE.match(sid):
                log.warning("skipping session with invalid id at %s", sdir)
                continue
            # Cross-check that the on-disk dir name matches the id, so a
            # planted session.json with id='other-session' can't redirect
            # us into a different folder.
            if sdir.name != sid:
                log.warning("skipping session id mismatch at %s (id=%s)", sdir, sid)
                continue
            original_name = meta.get("original")
            if not isinstance(original_name, str) or "/" in original_name or "\\" in original_name:
                continue
            original = sdir / original_name
            try:
                assert_within(original, sroot_resolved)
            except UnsafePathError:
                continue
            if not original.exists():
                continue
            sess = Session(
                id=sid,
                dir=sdir,
                original=original,
                original_size=original.stat().st_size,
                cursor=int(meta.get("cursor", -1)),
            )
            for raw in meta.get("history", []):
                if not isinstance(raw, dict):
                    continue
                output_name = raw.get("output")
                if not isinstance(output_name, str) or "/" in output_name or "\\" in output_name:
                    continue
                output_path = sdir / output_name
                try:
                    assert_within(output_path, sroot_resolved)
                except UnsafePathError:
                    continue
                if not output_path.exists():
                    continue
                raw_params = raw.get("params")
                params_dict = raw_params if isinstance(raw_params, dict) else {}
                sess.history.append(HistoryEntry(
                    op=str(raw.get("op", "?")),
                    params=params_dict,
                    output_path=str(output_path),
                    ts=float(raw.get("ts", time.time())),
                    note=str(raw.get("note", "")),
                    size=int(raw.get("size") or output_path.stat().st_size),
                ))
            sess.cursor = min(sess.cursor, len(sess.history) - 1)
            _sessions[sess.id] = sess
            restored += 1
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError) as exc:
            log.warning("failed to restore session from %s: %s", sdir, exc)
    if restored:
        log.info("restored %d session(s) from disk", restored)
    return restored


def create_session(image_bytes: bytes, ext: str = "png") -> Session:
    """Create a fresh session from raw image bytes.

    The bytes are validated as a real image (not e.g. a sneakily-renamed text
    file) and bounded by size BEFORE any persistence happens — failing closed
    is the safer default for a server that the chat agent can drive.
    """
    verify_image_bytes(image_bytes)
    safe = safe_ext(ext, fallback="png")
    sid = secrets.token_urlsafe(16)
    sdir = SESSIONS_ROOT / sid
    sdir.mkdir(parents=True, exist_ok=True)
    original = sdir / f"original.{safe}"
    original.write_bytes(image_bytes)
    sess = Session(
        id=sid,
        dir=sdir,
        original=original,
        original_size=len(image_bytes),
    )
    _sessions[sid] = sess
    sess.save()
    # Broadcast on the global hub so any open GUI tab can offer to switch
    # to the new session (the per-session hub doesn't help here — nobody's
    # subscribed to a brand-new session yet).
    from .events import GLOBAL_HUB
    GLOBAL_HUB.publish({
        "type": "session_created",
        "session_id": sid,
        "original": str(original.name),
    })
    return sess


def get_session(sid: str) -> Session | None:
    return _default_store.get(sid)


def list_sessions() -> list[Session]:
    return _default_store.all()


# ContextVar so apply_op can pick up the just-appended HistoryEntry without
# racing against other concurrent ops on the same session. Each apply_op
# coroutine has its own copy; record_op sets it inside the executor thread.
_RECORDED_ENTRY: contextvars.ContextVar[HistoryEntry | None] = \
    contextvars.ContextVar("picasso_recorded_entry", default=None)


def take_recorded_entry() -> HistoryEntry | None:
    """Pop the entry record_op set during this op's execution (if any)."""
    entry = _RECORDED_ENTRY.get()
    _RECORDED_ENTRY.set(None)
    return entry


def record_op(sess: Session, op: str, params: dict, output_path: Path, note: str = "") -> HistoryEntry:
    """Add an op result to history. Truncates redo branch first if cursor is mid-history."""
    if sess.cursor < len(sess.history) - 1:
        sess.history = sess.history[: sess.cursor + 1]
    try:
        size = output_path.stat().st_size
    except OSError:
        size = 0
    entry = HistoryEntry(
        op=op,
        params=params,
        output_path=str(output_path),
        note=note,
        size=size,
    )
    sess.history.append(entry)
    sess.cursor = len(sess.history) - 1
    sess.save()
    _RECORDED_ENTRY.set(entry)
    return entry
