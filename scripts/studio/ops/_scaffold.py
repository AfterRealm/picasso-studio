"""Scaffolding decorator for image-in / image-out ops.

The vast majority of ops follow the same shape: look up the session, load
the current image, run a transform, save the result, record it in history,
return `{output_path, note}`. Repeating that scaffolding across 60+ op
functions inflates each op by ~8 lines and means a contract change (e.g.
returning an OpResult dataclass instead of a dict) is a 60-place edit.

`@image_op` collapses all of that. The op author writes only the
transform:

    @image_op(category="transform", label="Resize", description="...",
              params={"width": {"type": "int", "min": 1, "max": 8192},
                      "height": {"type": "int", "min": 1, "max": 8192}})
    def resize(img, *, width, height):
        width = int(clamp(width, 1, MAX_DIMENSION))
        height = int(clamp(height, 1, MAX_DIMENSION))
        return img.resize((width, height), Image.LANCZOS), f"Resize -> {width}x{height}"

The decorator handles:
- session lookup (returns the standard `unknown session` error dict)
- image load via `open_image`
- output path via `step_path`
- save (PNG by default; pass `ext=` for jpg/webp/etc)
- history recording with the canonical params dict
- return envelope (OpResult.to_dict())

Ops that need to return SVG, drive multi-frame WebP/GIF, or otherwise
break the in:Image / out:Image contract continue to use `@register_op`
directly — `@image_op` is the high-level convenience for the majority
case (single-image PNG output).

The leading underscore in the filename keeps this module out of the ops
auto-discovery walk in `ops/__init__.py`.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from ..registry import register_op
from ..sessions import get_session, record_op
from ._helpers import open_image, step_path


@dataclass(frozen=True)
class OpResult:
    """Typed return value from an op.

    Most callers serialize this to a plain dict for the wire (HTTP / MCP),
    but having a typed result protects against silent typos in op author
    code and makes adding fields a single-place change.
    """
    output_path: str
    note: str

    def to_dict(self) -> dict:
        return {"output_path": self.output_path, "note": self.note}


_FORMAT_BY_EXT = {
    "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP",
    "gif": "GIF", "bmp": "BMP", "tif": "TIFF", "tiff": "TIFF",
}


def _format_for_ext(ext: str) -> str:
    return _FORMAT_BY_EXT.get(ext.lower(), "PNG")


def image_op(
    *,
    category: str,
    label: str,
    description: str,
    params: dict[str, Any] | None = None,
    interactive: dict[str, Any] | None = None,
    ext: str = "png",
    save_kwargs: dict[str, Any] | None = None,
) -> Callable:
    """Image-in / image-out scaffolding decorator.

    Wraps an op of signature
        `(img: Image.Image, **params) -> tuple[Image, str] | Image`
    into the full session-aware op signature
        `(session_id, **params) -> dict`
    and registers it with the global OP_REGISTRY via `register_op`.
    """
    save_kwargs_static = dict(save_kwargs or {})
    save_format = save_kwargs_static.pop("format", None) or _format_for_ext(ext)

    def decorate(transform: Callable) -> Callable:
        op_name = transform.__name__
        sig = inspect.signature(transform)
        param_names = [p for p in sig.parameters if p != "img"]

        def runner(session_id: str, **kwargs: Any) -> dict:
            sess = get_session(session_id)
            if sess is None:
                return {"error": f"unknown session: {session_id}"}
            img = open_image(sess.current_image)
            result = transform(img, **kwargs)
            if isinstance(result, tuple):
                out_img, note = result
            else:
                out_img, note = result, label
            out_path = step_path(sess, op_name, ext=ext)
            out_img.save(out_path, save_format, **save_kwargs_static)
            recorded = {k: kwargs[k] for k in param_names if k in kwargs}
            record_op(sess, op_name, recorded, out_path, note=note)
            return OpResult(output_path=str(out_path), note=note).to_dict()

        runner.__name__ = op_name
        runner.__doc__ = transform.__doc__
        runner.__qualname__ = op_name

        return register_op(
            category=category,
            label=label,
            description=description,
            params=params,
            interactive=interactive,
        )(runner)

    return decorate
