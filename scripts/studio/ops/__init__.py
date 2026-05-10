"""Op modules — importing this package side-effects the OP_REGISTRY.

Each submodule decorates its op functions with @register_op, which appends
to OP_REGISTRY at import time. We auto-discover every public submodule so
adding `ops/<new>.py` is a drop-in: no manual edit here required.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil

log = logging.getLogger("picasso_studio.ops")


def _autoload() -> None:
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f".{info.name}", __name__)
        except Exception as exc:  # noqa: BLE001  -- one bad op shouldn't kill the whole registry
            log.warning("failed to load ops.%s: %s", info.name, exc)


_autoload()
