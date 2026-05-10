# Filter ops

Color and stylistic filters — sepia, grayscale, blur, sharpen, posterize, oil painting, vaporwave, glitch, etc.

_21 ops in this category._

## `blur` — Blur

Gaussian blur — soften the image. Higher radius = blurrier.

**Params:**
- `radius` (float [0.1..50], default `5.0`) — Blur radius

## `cartoon` — Cartoon

Cartoon/toon shader — posterized colors with black edge lines.

## `deep_fry` — Deep fry

Classic deep-fried meme: oversaturated, high contrast, JPEG-artifacted.

## `duotone` — Duotone

Two-color stylized mapping — map shadows to one hex, highlights to another.

**Params:**
- `dark` (str, default `#1a1a2e`) — Shadow color (hex)
- `light` (str, default `#f5e6d3`) — Highlight color (hex)

## `edge` — Edge detect

Find and highlight edges in the image.

## `emboss` — Emboss

Embossed/3D-engraved relief effect.

## `glitch` — Glitch

RGB channel-shift glitch effect.

**Params:**
- `offset` (int [1..50], default `10`) — Channel shift in pixels

## `glow` — Glow

Soft bright bloom / halo around the subject.

**Params:**
- `strength` (float [1.0..2.5], default `1.2`) — Glow strength

## `grayscale` — Grayscale

Black and white — desaturate the image entirely.

## `halftone` — Halftone

Comic-book halftone (Floyd-Steinberg dithered B&W).

## `invert` — Invert

Invert colors (negative).

## `oil_painting` — Oil painting

Smooth, painterly oil-painting approximation.

## `pencil_sketch` — Pencil sketch

Color-dodge pencil sketch — classic graphite drawing technique.

## `pixelate` — Pixelate

Pixelate the image for a chunky 8-bit / mosaic look.

**Params:**
- `pixel_size` (int [2..64], default `12`) — Pixel block size

## `posterize` — Posterize

Reduce the number of bits per channel — flat banded poster look.

**Params:**
- `levels` (int [1..8], default `4`) — Bits per channel

## `scanlines` — Scanlines

CRT scanline overlay — horizontal dark lines for retro TV vibe.

## `sepia` — Sepia

Warm vintage tone — converts the image to sepia.

## `sharpen` — Sharpen

Sharpen edges and detail.

## `solarize` — Solarize

Invert pixels above a brightness threshold for a darkroom-style effect.

**Params:**
- `threshold` (int [0..255], default `128`) — Threshold

## `vaporwave` — Vaporwave

Pink-purple duotone with a neon grid overlay — vaporwave aesthetic.

## `vignette` — Vignette

Darken the edges in a soft radial gradient toward the corners.

**Params:**
- `strength` (float [0.1..1.5], default `0.6`) — Vignette strength
