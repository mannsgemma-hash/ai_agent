"""Pillow thumbnail compositor.

Stamps out Etsy listing thumbnails from three inputs:
  1. the artwork          (per listing)
  2. a branded frame PNG  (designed once in Canva, exported with transparency)
  3. title text           (per listing)

This is the automated backend for the pluggable `make_thumbnail()` step in
PLAN.md — the Canva design is reused for every image at no per-image cost.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.thumbnails.spec import Box, TextStyle, ThumbnailSpec

# Reasonable serif/sans fallbacks if the spec doesn't name a font file.
_FONT_FALLBACKS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
)

ImageSource = str | Path | bytes | Image.Image


def _load_image(src: ImageSource) -> Image.Image:
    if isinstance(src, Image.Image):
        return src.copy()
    if isinstance(src, bytes):
        return Image.open(io.BytesIO(src))
    return Image.open(src)


def _load_font(path: str | None, size: int) -> ImageFont.FreeTypeFont:
    candidates = ([path] if path else []) + list(_FONT_FALLBACKS)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    # Last resort: PIL's bitmap default (ignores `size`, but never crashes).
    return ImageFont.load_default()


def _fit_art(art: Image.Image, box: Box, mode: str) -> Image.Image:
    """Scale `art` to `box`, cropping the overflow ("cover") or letterboxing
    it whole ("contain")."""
    art = art.convert("RGBA")
    scale = (
        max(box.w / art.width, box.h / art.height)
        if mode == "cover"
        else min(box.w / art.width, box.h / art.height)
    )
    new_size = (max(1, round(art.width * scale)), max(1, round(art.height * scale)))
    art = art.resize(new_size, Image.LANCZOS)

    if mode == "cover":  # centre-crop to the box
        left = (art.width - box.w) // 2
        top = (art.height - box.h) // 2
        art = art.crop((left, top, left + box.w, top + box.h))
    return art


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Greedy word wrap. A word longer than the line is left to overflow
    rather than being broken mid-word."""
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _line_height(font: ImageFont.FreeTypeFont, spacing: float) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * spacing)


def _draw_text(canvas: Image.Image, text: str, style: TextStyle) -> None:
    """Auto-shrink `text` until it fits `style.box`, then draw it."""
    if not text:
        return
    draw = ImageDraw.Draw(canvas)
    if style.uppercase:
        text = text.upper()

    box = style.box
    font = _load_font(style.font_path, style.size)
    lines: list[str] = []

    for size in range(style.size, style.min_size - 1, -2):
        font = _load_font(style.font_path, size)
        lines = _wrap(text, font, box.w, draw)
        too_tall = len(lines) * _line_height(font, style.line_spacing) > box.h
        if len(lines) <= style.max_lines and not too_tall:
            break
    else:
        # Never fitted — keep the smallest size and trim to max_lines.
        if len(lines) > style.max_lines:
            lines = lines[: style.max_lines]
            lines[-1] = lines[-1].rstrip(" ,.") + "…"

    lh = _line_height(font, style.line_spacing)
    block_h = len(lines) * lh
    if style.valign == "top":
        y = box.y
    elif style.valign == "bottom":
        y = box.bottom - block_h
    else:
        y = box.y + (box.h - block_h) // 2

    for line in lines:
        w = draw.textlength(line, font=font)
        if style.align == "left":
            x = box.x
        elif style.align == "right":
            x = box.right - w
        else:
            x = box.x + (box.w - w) / 2

        if style.shadow:
            dx, dy = style.shadow_offset
            draw.text((x + dx, y + dy), line, font=font, fill=style.shadow_color)
        draw.text((x, y), line, font=font, fill=style.color)
        y += lh


def make_thumbnail(
    art: ImageSource,
    title: str = "",
    subtitle: str = "",
    spec: ThumbnailSpec | None = None,
) -> Image.Image:
    """Compose one thumbnail: artwork -> branded frame -> text.

    Returns an RGB image ready to upload to Etsy.
    """
    spec = spec or ThumbnailSpec()
    canvas = Image.new("RGBA", (spec.canvas_w, spec.canvas_h), spec.background)

    art_box = spec.resolved_art_box()
    fitted = _fit_art(_load_image(art), art_box, spec.art_fit)
    # "contain" may be smaller than the box — centre it.
    offset = (
        art_box.x + (art_box.w - fitted.width) // 2,
        art_box.y + (art_box.h - fitted.height) // 2,
    )
    canvas.paste(fitted, offset, fitted)

    if spec.frame_path and Path(spec.frame_path).exists():
        frame = _load_image(spec.frame_path).convert("RGBA")
        if frame.size != canvas.size:
            frame = frame.resize(canvas.size, Image.LANCZOS)
        canvas = Image.alpha_composite(canvas, frame)

    if spec.title:
        _draw_text(canvas, title, spec.title)
    if spec.subtitle:
        _draw_text(canvas, subtitle, spec.subtitle)

    return canvas.convert("RGB")


def to_bytes(image: Image.Image, fmt: str = "JPEG", quality: int = 92) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt, quality=quality, optimize=True)
    return buf.getvalue()
