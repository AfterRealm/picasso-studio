"""Hand-written MCP tools — setup, config, session lifecycle, browser launch.

These are NOT op tools (those are auto-registered against OP_REGISTRY by
`transport.register_all_ops`). They're the small set of tools Claude
needs for first-run setup and session management, plus the browser pop-
out that lets inline-mode users invoke the GUI on demand.

`register(mcp)` is called once during app construction; it binds every
tool here to the FastMCP instance.
"""
from __future__ import annotations

import logging
import webbrowser

from mcp.server.fastmcp import FastMCP

from .auth import mint_launch_nonce
from .config import load_config, set_mode
from .paths import UnsafePathError, safe_input_path
from .runtime import studio_url
from .sessions import create_session, list_sessions

log = logging.getLogger("picasso_studio.mcp_tools")


def register(mcp: FastMCP) -> None:
    """Bind the hand-written MCP tools to the given FastMCP instance."""

    @mcp.tool(
        name="setup_picasso",
        description=(
            "First-run setup. Persists the user's chosen mode for Picasso Studio. "
            "Call once after asking the user how they want to use it. "
            "mode='inline' returns generated images directly in chat (no browser). "
            "mode='gui' opens the visual editor in the browser when the server starts. "
            "mode=null leaves the choice unset (user wants to decide later) — first_run_complete is NOT flipped in that case."
        ),
    )
    def _setup_picasso(mode: str | None = None) -> dict:
        if mode not in ("inline", "gui", None):
            return {"error": f"invalid mode: {mode!r} (expected 'inline', 'gui', or null)"}
        config = set_mode(mode)
        return {
            "ok": True,
            "config": config,
            "note": (
                f"Mode set to {mode!r}. "
                + ("Image results will return inline in chat." if mode == "inline"
                   else "Browser editor will open when the server starts." if mode == "gui"
                   else "No mode set — Claude should ask again next time.")
            ),
        }

    @mcp.tool(
        name="get_picasso_config",
        description="Return the current Picasso Studio config (mode, first_run_complete).",
    )
    def _get_picasso_config() -> dict:
        return load_config()

    @mcp.tool(
        name="create_session",
        description=(
            "Create a fresh Picasso Studio session from a local image path. "
            "Returns the new session_id which is required by all op tools. "
            "Use this whenever starting a new image — DO NOT reuse an existing "
            "session_id, since sessions accumulate ops on top of each other and "
            "stale state will leak in. The path must point to an image inside the "
            "configured workspace (see PICASSO_WORKSPACE env var; defaults to "
            "the user's home directory)."
        ),
    )
    def _create_session_tool(image_path: str) -> dict:
        try:
            resolved = safe_input_path(image_path)
        except UnsafePathError as exc:
            return {"error": str(exc)}
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            return {"error": f"failed to read image: {exc}"}
        try:
            sess = create_session(data, ext=resolved.suffix.lstrip("."))
        except UnsafePathError as exc:
            return {"error": str(exc)}
        return {
            "session_id": sess.id,
            "original": str(sess.original),
            "note": f"new session {sess.id} from {resolved.name}",
        }

    @mcp.tool(
        name="list_sessions",
        description="List all currently-active Picasso Studio sessions with their ids and current op counts.",
    )
    def _list_sessions_tool() -> dict:
        sessions = list_sessions()
        return {
            "count": len(sessions),
            "sessions": [
                {
                    "id": s.id,
                    "ops_applied": len(s.history),
                    "cursor": s.cursor,
                    "original": str(s.original.name),
                }
                for s in sessions
            ],
        }

    @mcp.tool(
        name="open_studio",
        description=(
            "Open the Picasso Studio GUI in the user's default browser. Useful "
            "for inline-mode users who want to use the visual canvas (interactive "
            "crop, text placement, etc.) for a specific session without permanently "
            "switching modes. Optionally pass session_id to deep-link to that session."
        ),
    )
    def _open_studio(session_id: str | None = None) -> dict:
        nonce = mint_launch_nonce()
        url = studio_url(session_id=session_id, launch_nonce=nonce)
        opened = False
        try:
            opened = webbrowser.open(url)
        except (webbrowser.Error, OSError):
            opened = False
        return {
            "url": url,
            "opened": opened,
            "note": (
                f"Studio opened in browser at {url}." if opened
                else f"Couldn't auto-open. Visit {url} manually."
            ),
        }
