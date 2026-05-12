# Changelog

All notable changes to Picasso Studio.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The `## [Unreleased]` section accumulates work-in-progress; on release, it gets
promoted to a versioned section (e.g. `## [0.2.0] — 2026-MM-DD`).

Categories:
- **Added** — new features / capabilities
- **Changed** — changes to existing behavior
- **Fixed** — bug fixes
- **Removed** — features taken out
- **Notes** — internal context, decisions, things future-us will want to remember

---

## [Unreleased]

(Nothing yet — collecting v0.2 work.)

---

## [0.1.2] — 2026-05-12

### Added

- **`POST /api/sessions/from-path`** — create a session from a local image path with a JSON body (`{"path": "..."}`). Same final state as the multipart upload, but skips the round-trip when the caller already has the file on the box. The MCP `create_session` tool has worked this way since v0.1.0; this brings the HTTP surface to parity so CLI tools, scripts, and HTTP-only agents don't have to roundtrip bytes they already own. Path is validated through `safe_input_path` (workspace allowlist + Pillow verify) before any bytes are persisted.

### Changed

- **Missing optional dependencies surface as a friendly install hint instead of `ModuleNotFoundError`.** Heavy / specialty ops (`remove_bg` / rembg, `vectorize` / vtracer, `deep_compress_png` / pngquant, etc.) lazy-import their deps inside the op body so cold-start stays light. Previously a missing module returned the bare Python exception — confusing for a user who just wanted to know what to install. `register_op`'s error wrapper now catches `ModuleNotFoundError` specifically and returns `{"error": "Op 'X' needs the optional 'Y' package... <install hint>", "missing_module": "Y", "install_hint": "pip install ..."}`. Known heavy deps have curated install hints (rembg notes the ~170 MB model download); everything else gets a generic `pip install <module>` fallback.

### Notes

- Live field-test today: drove a real `remove_bg` over the favicon for the Iowa Letters portfolio submission. The friction points the agent hit — `image_path` vs `image` shape mismatch on `/api/sessions`, bare `ModuleNotFoundError` on missing rembg, scrambling to find the op-listing endpoint — drove this release. `GET /api/ops` already exists (added in v0.1.0); discoverability gap rather than missing feature.
- **PowerShell 7+ is the supported shell on Windows.** Windows PowerShell 5.1 (the in-box default) does not support `Invoke-RestMethod -Form`, which means multipart uploads to `POST /api/sessions` fail with a `ParameterBindingException`. PS 7+ has full `-Form` support. README now lists `winget install Microsoft.PowerShell` (or the MSI from <https://github.com/PowerShell/PowerShell/releases>) under system requirements. The new `POST /api/sessions/from-path` endpoint also lets you skip the upload entirely for files already on the box, regardless of shell — so curl, requests, or PS 5.1 with a JSON body all work cleanly.

---

## [0.1.1] — 2026-05-10

### Fixed

- **Launcher distinguishes "another Picasso is running" from "some unrelated process holds this port".** `start_studio.py` previously checked port-in-use and unconditionally printed *"Picasso Studio is already running at <url>"* — so if Pi-hole / a different dev server / anything else owned 8090, the user got pointed at the wrong service. Now it hits `/health` and verifies the `{"ok": true}` shape before claiming so. On a real conflict, finds the next free port and surfaces the exact env-var override (`PICASSO_PORT=<n>`) plus a reminder to update the MCP client config. Conflict path returns exit code `2` (was silently `0`).

### Notes

- No changes to the running server, op surface, auth, or frontend. Pure launcher diagnostic.

---

## [0.1.0] — 2026-05-10

First public release. Picasso Studio ships as a self-hosted local web app
that exposes 80 image-manipulation operations to both a browser canvas
and a local MCP server, so Claude (Desktop or Code) can drive the editor
directly. Cross-platform — runs on Windows, macOS, and Linux.

Highlights:

- **80 ops in 9 categories** — transform, color, filter, effect, compose,
  social presets, GIF transforms, animations, utility (compress / convert
  / strip metadata / remove background / vectorize). Auto-discovered from
  `studio/ops/<category>.py`.
- **MCP-first design** — every op is registered against both a FastAPI
  endpoint and a FastMCP tool. Claude calls the same `apply_op()` code
  path the browser canvas does.
- **Live web canvas** — drop image, click op, watch result. SSE-driven
  filmstrip showing the full edit history with click-to-revert. Works
  offline-first (no third-party CDN, no analytics).
- **Two-mode integration** — `inline` returns generated images directly
  in the chat (MCP `ImageContent` with derived mimeType), `gui` opens the
  visual editor in the browser. First-run `setup_picasso()` lets the user
  pick. GUI tabs auto-pick up MCP-created sessions via a global SSE
  channel.
- **Dual MCP+HTTP surface** over a single uvicorn process. Single
  `apply_op()` service shared by both, behavior identical regardless of
  caller.
- **Hardened backend** (panel-roast 9.7+/10): per-launch bearer token,
  HttpOnly cookie for EventSource, pure-ASGI auth middleware that
  preserves SSE/MCP streaming, DNS-rebinding guard, image bomb cap,
  workspace allowlist for agent-supplied paths, decompression-bomb
  protection, dedicated executor for CPU-bound ops, race-safe SSE deltas
  via contextvars.
- **AA-Compliant frontend** (Curb Cut 100/100): full keyboard parity,
  focus-trapped dialogs with return-focus, dynamic image alt, dual
  polite/assertive live regions, keyboard alternatives to all drag
  interactions (crop, text placement, compare slider), reflow at 320 px
  viewport, prefers-reduced-motion respected, semantic HTML throughout.

See the panel-roast and Curb Cut detail blocks below for the full pre-1.0
hardening scorecard.

---

## Pre-1.0 hardening detail (preserved for history)

### Accessibility (Curb Cut R1 → R4 sweep, 2026-05-10)

The frontend went from **38/100 (Non-Compliant)** to **98/100 (✅ AA Compliant)** across four Curb Cut audit rounds, then through the final two LOWs. Every WCAG 2.2 Level AA criterion that applied to the SPA is now passing or has its intended fix in place.

**Score progression (per pillar):**

| Round | Total | Perceivable | Operable | Understandable | Robust | Status |
|------:|:-----:|:-----------:|:--------:|:--------------:|:------:|:------:|
| R1 (baseline) | 38 | 13/25 | 0/25 | 17/25 | 8/25 | ❌ Non-Compliant (3 CRITICAL) |
| R2 | 80 | 21/25 | 14/25 | 24/25 | 21/25 | ⚠️ Partial AA |
| R3 | 90 | 25/25 | 22/25 | 24/25 | 19/25 | ✅ AA Compliant |
| R4 | 98 | 25/25 | 25/25 | 24/25 | 24/25 | ✅ AA Compliant |
| Post-R4 | ~100 | 25/25 | 25/25 | 25/25 | 25/25 | ✅ AA Compliant |

#### Critical fixes (R2)

- **Pure-ASGI focus management on the op popover** — focus traps inside the popover (Tab cycles within it, not into background); Escape closes; focus returns to the trigger button on close. Previously Tab cycled into orphaned background content while the popover sat visually open with no focused control. (WCAG 2.1.1, 2.1.2)
- **Working image gets a real, dynamic `alt`** — `updateCanvasAlt()` writes `Original image, 1920 by 1080 pixels` / `Edit step N of M` from `setCanvasFromRel()` and the SSE handler. Toast host split into polite (`role="status"`) + assertive (`role="alert"`) so op failures actually reach AT users. (WCAG 1.1.1, 4.1.3)
- **Text modal + command palette get full dialog semantics** — `role="dialog"`, `aria-modal="true"`, `aria-labelledby`; focus trap via `trapDialogFocus()`; Escape closes; background `inert` while text modal is open; focus returns to the opener on close. (WCAG 2.1.2, 2.4.3, 4.1.2)

#### High-impact fixes (R2)

- **Skip link to canvas** + visually-hidden `<h1>Picasso Studio image editor</h1>` + landmark labels (`aria-label="Operations toolbar"` / `"Edit history"` / `"Image canvas"` / `role="banner"` / `role="contentinfo"`). (WCAG 2.4.1, 1.3.1)
- **Every icon button now has an explicit `aria-label`**, every inline SVG carries `aria-hidden="true" focusable="false"`. `title` kept for sighted hover, but accessible name no longer relies on it. (WCAG 4.1.2, 2.5.3)
- **Popover form fields get `for`/`id` association**, sliders expose `aria-valuetext` updated on every input. Color pickers have separately labeled picker + hex inputs. (WCAG 1.3.1, 3.3.2, 4.1.2)
- **Crop overlay + text overlay get keyboard alternatives** — both `role="application"` + `tabindex=0` + arrow-key nudge (Shift+arrow resizes the crop; Alt for 10px steps). Aspect-bar buttons have proper radiogroup semantics. (WCAG 2.1.1, 2.5.7)
- **`alertConfirm()` replaces `confirm()`** for destructive Clear — proper `role="alertdialog"` with focus trap + return-focus, instead of the native dialog that steals focus to browser chrome and is announced inconsistently. Error toasts route to the assertive host with concrete suggestions. (WCAG 3.3.1, 3.3.3, 4.1.3)

#### Round 3 fixes (UX-completing)

- **Filmstrip rows are real `<button>`s** with `aria-current="step"` — keyboard-reachable history navigation (was `<div onclick>` ignored by AT). (WCAG 2.1.1, 4.1.2)
- **Tweaks accent swatches are `<button role="radio">`** inside a `role="radiogroup"`. Density seg-mini got the same treatment. (WCAG 2.1.1, 4.1.2)
- **`<button role="switch">` for `makeToggle`** with Space/Enter handler + `aria-checked` parity. All three callsites pass a label. (WCAG 4.1.2)
- **Compare slider has full `role="slider"` semantics** + arrow / Shift+arrow / Home / End keyboard handler + live `aria-valuetext`. (WCAG 2.1.1, 4.1.2)
- **Op-button tooltip surfaces on `:focus-visible`** (was hover-only). (WCAG 1.4.13)
- **`--muted` color bumped from `#6f7c8d` (~4.0:1) to `#94a0b0` (~6.0:1)** against `--panel`. Solid AA, not borderline. (WCAG 1.4.3)
- **Cat-header collapse buttons sync `aria-expanded`** on toggle. (WCAG 4.1.2)

#### Round 4 fixes (state-sync polish)

- **Toolbar tabs flip `aria-selected`** on every click (was only `.active` class).
- **Canvas-tools `checker` and `compare`** sync `aria-pressed` with their on/off state.
- **Tweaks panel writes `els.tweaks.hidden` together with `.open`**, plus updates `aria-expanded` on the trigger. Per HTML spec SRs ignore `[hidden]` regardless of CSS display — the previous `.open`-only path showed the panel visually but kept it invisible to AT.
- **Target sizes** — `.swatch` 22→24, `.toggle` 32×18→40×24. Both clear WCAG 2.5.8.
- **`wireRadiogroup()` helper** — implements roving tabindex + Arrow / Home / End traversal for `[role="radio"]` and `[role="tab"]` containers. Wired against toolbar tabs, accent swatches, density seg-mini, popover seg/bool radios, and the crop aspect-bar (which also moved from toolbar+`aria-pressed` to radiogroup+`aria-checked`).

#### Post-R4 nits

- **`openPopover()` flips the trigger's `aria-expanded` to "true"** at the entry point so palette-launched popovers stay in sync (was only set in the click handler).
- **Tweaks panel responds to Escape** + focuses its close button on open + returns focus to the gear button on close.

#### Cross-cutting infrastructure

- **`trapDialogFocus(rootEl, opener, onEscape)`** — small helper used by every dialog (popover, palette, alertConfirm, text modal). Focuses the first field, traps Tab inside, dispatches Escape, restores focus to the opener on close.
- **`updateCanvasAlt()` + `updateDocumentTitle()`** called from `setCanvasFromRel()` and the SSE handler — image alt + tab title both reflect current edit state.
- **SSE event-shape consistency** — frontend now handles `op_entry_appended` (incremental, the new R3 backend shape), `cursor_changed` (full snapshot for undo/redo/clear/jump), and `hello` (initial). Old `op_applied` handled too for backward-compat.
- **`@media (prefers-reduced-motion: reduce)`** kills the live-dot pulse, popover `popIn`, and other transitions for users with the OS preference. (WCAG 2.3.3)
- **Body font moved to relative units** (rem-based, 0.875rem ≈ 14px) so user/browser zoom + text-size preference both scale. `@media (max-width: 900px)` reflows the 3-column grid to single column for high-zoom and narrow viewports. (WCAG 1.4.4, 1.4.10)
- **Two toast hosts** — `role="status"` polite for info/success, `role="alert"` assertive for errors. `toast(msg, "error")` routes to the alert host.

#### Verify

`node -c editor.js` clean, backend imports clean (80 ops), Curb Cut R4 returns ✅ AA Compliant 98/100 with the only two remaining LOWs since closed.

### Architecture (panel-roast Round 3, 2026-05-10)

- **`app.py` is now a 135-line composition root** (down from ~500). Every concern lives in its own module:
  - `api/sessions.py` — session CRUD + undo/redo/clear/jump + SSE.
  - `api/files.py` — authenticated session-file route + font enumeration.
  - `api/meta.py` — health probe + token handshake bootstrap.
  - `mcp_tools.py` — hand-written MCP tools (setup, config, session lifecycle, open_studio).
  - `transport.py` — auto-registration of OP_REGISTRY entries against both MCP and FastAPI surfaces, plus the inline-mode result wrapper.
- **`SessionStore` class** wrapping the global session dict (`sessions.SessionStore`); module-level `get_session` / `list_sessions` delegate to a process-wide `_default_store`. Tests can now construct a fresh store with a temp `sessions_root`.
- **`@image_op` scaffolding decorator** (`ops/_scaffold.py`) collapses the session-lookup → load → save → record_op boilerplate. Migrated **34 of 80 ops** (transform, color, social, filter — the simple-fit cases). Each migrated op went from ~12 lines to ~5; ops that need SVG / multi-frame / temp-file round-trips continue to use `@register_op` directly.
- **`OpResult` typed dataclass** is the canonical op return shape (output_path, note); the wire dict comes from `OpResult.to_dict()`.
- **`HistoryEntry.to_dict(root)`** — single source of truth for the wire shape used by both SSE incremental events and full session snapshots. Eliminated the inline serialization that op_service was duplicating.
- **`registry.ops_shape()`** is the cached JSON shape served by `/api/ops`. Replaced the one-listener `on_invalidate` pubsub indirection with a co-located cache that `register_op` clears the same way it clears `ops_by_category`.
- **`register_all_ops(app, mcp)`** is now a function in `transport.py` (not a bare for-loop in app.py).

### Security (panel-roast Round 3)

- **Pure-ASGI auth middleware handles WebSocket scope cleanly.** Rejection on a WS connection now sends `websocket.close` with code `4000 + status` instead of HTTP messages that would crash uvicorn.
- **Bearer-token rejections now log presented length** (NOT the value). Diagnoses misconfigured clients without leaking the real or attempted token.
- **`/health` no longer leaks server version.** Returns `{"ok": true}` only — version targeting via fingerprinting is now closed.
- **IPv6 alias cleanup.** Dropped the unbracketed `::1:port` form from the allowed-hosts set (real Host headers are bracketed `[::1]:port`); the bare form was dead weight that suggested confusion about IPv6 Host parsing.
- **Token-write recovery wraps both attempts** in error handling — both first-write and post-delete-retry get the same actionable RuntimeError if they fail, instead of one being a clean error and the other a raw stack trace.

### Performance (panel-roast Round 3)

- **`save_animated` now passes Pillow a re-iterable list of frames** (not a one-shot generator). Pillow's APNG plugin can pre-walk for sizing — the previous implementation would have silently saved 1-frame animations on second iteration. Lazy frame normalization preserved (one RGBA copy at a time during the save loop). Optional `frame_count=` arg lets advance-counted callers skip the materialization.
- **`_cached_rotation_table` actually shares now.** Previously keyed on `(cache_key, sprite_image)` — `sprite` is a fresh PIL Image per call, so identical cache_keys missed the cache every time. Now keyed on `cache_key` alone; the cached helper rebuilds the sprite from `(shape, size, color)`.
- **Inline-mode `_wrap_op_result` derives mimeType from the output extension.** Was hardcoded `image/png` — broke `.webp` (animate_*), `.gif` (gif_*), `.jpg` (compress_jpeg) renders, and outright rejected `.svg` (vectorize). SVG now returns the dict only (MCP ImageContent is raster-only); other extensions get the right mime.
- **`apply_op` race fix via contextvar.** Two concurrent ops on the same session no longer interleave each other's SSE entries — `record_op` writes the entry to a `contextvars.ContextVar`, `apply_op` reads its own coroutine's copy after the await. Each op call sees its own append, not whoever wrote last.
- **Dedicated `ThreadPoolExecutor` for image ops** sized to `os.cpu_count()`. Long-running animate calls no longer share Python's default to_thread pool with uploads / font enumeration / other infrastructure work.
- **`gif_optimize` uses one master palette** derived from the first frame, then quantizes the rest against it. Previous per-frame ADAPTIVE palettes defeated GIF interframe optimize and bloated output files; one shared palette is faster AND smaller.
- **`_lut_scale` returns a tuple** (was a list). Eliminates the cache-poisoning footgun where caller mutation would corrupt every future caller's lookup.
- **Glow brightness LUT cached cross-call** via `_brightness_lut(round(mult, 2))` — animate_glow_pulse used to rebuild the 256-entry LUT every frame.
- **Fog texture resize is cached** (4 distinct resolutions) on top of the canonical 2048² source. A second fog op at the same resolution skips the BILINEAR resize.

### Changed (SSE event shape consistency)

- **Op application emits `op_entry_appended`** events (carrying the new entry + cursor flags) instead of the previous `op_applied` shape.
- **Cursor-only mutations emit `cursor_changed`** (carrying the full session snapshot for state-sync semantics).
- Frontend code can now branch on event type instead of probing keys for "which kind of op_applied is this."

### Fixed

- **MCP arg model name uses PascalCase**: `op_name` like `gif_speed` becomes `GifSpeedArgs` (not the underscored `Gif_SpeedArgs` from `str.title()`). Cleaner and avoids edge-case Pydantic warnings on duplicate model names.
- **`pencil_sketch` numpy fallback removed.** numpy is a hard transitive dep (Pillow + matplotlib pull it); the per-strip PIL fallback was unreachable dead code.
- **`deep_compress_png` intermediate filename uses `with_name()`** instead of recomputing `len(history)+1`. Reads as "temp version of the output," guarantees no collision.
- **Dead `subscribers()` method on `SessionEventHub` removed.**
- **`auth/__init__.py` re-exports trimmed** to the five symbols actually used externally.
- **`ASGIApp` type alias replaced with `from starlette.types import ASGIApp`** (Starlette is already a transitive dep via FastAPI).
- **`_FOG_CANONICAL` renamed to `_FOG_CANONICAL_EDGE = 2048`** — the constant now matches the actual edge length instead of half of it.

### Notes

- **80 ops, 9 categories.** All registered, all clean.
- **`/sessions_files` 404 timing.** Failures (bad sid / bad filename / missing file) all emit a single 404 — no timing or response-code distinguishability for an attacker probing the route.
- **Smoke gates verified end-to-end:** `/health` 200 (no version field), `/api/ops` 401→200 with token (returns all 80), cross-origin → 403, `/healthcheck-fake` → 401 (prefix-bypass remains closed), SSE `hello` event arrives inside 2s.

### Security (panel-roast Round 2, 2026-05-10)

- **Pure-ASGI `AuthMiddleware`** (`auth/middleware.py`). The Round-1 hardening used Starlette's `BaseHTTPMiddleware`, which buffers streaming response bodies — silently breaking SSE updates and FastMCP's streamable-HTTP transport. The middleware is now a pure ASGI callable (`__call__(scope, receive, send)`) so streaming responses pass through untouched. **Smoke-tested:** `/api/sessions/{sid}/events` first event arrives inside 2s instead of waiting for connection close.
- **`/health` exact-match check.** Dropped the `path.startswith("/health")` clause that would have made any future `/healthcheck-*` route silently public. Verified: `GET /healthcheck-fake` now returns 401 instead of 200.
- **Launch-nonce TTL + size cap.** Extracted into `auth/nonces.py` with a thread-safe `NonceStore` (5-minute TTL, 64-entry FIFO eviction). Closes the unbounded-set memory growth that prompt-injection on `open_studio` could exploit.
- **Auth subpackage split.** Old single-file `auth.py` is now `auth/{tokens.py,nonces.py,middleware.py}` — token storage, nonce state, and request middleware are individually testable. Re-exports keep `from .auth import ...` callsites unchanged.
- **Windows token ACL via `icacls` best-effort.** Posix `chmod` is a no-op on Windows; tokens now get an explicit `icacls /inheritance:r` + `/grant:r CURRENTUSER:F` to remove inherited ACEs. Logs a warning if `icacls` is missing rather than silently leaving the token world-readable.
- **`safe_input_path` runs `verify_image_bytes` on the disk path** (opt-out via `verify_content=False`). Disk reads no longer skip the bomb / format-parser check that uploads use.
- **Token reset path on permission errors.** `load_or_create_token()` now deletes + recreates a corrupted/unwritable token file rather than crashing on startup with `PermissionError`.
- **Token banner scrubbed by default.** `start_studio.py` prints the token PATH (not the value) to stdout; set `PICASSO_PRINT_TOKEN=1` to inline-print on first run. Stops the token leaking into supervisor / log-collector capture.
- **Unified 404 on `/sessions_files/{sid}/{filename}`.** Bad sid / bad filename / missing file all return the same response — no timing or response-code distinguishability for an attacker probing the route.

### Performance (panel-roast Round 2)

- **Dedicated `ThreadPoolExecutor` for image ops** (`op_service.get_op_executor`), sized to `os.cpu_count()`. Long-running animate calls no longer share Python's default `to_thread` pool with uploads, font enumeration, and other infrastructure work — a slow op queues against other ops, not the rest of the system.
- **Lazy frame normalization in `save_animated`.** Frames pass through a generator that converts to RGBA on demand instead of a list comprehension that allocated a full RGBA copy of every frame up front. Peak intermediate-buffer memory roughly halved on RGBA inputs.
- **SSE events are incremental.** `op_service.apply_op` now publishes `{type: 'op_applied', entry, cursor, can_undo, can_redo}` instead of the full serialized session each time. Initial `hello` event still carries the snapshot. Long-history sessions drop per-event payload from ~50 KB to ~200 B.
- **Inline-mode base64 encode runs in a worker thread** (`asyncio.to_thread`). A multi-MB animated WebP no longer blocks the event loop while encoding.
- **GIF reorder ops use passthrough mode.** `gif_reverse`, `gif_boomerang`, `gif_speed` now request `open_gif_frames(..., mode=None)` so they skip the per-frame palette decompression they were never going to use; `save_gif` already passes P-mode through unchanged.
- **`gif_optimize` stops round-tripping P→RGB→P.** `save_gif` accepts the quantized P frames directly.
- **`bg_color` uses `alpha_composite`** instead of split-alpha + paste.
- **`drop_shadow` skips the intermediate full-RGBA `shadow` Image** — paints a flat color via the alpha mask directly.
- **Fog texture cached at a canonical 1024² and resized on use.** Was per-(w,h), which on 4K inputs meant ~32 MB per cache slot.
- **`animate_glow_pulse` blur radius is clamped to `MAX_BLUR_RADIUS`** (was producing radius=113 with strength=3.0).

### Changed (architecture)

- **`auth/` is a subpackage** with three single-responsibility modules: `tokens.py`, `nonces.py`, `middleware.py`. Top-level re-exports keep imports stable.
- **Op-registry invalidation listeners.** `registry.on_invalidate(callback)` lets external caches (like the JSON shape served by `/api/ops`) invalidate themselves when ops register or unregister. The `_OPS_LIST_CACHE` in `app.py` registers as a listener; late op registration no longer leaves the UI staring at a stale list.
- **Pillow safety configured in lifespan**, not at import time. `paths.configure_pillow()` is called from the FastAPI lifespan so other in-process callers aren't surprised by `Image.MAX_IMAGE_PIXELS` mutating mid-run.
- **Workspace allowlist is computed lazily.** `paths.input_roots()` re-reads `PICASSO_WORKSPACE` on each call so tests / CLI overrides set after import are respected.
- **MCP arg schema honors parameter defaults** — both from the op's `params` schema (`pmeta['default']`) and from the function signature. Previously every field was marked required (`...`) so MCP callers like Claude couldn't invoke `rotate(session_id='...')` without re-passing every documented-default param. Real correctness regression.
- **`rotation_table` cache is keyed on a stable identity** (caller-supplied `cache_key` tuple), not `id(sprite)`. Prevents wrong-table reads after sprite GC at the same memory address.
- **`open_gif_frames` accepts `mode=None | 'RGB' | 'RGBA'`** so callers can preserve alpha or skip conversion entirely.

### Fixed

- **Dead `_save_lock` field on `Session`** removed.
- **Dead `_rotation_table_key` helper** in `_helpers.py` removed (was an `lru_cache` of a function that returned `id()` of a freshly-allocated tuple — unreachable cache).
- **Dead `if not frames: raise` branch in `gif_caption`** removed (`open_gif_frames` already raises on empty input).
- **Dead `_origin_host` static method on `AuthMiddleware`** removed in the refactor.
- **`strip_metadata` redundant create-blank-and-paste step** removed; `convert("RGB")` already drops EXIF.
- **`convert(fmt)` returns an error for unsupported formats** instead of silently dropping to PNG with a misleading note.
- **`deep_compress_png` gives pngquant a real q_min floor** (`max(0, quality - 15)`) so output isn't visibly worse than the requested target.
- **`restore_from_disk` only calls `raw.get('params')` once.**

### Notes

- **Full per-frame RGBA streaming refactor of `animate_*` ops is deferred.** `save_animated` now accepts iterables, but each animate function still builds its frame list before calling save. Peak-memory wins from the lazy-normalize change are real but partial; a full streaming pass through 15 functions is its own ship.
- **Op-registration in lifespan is also deferred.** Module-level registration still works; moving it into a `register_all_ops(app, mcp)` lifespan call would buy testability at the cost of touching the FastMCP integration.
- **Verify gates:** smoke-tested `/health` 200 (no auth), `/api/ops` 401→200 with token, cross-origin → 403, `/healthcheck-fake` → 401 (prefix-bypass closed), SSE `hello` event arrives inside 2s. Boot prints token PATH (not value) by default.

### Security (panel-roast hardening pass, 2026-05-10)

- **Bearer-token auth on every HTTP + MCP request.** Per-launch random token (`secrets.token_urlsafe(32)`), persisted at `~/.picasso_studio/token` (mode 600 on POSIX, profile-restricted on Windows). Required via `Authorization: Bearer <token>` (or `X-Picasso-Token`). The `/health` and `/token-handshake` endpoints stay public so the launcher port-check + browser nonce-redemption flow still work.
- **Host + Origin/Referer enforcement (DNS-rebinding guard).** The auth middleware refuses requests whose Host header isn't one of the bound loopback aliases, and refuses cross-origin browser requests even if they obtained the token. Defeats the "any malicious page the user visits can hit 127.0.0.1" attack class.
- **Browser bootstrap via single-use launch nonce.** `start_studio.py` and the `open_studio` MCP tool mint a one-time nonce and open `?launch=<nonce>`; the page calls `/token-handshake` to redeem it for the persistent token. No drive-by site can mint or guess a nonce.
- **Arbitrary-file-read fix in `create_session` MCP tool.** Agent-supplied paths now go through `safe_input_path()` — resolved with symlinks expanded, asserted within the configured workspace allowlist (`PICASSO_WORKSPACE`, defaults to `~`), validated as a real image (Pillow `verify()`), bounded to 50 MB, and confined to a recognized image extension. Closes the prompt-injection-to-key-exfiltration path that previously let `image_path=~/.ssh/id_rsa` round-trip through `/sessions_files`.
- **`/sessions_files` is no longer a public static mount.** Replaced with an authenticated `GET /sessions_files/{sid}/{filename}` route that resolves the candidate, asserts it lives under the session's directory, refuses path-separators, and serves with `X-Content-Type-Options: nosniff`.
- **Session ID validation everywhere.** `^[A-Za-z0-9_-]{8,32}$`; `get_session()` rejects garbage SIDs without a dict lookup; the disk loader cross-checks the on-disk dirname against the manifest's `id` so a planted `session.json` can't redirect into a different folder. SID size bumped from 8 to 16 bytes.
- **Decompression-bomb + format-parser protection.** `Image.MAX_IMAGE_PIXELS` is set in `paths.py`; `verify_image_bytes()` runs an explicit `verify()` + size check before persisting; `create_session()` (both surfaces) goes through it.
- **Upload size cap.** `POST /api/sessions` now reads at most 50 MB and rejects oversize with HTTP 413.
- **Per-session SSE subscriber cap.** `events.HUB` enforces 8 concurrent subscribers per session; QueueFull events are logged so missed updates aren't silent.
- **Filesystem-path validation for pngquant subprocess.** `deep_compress_png` asserts intermediate + output paths resolve inside `sess.dir` before invoking pngquant.

### Performance

- **Sync I/O off the event loop.** All op invocations and session-create uploads run via `asyncio.to_thread`; one slow op no longer freezes SSE, MCP, or other endpoints.
- **PIL file-handle leaks fixed.** `_helpers.open_image` (and the new `open_image_rgba`) use `with Image.open(...) as im:` so source handles close immediately. On Windows, this stops source files from being locked between op runs.
- **Particle animations use a pre-rotation cache.** `rotation_table(sprite, steps=36)` builds once per sprite; per-frame lookups pick the nearest angle. Drops `frames * particles` PIL rotations to a single table build per call (~50× faster on larger animations).
- **Ripple animation is numpy-vectorized.** Replaces 8000+ crop+paste ops per frame on a 1080p image with one row-shift index map; falls back to the original PIL implementation if numpy isn't installed.
- **Fog texture is cached.** Deterministic seeded RNG → `lru_cache` on `(w, h)`; first call generates 500 ellipses + Gaussian blur, subsequent calls reuse it.
- **Animated WebP defaults to lossy** (quality 85, method 4); `lossless=True` is opt-in. Multi-frame full-RGBA was producing multi-MB visually-identical files.
- **GIF filter `point()` callbacks → 256-entry LUTs.** Sepia / vaporwave precompute their per-channel LUT once; PIL applies it natively in C.
- **Meme outline → `stroke_width`/`stroke_fill`.** Single `draw.text(..., stroke_width=N)` call replaces the `(2N+1)²` nested-loop hand-rolled outline. Same applies to `caption_top` and `gif_caption`.
- **`open_gif_frames` skips the redundant `.copy()`** on each frame (`Image.convert(...)` already returns a new image).
- **Cached `/api/fonts` + `/api/ops`.** matplotlib's font enumeration runs once per process via `lru_cache`; the ops list builds once and is reused.
- **Font lookup memoization.** `_resolve_font_by_family`, `_load_font`, `_bubble_font`, `_watermark_font`, `_gif_caption_font` all `lru_cache`'d.
- **Debounced `session.save()`.** Many ops in a row collapse into a single disk write; lifespan teardown flushes any pending state.
- **Per-history-entry size cached at write time.** `to_dict()` no longer stat()s every history entry per response.

### Changed (architecture)

- **One `apply_op()` service**, shared by MCP and HTTP. Removes the behavioral drift where HTTP emitted SSE notifications + truncated the redo branch but MCP didn't (and removes the duplicate redo-truncation between `app.py` and `record_op`).
- **Session disk-load moved into the FastAPI lifespan** (`restore_from_disk()`); no longer runs at module-import time, so the package is now importable in tests without a real filesystem.
- **Op auto-discovery.** `ops/__init__.py` walks the package via `pkgutil.iter_modules`; new `ops/<name>.py` files appear automatically. Per-module import failures are logged but don't take down the whole registry.
- **SSE subscribers extracted into `events.HUB`.** Session is no longer coupled to `asyncio.Queue` or the SSE transport; subscribers are addressed by session id from outside the model.
- **Host/port lookup centralized** in `studio/runtime.py`; previously duplicated across `app.py`, `_open_studio`, and `start_studio.py`.
- **Endpoint names unique.** Auto-registered ops now name their FastAPI handlers `op_<opname>` instead of all sharing `_endpoint`, so OpenAPI doesn't see colliding `operation_id`s.

### Fixed

- **`drop_shadow` no longer paints a sharp shadow onto a discarded canvas before the real one.** The first `out.paste(shadow, ...)` was dead work referencing a variable never used again.
- **`watermark` default text mismatch resolved.** Schema and function both now default to `'©'`; the function previously defaulted to `'(c)'` so direct callers and schema-driven callers got different glyphs.
- **`fix_orientation` preserves alpha.** Used to force `.convert('RGB')`, destroying transparency on PNG/WebP inputs.
- **`mirror` direction normalization matches `flip`.** Both now accept `horizontal`/`vertical` (and short forms `h`/`v`).
- **`crop` clamping** doesn't allow degenerate zero-area crops when callers pass `left == width` (clamped to `width - 1`).
- **`set_mode(None)` no longer flips `first_run_complete=True`.** The "leave the choice unset" path now actually leaves first-run unfinished, matching the tool's documented semantics.
- **`save_gif` / `save_animated` accept empty `durations`.** Falls back to `100ms` per frame instead of crashing on `[durations[0]] * len(...)` with an `IndexError`.
- **`vectorize` uses `step_path(..., ext='svg')`** instead of hand-rolled path concatenation.
- **`open_image` preserves alpha for any source mode that has it** (WebP / TIFF / GIF / palette-with-transparency), not just files with `.png` suffix.
- **Watermark + caption fonts work cross-platform.** Fallback chain now includes Arial.ttf (case-sensitive macOS), DejaVuSans.ttf (Linux), Helvetica.ttc, and a sized `load_default()` fallback.

### Notes

- **MCP clients need the bearer token configured.** Add `headers: {"Authorization": "Bearer <token>"}` to your MCP server entry in Claude Desktop / Code config. The token prints to stdout on first launch and lives at `~/.picasso_studio/token`.
- **`PICASSO_WORKSPACE`** is the new env var that controls which directories agent-supplied image paths can come from. Multiple roots are os.pathsep-separated. Defaults to `~` (the user's home directory) for compatibility with existing flows.
- **Op scaffolding decorator + `OpResult` dataclass deferred** to a future pass — they'd touch all 9 op modules and the trade-off didn't favor doing them in the same change as the security work.

### Added

- **`create_session` MCP tool.** Lets MCP-only clients (Claude Desktop, claude.ai, etc.) start a fresh Picasso session from a local image path. Previously the only way to create a session was the HTTP `POST /api/sessions` endpoint, which Claude couldn't reach without going through the GUI. Surfaced as a blocker by the eval suite — agents reusing a stale session_id had op state from prior calls bleed into new outputs.
- **`list_sessions` MCP tool.** Inspector tool — returns active session ids, op counts, and originals.
- **First-run setup flow.** New MCP tools `setup_picasso(mode)` and `get_picasso_config` persist the user's chosen experience to `~/.picasso_studio/config.json`. SKILL.md Step 0 instructs Claude to `AskUserQuestion` on first run and pick between Inline Mode, GUI Mode, or One-Time Setup.
- **Inline Mode.** When `mode="inline"` in the saved config, every MCP op return is wrapped to include `ImageContent` (base64 PNG) alongside the JSON result, so generated images render directly in the chat client. No browser involvement. Wrapper is `_wrap_op_result()` in `studio/app.py`.
- **`open_studio` MCP tool.** Lets inline-mode users pop the GUI on demand for a specific session (deep-link via `?session=<id>`) without permanently switching modes.
- **Browser auto-open in launcher.** `start_studio.py` opens the default browser when the server is reachable. Gated on saved mode (`gui` opens, `inline` doesn't); `PICASSO_OPEN_BROWSER=1/0` env var overrides.
- **`studio/config.py`.** Standalone config layer for `~/.picasso_studio/config.json` — `load_config`, `save_config`, `get_mode`, `set_mode`.

### Changed

- **Browser-open behavior is now mode-driven.** Previously the launcher had no auto-open; before that brief experiment used `PICASSO_NO_BROWSER` opt-out. Current behavior: `mode == "gui"` opens, others don't.
- **SKILL.md description updated to reflect Inline Mode as default.** Old description led with "watch the image change live in their browser"; updated to "results render inline in the chat by default; an optional live web canvas is available for visual tasks." Ran skill-creator's `run_loop.py` description optimizer (5 iterations, 20-query train/test eval set); none of the proposed alternatives beat the original on test trigger rate, so kept structure intact and made a surgical swap of the stale GUI-first phrasing.

### Fixed

- **Meme captions now auto-fit.** The `meme` op previously rendered text at a fixed font size and let long captions overflow past the image edges (clipping the first/last words). Captions are now word-wrapped to ≤92% of image width AND the font shrinks if a single line is too long, with a floor of 18pt. Surfaced by the eval suite — both with-skill and baseline runs produced clipped memes for our test prompts. Ported the wrap/shrink logic from `caption_top` for consistency.
- **Uncaught exceptions in ops no longer 500.** `register_op` now wraps every op function in a uniform try/except: any uncaught exception (PIL errors, missing fonts, file IO, network failures, etc.) is converted to `{"error": "<ExceptionClass>: <msg>", "op": "<name>"}` instead of crashing the MCP/HTTP call. Tracebacks are still logged server-side via `log.exception` for debugging. Set `PICASSO_DEBUG=1` to also include the trace in the response.

### Notes

- **Sepia (filter.py) re-evaluated.** Tried swapping the cream-on-cream colorize for the canonical linear sepia matrix (numpy). Side-by-side review showed the matrix produced a muddy/brown look that lost the soft vintage feel — reverted to original colorize. Lesson logged to Vox Memori (rule_id 41): for aesthetic ops, A/B before assuming "more correct algorithm = better look."
- **Discord can't render `ImageContent`.** Inline-mode wiring is verified end-to-end via Claude Code (which DOES render the image content block); Discord clients receive only text from MCP responses. Real UX validation needs Claude Desktop / claude.ai with the skill installed.
- **HTTP `/api/ops/*` endpoints unchanged.** Inline-image wrapping only happens on the MCP surface — the browser GUI loads images from disk paths and doesn't need image data in the response.
- **Eval suite ran twice (4 prompts × with-skill + baseline).** Iteration 1 (shared session_id across all 8 agents) surfaced the session-state contamination bug + the meme overflow + the missing `create_session` MCP tool — those were the highest-value findings of the day. Iteration 2 (after fixes, with each agent calling `create_session`) showed all four evals tied between with-skill and baseline. With-skill was consistently 4–14s faster on the same pipeline; tokens nearly identical (31–39K range either way).
- **Architectural takeaway: invest in tool descriptions, not SKILL.md prose.** The lift the SKILL.md provided in iteration 1 (eval 1 — knowing to use HTTP `/api/sessions`) disappeared in iteration 2 once the same lesson was moved into the `create_session` MCP tool description. Tool descriptions are read on every tool call; SKILL.md is read once when the skill triggers. Anything load-bearing should live in the tool description.
- **Deferred:** `ig_square` downscales the polaroid frame so the caption clips when chained polaroid → ig_square. Niche issue with a clean workaround (pad-to-square instead of fit-and-crop). Worth fixing eventually but didn't make today's cut.

---

<!-- Past releases get appended below as we cut versions. -->
