"""Shared helpers for ops — clamps, hex parsing, gif IO, particle sprites.

The leading underscore prevents the ops package __init__ from auto-loading this
module as if it were a category of ops.
"""
from __future__ import annotations

import functools
import math
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from PIL import Image, ImageDraw, ImageFilter

if TYPE_CHECKING:
    from ..sessions import Session

MAX_DIMENSION = 8192
MAX_BLUR_RADIUS = 50
MAX_GIF_FRAMES = 200
MAX_ANIMATE_FRAMES = 48

# Modes that carry an alpha channel and should be preserved on load.
_ALPHA_MODES = frozenset({"RGBA", "LA", "PA"})


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def parse_hex(hex_str: str) -> tuple[int, int, int]:
    cleaned = hex_str.lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(digit * 2 for digit in cleaned)
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def open_image(path: Path) -> Image.Image:
    """Open an image, preserving alpha when the source has it.

    Always uses a context manager so the underlying file handle closes
    immediately — Image.open is lazy and will hold the handle until GC
    otherwise, which on Windows locks the source file.
    """
    with Image.open(path) as im:
        # Preserve alpha for any mode that carries it, not just .png suffix —
        # WebP, GIF, TIFF, and AVIF can all have alpha.
        if im.mode in _ALPHA_MODES or "A" in im.getbands():
            return im.convert("RGBA")
        # Palette mode with transparency stored separately:
        if im.mode == "P" and im.info.get("transparency") is not None:
            return im.convert("RGBA")
        return im.convert("RGB")


def open_image_rgba(path: Path) -> Image.Image:
    """Always return RGBA; cheaper than open_image(path).convert('RGBA')
    for non-alpha sources because it skips the intermediate RGB conversion."""
    with Image.open(path) as im:
        return im.convert("RGBA")


def step_path(sess: "Session", opname: str, ext: str = "png") -> Path:
    """Build the next step output path for a session."""
    return sess.dir / f"step{len(sess.history) + 1:03d}_{opname}.{ext}"


def open_gif_frames(
    path: Path,
    *,
    mode: str | None = "RGB",
) -> tuple[list[Image.Image], list[int]]:
    """Load all frames from an animated image.

    `mode='RGB'` (default) → frames converted to RGB. Cheap and fine for
    most filters / resizers, but it strips alpha — animated WebP / APNG
    transparency is lost. Use `'RGBA'` to preserve it (slower, larger
    intermediate buffers).

    `mode=None` → passthrough: return frames in their source mode (often
    `'P'` for GIFs) without any conversion. The right call for ops that
    only reorder or re-time frames (gif_reverse / gif_boomerang /
    gif_speed) — there's no point paying the palette decompression cost
    just to throw the result back into save_gif unchanged.

    Frames inherit duration from the prior frame when `info['duration']`
    is missing; we default to 100ms only for the very first frame.
    """
    frames: list[Image.Image] = []
    durations: list[int] = []
    last_duration = 100
    with Image.open(path) as im:
        try:
            while True:
                if mode is None:
                    frames.append(im.copy())  # decouple from the seek cursor
                else:
                    frames.append(im.convert(mode))
                last_duration = int(im.info.get("duration", last_duration))
                durations.append(last_duration)
                if len(frames) >= MAX_GIF_FRAMES:
                    break
                im.seek(im.tell() + 1)
        except EOFError:
            pass
    if not frames:
        raise ValueError("no frames found")
    return frames, durations


def _normalize_durations(durations: Iterable[int], frame_count: int, default: int = 100) -> list[int]:
    """Coerce a per-frame durations list to match the frame count.

    Used to crash on `durations=[]` because we tried `[durations[0]] * len(...)`
    without checking emptiness.
    """
    durs = list(durations)
    if len(durs) == frame_count:
        return durs
    base = durs[0] if durs else default
    return [base] * frame_count


def save_gif(frames, durations, out: Path, loop: int = 0) -> Path:
    """Save a list of frames as an animated GIF with an adaptive palette."""
    if not frames:
        raise ValueError("no frames to save")
    converted = []
    for frame in frames:
        if frame.mode == "P":
            converted.append(frame)
        else:
            converted.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))
    durs = _normalize_durations(durations, len(converted))
    converted[0].save(
        out,
        save_all=True,
        append_images=converted[1:],
        duration=durs,
        loop=loop,
        optimize=True,
        disposal=2,
    )
    return out


def save_animated(
    frames,
    durations,
    out: Path,
    loop: int = 0,
    fmt: str = "webp",
    quality: int = 85,
    lossless: bool = False,
    frame_count: int | None = None,
) -> Path:
    """Save RGBA frames as animated WebP (default) or APNG.

    `frames` may be a list, any iterable, or a generator. We honor the
    iterable contract honestly:
      - If `durations` is a list whose length equals `frame_count` (or just
        equals the frame count when frame_count is None and durations is a
        sequence), we never materialize the rest of the frame iterator —
        normalization is per-frame inside the save loop.
      - If we MUST infer the frame count to align durations, we materialize
        the remaining frames as a list (Pillow needs a re-iterable anyway,
        per APNG plugin behavior).

    Defaults to lossy WebP at quality=85 — lossless on N full-RGBA frames
    is extremely slow and produces multi-MB files for visually-identical
    output. Pass `lossless=True` explicitly when bit-perfect is required.
    """
    iterator = iter(frames)
    try:
        first = next(iterator)
    except StopIteration as exc:
        raise ValueError("no frames to save") from exc

    def _normalized(frame):
        return frame if frame.mode == "RGBA" else frame.convert("RGBA")

    first_n = _normalized(first)

    # Decide on the frames sequence Pillow will iterate. We want:
    # - a single, re-iterable list (Pillow APNG plugin can pre-walk for
    #   sizing, which would exhaust a one-shot generator)
    # - lazy normalization so we don't double the RGBA buffer count
    # If callers pass a known frame_count (or a length-aligned durations
    # list), we trust them and avoid building an intermediate list — but
    # we still need a re-iterable, so we pass a small repeating-iterator
    # wrapper. Practically: every animate_* op builds a list anyway, so
    # the materialization branch is the common path and is honest about it.
    if isinstance(frames, list):
        rest_source: list = frames[1:]
    elif isinstance(frames, tuple):
        rest_source = list(frames[1:])
    else:
        rest_source = list(iterator)

    rest_n = [_normalized(f) for f in rest_source]
    total = frame_count if frame_count is not None else 1 + len(rest_n)
    durs = _normalize_durations(durations, total)

    if fmt == "apng":
        first_n.save(
            out, save_all=True, append_images=rest_n,
            duration=durs, loop=loop, disposal=2,
        )
    else:
        save_kwargs: dict = {
            "save_all": True,
            "append_images": rest_n,
            "duration": durs,
            "loop": loop,
            "method": 4,
        }
        if lossless:
            save_kwargs["lossless"] = True
        else:
            save_kwargs["quality"] = quality
        first_n.save(out, **save_kwargs)
    return out


def make_particle_sprite(shape: str, size: int, color: tuple) -> Image.Image:
    """Render a single particle sprite on a small RGBA canvas."""
    canvas_size = max(size * 3, 16)
    sprite = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(sprite)
    center = canvas_size // 2
    if shape == "petal":
        drawer.ellipse(
            (center - size // 2, center - size, center + size // 2, center + size),
            fill=color,
        )
    elif shape == "circle":
        drawer.ellipse(
            (center - size // 2, center - size // 2, center + size // 2, center + size // 2),
            fill=color,
        )
    elif shape == "leaf":
        points = []
        for i in range(24):
            angle = (i / 24) * 2 * math.pi
            radius = size * (0.95 if abs(math.cos(angle)) > 0.2 else 0.35)
            points.append((
                center + math.cos(angle) * radius,
                center + math.sin(angle) * size * 0.45,
            ))
        drawer.polygon(points, fill=color)
    elif shape == "sparkle":
        drawer.polygon([
            (center, center - size),
            (center + max(1, size // 4), center),
            (center, center + size),
            (center - max(1, size // 4), center),
        ], fill=color)
        drawer.polygon([
            (center - size, center),
            (center, center - max(1, size // 4)),
            (center + size, center),
            (center, center + max(1, size // 4)),
        ], fill=color)
    elif shape == "glow":
        drawer.ellipse(
            (center - size, center - size, center + size, center + size),
            fill=color,
        )
        sprite = sprite.filter(ImageFilter.GaussianBlur(max(1, size // 3)))
        drawer2 = ImageDraw.Draw(sprite)
        drawer2.ellipse(
            (center - size // 3, center - size // 3, center + size // 3, center + size // 3),
            fill=(color[0], color[1], color[2], min(255, color[3] + 20)),
        )
    elif shape == "bubble":
        drawer.ellipse(
            (center - size // 2, center - size // 2, center + size // 2, center + size // 2),
            outline=color, width=max(1, size // 8),
        )
        highlight_size = max(2, size // 5)
        drawer.ellipse(
            (center - size // 3, center - size // 3,
             center - size // 3 + highlight_size, center - size // 3 + highlight_size),
            fill=(255, 255, 255, 180),
        )
    elif shape == "streak":
        drawer.line(
            (center, center - size * 3, center, center + size * 3),
            fill=color, width=max(1, size),
        )
    return sprite


RotationCacheKey = tuple[str, int, tuple, int]  # (shape, size, color, steps)


def rotation_table(
    sprite: Image.Image,
    steps: int = 36,
    *,
    cache_key: RotationCacheKey | None = None,
) -> list[Image.Image]:
    """Pre-compute `steps` rotated copies of a sprite.

    Particle systems used to call `sprite.rotate(angle)` per particle per
    frame (frames * particles rotations every call — thousands). Picking
    the nearest pre-rotated copy from a small table is dramatically faster
    and visually indistinguishable for particles.

    Pass a stable `cache_key = (shape, size, color, steps)` to share
    rotation tables across particles with identical sprite parameters.
    The cached helper rebuilds the sprite from cache_key — keying on the
    sprite Image directly would defeat sharing because the lru_cache
    keys on the (Image-by-id) full args tuple, missing every time.
    """
    if cache_key is None:
        return [
            sprite.rotate((i / steps) * 360.0, resample=Image.BICUBIC)
            for i in range(steps)
        ]
    return _cached_rotation_table(cache_key)


@functools.lru_cache(maxsize=64)
def _cached_rotation_table(cache_key: RotationCacheKey) -> list[Image.Image]:
    shape, size, color, steps = cache_key
    sprite = make_particle_sprite(shape, size, color)
    return [
        sprite.rotate((i / steps) * 360.0, resample=Image.BICUBIC)
        for i in range(steps)
    ]


def pick_rotation(table: list[Image.Image], angle_degrees: float) -> Image.Image:
    """Pick the closest pre-rotated sprite for an arbitrary angle."""
    steps = len(table)
    idx = int((angle_degrees % 360.0) / 360.0 * steps) % steps
    return table[idx]


PARTICLE_PRESETS = {
    "petals":   {"count": 25, "size": (12, 28), "colors": [(255, 182, 193, 220), (255, 192, 203, 220), (255, 150, 170, 200), (255, 210, 220, 210)], "fall": (2.5, 5.0), "sway": 1.0, "rotate": True,  "shape": "petal"},
    "snow":     {"count": 45, "size": (3, 10),  "colors": [(255, 255, 255, 230), (240, 248, 255, 215)], "fall": (1.5, 3.0), "sway": 0.6, "rotate": False, "shape": "circle"},
    "leaves":   {"count": 20, "size": (14, 28), "colors": [(204, 119, 34, 220), (218, 165, 32, 220), (184, 90, 30, 220), (139, 69, 19, 200), (230, 180, 60, 210)], "fall": (2.0, 4.0), "sway": 1.4, "rotate": True,  "shape": "leaf"},
    "sparkles": {"count": 30, "size": (5, 12),  "colors": [(255, 255, 200, 240), (255, 255, 255, 240), (255, 215, 0, 220)], "fall": (0.3, 1.2), "sway": 0.3, "rotate": False, "shape": "sparkle"},
    "embers":   {"count": 30, "size": (3, 8),   "colors": [(255, 100, 0, 230), (255, 140, 0, 220), (255, 69, 0, 230), (255, 180, 50, 200)], "fall": (-3.5, -1.5), "sway": 0.5, "rotate": False, "shape": "glow"},
    "bubbles":  {"count": 20, "size": (10, 26), "colors": [(200, 230, 255, 160)], "fall": (-3.0, -1.2), "sway": 0.6, "rotate": False, "shape": "bubble"},
    "rain":     {"count": 80, "size": (1, 2),   "colors": [(180, 200, 240, 180)], "fall": (10.0, 16.0), "sway": 0.1, "rotate": False, "shape": "streak"},
}


GLOW_COLORS = {
    "white":  (255, 255, 255), "warm":  (255, 220, 150), "cool":   (150, 200, 255),
    "gold":   (255, 200, 60),  "pink":  (255, 180, 200), "green":  (150, 255, 180),
    "purple": (200, 150, 255), "red":   (255, 100, 100), "blue":   (100, 150, 255),
    "orange": (255, 160, 60),  "cyan":  (100, 230, 255),
}
