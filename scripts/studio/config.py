"""User-level config for Picasso Studio.

Stored at `~/.picasso_studio/config.json`. Persists the user's chosen mode
across sessions so the launcher and MCP layer behave consistently.

Schema:
    {
        "mode": "inline" | "gui" | null,
        "first_run_complete": bool
    }

`mode=null` means the user hasn't chosen yet — Claude should AskUserQuestion
on the next invocation.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger("picasso_studio.config")

Mode = Literal["inline", "gui"]

CONFIG_DIR = Path.home() / ".picasso_studio"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "mode": None,
    "first_run_complete": False,
}

# In-memory cache invalidated by file mtime. Without this, get_mode() ran
# on every inline-mode op result, hammering the disk on the hot path.
_cache: dict[str, Any] | None = None
_cache_mtime: float = 0.0


def _restrict_perms() -> None:
    """Tighten config file perms so other local users can't read secrets we
    might add here later (auth tokens belong elsewhere, but the hygiene cost
    is near zero)."""
    try:
        if os.name == "posix":
            if CONFIG_DIR.exists():
                os.chmod(CONFIG_DIR, 0o700)
            if CONFIG_PATH.exists():
                os.chmod(CONFIG_PATH, 0o600)
    except OSError as exc:
        log.warning("could not restrict config perms: %s", exc)


def _read_disk() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return copy.deepcopy(DEFAULT_CONFIG)
        merged = copy.deepcopy(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return copy.deepcopy(DEFAULT_CONFIG)


def load_config() -> dict[str, Any]:
    """Read the config file, with mtime-invalidated in-memory caching."""
    global _cache, _cache_mtime
    try:
        mtime = CONFIG_PATH.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _cache is None or mtime != _cache_mtime:
        _cache = _read_disk()
        _cache_mtime = mtime
    return copy.deepcopy(_cache)


def save_config(config: dict[str, Any]) -> None:
    global _cache, _cache_mtime
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    _restrict_perms()
    _cache = copy.deepcopy(config)
    try:
        _cache_mtime = CONFIG_PATH.stat().st_mtime
    except OSError:
        _cache_mtime = time.time()


def get_mode() -> Mode | None:
    """Return the current mode, or None if not yet chosen."""
    return load_config().get("mode")


def set_mode(mode: Mode | None) -> dict[str, Any]:
    """Persist a new mode. Returns the updated config.

    Only flips first_run_complete=True when the user actually picked a mode;
    set_mode(None) is the 'leave the choice unset' path and shouldn't claim
    setup is done.
    """
    config = load_config()
    config["mode"] = mode
    if mode is not None:
        config["first_run_complete"] = True
    save_config(config)
    return config
