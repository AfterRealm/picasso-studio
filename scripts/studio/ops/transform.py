"""Geometric transforms — resize, crop, rotate, flip, mirror, upscale, thumbnail, fix_orientation.

All ops here use `@image_op` — the scaffolding decorator handles session
lookup, image load, output path, save, and history recording. The op
function only carries the actual transform logic.
"""
from PIL import Image, ImageOps, ImageFilter

from ._helpers import MAX_DIMENSION, clamp
from ._scaffold import image_op


def _normalize_direction(raw: str) -> str:
    """Map a horizontal/vertical input to a canonical token, accepting
    common short forms ('h', 'v', 'horizontal', 'vertical')."""
    value = (raw or "horizontal").lower().strip()
    if value.startswith("v"):
        return "vertical"
    return "horizontal"


@image_op(
    category="transform",
    label="Resize",
    description=(
        "Resize the image to specific pixel dimensions. Use this when the user "
        "wants the image at a particular size — e.g. '1080x1080', 'make it square', "
        "or for a specific platform target."
    ),
    params={
        "width": {"type": "int", "min": 1, "max": 8192, "help": "New width in pixels"},
        "height": {"type": "int", "min": 1, "max": 8192, "help": "New height in pixels"},
    },
)
def resize(img, *, width: int, height: int):
    width = int(clamp(width, 1, MAX_DIMENSION))
    height = int(clamp(height, 1, MAX_DIMENSION))
    return img.resize((width, height), Image.LANCZOS), f"Resize -> {width}x{height}"


@image_op(
    category="transform",
    label="Crop",
    description="Crop the image to a rectangle defined by left/top/right/bottom pixels.",
    params={
        "left": {"type": "int", "default": 0, "min": 0, "max": 8192, "help": "Left edge"},
        "top": {"type": "int", "default": 0, "min": 0, "max": 8192, "help": "Top edge"},
        "right": {"type": "int", "default": 100, "min": 1, "max": 8192, "help": "Right edge"},
        "bottom": {"type": "int", "default": 100, "min": 1, "max": 8192, "help": "Bottom edge"},
    },
    interactive={"type": "rect", "params": ["left", "top", "right", "bottom"]},
)
def crop(img, *, left: int, top: int, right: int, bottom: int):
    w, h = img.size
    left = int(clamp(left, 0, max(0, w - 1)))
    top = int(clamp(top, 0, max(0, h - 1)))
    right = int(clamp(right, left + 1, w))
    bottom = int(clamp(bottom, top + 1, h))
    out = img.crop((left, top, right, bottom))
    return out, f"Crop -> ({left},{top})-({right},{bottom})"


@image_op(
    category="transform",
    label="Rotate",
    description="Rotate the image by an arbitrary number of degrees (clockwise).",
    params={"degrees": {"type": "float", "default": 90.0, "min": -360, "max": 360, "help": "Degrees clockwise"}},
)
def rotate(img, *, degrees: float = 90.0):
    degrees = float(clamp(degrees, -360, 360))
    return img.rotate(-degrees, expand=True), f"Rotate -> {degrees:.1f}deg"


@image_op(
    category="transform",
    label="Flip",
    description="Flip the image horizontally or vertically (mirror across an axis).",
    params={"direction": {"type": "str", "default": "horizontal", "help": "horizontal or vertical"}},
)
def flip(img, *, direction: str = "horizontal"):
    direction = _normalize_direction(direction)
    out = ImageOps.flip(img) if direction == "vertical" else ImageOps.mirror(img)
    return out, f"Flip -> {direction}"


@image_op(
    category="transform",
    label="Mirror (symmetry)",
    description="Symmetrical reflection — duplicate and mirror the image side-by-side or top-and-bottom.",
    params={"direction": {"type": "str", "default": "horizontal", "help": "horizontal or vertical"}},
)
def mirror(img, *, direction: str = "horizontal"):
    direction = _normalize_direction(direction)
    img = img.convert("RGB")
    if direction == "vertical":
        flipped = ImageOps.flip(img)
        out = Image.new("RGB", (img.width, img.height * 2))
        out.paste(img, (0, 0))
        out.paste(flipped, (0, img.height))
    else:
        flipped = ImageOps.mirror(img)
        out = Image.new("RGB", (img.width * 2, img.height))
        out.paste(img, (0, 0))
        out.paste(flipped, (img.width, 0))
    return out, f"Mirror -> {direction}"


@image_op(
    category="transform",
    label="Upscale",
    description="Quality upscale via LANCZOS + sharpen (not AI). Use when user wants the image larger/sharper.",
    params={"factor": {"type": "int", "default": 2, "min": 2, "max": 4, "help": "Scale factor (2-4)"}},
)
def upscale(img, *, factor: int = 2):
    factor = int(clamp(factor, 2, 4))
    new_w = min(img.width * factor, MAX_DIMENSION)
    new_h = min(img.height * factor, MAX_DIMENSION)
    out = img.resize((new_w, new_h), Image.LANCZOS).filter(ImageFilter.SHARPEN)
    return out, f"Upscale -> {factor}x"


@image_op(
    category="transform",
    label="Thumbnail",
    description="Shrink the image so the longer dimension is at most max_dim, preserving aspect ratio.",
    params={"max_dim": {"type": "int", "default": 512, "min": 32, "max": 8192, "help": "Max width or height"}},
)
def thumbnail(img, *, max_dim: int = 512):
    max_dim = int(clamp(max_dim, 32, MAX_DIMENSION))
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    return img, f"Thumbnail -> max {max_dim}px"


@image_op(
    category="transform",
    label="Fix orientation",
    description="Auto-rotate based on the EXIF orientation tag (fixes sideways phone photos).",
    params={},
)
def fix_orientation(img):
    # Preserve the source's color mode — don't force-flatten alpha to RGB.
    return ImageOps.exif_transpose(img), "Fix orientation (EXIF)"
