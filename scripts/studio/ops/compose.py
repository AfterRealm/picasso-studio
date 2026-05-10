"""Composition — meme, polaroid, caption_top, thought_bubble, annotate, add_text."""
import functools

from PIL import Image, ImageDraw, ImageFont

from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import clamp, open_image, open_image_rgba, step_path


@functools.lru_cache(maxsize=128)
def _load_font(names: tuple[str, ...], size: int) -> ImageFont.ImageFont:
    """Cached font lookup over a fallback list. The default-font branch hits
    the filesystem on misses, so memoizing per (names, size) keeps ops cheap
    on repeat invocations."""
    for fname in names:
        try:
            return ImageFont.truetype(fname, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


@functools.lru_cache(maxsize=256)
def _resolve_font_by_family(family: str, size: int) -> ImageFont.ImageFont:
    """Resolve a font family (e.g. 'Arial') via matplotlib, with cached lookup."""
    try:
        from matplotlib import font_manager
        path = font_manager.findfont(family, fallback_to_default=True)
        return ImageFont.truetype(path, size)
    except (OSError, ImportError):
        for candidate in (family, family + ".ttf", family.lower() + ".ttf"):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


_BUBBLE_FONT_CANDIDATES = (
    "seguiemj.ttf", "AppleColorEmoji.ttf", "NotoColorEmoji.ttf",
    "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
    "arial.ttf", "Arial.ttf", "segoeui.ttf",
)
_EMOJI_FONTS = frozenset({"seguiemj.ttf", "AppleColorEmoji.ttf", "NotoColorEmoji.ttf"})


@functools.lru_cache(maxsize=64)
def _bubble_font(size: int) -> tuple[ImageFont.ImageFont, dict]:
    for fname in _BUBBLE_FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(fname, size)
            kwargs = {"embedded_color": True} if fname in _EMOJI_FONTS else {}
            return font, kwargs
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size), {}
    except TypeError:
        return ImageFont.load_default(), {}


@register_op(
    category="compose",
    label="Annotate",
    description="Add a small caption bar centered near the bottom of the image.",
    params={"text": {"type": "str", "default": "Note", "help": "Annotation text"}},
)
def annotate(session_id: str, text: str = "Note") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image_rgba(sess.current_image)
    draw = ImageDraw.Draw(img)
    font = _load_font(("arial.ttf", "Arial.ttf", "DejaVuSans.ttf"), max(16, img.width // 20))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (img.width - tw) // 2, img.height - th - 20
    draw.rectangle([x - 10, y - 5, x + tw + 10, y + th + 5], fill=(0, 0, 0, 180))
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    final = img.convert("RGB")
    out_path = step_path(sess, "annotate")
    final.save(out_path, "PNG")
    note = f"Annotate -> {text!r}"
    record_op(sess, "annotate", {"text": text}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


_MEME_FONT_CANDIDATES = ("impact.ttf", "Impact.ttf", "arialbd.ttf", "Arial Bold.ttf",
                         "DejaVuSans-Bold.ttf", "arial.ttf", "Arial.ttf")


@register_op(
    category="compose",
    label="Meme caption",
    description="Classic white-text-with-black-outline meme caption (top and/or bottom).",
    params={
        "top": {"type": "str", "default": "", "help": "Top text"},
        "bottom": {"type": "str", "default": "", "help": "Bottom text"},
    },
)
def meme(session_id: str, top: str = "", bottom: str = "") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image(sess.current_image).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    max_text_w = int(w * 0.92)
    margin = max(20, h // 40)

    def fit_caption(text: str):
        """Pick a font size and wrap so the rendered block stays inside max_text_w
        without exceeding ~30% of image height. Returns (font, lines, line_h, font_size)."""
        upper_text = text.upper()
        font_size = max(24, w // 12)
        words = upper_text.split()
        while True:
            font = _load_font(_MEME_FONT_CANDIDATES, font_size)
            tmp = Image.new("RGB", (1, 1))
            tdraw = ImageDraw.Draw(tmp)
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if tdraw.textlength(candidate, font=font) > max_text_w and current:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                lines.append(current)
            longest = max((tdraw.textlength(line, font=font) for line in lines), default=0)
            ref_bbox = tdraw.textbbox((0, 0), "Ag", font=font)
            line_h = (ref_bbox[3] - ref_bbox[1]) + max(4, font_size // 6)
            block_h = line_h * len(lines)
            if (longest <= max_text_w and block_h <= h * 0.30) or font_size <= 18:
                return font, lines, line_h, font_size
            font_size = max(18, int(font_size * 0.9))

    def draw_caption(text: str, y_anchor: str):
        if not text:
            return
        font, lines, line_h, font_size = fit_caption(text)
        outline = max(2, font_size // 14)
        block_h = line_h * len(lines)
        y0 = margin if y_anchor == "top" else h - block_h - margin
        for i, line in enumerate(lines):
            tw = draw.textlength(line, font=font)
            x = (w - tw) // 2
            y = y0 + i * line_h
            # PIL's stroke_width does the outline natively in a single draw
            # call instead of (2*outline+1)^2 separate text rasterizations.
            draw.text((x, y), line, fill="white", font=font,
                      stroke_width=outline, stroke_fill="black")

    draw_caption(top, "top")
    draw_caption(bottom, "bottom")
    out_path = step_path(sess, "meme")
    img.save(out_path, "PNG")
    note = "Meme caption"
    record_op(sess, "meme", {"top": top, "bottom": bottom}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="compose",
    label="Polaroid",
    description="White polaroid frame around the image with optional caption below.",
    params={"caption": {"type": "str", "default": "", "help": "Optional caption"}},
)
def polaroid(session_id: str, caption: str = "") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image(sess.current_image).convert("RGB")
    w, h = img.size
    border_top = border_lr = max(20, w // 40)
    border_bottom = max(80, h // 8)
    new_w = w + 2 * border_lr
    new_h = h + border_top + border_bottom
    out = Image.new("RGB", (new_w, new_h), "white")
    out.paste(img, (border_lr, border_top))
    if caption:
        draw = ImageDraw.Draw(out)
        font = _load_font(("arial.ttf", "Arial.ttf", "DejaVuSans.ttf"), max(18, border_bottom // 3))
        bbox = draw.textbbox((0, 0), caption, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (new_w - tw) // 2
        y = border_top + h + (border_bottom - th) // 2
        draw.text((x, y), caption, fill=(60, 60, 60), font=font)
    out_path = step_path(sess, "polaroid")
    out.save(out_path, "PNG")
    note = "Polaroid"
    record_op(sess, "polaroid", {"caption": caption}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="compose",
    label="Caption (top)",
    description="Add wrapped meme-style text above the subject on a transparent canvas extension.",
    params={"text": {"type": "str", "default": "Caption", "help": "Caption text"}},
)
def caption_top(session_id: str, text: str = "Caption") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image_rgba(sess.current_image)
    w, h = img.size
    if not text:
        out_path = step_path(sess, "caption_top")
        img.save(out_path, "PNG")
        record_op(sess, "caption_top", {"text": text}, out_path, note="Caption (empty)")
        return {"output_path": str(out_path), "note": "Caption (empty)"}

    font_size = max(24, w // 16)
    font = _load_font(_MEME_FONT_CANDIDATES, font_size)

    tmp = Image.new("RGBA", (1, 1))
    tdraw = ImageDraw.Draw(tmp)
    max_text_w = int(w * 0.92)

    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if tdraw.textlength(candidate, font=font) > max_text_w and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    ref_bbox = tdraw.textbbox((0, 0), "Ag", font=font)
    line_h = (ref_bbox[3] - ref_bbox[1]) + max(4, font_size // 6)
    padding = max(20, font_size // 2)
    caption_h = padding * 2 + line_h * len(lines)

    canvas = Image.new("RGBA", (w, h + caption_h), (0, 0, 0, 0))
    canvas.paste(img, (0, caption_h), img)

    draw = ImageDraw.Draw(canvas)
    outline = max(2, font_size // 14)
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font)
        x = (w - tw) // 2
        y = padding + i * line_h
        draw.text((x, y), line, fill="white", font=font,
                  stroke_width=outline, stroke_fill="black")

    out_path = step_path(sess, "caption_top")
    canvas.save(out_path, "PNG")
    note = "Caption (top)"
    record_op(sess, "caption_top", {"text": text}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="compose",
    label="Thought bubble",
    description="Cartoon thought-bubble overlay with optional text or emoji content.",
    params={
        "content": {"type": "str", "default": "...", "help": "Bubble content (text or emoji)"},
        "position": {"type": "str", "default": "top-right", "help": "top-right/top-left/bottom-right/bottom-left"},
        "size_frac": {"type": "float", "default": 0.30, "min": 0.15, "max": 0.50, "help": "Bubble width fraction"},
    },
)
def thought_bubble(session_id: str, content: str = "...", position: str = "top-right", size_frac: float = 0.30) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    base = open_image_rgba(sess.current_image)
    w, h = base.size
    content = (content or "").strip()

    sf = float(clamp(size_frac, 0.15, 0.50))
    bubble_w = int(max(120, min(w * sf, 520)))
    bubble_h = int(bubble_w * 0.62)
    padding = int(max(20, w * 0.035))
    if bubble_w + 2 * padding > w:
        bubble_w = max(80, w - 2 * padding)
        bubble_h = int(bubble_w * 0.62)
    if bubble_h + 2 * padding > h:
        bubble_h = max(50, h - 2 * padding)

    pos = (position or "top-right").lower().strip()
    if pos == "top-left":
        bx, by = padding, padding
    elif pos == "bottom-right":
        bx, by = w - bubble_w - padding, h - bubble_h - padding
    elif pos == "bottom-left":
        bx, by = padding, h - bubble_h - padding
    else:
        bx, by = w - bubble_w - padding, padding
    bx = max(padding, min(bx, w - bubble_w - padding))
    by = max(padding, min(by, h - bubble_h - padding))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    outline = max(3, bubble_w // 80)
    draw.ellipse([bx, by, bx + bubble_w, by + bubble_h],
                 fill=(255, 255, 255, 240), outline=(0, 0, 0, 255), width=outline)

    img_cx, img_cy = w // 2, h // 2
    bubble_cx, bubble_cy = bx + bubble_w // 2, by + bubble_h // 2
    norm = max(1.0, ((img_cx - bubble_cx) ** 2 + (img_cy - bubble_cy) ** 2) ** 0.5)
    dx = (img_cx - bubble_cx) / norm
    dy = (img_cy - bubble_cy) / norm

    trailing = [(0.38, 0.22), (0.58, 0.13), (0.74, 0.08)]
    edge_x = bubble_cx + dx * (bubble_w // 2) * 0.9
    edge_y = bubble_cy + dy * (bubble_h // 2) * 0.9
    for dist_frac, sf2 in trailing:
        cx = edge_x + dx * bubble_w * dist_frac
        cy = edge_y + dy * bubble_h * dist_frac
        r = int(bubble_w * sf2 * 0.5)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(255, 255, 255, 240), outline=(0, 0, 0, 255), width=max(2, outline - 1))

    if content:
        font_size = int(bubble_h * 0.45) if len(content) <= 3 else max(18, int(bubble_h * 0.22))
        font, font_kwargs = _bubble_font(font_size)

        max_text_w = int(bubble_w * 0.82)
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words = content.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if tmp_draw.textlength(candidate, font=font) > max_text_w and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)

        ref = tmp_draw.textbbox((0, 0), "Ag", font=font)
        line_h = (ref[3] - ref[1]) + 4
        total_h = line_h * len(lines)
        y_start = bubble_cy - total_h // 2
        for i, line in enumerate(lines):
            tw = draw.textlength(line, font=font)
            draw.text((bubble_cx - tw // 2, y_start + i * line_h), line,
                      fill=(0, 0, 0, 255), font=font, **font_kwargs)

    result = Image.alpha_composite(base, overlay)
    out_path = step_path(sess, "thought_bubble")
    result.save(out_path, "PNG")
    note = f"Thought bubble -> {position}"
    record_op(sess, "thought_bubble", {"content": content, "position": position, "size_frac": sf}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="compose",
    label="Add text",
    description="Place custom text on the image at a chosen position with font, size, and color.",
    params={
        "text": {"type": "str", "default": "Hello", "help": "The text to render"},
        "x": {"type": "int", "default": 50, "min": 0, "max": 8192, "help": "Horizontal position (px from left, top-left of text)"},
        "y": {"type": "int", "default": 50, "min": 0, "max": 8192, "help": "Vertical position (px from top, top-left of text)"},
        "font": {"type": "str", "default": "Arial", "help": "Font family name (e.g. Arial, Times New Roman)"},
        "size": {"type": "int", "default": 48, "min": 6, "max": 1024, "help": "Font size in px"},
        "color": {"type": "str", "default": "#ffffff", "help": "Text color (hex like #ff8800 or CSS name)"},
    },
    interactive={
        "type": "text",
        "params": {"x": "x", "y": "y", "text": "text", "font": "font", "size": "size", "color": "color"},
    },
)
def add_text(session_id: str, text: str = "Hello", x: int = 50, y: int = 50,
             font: str = "Arial", size: int = 48, color: str = "#ffffff") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image_rgba(sess.current_image)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    pil_font = _resolve_font_by_family(font, max(6, int(size)))
    draw.text((int(x), int(y)), text, fill=color, font=pil_font)
    final = Image.alpha_composite(img, layer).convert("RGB")
    out_path = step_path(sess, "add_text")
    final.save(out_path, "PNG")
    note = f"Text -> {text!r} at ({x},{y}) {font} {size}px {color}"
    record_op(sess, "add_text", {"text": text, "x": int(x), "y": int(y),
                                  "font": font, "size": int(size), "color": color}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}
