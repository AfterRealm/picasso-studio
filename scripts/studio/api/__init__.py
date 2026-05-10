"""HTTP API routers — split out of app.py so each surface area is its own
small module.

- `sessions` — session CRUD, undo/redo/clear/jump, SSE event stream.
- `files`    — authenticated session-file route + font enumeration.
- `meta`     — health probe + token handshake bootstrap.

The op-endpoint registration (`/api/ops/<name>`) lives in
`studio.transport` because it's tightly coupled to the OP_REGISTRY +
FastMCP wiring, not a fixed router.
"""
