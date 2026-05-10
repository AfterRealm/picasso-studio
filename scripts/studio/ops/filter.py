"""Filters — sepia, grayscale, blur, sharpen, invert, posterize, solarize, emboss,
edge, pixelate, halftone, scanlines, oil_painting, pencil_sketch, cartoon,
vaporwave, glitch, deep_fry, vignette, duotone, glow.

All single-image PNG-output ops use `@image_op`; deep_fry has a JPEG side
channel (round-trips through low-quality JPEG to bake artifacts) and uses
the lower-level `@register_op` so it can manage its own temp file.
"""
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import MAX_BLUR_RADIUS, clamp, open_image, step_path
from ._scaffold import image_op


@image_op(category="filter", label="Sepia",
          description="Warm vintage tone — converts the image to sepia.", params={})
def sepia(img):
    img = img.convert("RGB")
    gray = ImageOps.grayscale(img)
    return ImageOps.colorize(gray, black=(40, 20, 0), white=(255, 220, 180)), "Sepia"


@image_op(category="filter", label="Grayscale",
          description="Black and white — desaturate the image entirely.", params={})
def grayscale(img):
    return ImageOps.grayscale(img).convert("RGB"), "Grayscale"


@image_op(category="filter", label="Blur",
          description="Gaussian blur — soften the image. Higher radius = blurrier.",
          params={"radius": {"type": "float", "default": 5.0, "min": 0.1, "max": 50, "help": "Blur radius"}})
def blur(img, *, radius: float = 5.0):
    radius = float(clamp(radius, 0.1, MAX_BLUR_RADIUS))
    return img.filter(ImageFilter.GaussianBlur(radius)), f"Blur -> r={radius}"


@image_op(category="filter", label="Sharpen",
          description="Sharpen edges and detail.", params={})
def sharpen(img):
    return img.filter(ImageFilter.SHARPEN), "Sharpen"


@image_op(category="filter", label="Invert",
          description="Invert colors (negative).", params={})
def invert(img):
    return ImageOps.invert(img.convert("RGB")), "Invert"


@image_op(category="filter", label="Posterize",
          description="Reduce the number of bits per channel — flat banded poster look.",
          params={"levels": {"type": "int", "default": 4, "min": 1, "max": 8, "help": "Bits per channel"}})
def posterize(img, *, levels: int = 4):
    levels = int(clamp(levels, 1, 8))
    return ImageOps.posterize(img.convert("RGB"), levels), f"Posterize -> {levels}"


@image_op(category="filter", label="Solarize",
          description="Invert pixels above a brightness threshold for a darkroom-style effect.",
          params={"threshold": {"type": "int", "default": 128, "min": 0, "max": 255, "help": "Threshold"}})
def solarize(img, *, threshold: int = 128):
    threshold = int(clamp(threshold, 0, 255))
    return ImageOps.solarize(img.convert("RGB"), threshold), f"Solarize -> t={threshold}"


@image_op(category="filter", label="Emboss",
          description="Embossed/3D-engraved relief effect.", params={})
def emboss(img):
    return img.filter(ImageFilter.EMBOSS), "Emboss"


@image_op(category="filter", label="Edge detect",
          description="Find and highlight edges in the image.", params={})
def edge(img):
    return img.filter(ImageFilter.FIND_EDGES), "Edge detect"


@image_op(category="filter", label="Pixelate",
          description="Pixelate the image for a chunky 8-bit / mosaic look.",
          params={"pixel_size": {"type": "int", "default": 12, "min": 2, "max": 64, "help": "Pixel block size"}})
def pixelate(img, *, pixel_size: int = 12):
    pixel_size = int(clamp(pixel_size, 2, 64))
    w, h = img.size
    small = img.resize((max(1, w // pixel_size), max(1, h // pixel_size)), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST), f"Pixelate -> {pixel_size}px"


@image_op(category="filter", label="Halftone",
          description="Comic-book halftone (Floyd-Steinberg dithered B&W).", params={})
def halftone(img):
    out = img.convert("L").convert("1", dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")
    return out, "Halftone"


@image_op(category="filter", label="Scanlines",
          description="CRT scanline overlay — horizontal dark lines for retro TV vibe.", params={})
def scanlines(img):
    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, img.height, 3):
        draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, 110))
    return Image.alpha_composite(img, overlay).convert("RGB"), "Scanlines"


@image_op(category="filter", label="Oil painting",
          description="Smooth, painterly oil-painting approximation.", params={})
def oil_painting(img):
    img = img.convert("RGB")
    out = img.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.ModeFilter(5)).filter(ImageFilter.SHARPEN)
    return out, "Oil painting"


@image_op(category="filter", label="Pencil sketch",
          description="Color-dodge pencil sketch — classic graphite drawing technique.", params={})
def pencil_sketch(img):
    import numpy as np
    gray = img.convert("L")
    inverted = ImageOps.invert(gray)
    blurred = inverted.filter(ImageFilter.GaussianBlur(25))
    arr = np.array(gray, dtype=np.float32)
    blur_arr = np.array(blurred, dtype=np.float32)
    result = np.clip(arr * 256 / (257 - blur_arr), 0, 255).astype(np.uint8)
    return Image.fromarray(result, mode="L").convert("RGB"), "Pencil sketch"


@image_op(category="filter", label="Cartoon",
          description="Cartoon/toon shader — posterized colors with black edge lines.", params={})
def cartoon(img):
    img = img.convert("RGB")
    edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
    edges = edges.point(lambda p: 0 if p > 30 else 255).convert("RGB")
    posterized = ImageOps.posterize(img, 3)
    return ImageChops.multiply(posterized, edges), "Cartoon"


@image_op(category="filter", label="Vaporwave",
          description="Pink-purple duotone with a neon grid overlay — vaporwave aesthetic.", params={})
def vaporwave(img):
    gray = img.convert("L")
    duo = ImageOps.colorize(gray, black=(20, 0, 60), white=(255, 130, 220)).convert("RGBA")
    overlay = Image.new("RGBA", duo.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    step = max(20, min(duo.size) // 20)
    for x in range(0, duo.width, step):
        draw.line([(x, 0), (x, duo.height)], fill=(255, 80, 200, 70), width=1)
    for y in range(0, duo.height, step):
        draw.line([(0, y), (duo.width, y)], fill=(80, 200, 255, 70), width=1)
    return Image.alpha_composite(duo, overlay).convert("RGB"), "Vaporwave"


@image_op(category="filter", label="Glitch",
          description="RGB channel-shift glitch effect.",
          params={"offset": {"type": "int", "default": 10, "min": 1, "max": 50, "help": "Channel shift in pixels"}})
def glitch(img, *, offset: int = 10):
    offset = int(clamp(offset, 1, 50))
    img = img.convert("RGB")
    r, g, b = img.split()
    r = ImageChops.offset(r, offset, 0)
    b = ImageChops.offset(b, -offset, 0)
    return Image.merge("RGB", (r, g, b)), f"Glitch -> {offset}px"


@register_op(
    category="filter",
    label="Deep fry",
    description="Classic deep-fried meme: oversaturated, high contrast, JPEG-artifacted.",
    params={},
)
def deep_fry(session_id: str) -> dict:
    """Doesn't fit @image_op — needs a JPEG temp-file round-trip mid-pipeline
    to bake real JPEG artifacts."""
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    img = open_image(sess.current_image).convert("RGB")
    img = ImageEnhance.Color(img).enhance(2.5)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = img.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
    tmp = sess.dir / "_fry_tmp.jpg"
    img.save(tmp, "JPEG", quality=10)
    img = Image.open(tmp).convert("RGB")
    try:
        tmp.unlink()
    except OSError:
        pass
    out_path = step_path(sess, "deep_fry")
    img.save(out_path, "PNG")
    note = "Deep fry"
    record_op(sess, "deep_fry", {}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@image_op(category="filter", label="Vignette",
          description="Darken the edges in a soft radial gradient toward the corners.",
          params={"strength": {"type": "float", "default": 0.6, "min": 0.1, "max": 1.5, "help": "Vignette strength"}})
def vignette(img, *, strength: float = 0.6):
    strength = float(clamp(strength, 0.1, 1.5))
    img = img.convert("RGB")
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for i in range(min(w, h) // 2, 0, -1):
        alpha = int(255 * (1 - (min(w, h) / 2 - i) / (min(w, h) / 2) * strength))
        draw.ellipse([w // 2 - i, h // 2 - i, w // 2 + i, h // 2 + i], fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(20))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, black, mask), f"Vignette -> {strength}"


@image_op(category="filter", label="Duotone",
          description="Two-color stylized mapping — map shadows to one hex, highlights to another.",
          params={
              "dark": {"type": "str", "default": "#1a1a2e", "help": "Shadow color (hex)"},
              "light": {"type": "str", "default": "#f5e6d3", "help": "Highlight color (hex)"},
          })
def duotone(img, *, dark: str = "#1a1a2e", light: str = "#f5e6d3"):
    gray = img.convert("L")
    try:
        d_rgb = tuple(int(dark.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        l_rgb = tuple(int(light.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        d_rgb, l_rgb = (26, 26, 46), (245, 230, 211)
    return ImageOps.colorize(gray, black=d_rgb, white=l_rgb), f"Duotone -> {dark}/{light}"


@image_op(category="filter", label="Glow",
          description="Soft bright bloom / halo around the subject.",
          params={"strength": {"type": "float", "default": 1.2, "min": 1.0, "max": 2.5, "help": "Glow strength"}})
def glow(img, *, strength: float = 1.2):
    img = img.convert("RGB")
    bloom = img.filter(ImageFilter.GaussianBlur(20))
    bloom = ImageEnhance.Brightness(bloom).enhance(float(clamp(strength, 1.0, 2.5)))
    return ImageChops.screen(img, bloom), f"Glow -> {strength}"
