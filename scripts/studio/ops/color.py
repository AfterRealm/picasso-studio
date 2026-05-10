"""Color adjustments — brightness, contrast, saturation, auto_contrast, auto_level."""
from PIL import ImageEnhance, ImageOps

from ._helpers import clamp
from ._scaffold import image_op


@image_op(
    category="color", label="Brightness",
    description="Adjust brightness — factor 1.0 is unchanged, <1 darker, >1 brighter.",
    params={"factor": {"type": "float", "default": 1.2, "min": 0.0, "max": 5.0, "help": "Brightness factor"}},
)
def brightness(img, *, factor: float = 1.2):
    factor = float(clamp(factor, 0.0, 5.0))
    return ImageEnhance.Brightness(img).enhance(factor), f"Brightness -> {factor}"


@image_op(
    category="color", label="Contrast",
    description="Adjust contrast — factor 1.0 is unchanged, <1 flatter, >1 punchier.",
    params={"factor": {"type": "float", "default": 1.2, "min": 0.0, "max": 5.0, "help": "Contrast factor"}},
)
def contrast(img, *, factor: float = 1.2):
    factor = float(clamp(factor, 0.0, 5.0))
    return ImageEnhance.Contrast(img).enhance(factor), f"Contrast -> {factor}"


@image_op(
    category="color", label="Saturation",
    description="Adjust saturation — factor 0 is grayscale, 1.0 unchanged, >1 more vivid.",
    params={"factor": {"type": "float", "default": 1.5, "min": 0.0, "max": 5.0, "help": "Saturation factor"}},
)
def saturation(img, *, factor: float = 1.5):
    factor = float(clamp(factor, 0.0, 5.0))
    return ImageEnhance.Color(img).enhance(factor), f"Saturation -> {factor}"


@image_op(
    category="color", label="Auto contrast",
    description="Automatically stretch contrast to use the full tonal range.",
    params={},
)
def auto_contrast(img):
    return ImageOps.autocontrast(img.convert("RGB")), "Auto contrast"


@image_op(
    category="color", label="Auto level",
    description="Equalize the histogram for an even tonal distribution.",
    params={},
)
def auto_level(img):
    return ImageOps.equalize(img.convert("RGB")), "Auto level"
