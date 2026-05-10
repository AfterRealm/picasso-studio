"""Effects — drop_shadow, round_corners, watermark, border, bg_color, vectorize."""
import functools

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import clamp, open_image_rgba, step_path


@register_op(
    category="effect",
    label="Drop shadow",
    description="Place the image on a white canvas with a soft drop shadow.",
    params={
        "offset": {"type": "int", "default": 15, "min": 2, "max": 80, "help": "Shadow offset (px)"},
        "blur": {"type": "int", "default": 20, "min": 2, "max": 50, "help": "Shadow blur (px)"},
    },
)
def drop_shadow(session_id: str, offset: int = 15, blur: int = 20) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    offset = int(clamp(offset, 2, 80))
    blur = int(clamp(blur, 2, 50))
    img = open_image_rgba(sess.current_image)
    pad = offset + blur * 2
    canvas_size = (img.width + pad * 2, img.height + pad * 2)
    alpha = img.split()[-1]

    # Build the blurred shadow on its own RGBA layer, then composite over a
    # white canvas, then paste the image on top. Earlier versions painted a
    # second sharp shadow onto a discarded canvas before this — dead work.
    # Bonus over the previous fix: paste a flat color via the alpha mask
    # directly, instead of allocating a full RGBA `shadow` Image just to
    # use it as a colored stamp.
    shadow_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    shadow_box = (pad + offset, pad + offset,
                  pad + offset + img.width, pad + offset + img.height)
    shadow_layer.paste((0, 0, 0, 160), shadow_box, alpha)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))

    canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 255))
    canvas = Image.alpha_composite(canvas, shadow_layer)
    canvas.paste(img, (pad, pad), img)
    final = canvas.convert("RGB")

    out_path = step_path(sess, "drop_shadow")
    final.save(out_path, "PNG")
    note = f"Drop shadow -> off={offset} blur={blur}"
    record_op(sess, "drop_shadow", {"offset": offset, "blur": blur}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="effect",
    label="Round corners",
    description="Apply rounded corners (PNG with transparency).",
    params={"radius": {"type": "int", "default": 40, "min": 2, "max": 500, "help": "Corner radius (px)"}},
)
def round_corners(session_id: str, radius: int = 40) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    radius = int(clamp(radius, 2, 500))
    img = open_image_rgba(sess.current_image)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width, img.height], radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    out_path = step_path(sess, "round_corners")
    out.save(out_path, "PNG")
    note = f"Round corners -> r={radius}"
    record_op(sess, "round_corners", {"radius": radius}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


# Cross-platform font fallback chain. arial.ttf only resolves on Windows;
# the rest cover macOS / Linux distributions.
_WATERMARK_FONT_CANDIDATES = (
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "Helvetica.ttc",
    "LiberationSans-Regular.ttf",
)


@functools.lru_cache(maxsize=64)
def _watermark_font(size: int) -> ImageFont.ImageFont:
    for name in _WATERMARK_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    # PIL 10+ supports a size hint on the default font; older versions ignore it.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


@register_op(
    category="effect",
    label="Watermark",
    description="Add a small text watermark at a chosen corner or center.",
    params={
        "text": {"type": "str", "default": "©", "help": "Watermark text"},
        "position": {"type": "str", "default": "bottom-right", "help": "bottom-right/bottom-left/top-right/top-left/center"},
    },
)
def watermark(session_id: str, text: str = "©", position: str = "bottom-right") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    font_size = max(14, min(w, h) // 25)
    font = _watermark_font(font_size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 12
    positions = {
        "bottom-right": (w - tw - pad, h - th - pad),
        "bottom-left": (pad, h - th - pad),
        "top-right": (w - tw - pad, pad),
        "top-left": (pad, pad),
        "center": ((w - tw) // 2, (h - th) // 2),
    }
    x, y = positions.get(position, positions["bottom-right"])
    draw.text((x + 2, y + 2), text, fill=(0, 0, 0, 180), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, 200), font=font)
    combined = Image.alpha_composite(img, layer).convert("RGB")
    out_path = step_path(sess, "watermark")
    combined.save(out_path, "PNG")
    note = f"Watermark -> {position}"
    record_op(sess, "watermark", {"text": text, "position": position}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="effect",
    label="Border",
    description="Add a solid color border around the image.",
    params={
        "px": {"type": "int", "default": 20, "min": 1, "max": 500, "help": "Border thickness"},
        "color": {"type": "str", "default": "black", "help": "Border color name or hex"},
    },
)
def border(session_id: str, px: int = 20, color: str = "black") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image_rgba(sess.current_image)
    out = ImageOps.expand(img, border=px, fill=color)
    out_path = step_path(sess, "border")
    out.save(out_path, "PNG")
    note = f"Border -> {px}px {color}"
    record_op(sess, "border", {"px": px, "color": color}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="effect",
    label="Background color",
    description="Replace transparency with a solid background color (chains with remove_bg).",
    params={"color": {"type": "str", "default": "white", "help": "Background color name or hex"}},
)
def bg_color(session_id: str, color: str = "white") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image_rgba(sess.current_image)
    bg = Image.new("RGBA", img.size, color)
    # alpha_composite uses the source's own alpha — no need to split() the
    # alpha channel and feed it back as a mask.
    bg.alpha_composite(img)
    final = bg.convert("RGB")
    out_path = step_path(sess, "bg_color")
    final.save(out_path, "PNG")
    note = f"Background -> {color}"
    record_op(sess, "bg_color", {"color": color}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="effect",
    label="Vectorize (SVG)",
    description="Convert the raster image to an SVG via vtracer. mode='color' or 'bw'.",
    params={"mode": {"type": "str", "default": "color", "help": "color or bw"}},
)
def vectorize(session_id: str, mode: str = "color") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    import vtracer  # type: ignore  # heavy dep, lazy-imported
    colormode = "binary" if mode.lower() in ("bw", "binary", "mono", "black-white") else "color"
    out_path = step_path(sess, "vectorize", ext="svg")
    vtracer.convert_image_to_svg_py(
        str(sess.current_image), str(out_path),
        colormode=colormode, hierarchical="stacked", mode="spline",
        filter_speckle=4, color_precision=6, layer_difference=16,
        corner_threshold=60, length_threshold=4.0, max_iterations=10,
        splice_threshold=45, path_precision=3,
    )
    note = f"Vectorize -> {colormode}"
    record_op(sess, "vectorize", {"mode": mode}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}
