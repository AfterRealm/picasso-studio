# Color ops

Color/exposure adjustments — brightness, contrast, saturation, auto-contrast, auto-level.

_5 ops in this category._

## `auto_contrast` — Auto contrast

Automatically stretch contrast to use the full tonal range.

## `auto_level` — Auto level

Equalize the histogram for an even tonal distribution.

## `brightness` — Brightness

Adjust brightness — factor 1.0 is unchanged, <1 darker, >1 brighter.

**Params:**
- `factor` (float [0.0..5.0], default `1.2`) — Brightness factor

## `contrast` — Contrast

Adjust contrast — factor 1.0 is unchanged, <1 flatter, >1 punchier.

**Params:**
- `factor` (float [0.0..5.0], default `1.2`) — Contrast factor

## `saturation` — Saturation

Adjust saturation — factor 0 is grayscale, 1.0 unchanged, >1 more vivid.

**Params:**
- `factor` (float [0.0..5.0], default `1.5`) — Saturation factor
