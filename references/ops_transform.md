# Transform ops

Geometric/dimensional changes — resize, crop, rotate, flip, mirror, upscale, thumbnail, fix orientation.

_8 ops in this category._

## `crop` — Crop

Crop the image to a rectangle defined by left/top/right/bottom pixels.

**Params:**
- `left` (int [0..8192], default `0`) — Left edge
- `top` (int [0..8192], default `0`) — Top edge
- `right` (int [1..8192], default `100`) — Right edge
- `bottom` (int [1..8192], default `100`) — Bottom edge

## `fix_orientation` — Fix orientation

Auto-rotate based on the EXIF orientation tag (fixes sideways phone photos).

## `flip` — Flip

Flip the image horizontally or vertically (mirror across an axis).

**Params:**
- `direction` (str, default `horizontal`) — horizontal or vertical

## `mirror` — Mirror (symmetry)

Symmetrical reflection — duplicate and mirror the image side-by-side or top-and-bottom.

**Params:**
- `direction` (str, default `horizontal`) — horizontal or vertical

## `resize` — Resize

Resize the image to specific pixel dimensions. Use this when the user wants the image at a particular size — e.g. '1080x1080', 'make it square', or for a specific platform target.

**Params:**
- `width` (int [1..8192], default `—`) — New width in pixels
- `height` (int [1..8192], default `—`) — New height in pixels

## `rotate` — Rotate

Rotate the image by an arbitrary number of degrees (clockwise).

**Params:**
- `degrees` (float [-360..360], default `90.0`) — Degrees clockwise

## `thumbnail` — Thumbnail

Shrink the image so the longer dimension is at most max_dim, preserving aspect ratio.

**Params:**
- `max_dim` (int [32..8192], default `512`) — Max width or height

## `upscale` — Upscale

Quality upscale via LANCZOS + sharpen (not AI). Use when user wants the image larger/sharper.

**Params:**
- `factor` (int [2..4], default `2`) — Scale factor (2-4)
