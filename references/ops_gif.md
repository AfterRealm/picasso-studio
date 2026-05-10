# Gif ops

Operations on animated GIFs — reverse, boomerang, speed, resize, filter, caption, optimize.

_7 ops in this category._

## `gif_boomerang` — Boomerang GIF

Play the GIF forwards then backwards (boomerang loop).

## `gif_caption` — GIF caption

Bake a top/bottom meme caption into every frame of a GIF.

**Params:**
- `top` (str, default ``) — Top text
- `bottom` (str, default ``) — Bottom text

## `gif_filter` — GIF filter

Apply a per-frame filter across an animated GIF (grayscale/sepia/invert/blur/etc).

**Params:**
- `filter_name` (str, default `grayscale`) — grayscale, sepia, invert, blur, posterize, solarize, pixelate, vaporwave, deep_fry, edge, emboss

## `gif_optimize` — GIF optimize

Reduce palette depth + re-save for smaller file size.

## `gif_resize` — GIF resize

Resize all frames of a GIF to specific pixel dimensions.

**Params:**
- `width` (int [1..8192], default `—`) — New width
- `height` (int [1..8192], default `—`) — New height

## `gif_reverse` — Reverse GIF

Play the GIF backwards.

## `gif_speed` — GIF speed

Speed up or slow down a GIF (factor 2 = 2x faster, 0.5 = 2x slower).

**Params:**
- `factor` (float [0.1..10.0], default `2.0`) — Speed multiplier
