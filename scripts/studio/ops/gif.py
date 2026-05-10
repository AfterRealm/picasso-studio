"""GIF transforms — reverse, boomerang, speed, resize, filter, caption, optimize."""
import functools

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import MAX_DIMENSION, clamp, open_gif_frames, save_gif


def _gif_path(sess, opname: str):
    return sess.dir / f"step{len(sess.history) + 1:03d}_{opname}.gif"


@register_op(category="gif", label="Reverse GIF",
             description="Play the GIF backwards.", params={})
def gif_reverse(session_id: str) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    # Reorder-only op — passthrough mode skips the unnecessary palette decode.
    frames, durations = open_gif_frames(sess.current_image, mode=None)
    out_path = _gif_path(sess, "gif_reverse")
    save_gif(list(reversed(frames)), list(reversed(durations)), out_path)
    note = "GIF reverse"
    record_op(sess, "gif_reverse", {}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="gif", label="Boomerang GIF",
             description="Play the GIF forwards then backwards (boomerang loop).", params={})
def gif_boomerang(session_id: str) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames, durations = open_gif_frames(sess.current_image, mode=None)
    if len(frames) > 2:
        frames = frames + list(reversed(frames[1:-1]))
        durations = durations + list(reversed(durations[1:-1]))
    out_path = _gif_path(sess, "gif_boomerang")
    save_gif(frames, durations, out_path)
    note = "GIF boomerang"
    record_op(sess, "gif_boomerang", {}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="gif", label="GIF speed",
             description="Speed up or slow down a GIF (factor 2 = 2x faster, 0.5 = 2x slower).",
             params={"factor": {"type": "float", "default": 2.0, "min": 0.1, "max": 10.0, "help": "Speed multiplier"}})
def gif_speed(session_id: str, factor: float = 2.0) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    factor = float(clamp(factor, 0.1, 10.0))
    frames, durations = open_gif_frames(sess.current_image, mode=None)
    new_durs = [max(20, int(d / factor)) for d in durations]
    out_path = _gif_path(sess, "gif_speed")
    save_gif(frames, new_durs, out_path)
    note = f"GIF speed -> {factor}x"
    record_op(sess, "gif_speed", {"factor": factor}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="gif", label="GIF resize",
             description="Resize all frames of a GIF to specific pixel dimensions.",
             params={
                 "width": {"type": "int", "min": 1, "max": 8192, "help": "New width"},
                 "height": {"type": "int", "min": 1, "max": 8192, "help": "New height"},
             })
def gif_resize(session_id: str, width: int, height: int) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    width = int(clamp(width, 1, MAX_DIMENSION))
    height = int(clamp(height, 1, MAX_DIMENSION))
    frames, durations = open_gif_frames(sess.current_image)
    resized = [f.resize((width, height), Image.LANCZOS) for f in frames]
    out_path = _gif_path(sess, "gif_resize")
    save_gif(resized, durations, out_path)
    note = f"GIF resize -> {width}x{height}"
    record_op(sess, "gif_resize", {"width": width, "height": height}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


# Precomputed 256-entry lookup tables. Image.point() with a sequence runs
# in C instead of invoking a Python callable per pixel value, which
# compounds across all frames * all channels.
#
# Returned as tuples so the cached value can't be poisoned by an accidental
# caller-side mutation.
@functools.lru_cache(maxsize=8)
def _lut_scale(scale: float, ceiling: int = 255) -> tuple[int, ...]:
    return tuple(min(ceiling, int(v * scale)) for v in range(256))


_SEPIA_R = _lut_scale(1.10)
_SEPIA_G = tuple(int(v * 0.88) for v in range(256))
_SEPIA_B = tuple(int(v * 0.56) for v in range(256))
_VAPOR_R = _lut_scale(1.15)
_VAPOR_G = tuple(int(v * 0.85) for v in range(256))
_VAPOR_B = _lut_scale(1.25)


@register_op(category="gif", label="GIF filter",
             description="Apply a per-frame filter across an animated GIF (grayscale/sepia/invert/blur/etc).",
             params={"filter_name": {"type": "str", "default": "grayscale", "help": "grayscale, sepia, invert, blur, posterize, solarize, pixelate, vaporwave, deep_fry, edge, emboss"}})
def gif_filter(session_id: str, filter_name: str = "grayscale") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames, durations = open_gif_frames(sess.current_image)
    fn = (filter_name or "").lower().strip()

    def apply(rgb):
        if fn == "grayscale":
            return ImageOps.grayscale(rgb).convert("RGB")
        if fn == "sepia":
            gray = ImageOps.grayscale(rgb)
            return Image.merge("RGB", (
                gray.point(_SEPIA_R),
                gray.point(_SEPIA_G),
                gray.point(_SEPIA_B),
            ))
        if fn == "invert":
            return ImageOps.invert(rgb)
        if fn == "blur":
            return rgb.filter(ImageFilter.GaussianBlur(3))
        if fn == "posterize":
            return ImageOps.posterize(rgb, 3)
        if fn == "solarize":
            return ImageOps.solarize(rgb, 128)
        if fn == "pixelate":
            w, h = rgb.size
            small = rgb.resize((max(1, w // 12), max(1, h // 12)), Image.NEAREST)
            return small.resize((w, h), Image.NEAREST)
        if fn == "vaporwave":
            r, g, b = rgb.split()
            return Image.merge("RGB", (
                r.point(_VAPOR_R),
                g.point(_VAPOR_G),
                b.point(_VAPOR_B),
            ))
        if fn == "deep_fry":
            e = ImageEnhance.Contrast(rgb).enhance(2.0)
            e = ImageEnhance.Color(e).enhance(2.5)
            e = ImageEnhance.Sharpness(e).enhance(3.0)
            return e
        if fn == "edge":
            return rgb.filter(ImageFilter.FIND_EDGES)
        if fn == "emboss":
            return rgb.filter(ImageFilter.EMBOSS)
        return rgb

    processed = [apply(f) for f in frames]
    out_path = _gif_path(sess, "gif_filter")
    save_gif(processed, durations, out_path)
    note = f"GIF filter -> {fn}"
    record_op(sess, "gif_filter", {"filter_name": filter_name}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


_GIF_CAPTION_FONTS = ("impact.ttf", "Impact.ttf", "arialbd.ttf", "Arial Bold.ttf",
                      "DejaVuSans-Bold.ttf", "arial.ttf", "Arial.ttf")


@functools.lru_cache(maxsize=64)
def _gif_caption_font(size: int) -> ImageFont.ImageFont:
    for name in _GIF_CAPTION_FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


@register_op(category="gif", label="GIF caption",
             description="Bake a top/bottom meme caption into every frame of a GIF.",
             params={
                 "top": {"type": "str", "default": "", "help": "Top text"},
                 "bottom": {"type": "str", "default": "", "help": "Bottom text"},
             })
def gif_caption(session_id: str, top: str = "", bottom: str = "") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames, durations = open_gif_frames(sess.current_image)
    captioned = []
    # open_gif_frames already raises ValueError on empty input — don't double-check.
    font = _gif_caption_font(max(20, frames[0].size[1] // 10))

    for frame in frames:
        img = frame.copy()
        w, h = img.size
        draw = ImageDraw.Draw(img)

        def stroke_text(text, y):
            if not text:
                return
            text = text.upper()
            tw = draw.textlength(text, font=font)
            x = (w - tw) // 2
            # PIL's stroke_width: single draw call, native outline. Replaces
            # the 3x3 nested-loop hand-rolled stroke.
            draw.text((x, y), text, font=font, fill="white",
                      stroke_width=2, stroke_fill="black")

        stroke_text(top, 10)
        stroke_text(bottom, h - (h // 8) - 10)
        captioned.append(img)
    out_path = _gif_path(sess, "gif_caption")
    save_gif(captioned, durations, out_path)
    note = "GIF caption"
    record_op(sess, "gif_caption", {"top": top, "bottom": bottom}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(category="gif", label="GIF optimize",
             description="Reduce palette depth + re-save for smaller file size.", params={})
def gif_optimize(session_id: str) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    frames, durations = open_gif_frames(sess.current_image)
    # Derive a single 64-color palette from the first frame and reuse it
    # across the rest. Per-frame ADAPTIVE palettes (the previous version)
    # defeated GIF interframe optimize: the writer either remapped to a
    # global palette anyway (silently undoing the per-frame work) or
    # stored a palette per frame (bloating the file). One master palette
    # is faster AND smaller.
    master = frames[0].convert("P", palette=Image.Palette.ADAPTIVE, colors=64)
    reduced = [master] + [
        f.quantize(palette=master, dither=Image.Dither.FLOYDSTEINBERG)
        for f in frames[1:]
    ]
    out_path = _gif_path(sess, "gif_optimize")
    save_gif(reduced, durations, out_path)
    note = "GIF optimize"
    record_op(sess, "gif_optimize", {}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}
