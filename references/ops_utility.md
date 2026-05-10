# Utility ops

House-keeping ops — format conversion, compression, metadata strip, background removal.

_4 ops in this category._

## `compress` — Compress (JPEG)

Save as JPEG at the given quality (1-100). Great for shrinking files.

**Params:**
- `quality` (int [1..100], default `70`) — JPEG quality

## `convert` — Convert format

Convert image to a different format (jpg, png, webp).

**Params:**
- `fmt` (str, default `jpg`) — Target format: jpg, png, webp

## `remove_bg` — Remove background

Remove the background from an image (rembg / U2-Net). Returns a transparent PNG.

## `strip_metadata` — Strip metadata

Remove all EXIF / metadata from the image.
