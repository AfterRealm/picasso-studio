# Compose ops

Composed pieces with text/layout — meme, polaroid, top caption, thought bubble, annotation.

_5 ops in this category._

## `annotate` — Annotate

Add a small caption bar centered near the bottom of the image.

**Params:**
- `text` (str, default `Note`) — Annotation text

## `caption_top` — Caption (top)

Add wrapped meme-style text above the subject on a transparent canvas extension.

**Params:**
- `text` (str, default `Caption`) — Caption text

## `meme` — Meme caption

Classic white-text-with-black-outline meme caption (top and/or bottom).

**Params:**
- `top` (str, default ``) — Top text
- `bottom` (str, default ``) — Bottom text

## `polaroid` — Polaroid

White polaroid frame around the image with optional caption below.

**Params:**
- `caption` (str, default ``) — Optional caption

## `thought_bubble` — Thought bubble

Cartoon thought-bubble overlay with optional text or emoji content.

**Params:**
- `content` (str, default `...`) — Bubble content (text or emoji)
- `position` (str, default `top-right`) — top-right/top-left/bottom-right/bottom-left
- `size_frac` (float [0.15..0.5], default `0.3`) — Bubble width fraction
