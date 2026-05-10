# Animate ops

Turn a still image into an animated WebP — rotate, pulse, shake, zoom, pan, particles, shimmer, ripple, lightning, fog, etc.

_15 ops in this category._

## `animate_drift` — Animate drift

Gentle floating drift on one axis (vertical or horizontal).

**Params:**
- `axis` (str, default `vertical`) — vertical or horizontal
- `frames` (int [12..48], default `30`) — Frame count

## `animate_flicker` — Animate flicker

Flame-like brightness flicker.

**Params:**
- `intensity` (float [0.3..2.5], default `1.0`) — Flicker intensity
- `frames` (int [12..48], default `24`) — Frame count

## `animate_fog` — Animate fog

Drifting fog/mist overlay across the image.

**Params:**
- `direction` (str, default `right`) — right/left/up/down
- `frames` (int [12..48], default `30`) — Frame count

## `animate_glow_pulse` — Animate glow pulse

Breathing colored glow around the subject (uses alpha silhouette).

**Params:**
- `color` (str, default `white`) — white/warm/cool/gold/pink/green/purple/red/blue/orange/cyan
- `strength` (float [0.2..3.0], default `1.0`) — Glow strength
- `frames` (int [10..48], default `20`) — Frame count

## `animate_ken_burns` — Animate Ken Burns

Slow cinematic zoom + pan (documentary feel).

**Params:**
- `zoom_pct` (float [5..60], default `20`) — Zoom percent
- `direction` (str, default `right`) — right/left/up/down/center
- `frames` (int [16..48], default `40`) — Frame count

## `animate_lightning` — Animate lightning

Flash burst — mostly normal with occasional bright lightning flashes.

**Params:**
- `frames` (int [10..48], default `20`) — Frame count

## `animate_pan` — Animate pan

Pan across a slightly zoomed version of the image (left/right/up/down).

**Params:**
- `direction` (str, default `right`) — left/right/up/down
- `frames` (int [8..48], default `30`) — Frame count

## `animate_particles` — Animate particles

Overlay drifting particles (petals/snow/leaves/sparkles/embers/bubbles/rain).

**Params:**
- `preset` (str, default `petals`) — petals/snow/leaves/sparkles/embers/bubbles/rain
- `frames` (int [16..48], default `30`) — Frame count

## `animate_pulse` — Animate pulse

Rhythmic zoom-in/zoom-out pulse like a heartbeat.

**Params:**
- `frames` (int [8..48], default `20`) — Frame count

## `animate_ripple` — Animate ripple

Water-surface horizontal ripple distortion.

**Params:**
- `strength` (float [0.3..3.0], default `1.0`) — Ripple strength
- `frames` (int [12..48], default `30`) — Frame count

## `animate_rotate` — Animate rotate

Spin the image full 360 degrees over N frames (animated WebP).

**Params:**
- `frames` (int [8..48], default `24`) — Frame count

## `animate_shake` — Animate shake

Random jitter shake — the image vibrates.

**Params:**
- `frames` (int [8..48], default `16`) — Frame count
- `amount` (int [1..50], default `10`) — Shake amplitude (px)

## `animate_shimmer` — Animate shimmer

Sweep a metallic/holographic light band across the image.

**Params:**
- `direction` (str, default `diagonal`) — diagonal/horizontal/vertical
- `frames` (int [12..48], default `24`) — Frame count

## `animate_sway` — Animate sway

Back-and-forth gentle rotation — flowers in wind, pendants.

**Params:**
- `degrees` (float [1..30], default `5.0`) — Sway angle
- `frames` (int [12..48], default `30`) — Frame count

## `animate_zoom` — Animate zoom

Slow continuous zoom-in.

**Params:**
- `frames` (int [8..48], default `30`) — Frame count
