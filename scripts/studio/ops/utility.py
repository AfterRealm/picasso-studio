"""Utility ops — convert, compress_jpeg, compress_png, compress_webp, deep_compress_png, strip_metadata, remove_bg."""
import shutil
import subprocess

from PIL import Image

from ..paths import UnsafePathError, assert_within
from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import clamp, open_image, step_path


_CONVERT_EXTS = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "webp": "webp"}


@register_op(
    category="utility",
    label="Convert format",
    description="Convert image to a different format (jpg, png, webp).",
    params={"fmt": {"type": "str", "default": "jpg", "help": "Target format: jpg, png, webp"}},
)
def convert(session_id: str, fmt: str = "jpg") -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    ext = _CONVERT_EXTS.get((fmt or "").lower())
    if ext is None:
        return {"error": f"unsupported fmt: {fmt!r} (expected one of {sorted(_CONVERT_EXTS)})"}
    img = open_image(sess.current_image)
    out_path = step_path(sess, "convert", ext=ext)
    if ext == "jpg":
        img.convert("RGB").save(out_path, "JPEG", quality=92)
    else:
        img.save(out_path, ext.upper())
    note = f"Convert -> {ext}"
    record_op(sess, "convert", {"fmt": fmt}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="utility",
    label="Compress (JPEG)",
    description="Save as JPEG at the given quality (1-100, lossy). Best for photos. Drops alpha.",
    params={"quality": {"type": "int", "default": 70, "min": 1, "max": 100, "help": "JPEG quality"}},
)
def compress_jpeg(session_id: str, quality: int = 70) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    quality = int(clamp(quality, 1, 100))
    img = open_image(sess.current_image).convert("RGB")
    out_path = step_path(sess, "compress_jpeg", ext="jpg")
    img.save(out_path, "JPEG", quality=quality, optimize=True)
    note = f"Compress JPEG -> q={quality}"
    record_op(sess, "compress_jpeg", {"quality": quality}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="utility",
    label="Compress (PNG)",
    description="Save as PNG with zlib compression level (1-9, lossless). Higher = smaller file, slower. Preserves alpha.",
    params={"level": {"type": "int", "default": 9, "min": 0, "max": 9, "help": "zlib compression level (0=none, 9=max)"}},
)
def compress_png(session_id: str, level: int = 9) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    level = int(clamp(level, 0, 9))
    img = open_image(sess.current_image)
    out_path = step_path(sess, "compress_png")
    img.save(out_path, "PNG", optimize=True, compress_level=level)
    note = f"Compress PNG -> level={level}"
    record_op(sess, "compress_png", {"level": level}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="utility",
    label="Compress (WebP)",
    description="Save as WebP. Lossy quality 1-100, or set lossless=true for lossless mode. Preserves alpha.",
    params={
        "quality": {"type": "int", "default": 80, "min": 1, "max": 100, "help": "WebP quality (lossy mode) or effort (lossless mode)"},
        "lossless": {"type": "bool", "default": False, "help": "Use lossless WebP"},
    },
)
def compress_webp(session_id: str, quality: int = 80, lossless: bool = False) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    quality = int(clamp(quality, 1, 100))
    img = open_image(sess.current_image)
    out_path = step_path(sess, "compress_webp", ext="webp")
    img.save(out_path, "WEBP", quality=quality, lossless=bool(lossless), method=6)
    note = f"Compress WebP -> q={quality} lossless={lossless}"
    record_op(sess, "compress_webp", {"quality": quality, "lossless": lossless}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="utility",
    label="Deep Compress (PNG, lossy palette)",
    description="Aggressive PNG shrink via pngquant — lossy palette quantization down to 256 colors. Typically 60-80% smaller than the original. Preserves alpha. Requires pngquant binary (pip install pngquant-cli).",
    params={
        "quality": {"type": "int", "default": 75, "min": 10, "max": 100, "help": "Target quality (pngquant maps to a min/max range around this)"},
        "speed": {"type": "int", "default": 3, "min": 1, "max": 11, "help": "1=slow/best, 11=fast/rough (default 3)"},
    },
)
def deep_compress_png(session_id: str, quality: int = 75, speed: int = 3) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    pngquant = shutil.which("pngquant")
    if not pngquant:
        return {"error": "pngquant not found on PATH. Install with: pip install pngquant-cli"}
    quality = int(clamp(quality, 10, 100))
    speed = int(clamp(speed, 1, 11))
    # pngquant treats 0 as "accept any quality, even garbage" — give it a
    # real floor so output isn't visibly worse than the requested target.
    q_min = max(0, quality - 15)
    q_max = quality
    img = open_image(sess.current_image)
    # Both intermediate + final go inside the session dir; assert_within is a
    # belt-and-suspenders check now that record_op never advances the cursor
    # before this returns.
    out_path = step_path(sess, "deep_compress_png")
    intermediate = out_path.with_name(out_path.stem + "_in.png")
    try:
        assert_within(intermediate, sess.dir)
        assert_within(out_path, sess.dir)
    except UnsafePathError as exc:
        return {"error": str(exc)}
    img.save(intermediate, "PNG")
    result = subprocess.run(
        [pngquant, "--force", "--quality", f"{q_min}-{q_max}", "--speed", str(speed),
         "--strip", "--output", str(out_path), str(intermediate)],
        capture_output=True, text=True, check=False,
    )
    intermediate.unlink(missing_ok=True)
    if result.returncode != 0:
        return {"error": f"pngquant failed (exit {result.returncode}): {result.stderr.strip()}"}
    note = f"Deep compress PNG -> q={q_min}-{q_max} speed={speed}"
    record_op(sess, "deep_compress_png", {"quality": quality, "speed": speed}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="utility",
    label="Strip metadata",
    description="Remove all EXIF / metadata from the image.",
    params={},
)
def strip_metadata(session_id: str) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    # Pillow's convert() doesn't carry EXIF across, and saving without
    # exif=... arg writes none — so the previous "create blank + paste"
    # step was redundant defense.
    img = open_image(sess.current_image).convert("RGB")
    out_path = step_path(sess, "strip_metadata")
    img.save(out_path, "PNG")
    note = "Strip metadata"
    record_op(sess, "strip_metadata", {}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}


@register_op(
    category="utility",
    label="Remove background",
    description="Remove the background from an image (rembg / U2-Net). Returns a transparent PNG.",
    params={},
)
def remove_bg(session_id: str) -> dict:
    sess = get_session(session_id)
    if sess is None:
        return {"error": f"unknown session: {session_id}"}
    from rembg import remove  # type: ignore  # heavy dep, lazy-imported
    with open(sess.current_image, "rb") as fh:
        input_bytes = fh.read()
    output_bytes = remove(input_bytes)
    out_path = step_path(sess, "remove_bg")
    out_path.write_bytes(output_bytes)
    note = "Remove background"
    record_op(sess, "remove_bg", {}, out_path, note=note)
    return {"output_path": str(out_path), "note": note}
