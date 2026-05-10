"""Social media presets — IG square/portrait/story, Twitter header, YouTube thumbnail."""
from PIL import Image, ImageOps

from ._scaffold import image_op


def _fit(img, target_w: int, target_h: int, label: str):
    """Crop+resize to exact target dimensions; returns (image, note)."""
    img = img.convert("RGB")
    fitted = ImageOps.fit(img, (target_w, target_h), Image.LANCZOS)
    return fitted, f"{label} ({target_w}x{target_h})"


@image_op(category="social", label="Instagram square (1080x1080)",
          description="Crop and resize to 1080x1080 — Instagram square post.", params={})
def ig_square(img):
    return _fit(img, 1080, 1080, "IG square")


@image_op(category="social", label="Instagram portrait (1080x1350)",
          description="Crop and resize to 1080x1350 — Instagram portrait post.", params={})
def ig_portrait(img):
    return _fit(img, 1080, 1350, "IG portrait")


@image_op(category="social", label="Instagram story (1080x1920)",
          description="Crop and resize to 1080x1920 — Instagram story / vertical.", params={})
def ig_story(img):
    return _fit(img, 1080, 1920, "IG story")


@image_op(category="social", label="Twitter/X header (1500x500)",
          description="Crop and resize to 1500x500 — Twitter / X header banner.", params={})
def twitter_header(img):
    return _fit(img, 1500, 500, "Twitter header")


@image_op(category="social", label="YouTube thumbnail (1280x720)",
          description="Crop and resize to 1280x720 — YouTube thumbnail.", params={})
def yt_thumbnail(img):
    return _fit(img, 1280, 720, "YT thumbnail")
