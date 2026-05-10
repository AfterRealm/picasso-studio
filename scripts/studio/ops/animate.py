"""Single-image animations producing animated WebP — rotate, pulse, shake, zoom,
pan, particles, glow_pulse, shimmer, ripple, flicker, ken_burns, drift, sway,
lightning, fog."""
import functools
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import (
    GLOW_COLORS, MAX_ANIMATE_FRAMES, MAX_BLUR_RADIUS, PARTICLE_PRESETS,
    clamp, make_particle_sprite, open_image_rgba,
    pick_rotation, rotation_table, save_animated,
)


def _webp_path(sess, opname: str):
    return sess.dir / f"step{len(sess.history) + 1:03d}_{opname}.webp"


@register_op(category="animate", label="Animate rotate",
             description="Spin the image full 360 degrees over N frames (animated WebP).",
             params={"frames": {"type": "int", "default": 24, "min": 8, "max": 48, "help": "Frame count"}})
def animate_rotate(session_id: str, frames: int = 24) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 8, MAX_ANIMATE_FRAMES))
    img = open_image_rgba(sess.current_image)
    result = []
    for i in range(frames):
        angle = (360 / frames) * i
        result.append(img.rotate(angle, resample=Image.BICUBIC, expand=False))
    out_path = _webp_path(sess, "animate_rotate")
    save_animated(result, [80] * frames, out_path)
    note = f"Animate rotate -> {frames}f"
    record_op(sess, "animate_rotate", {"frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate pulse",
             description="Rhythmic zoom-in/zoom-out pulse like a heartbeat.",
             params={"frames": {"type": "int", "default": 20, "min": 8, "max": 48, "help": "Frame count"}})
def animate_pulse(session_id: str, frames: int = 20) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 8, MAX_ANIMATE_FRAMES))
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    out = []
    for i in range(frames):
        scale = 1.0 + 0.15 * math.sin(i / frames * 2 * math.pi)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        zoomed = img.resize((nw, nh), Image.LANCZOS)
        if scale >= 1.0:
            x = (nw - w) // 2
            y = (nh - h) // 2
            framed = zoomed.crop((x, y, x + w, y + h))
        else:
            framed = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            framed.paste(zoomed, ((w - nw) // 2, (h - nh) // 2), zoomed)
        out.append(framed)
    out_path = _webp_path(sess, "animate_pulse")
    save_animated(out, [60] * frames, out_path)
    note = f"Animate pulse -> {frames}f"
    record_op(sess, "animate_pulse", {"frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate shake",
             description="Random jitter shake — the image vibrates.",
             params={
                 "frames": {"type": "int", "default": 16, "min": 8, "max": 48, "help": "Frame count"},
                 "amount": {"type": "int", "default": 10, "min": 1, "max": 50, "help": "Shake amplitude (px)"},
             })
def animate_shake(session_id: str, frames: int = 16, amount: int = 10) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 8, MAX_ANIMATE_FRAMES))
    amount = int(clamp(amount, 1, 50))
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    out = []
    for _ in range(frames):
        dx = random.randint(-amount, amount)
        dy = random.randint(-amount, amount)
        framed = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        framed.paste(img, (dx, dy), img)
        out.append(framed)
    out_path = _webp_path(sess, "animate_shake")
    save_animated(out, [50] * frames, out_path)
    note = f"Animate shake -> {amount}px"
    record_op(sess, "animate_shake", {"frames": frames, "amount": amount}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate zoom",
             description="Slow continuous zoom-in.",
             params={"frames": {"type": "int", "default": 30, "min": 8, "max": 48, "help": "Frame count"}})
def animate_zoom(session_id: str, frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 8, MAX_ANIMATE_FRAMES))
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    out = []
    for i in range(frames):
        scale = 1.0 + (0.3 * i / max(1, frames - 1))
        nw, nh = int(w * scale), int(h * scale)
        zoomed = img.resize((nw, nh), Image.LANCZOS)
        x = (nw - w) // 2
        y = (nh - h) // 2
        out.append(zoomed.crop((x, y, x + w, y + h)))
    out_path = _webp_path(sess, "animate_zoom")
    save_animated(out, [80] * frames, out_path)
    note = f"Animate zoom -> {frames}f"
    record_op(sess, "animate_zoom", {"frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate pan",
             description="Pan across a slightly zoomed version of the image (left/right/up/down).",
             params={
                 "direction": {"type": "str", "default": "right", "help": "left/right/up/down"},
                 "frames": {"type": "int", "default": 30, "min": 8, "max": 48, "help": "Frame count"},
             })
def animate_pan(session_id: str, direction: str = "right", frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 8, MAX_ANIMATE_FRAMES))
    direction = (direction or "right").lower().strip()
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    zoom = 1.4
    zw, zh = int(w * zoom), int(h * zoom)
    zoomed = img.resize((zw, zh), Image.LANCZOS)
    out = []
    for i in range(frames):
        t = i / max(1, frames - 1)
        if direction == "left":
            x, y = int((1 - t) * (zw - w)), (zh - h) // 2
        elif direction == "down":
            x, y = (zw - w) // 2, int(t * (zh - h))
        elif direction == "up":
            x, y = (zw - w) // 2, int((1 - t) * (zh - h))
        else:
            x, y = int(t * (zw - w)), (zh - h) // 2
        out.append(zoomed.crop((x, y, x + w, y + h)))
    out_path = _webp_path(sess, "animate_pan")
    save_animated(out, [70] * frames, out_path)
    note = f"Animate pan -> {direction}"
    record_op(sess, "animate_pan", {"direction": direction, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate particles",
             description="Overlay drifting particles (petals/snow/leaves/sparkles/embers/bubbles/rain).",
             params={
                 "preset": {"type": "str", "default": "petals", "help": "petals/snow/leaves/sparkles/embers/bubbles/rain"},
                 "frames": {"type": "int", "default": 30, "min": 16, "max": 48, "help": "Frame count"},
             })
def animate_particles(session_id: str, preset: str = "petals", frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 16, MAX_ANIMATE_FRAMES))
    key = (preset or "petals").lower().strip()
    cfg = PARTICLE_PRESETS.get(key, PARTICLE_PRESETS["petals"])
    img = open_image_rgba(sess.current_image)
    w, h = img.size

    rng = random.Random(12345)
    particles = []
    rising = cfg["fall"][0] < 0
    for _ in range(cfg["count"]):
        sz = rng.randint(*cfg["size"])
        color = rng.choice(cfg["colors"])
        sprite = make_particle_sprite(cfg["shape"], sz, color)
        # Pre-rotation table (36 angles): swaps frames*count PIL rotations for
        # a cheap nearest-angle lookup. Cache key is (shape, size, color, steps)
        # so particles with identical sprites share one table — and so the
        # cache survives sprite GC unlike id()-keyed memoization.
        table = (
            rotation_table(sprite, steps=36, cache_key=(cfg["shape"], sz, color, 36))
            if cfg["rotate"] else None
        )
        particles.append({
            "sprite": sprite,
            "rotation_table": table,
            "x": rng.uniform(-20, w + 20),
            "y": rng.uniform(-h * 0.3, h * 1.1) if not rising else rng.uniform(-h * 0.1, h * 1.2),
            "size": sz,
            "speed": rng.uniform(*cfg["fall"]),
            "sway_phase": rng.uniform(0, 2 * math.pi),
            "sway_amp": cfg["sway"] * rng.uniform(3, 10),
            "rotation": rng.uniform(0, 360) if cfg["rotate"] else 0.0,
            "rot_speed": rng.uniform(-6, 6) if cfg["rotate"] else 0.0,
        })

    out = []
    for t in range(frames):
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for p in particles:
            p["y"] += p["speed"]
            if rising:
                if p["y"] < -p["size"] * 3:
                    p["y"] = h + rng.uniform(0, h * 0.2)
                    p["x"] = rng.uniform(-20, w + 20)
            else:
                if p["y"] > h + p["size"] * 3:
                    p["y"] = -rng.uniform(0, h * 0.3) - p["size"] * 3
                    p["x"] = rng.uniform(-20, w + 20)
            sway = p["sway_amp"] * math.sin(p["sway_phase"] + t * 0.2)
            x = p["x"] + sway
            y = p["y"]
            if p["rotation_table"] is not None:
                rot = p["rotation"] + p["rot_speed"] * t
                sprite = pick_rotation(p["rotation_table"], rot)
            else:
                sprite = p["sprite"]
            sw, sh = sprite.size
            overlay.alpha_composite(sprite, (int(x - sw // 2), int(y - sh // 2)))
        frame = Image.alpha_composite(img, overlay)
        out.append(frame)
    out_path = _webp_path(sess, "animate_particles")
    save_animated(out, [60] * frames, out_path)
    note = f"Animate particles -> {key}"
    record_op(sess, "animate_particles", {"preset": preset, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate glow pulse",
             description="Breathing colored glow around the subject (uses alpha silhouette).",
             params={
                 "color": {"type": "str", "default": "white", "help": "white/warm/cool/gold/pink/green/purple/red/blue/orange/cyan"},
                 "strength": {"type": "float", "default": 1.0, "min": 0.2, "max": 3.0, "help": "Glow strength"},
                 "frames": {"type": "int", "default": 20, "min": 10, "max": 48, "help": "Frame count"},
             })
def animate_glow_pulse(session_id: str, color: str = "white", strength: float = 1.0, frames: int = 20) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 10, MAX_ANIMATE_FRAMES))
    strength = float(clamp(strength, 0.2, 3.0))
    glow_color = GLOW_COLORS.get((color or "white").lower().strip(), GLOW_COLORS["white"])
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    alpha = img.split()[-1]
    out = []
    for i in range(frames):
        pulse = (math.sin(i / frames * 2 * math.pi) + 1) * 0.5
        # Honor the codebase-wide MAX_BLUR_RADIUS contract; without the
        # clamp, strength=3.0 produced radius=113 vs the documented 50.
        radius = int(clamp(8 + 35 * pulse * strength, 1, MAX_BLUR_RADIUS))
        mult = 0.3 + 0.7 * pulse * strength
        # Brightness LUT — quantize to 0.01 buckets so the cache hits across
        # frames AND across calls with similar strength values.
        lut = _brightness_lut(round(mult, 2))
        blurred = alpha.filter(ImageFilter.GaussianBlur(radius))
        scaled = blurred.point(lut)
        glow = Image.new("RGBA", (w, h), glow_color + (0,))
        glow.putalpha(scaled)
        frame = Image.alpha_composite(glow, img)
        out.append(frame)
    out_path = _webp_path(sess, "animate_glow_pulse")
    save_animated(out, [70] * frames, out_path)
    note = f"Animate glow -> {color}"
    record_op(sess, "animate_glow_pulse", {"color": color, "strength": strength, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate shimmer",
             description="Sweep a metallic/holographic light band across the image.",
             params={
                 "direction": {"type": "str", "default": "diagonal", "help": "diagonal/horizontal/vertical"},
                 "frames": {"type": "int", "default": 24, "min": 12, "max": 48, "help": "Frame count"},
             })
def animate_shimmer(session_id: str, direction: str = "diagonal", frames: int = 24) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 12, MAX_ANIMATE_FRAMES))
    direction = (direction or "diagonal").lower().strip()
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    img_alpha = img.split()[-1]
    band = max(40, int(min(w, h) * 0.2))
    travel = max(w, h) + band * 3
    out = []
    for i in range(frames):
        t = i / max(1, frames - 1)
        overlay = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        od = ImageDraw.Draw(overlay)
        center = -band + int(t * travel)
        for off in range(-band, band + 1, 2):
            a = int(200 * math.exp(-(off / (band / 2.2)) ** 2))
            if a <= 0:
                continue
            if direction == "horizontal":
                od.line([(center + off, 0), (center + off, h)], fill=(255, 255, 255, a), width=2)
            elif direction == "vertical":
                od.line([(0, center + off), (w, center + off)], fill=(255, 255, 255, a), width=2)
            else:
                od.line([(center + off, 0), (center + off - h, h)], fill=(255, 255, 255, a), width=2)
        overlay_alpha = ImageChops.multiply(overlay.split()[-1], img_alpha)
        overlay.putalpha(overlay_alpha)
        frame = Image.alpha_composite(img, overlay)
        out.append(frame)
    out_path = _webp_path(sess, "animate_shimmer")
    save_animated(out, [55] * frames, out_path)
    note = f"Animate shimmer -> {direction}"
    record_op(sess, "animate_shimmer", {"direction": direction, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


def _ripple_frame(arr, w: int, h: int, amp: int, freq: float, phase: float):
    """Vectorized horizontal-ripple distortion using numpy fancy indexing.

    Replaces the per-strip crop+paste loop (8000+ PIL ops on a 1080p frame)
    with one np.array build, one column-shift index map, and one round-trip
    back to PIL. Visually identical, dramatically faster on big images.
    """
    import numpy as np
    # Per-row column shift: shift = amp * sin(freq * y + phase).
    rows = np.arange(h, dtype=np.float32)
    shifts = (amp * np.sin(freq * rows + phase)).astype(np.int32)
    cols = np.arange(w, dtype=np.int32)[None, :] - shifts[:, None]
    cols = np.clip(cols, 0, w - 1)
    # Build (row, col) index arrays for fancy indexing across all channels.
    row_idx = np.arange(h, dtype=np.int32)[:, None]
    return arr[row_idx, cols]


@register_op(category="animate", label="Animate ripple",
             description="Water-surface horizontal ripple distortion.",
             params={
                 "strength": {"type": "float", "default": 1.0, "min": 0.3, "max": 3.0, "help": "Ripple strength"},
                 "frames": {"type": "int", "default": 30, "min": 12, "max": 48, "help": "Frame count"},
             })
def animate_ripple(session_id: str, strength: float = 1.0, frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 12, MAX_ANIMATE_FRAMES))
    strength = float(clamp(strength, 0.3, 3.0))
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    amp = max(2, int(8 * strength))
    freq = 0.06

    # numpy is a hard transitive dep (Pillow / matplotlib pull it). The
    # previous per-strip PIL fallback was dead code.
    import numpy as np
    arr = np.array(img)  # shape (h, w, 4) for RGBA
    out = []
    for i in range(frames):
        phase = i / frames * 2 * math.pi
        shifted = _ripple_frame(arr, w, h, amp, freq, phase)
        out.append(Image.fromarray(shifted, mode="RGBA"))

    out_path = _webp_path(sess, "animate_ripple")
    save_animated(out, [55] * frames, out_path)
    note = f"Animate ripple -> {strength}"
    record_op(sess, "animate_ripple", {"strength": strength, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate flicker",
             description="Flame-like brightness flicker.",
             params={
                 "intensity": {"type": "float", "default": 1.0, "min": 0.3, "max": 2.5, "help": "Flicker intensity"},
                 "frames": {"type": "int", "default": 24, "min": 12, "max": 48, "help": "Frame count"},
             })
def animate_flicker(session_id: str, intensity: float = 1.0, frames: int = 24) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 12, MAX_ANIMATE_FRAMES))
    intensity = float(clamp(intensity, 0.3, 2.5))
    img = open_image_rgba(sess.current_image)
    rng = random.Random(7)
    out = []
    for _ in range(frames):
        b = 1.0 + rng.uniform(-0.22, 0.22) * intensity
        out.append(ImageEnhance.Brightness(img).enhance(b))
    out_path = _webp_path(sess, "animate_flicker")
    save_animated(out, [55] * frames, out_path)
    note = f"Animate flicker -> {intensity}"
    record_op(sess, "animate_flicker", {"intensity": intensity, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate Ken Burns",
             description="Slow cinematic zoom + pan (documentary feel).",
             params={
                 "zoom_pct": {"type": "float", "default": 20, "min": 5, "max": 60, "help": "Zoom percent"},
                 "direction": {"type": "str", "default": "right", "help": "right/left/up/down/center"},
                 "frames": {"type": "int", "default": 40, "min": 16, "max": 48, "help": "Frame count"},
             })
def animate_ken_burns(session_id: str, zoom_pct: float = 20, direction: str = "right", frames: int = 40) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 16, MAX_ANIMATE_FRAMES))
    zoom_pct = float(clamp(zoom_pct, 5, 60))
    direction = (direction or "right").lower().strip()
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    out = []
    for i in range(frames):
        t = i / max(1, frames - 1)
        zoom = 1.0 + (zoom_pct / 100) * t
        zw, zh = int(w * zoom), int(h * zoom)
        zoomed = img.resize((zw, zh), Image.LANCZOS)
        if direction == "right":
            cx, cy = int((zw - w) * t), (zh - h) // 2
        elif direction == "left":
            cx, cy = int((zw - w) * (1 - t)), (zh - h) // 2
        elif direction == "up":
            cx, cy = (zw - w) // 2, int((zh - h) * (1 - t))
        elif direction == "down":
            cx, cy = (zw - w) // 2, int((zh - h) * t)
        else:
            cx, cy = (zw - w) // 2, (zh - h) // 2
        out.append(zoomed.crop((cx, cy, cx + w, cy + h)))
    out_path = _webp_path(sess, "animate_ken_burns")
    save_animated(out, [75] * frames, out_path)
    note = f"Ken Burns -> {direction}"
    record_op(sess, "animate_ken_burns", {"zoom_pct": zoom_pct, "direction": direction, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate drift",
             description="Gentle floating drift on one axis (vertical or horizontal).",
             params={
                 "axis": {"type": "str", "default": "vertical", "help": "vertical or horizontal"},
                 "frames": {"type": "int", "default": 30, "min": 12, "max": 48, "help": "Frame count"},
             })
def animate_drift(session_id: str, axis: str = "vertical", frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 12, MAX_ANIMATE_FRAMES))
    axis = (axis or "vertical").lower().strip()
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    amp = 14
    out = []
    for i in range(frames):
        off = int(amp * math.sin(i / frames * 2 * math.pi))
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if axis in ("horizontal", "h", "x"):
            frame.paste(img, (off, 0), img)
        else:
            frame.paste(img, (0, off), img)
        out.append(frame)
    out_path = _webp_path(sess, "animate_drift")
    save_animated(out, [60] * frames, out_path)
    note = f"Animate drift -> {axis}"
    record_op(sess, "animate_drift", {"axis": axis, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate sway",
             description="Back-and-forth gentle rotation — flowers in wind, pendants.",
             params={
                 "degrees": {"type": "float", "default": 5.0, "min": 1, "max": 30, "help": "Sway angle"},
                 "frames": {"type": "int", "default": 30, "min": 12, "max": 48, "help": "Frame count"},
             })
def animate_sway(session_id: str, degrees: float = 5.0, frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 12, MAX_ANIMATE_FRAMES))
    degrees = float(clamp(degrees, 1, 30))
    img = open_image_rgba(sess.current_image)
    out = []
    for i in range(frames):
        ang = degrees * math.sin(i / frames * 2 * math.pi)
        out.append(img.rotate(ang, resample=Image.BICUBIC, expand=False))
    out_path = _webp_path(sess, "animate_sway")
    save_animated(out, [55] * frames, out_path)
    note = f"Animate sway -> {degrees}deg"
    record_op(sess, "animate_sway", {"degrees": degrees, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="animate", label="Animate lightning",
             description="Flash burst — mostly normal with occasional bright lightning flashes.",
             params={"frames": {"type": "int", "default": 20, "min": 10, "max": 48, "help": "Frame count"}})
def animate_lightning(session_id: str, frames: int = 20) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 10, MAX_ANIMATE_FRAMES))
    img = open_image_rgba(sess.current_image)
    rng = random.Random(3)
    flash = {rng.randint(0, frames - 1) for _ in range(max(1, frames // 7))}
    out = []
    for i in range(frames):
        if i in flash:
            out.append(ImageEnhance.Brightness(img).enhance(rng.uniform(1.7, 2.2)))
        elif (i - 1 in flash) or (i + 1 in flash):
            out.append(ImageEnhance.Brightness(img).enhance(1.25))
        else:
            out.append(img.copy())
    out_path = _webp_path(sess, "animate_lightning")
    save_animated(out, [70] * frames, out_path)
    note = "Animate lightning"
    record_op(sess, "animate_lightning", {"frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


_FOG_CANONICAL_EDGE = 2048  # canonical fog texture edge length in pixels


@functools.lru_cache(maxsize=1)
def _fog_texture_canonical() -> Image.Image:
    """Build the fog noise once at a canonical 2048x2048 (then scaled per call).

    Used to be cached per-(w,h), which on 4K inputs put ~32MB per slot into
    memory. Generating at a fixed size and resizing on use keeps the cache
    flat and the fog visually indistinguishable.
    """
    edge = _FOG_CANONICAL_EDGE
    fog = Image.new("L", (edge, edge), 0)
    drawer = ImageDraw.Draw(fog)
    rng = random.Random(42)
    for _ in range(500):
        cx = rng.randint(0, edge)
        cy = rng.randint(0, edge)
        r = rng.randint(50, 180)
        bright = rng.randint(60, 150)
        drawer.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bright)
    return fog.filter(ImageFilter.GaussianBlur(60))


@functools.lru_cache(maxsize=128)
def _brightness_lut(mult: float) -> tuple[int, ...]:
    """Pre-quantized brightness LUT — used by animate_glow_pulse per frame."""
    return tuple(min(255, int(v * mult)) for v in range(256))


@functools.lru_cache(maxsize=4)
def _fog_texture(w: int, h: int) -> Image.Image:
    """Cached resize of the canonical fog to fit a (w*2, h*2) window.

    Cap is small (max 4 distinct resolutions cached) so memory stays
    bounded; a second fog op at the same resolution skips the resize.
    """
    base = _fog_texture_canonical()
    return base.resize((w * 2, h * 2), Image.BILINEAR)


@register_op(category="animate", label="Animate fog",
             description="Drifting fog/mist overlay across the image.",
             params={
                 "direction": {"type": "str", "default": "right", "help": "right/left/up/down"},
                 "frames": {"type": "int", "default": 30, "min": 12, "max": 48, "help": "Frame count"},
             })
def animate_fog(session_id: str, direction: str = "right", frames: int = 30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames = int(clamp(frames, 12, MAX_ANIMATE_FRAMES))
    direction = (direction or "right").lower().strip()
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    fog = _fog_texture(w, h)

    out = []
    for i in range(frames):
        t = i / max(1, frames - 1)
        if direction == "left":
            ox, oy = int((1 - t) * w), 0
        elif direction == "up":
            ox, oy = 0, int((1 - t) * h)
        elif direction == "down":
            ox, oy = 0, int(t * h)
        else:
            ox, oy = int(t * w), 0
        window = fog.crop((ox, oy, ox + w, oy + h))
        layer = Image.new("RGBA", (w, h), (245, 245, 250, 0))
        layer.putalpha(window)
        out.append(Image.alpha_composite(img, layer))
    out_path = _webp_path(sess, "animate_fog")
    save_animated(out, [70] * frames, out_path)
    note = f"Animate fog -> {direction}"
    record_op(sess, "animate_fog", {"direction": direction, "frames": frames}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}
