#!/usr/bin/env python
"""Bootstrap entrypoint for Picasso Studio.

Adds the scripts/ directory to sys.path so `studio` resolves as a package,
checks for required dependencies, prints the bearer token + handshake URL
so the user can configure their MCP client, then starts the FastAPI +
FastMCP server on localhost:8090 (override via PICASSO_HOST / PICASSO_PORT
env vars).

Idempotent: if a server is already running on the port, this prints the URL
and exits without starting a second one.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

REQUIRED = {
    "fastapi": "fastapi>=0.115",
    "uvicorn": "uvicorn[standard]>=0.30",
    "mcp": "mcp>=1.0",
    "PIL": "pillow>=10.0",
    "pydantic": "pydantic>=2.0",
}


def _check_deps() -> list[str]:
    """Return a list of pip-installable specs for missing modules."""
    missing: list[str] = []
    for mod, spec in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(spec)
    return missing


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def _is_picasso_on_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Hit /health and decide if the listener is Picasso (vs some other
    service that happens to be on this port).

    /health is the unauthenticated probe; we look for the exact `{"ok": true}`
    shape Picasso returns. Anything else (different JSON, HTML, timeout,
    connection reset) → not Picasso.
    """
    import json
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    try:
        req = Request(f"http://{host}:{port}/health", headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            return isinstance(body, dict) and body.get("ok") is True
    except (URLError, json.JSONDecodeError, TimeoutError, OSError, ValueError):
        return False


def _find_free_port(host: str, start: int, ceiling: int = 50) -> int | None:
    """Return the lowest free port at or above `start` (within `ceiling`
    consecutive tries), or None if none free."""
    for candidate in range(start, start + ceiling):
        if not _is_port_in_use(host, candidate):
            return candidate
    return None


def _print_auth_banner(token: str, base_url: str) -> None:
    """Show the bearer token + handshake URL once on startup.

    Required for MCP clients (Claude Desktop / Code) and for any non-browser
    HTTP caller. Browser bootstrap goes through /token-handshake with a
    one-time launch nonce — see studio/auth/.

    Defaults to printing the token PATH only; set PICASSO_PRINT_TOKEN=1 to
    inline-print the value (useful on first run; risky if stdout is captured
    by a service supervisor / log collector / shared terminal).
    """
    token_path = Path.home() / ".picasso_studio" / "token"
    print()
    print("=" * 64)
    if os.environ.get("PICASSO_PRINT_TOKEN", "").lower() in ("1", "true", "yes"):
        print("Picasso Studio bearer token (required for MCP + HTTP clients):")
        print(f"   {token}")
        print()
        print("MCP client config: add to your MCP server entry's headers:")
        print(f"   Authorization: Bearer {token}")
    else:
        print("Picasso Studio bearer token written to:")
        print(f"   {token_path}")
        print()
        print("MCP client config: add to your MCP server entry's headers:")
        print(f'   Authorization: Bearer $(cat "{token_path}")')
        print()
        print("(Set PICASSO_PRINT_TOKEN=1 to print the token inline instead.)")
    print("=" * 64)
    print()


def main() -> int:
    missing = _check_deps()
    if missing:
        print("Picasso Studio needs a few Python packages first.")
        print("Run this, then try again:")
        print()
        print(f"   pip install {' '.join(missing)}")
        print()
        return 1

    from studio.config import get_mode
    from studio.runtime import get_bind
    bind = get_bind()
    host, port = bind.host, bind.port

    url = f"http://{host}:{port}/"

    env_override = os.environ.get("PICASSO_OPEN_BROWSER", "").lower()
    if env_override in ("1", "true", "yes"):
        should_open = True
    elif env_override in ("0", "false", "no"):
        should_open = False
    else:
        should_open = get_mode() == "gui"

    if _is_port_in_use(host, port):
        # Distinguish "another Picasso is already running" (idempotent
        # success) from "some unrelated service holds this port" (real
        # error the user has to resolve).
        if _is_picasso_on_port(host, port):
            print(f"Picasso Studio is already running at {url}")
            if should_open:
                webbrowser.open(url)
            return 0

        # Not Picasso. Find a free port and tell the user how to switch.
        suggested = _find_free_port(host, port + 1)
        print()
        print("=" * 64)
        print(f"⚠  Port {port} is in use by another process (not Picasso Studio).")
        print(f"   /health on http://{host}:{port}/ returned an unexpected response.")
        print()
        if suggested is not None:
            print(f"Next free port: {suggested}")
            print("To use it, set PICASSO_PORT and try again:")
            print()
            if os.name == "nt":
                print(f"   set PICASSO_PORT={suggested}")
                print(f"   python scripts\\start_studio.py")
            else:
                print(f"   PICASSO_PORT={suggested} ./start_studio.sh")
            print()
            print("Then update your MCP client config to point at the new port.")
        else:
            print(f"Couldn't find a free port near {port}. Either stop the conflicting")
            print(f"process or pick an explicit port:  PICASSO_PORT=<port>  and re-run.")
        print("=" * 64)
        return 2

    # Defer imports until after dep check + port check so missing-dep errors
    # are clean and we don't double-load the FastAPI app.
    from studio.app import TOKEN
    from studio.app import main as run_server
    from studio.auth import mint_launch_nonce

    _print_auth_banner(TOKEN, url)

    print(f"Starting Picasso Studio at {url}")
    print(f"   MCP endpoint: {url}mcp")
    print()

    if should_open:
        nonce = mint_launch_nonce()
        launch_url = f"{url}?launch={nonce}"

        def _open_when_ready() -> None:
            for _ in range(60):
                if _is_port_in_use(host, port):
                    webbrowser.open(launch_url)
                    return
                time.sleep(0.5)
        threading.Thread(target=_open_when_ready, daemon=True).start()

    run_server()
    return 0


if __name__ == "__main__":
    sys.exit(main())
