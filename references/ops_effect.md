# Effect ops

Visual effects added on top of the image — drop shadow, round corners, watermark, border, glow, vectorize.

_6 ops in this category._

## `bg_color` — Background color

Replace transparency with a solid background color (chains with remove_bg).

**Params:**
- `color` (str, default `white`) — Background color name or hex

## `border` — Border

Add a solid color border around the image.

**Params:**
- `px` (int [1..500], default `20`) — Border thickness
- `color` (str, default `black`) — Border color name or hex

## `drop_shadow` — Drop shadow

Place the image on a white canvas with a soft drop shadow.

**Params:**
- `offset` (int [2..80], default `15`) — Shadow offset (px)
- `blur` (int [2..50], default `20`) — Shadow blur (px)

## `round_corners` — Round corners

Apply rounded corners (PNG with transparency).

**Params:**
- `radius` (int [2..500], default `40`) — Corner radius (px)

## `vectorize` — Vectorize (SVG)

Convert the raster image to an SVG via vtracer. mode='color' or 'bw'.

**Params:**
- `mode` (str, default `color`) — color or bw

## `watermark` — Watermark

Add a small text watermark at a chosen corner or center.

**Params:**
- `text` (str, default `©`) — Watermark text
- `position` (str, default `bottom-right`) — bottom-right/bottom-left/top-right/top-left/center
