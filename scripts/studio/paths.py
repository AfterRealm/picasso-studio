"""Safe path resolution + image validation for Picasso Studio.

Picasso Studio takes file paths from a chat agent (via MCP) and from a browser
(via HTTP). Both surfaces are user-trusted in practice but agents are routinely
prompt-injected, and a malicious page can talk to the local server. So every
path we read or write goes through this module, which:

- Resolves the path with symlinks expanded.
- Confirms the resolved path is inside an explicit allowlist (a workspace
  root). Reading `~/.ssh/id_rsa` because the agent was tricked into asking
  for it stops here.
- Sniffs image bytes via Pillow's verify() before persisting anything.
- Caps file size and pixel count so a decompression bomb can't OOM the
  process.
- Whitelists output extensions so a path traversal via filename can't end
  up writing `pwn.exe.png` style names.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

log = logging.getLogger("picasso_studio.paths")

# Hard ceilings — bound the "an agent in a loop with a bad input" worst case.
MAX_INPUT_BYTES = 50 * 1024 * 1024  # 50 MB on disk
MAX_PIXELS = 8192 * 8192            # ~67M; matches the MAX_DIMENSION cap
ALLOWED_INPUT_EXTS = frozenset({
    "png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "avif", "ico",
})
SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def _compute_input_roots() -> list[Path]:
    """Default allowlist roots for inputs from the chat agent.

    Override at runtime via PICASSO_WORKSPACE (os.pathsep-separated).
    Defaults to the user's home directory; never the filesystem root.
    Computed lazily so PICASSO_WORKSPACE set after import (in tests, etc.)
    is respected.
    """
    extra = os.environ.get("PICASSO_WORKSPACE", "")
    roots: list[Path] = []
    if extra:
        for raw_entry in extra.split(os.pathsep):
            entry = raw_entry.strip()
            if not entry:
                continue
            try:
                roots.append(Path(entry).expanduser().resolve())
            except OSError:
                continue
    if not roots:
        roots.append(Path.home().resolve())
    return roots


def input_roots() -> list[Path]:
    """Current input allowlist (re-read each call so tests can reconfigure)."""
    return _compute_input_roots()


def configure_pillow() -> None:
    """Apply Picasso's Pillow safety settings.

    Called from the FastAPI lifespan so tests / other in-process callers
    aren't surprised by an import-time global mutation.
    """
    from PIL import Image as _Image
    _Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class UnsafePathError(ValueError):
    """Raised when a caller-supplied path fails any safety check."""


def _is_within(child: Path, parents: Iterable[Path]) -> bool:
    try:
        rc = child.resolve()
    except OSError:
        return False
    for parent in parents:
        try:
            rc.relative_to(parent)
            return True
        except ValueError:
            continue
    return False


def safe_input_path(raw: str, *, verify_content: bool = True) -> Path:
    """Resolve an agent-supplied input path; raise if it escapes the allowlist.

    Returns a fully-resolved Path that is guaranteed to be within one of the
    configured input roots, exists on disk, is a regular file (not a device,
    pipe, symlink-to-elsewhere, etc.), has a recognized image suffix, AND —
    when `verify_content=True` (default) — passes Pillow's verify() so we
    don't persist a sneakily-renamed text file (or worse) as 'an image'.
    """
    if not raw or not isinstance(raw, str):
        raise UnsafePathError("path required")
    candidate = Path(raw).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UnsafePathError(f"path not found or unresolvable: {raw}") from exc
    if not resolved.is_file():
        raise UnsafePathError(f"not a regular file: {raw}")
    if not _is_within(resolved, _compute_input_roots()):
        raise UnsafePathError(
            "path outside the allowed workspace; set PICASSO_WORKSPACE to"
            " widen the allowlist if you trust this directory"
        )
    suffix = resolved.suffix.lstrip(".").lower()
    if suffix not in ALLOWED_INPUT_EXTS:
        raise UnsafePathError(f"unsupported file extension: {suffix or '(none)'}")
    if resolved.stat().st_size > MAX_INPUT_BYTES:
        raise UnsafePathError(
            f"input file exceeds {MAX_INPUT_BYTES // (1024 * 1024)} MB cap"
        )
    if verify_content:
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            raise UnsafePathError(f"could not read {raw}: {exc}") from exc
        verify_image_bytes(data)
    return resolved


def safe_ext(raw: str | None, fallback: str = "png") -> str:
    """Whitelist an extension string. Returns a safe lowercase ext."""
    if not raw:
        return fallback
    cleaned = re.sub(r"[^a-z0-9]", "", raw.lower())[:5]
    return cleaned if cleaned in ALLOWED_INPUT_EXTS else fallback


def verify_image_bytes(data: bytes) -> None:
    """Sniff bytes with Pillow. Raises UnsafePathError on bomb / parse fail."""
    if len(data) > MAX_INPUT_BYTES:
        raise UnsafePathError(
            f"input exceeds {MAX_INPUT_BYTES // (1024 * 1024)} MB cap"
        )
    # Pillow's MAX_IMAGE_PIXELS is module-global; we set it once at import
    # and rely on Image.open raising DecompressionBombError when exceeded.
    try:
        from io import BytesIO
        with Image.open(BytesIO(data)) as im:
            im.verify()
        with Image.open(BytesIO(data)) as im:
            w, h = im.size
        if w * h > MAX_PIXELS:
            raise UnsafePathError("image pixel count exceeds safety cap")
    except UnsafePathError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise UnsafePathError(f"input is not a valid image: {exc}") from exc


def safe_session_id(raw: str | None) -> str:
    """Validate a session id matches the strict id format."""
    if not raw or not SID_RE.match(raw):
        raise UnsafePathError("invalid session id")
    return raw


def assert_within(child: Path, parent: Path) -> Path:
    """Resolve `child` and assert it lives under `parent`. Returns resolved."""
    try:
        rc = child.resolve()
        rp = parent.resolve()
        rc.relative_to(rp)
    except (OSError, ValueError) as exc:
        raise UnsafePathError(f"path escapes session directory: {child}") from exc
    return rc


# Pillow's MAX_IMAGE_PIXELS used to be set here at import time; that's a
# global mutation surprising to anyone else in-process. configure_pillow()
# above is now called from the FastAPI lifespan so the change is explicit.
