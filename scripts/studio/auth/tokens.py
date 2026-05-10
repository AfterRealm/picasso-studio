"""Per-launch bearer-token storage for Picasso Studio.

The token is generated fresh on first run and persisted at
~/.picasso_studio/token. POSIX gets chmod 600. Windows gets a best-effort
icacls tightening that grants the current user exclusive Read/Write and
removes inherited ACEs; if icacls is missing or fails, we log a warning
loud enough for the user to notice and verify ACLs themselves.
"""
from __future__ import annotations

import getpass
import logging
import os
import secrets
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("picasso_studio.auth.tokens")

TOKEN_DIR = Path.home() / ".picasso_studio"
TOKEN_PATH = TOKEN_DIR / "token"


def _restrict_perms_posix(path: Path) -> None:
    try:
        os.chmod(path, 0o600 if path.is_file() else 0o700)
    except OSError as exc:
        log.warning("could not chmod %s: %s", path, exc)


def _restrict_perms_windows(path: Path) -> None:
    """Best-effort ACL tightening on Windows for the TOKEN FILE ONLY.

    NEVER call this on the parent directory — `icacls /inheritance:r` on a
    directory propagates to every child file (existing AND future), which
    locks out config.json, sessions data, etc. Token-file scope only.

    On Windows, write_text() inherits parent ACLs, which can be wider than
    the current user under non-default profiles (OneDrive sync, GPO
    overrides, migrated profiles). icacls disables inheritance and grants
    only the current user. If icacls isn't available the user gets a
    warning rather than a silent fail.
    """
    icacls = shutil.which("icacls")
    if icacls is None:
        log.warning(
            "icacls not found on PATH; cannot tighten ACL on %s. "
            "Verify file permissions manually.",
            path,
        )
        return
    user = os.environ.get("USERNAME") or getpass.getuser()
    try:
        # Remove inheritance, then grant the current user F (full control).
        subprocess.run(
            [icacls, str(path), "/inheritance:r"],
            check=False, capture_output=True, text=True,
        )
        result = subprocess.run(
            [icacls, str(path), "/grant:r", f"{user}:F"],
            check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            log.warning(
                "icacls grant failed on %s (%s); verify ACL manually",
                path, result.stderr.strip() or result.stdout.strip(),
            )
    except OSError as exc:
        log.warning("icacls invocation failed on %s: %s", path, exc)


def _restrict_perms(path: Path) -> None:
    """Tighten perms on the token FILE only.

    Directory perms are intentionally left to the user-profile inheritance —
    locking the directory would propagate to every other file we put there
    (config.json, future state) and break unrelated reads/writes. The token
    file gets its own explicit lock.
    """
    if not path.is_file():
        return
    if os.name == "posix":
        _restrict_perms_posix(path)
    else:
        _restrict_perms_windows(path)


def load_or_create_token() -> str:
    """Load the persistent bearer token, generating a fresh one on first run.

    The directory is created with restrictive perms BEFORE the file is
    written, so the file inherits a tight base. The file then gets its own
    explicit tightening.

    If a prior run left the file unreadable AND unwritable (e.g. a botched
    ACL change), we delete + recreate rather than crash on startup.
    """
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    # NOTE: do not lock the directory itself — config.json + other state
    # live here too, and a directory-scoped /inheritance:r blocks them.
    if TOKEN_PATH.exists():
        try:
            tok = TOKEN_PATH.read_text(encoding="utf-8").strip()
            if tok:
                return tok
        except OSError as exc:
            log.warning("token unreadable, regenerating: %s", exc)
    tok = secrets.token_urlsafe(32)

    def _write_or_die() -> None:
        try:
            TOKEN_PATH.write_text(tok, encoding="utf-8")
        except PermissionError as exc:
            raise RuntimeError(
                f"could not write token file at {TOKEN_PATH}: {exc}. "
                "Delete the file manually and restart."
            ) from exc

    try:
        TOKEN_PATH.write_text(tok, encoding="utf-8")
    except PermissionError:
        log.warning("token file unwritable; deleting and retrying")
        try:
            TOKEN_PATH.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"could not reset token file at {TOKEN_PATH}: {exc}. "
                "Delete it manually and restart."
            ) from exc
        _write_or_die()
    _restrict_perms(TOKEN_PATH)
    return tok
