---
name: picasso-studio
description: Image editor sidecar — when the user wants to modify, transform, filter, animate, or compose images, this skill exposes a full image-manipulation toolkit Claude can call directly. Results render inline in the chat by default; an optional live web canvas is available for visual tasks like interactive crop or text placement. Use this whenever the user says "edit this image," "apply [a filter / sepia / a polaroid / a watermark / etc.]," "resize / crop / rotate," "make it look [vintage / cartoon / etc.]," "animate this," or shares an image and wants any kind of manipulation done. Also use it for image creation primitives (gradients, color palettes, QR codes) and image-to-audio sonification. Don't reach for this skill for image generation from prompts (that's a different model); reach for it whenever there's an existing image and the user wants something done TO it.
license: MIT
metadata:
  author: AfterRealm
  version: "0.1.0"
---

# Picasso Studio

An image editor that pairs Claude with a live web canvas. The user uploads or references an image, you (Claude) call image-manipulation tools, and a sidecar browser app shows the canonical image and a running edit-history sidebar. Same operations are exposed two ways from one Python process: as MCP tools you call directly, and as toolbar buttons the user can click.

## When to use this skill

Reach for Picasso Studio whenever the user has an image (attached, on disk, or generated earlier in conversation) and wants any kind of manipulation: resize, crop, rotate, color filters (sepia, grayscale, vintage), artistic styles (oil painting, pencil sketch, cartoon), composition tweaks (watermark, polaroid frame, QR code), animation (turn a still into a looping WebP), or sonification. Also reach for it when they want creation primitives like color gradients, harmony swatches, or solid-color cards.

Don't use this skill for generating new images from a text prompt — that needs an image generation model, not Picasso Studio.

## How to use this skill

### Step 0 — First-run mode setup (do this once per user)

Before doing anything else, call `get_picasso_config`. If `first_run_complete` is `false`, ask the user how they want to use Picasso Studio with `AskUserQuestion`:

- **Inline Mode** — Image results appear directly in chat. No browser. *Recommended for most users.*
- **GUI Mode** — A live web canvas opens in their browser when the server starts. Best for visual editing tasks (crop, place text, iteratively tweak).
- **One-Time Setup Only** — Just install dependencies and exit; user will pick a mode later.

Then call `setup_picasso(mode="inline")` or `setup_picasso(mode="gui")` to persist the choice. For "One-Time Setup Only", call `setup_picasso(mode=null)` and stop after dependency setup — they'll be re-asked next session.

The persisted mode controls two behaviors:
- **Inline mode** → MCP ops return generated images directly as inline `ImageContent` so they render in chat. The launcher does NOT open a browser.
- **GUI mode** → The launcher opens the browser when the server starts. Ops return paths; the live canvas is the visual surface.

If `first_run_complete` is already `true`, skip this step entirely.

### Step 1 — Start (or attach to) the studio server

The studio is a local Python process. If it's not running, start it. If it's already running (the user may have it open in another tab), reuse it.

```bash
python scripts/start_studio.py
```

This script:
1. Checks for required Python packages (FastAPI, uvicorn, mcp, Pillow). If any are missing, prints the `pip install` command and exits — the user will need to run that, then re-invoke.
2. If everything's installed, starts the server on `http://localhost:8090` (the default) and prints the URL.
3. The server is idempotent — if it's already running on the port, the script no-ops and just prints the URL.

Once it's up, **tell the user the URL** so they can open it in their browser to watch live edits. Always include the URL in your reply.

### Step 2 — Open or create a session

A session is one image being edited. Two flows:

**Flow A: User uploads via the web UI.** They drag an image onto the upload area, the server creates a session and returns its ID. They tell you the ID (or you can list sessions via the `list_sessions` tool to find theirs).

**Flow B: You create a session from a file path.** Use the `create_session` MCP tool with a path to an image on disk. The server returns the new session ID and starts tracking edits.

### Step 3 — Apply ops

Each operation is its own MCP tool. Every op takes a `session_id` argument. The server applies the op, records it in the session's history, and pushes a live update to any browser connected to that session — the user sees the canvas refresh in real time.

Ops are grouped into nine categories. **Don't load all of them up front** — read only the category file for what the user asked for:

| Category   | What's in it                                                                                  | Reference                          |
|------------|-----------------------------------------------------------------------------------------------|------------------------------------|
| transform  | Resize, crop, rotate, flip, mirror, upscale, thumbnail, fix orientation                       | `references/ops_transform.md`      |
| filter     | Sepia, grayscale, blur, sharpen, posterize, oil painting, vaporwave, glitch, etc.             | `references/ops_filter.md`         |
| color      | Brightness, contrast, saturation, auto-contrast, auto-level                                   | `references/ops_color.md`          |
| effect     | Drop shadow, round corners, watermark, border, glow, vectorize                                | `references/ops_effect.md`         |
| compose    | Meme, polaroid, caption, thought bubble, annotation                                           | `references/ops_compose.md`        |
| social     | Instagram square/portrait/story, Twitter header, YouTube thumbnail                            | `references/ops_social.md`         |
| gif        | Reverse, boomerang, speed, resize, filter, caption, optimize (animated GIFs)                  | `references/ops_gif.md`            |
| animate    | Turn a still into an animated WebP — rotate, pulse, shake, zoom, pan, shimmer, fog, etc.      | `references/ops_animate.md`        |
| utility    | Format convert, compress, strip metadata, remove background                                   | `references/ops_utility.md`        |

Read the relevant category file when the user's intent matches it. For fuzzy asks ("make it look like a magazine cover"), pull two or three categories and pick the right combo.

### Step 4 — Compose multi-step workflows

When the user asks for "make this vintage and add a polaroid frame," chain the right ops. Tell them what you're doing as you go ("applying sepia → adding polaroid frame"), so they can follow in the browser. If an op needs parameters you're not sure about, ask once and proceed — don't bombard them with three clarifying questions.

### Step 5 — Save / export

The user can right-click the canvas to save the current image, OR you can return the on-disk path of the latest version. The session directory holds every intermediate frame, so they can roll back via the UI.

## Tone

Picasso Studio is a tool, not a personality wrapper. You stay yourself — match the user's energy, be direct, explain what you're doing as you do it. When the user types "make it sepia," reply briefly ("On it — applying sepia, watch the canvas") and call the tool. When they ask "what would look good for a flyer?", give a real opinion based on what you can see in the image, then propose specific ops.

## Local-only by default

Picasso Studio runs on `localhost`. It does not phone home, transmit images, or require an account. Sessions live on the user's machine in `scripts/studio/sessions_data/`. For deploying to Claude.ai (which requires a public HTTPS URL with OAuth), the user needs to set up their own tunneling and auth — see the README for pointers, but the skill itself doesn't ship that.

## Adding new ops

Drop a new function into `scripts/studio/ops/` decorated with `@register_op(...)` and it appears as both an MCP tool AND a UI button on next server start. One source of truth, two surfaces. See existing ops in `scripts/studio/ops/transform.py` and `scripts/studio/ops/filter.py` for the pattern.
