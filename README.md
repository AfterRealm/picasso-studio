# Picasso Studio

A self-hosted local image editor that doubles as an MCP server. Drop an
image, watch Claude (Desktop or Code) edit it live in your browser.

- 🎨 **80 ops in 9 categories** — transform, color, filter, effect,
  compose, social presets, GIF, animations, utility (compress / convert /
  strip metadata / remove background / vectorize)
- 🔌 **MCP-first** — every op is callable by Claude as a tool, identical
  to clicking it in the canvas
- 👀 **Live web canvas** — drop image → click op → see the result. SSE
  filmstrip with click-to-revert history
- 🔒 **Local-only by default** — no telemetry, no cloud, no account.
  Bearer-token auth on every request, DNS-rebinding guard, decompression-
  bomb cap, workspace allowlist for agent-supplied paths
- ♿ **WCAG 2.2 Level AA** frontend — full keyboard parity, screen-reader
  labels, focus-trapped dialogs, keyboard alternatives to every drag

Cross-platform: Windows, macOS, Linux. Single Python process serving both
the FastAPI HTTP API and the FastMCP streamable-HTTP transport.

## Install

```bash
git clone https://github.com/<you>/picasso-studio
cd picasso-studio
pip install -r scripts/requirements.txt
```

Optional but recommended for the heavy ops: `pip install rembg vtracer
pngquant-cli numpy` (background removal, SVG vectorize, deep PNG
compression, vectorized animations). All gracefully fall back to "feature
unavailable" errors if missing.

## Run

```bash
# Windows:
start_studio.bat

# macOS / Linux:
./start_studio.sh

# or directly, anywhere:
python scripts/start_studio.py
```

First launch:

1. Opens your default browser to `http://127.0.0.1:8090/`
2. Generates a per-launch bearer token at `~/.picasso_studio/token`
3. Prints the token path (set `PICASSO_PRINT_TOKEN=1` to print the
   value inline — useful for one-off MCP client setup)

## Wire up Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "picasso-studio": {
      "command": "cmd",
      "args": [
        "/c", "npx", "-y", "mcp-remote",
        "http://127.0.0.1:8090/mcp",
        "--header", "Authorization:Bearer <YOUR-TOKEN-HERE>"
      ]
    }
  }
}
```

(macOS / Linux: drop `"command": "cmd", "args": ["/c", ...]` and use
`"command": "npx"` with the rest of the args directly.)

Restart Claude Desktop. Ask:

> *Create a Picasso session from `~/Desktop/sunset.jpg`, then apply
> sepia, then a soft drop shadow.*

Watch the browser — image loads, sepia applies, drop shadow applies. Each
step shows up in the right-hand filmstrip; click any to revert.

On first run Claude will ask whether you want **inline mode** (the
generated image returns directly in the chat as `ImageContent`) or **gui
mode** (the browser canvas is the source of truth, chat replies are
text-only). Pick whichever fits your workflow — switch any time with the
`setup_picasso` tool.

## Architecture

```
picasso-studio/
├── start_studio.bat            # Windows launcher
├── start_studio.sh             # macOS / Linux launcher
├── CHANGELOG.md
├── scripts/
│   ├── start_studio.py         # cross-platform entry point
│   ├── requirements.txt
│   └── studio/                 # the package
│       ├── app.py              # composition root (~135 lines)
│       ├── auth/               # token + nonce + pure-ASGI middleware
│       ├── api/                # FastAPI routers (sessions / files / meta)
│       ├── ops/                # the 80 ops, auto-discovered
│       │   └── _scaffold.py    # @image_op decorator (boilerplate-free ops)
│       ├── op_service.py       # apply_op() shared by MCP + HTTP
│       ├── transport.py        # registers ops against MCP + FastAPI
│       ├── mcp_tools.py        # hand-written setup tools
│       ├── sessions.py         # session lifecycle + on-disk persistence
│       ├── events.py           # SSE hub (per-session + global)
│       ├── paths.py            # workspace allowlist + image safety
│       ├── registry.py         # @register_op decorator
│       └── static/             # vanilla HTML+JS frontend
├── references/                 # op category docs (Claude reads on demand)
└── evals/
    └── evals.json              # eval prompts
```

**Add a new op:** drop a function in `scripts/studio/ops/<category>.py`
with the `@image_op` decorator. It appears as both an MCP tool and a UI
button automatically — no manual registration:

```python
from PIL import ImageOps
from ._scaffold import image_op

@image_op(category="filter", label="Mono", description="Black + white",
          params={})
def mono(img):
    return ImageOps.grayscale(img).convert("RGB"), "Mono"
```

For ops that don't fit the single-image PNG-out shape (multi-frame, SVG
output, subprocess pipelines), use `@register_op` directly — see
`ops/animate.py` and `ops/utility.py` for examples.

## Configuration

Environment variables (all optional):

- `PICASSO_HOST` — bind address (default `127.0.0.1`)
- `PICASSO_PORT` — bind port (default `8090`)
- `PICASSO_OPEN_BROWSER` — `1` / `0` to force browser auto-open
  (default: opens iff `mode == "gui"`)
- `PICASSO_PRINT_TOKEN` — `1` to inline-print the bearer token on launch
  (default: prints path only)
- `PICASSO_WORKSPACE` — `os.pathsep`-separated roots that
  agent-supplied paths must live inside (default: user's home)
- `PICASSO_DEBUG` — `1` to include full Python tracebacks in op error
  responses

## Security model

Picasso Studio binds to localhost by default, but localhost-only isn't a
fence — DNS rebinding lets a malicious page in a tab the user has open
hit `127.0.0.1` directly. We layer:

- **Bearer-token auth** on every authenticated request
  (`Authorization: Bearer …` for fetch, `X-Picasso-Token` for MCP, an
  HttpOnly SameSite=Strict cookie for EventSource and `<img src>`)
- **Pure-ASGI middleware** — does not buffer streaming responses (would
  silently break SSE + MCP streamable-HTTP)
- **Host header check** — exact match against the bound host:port plus
  loopback aliases. DNS-rebinding requests get 403
- **Origin / Referer same-origin** — cross-origin browser requests get
  403 even with a valid token
- **Single-use launch nonces** — the browser bootstrap goes through
  `/token-handshake?launch=<nonce>` so the token never travels in URLs
  outside this exchange. Nonces have a 5-minute TTL and are bounded
- **Path safety on agent-supplied inputs** — `safe_input_path()`
  resolves with symlinks, asserts inside the workspace allowlist,
  validates extension, runs `Pillow.verify()`, caps at 50 MB, caps total
  pixel count at the decompression-bomb threshold
- **Authenticated session-files route** — replaces the previous open
  `StaticFiles` mount; resolves under the session's directory only,
  uniform 404 for every failure mode (no timing oracle)

The token rotates every server launch. To use Picasso with `claude.ai`
(which requires a public HTTPS URL + OAuth), front it with Caddy / nginx
+ Let's Encrypt and add OAuth in front of `/mcp` per the Anthropic
connector spec — outside this repo's scope.

## Status

**v0.1.0** — first release. 80 ops shipping, MCP integration verified
end-to-end, full panel-roast (backend 9.7+/10) and Curb Cut (frontend
WCAG 2.2 AA Compliant) audit passes complete.

## License

MIT.
