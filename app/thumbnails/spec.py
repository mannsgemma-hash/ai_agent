"""Declarative description of a thumbnail layout.

The layout lives in JSON (see `thumbnail_spec.json`) so the design can be tuned
— frame swapped, text moved, font changed — without editing Python.

Coordinates are in pixels on the output canvas, origin top-left.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @classmethod
    def from_list(cls, v: list[int] | tuple[int, int, int, int]) -> "Box":
        return cls(int(v[0]), int(v[1]), int(v[2]), int(v[3]))


@dataclass(frozen=True)
class TextStyle:
    """A block of text auto-fitted into `box`."""

    box: Box
    font_path: str | None = None  # .ttf/.otf; falls back to a bundled default
    size: int = 96  # starting size; shrinks to fit
    min_size: int = 28
    color: str = "#2B2B2B"
    align: Literal["left", "center", "right"] = "center"
    valign: Literal["top", "middle", "bottom"] = "middle"
    line_spacing: float = 1.15
    uppercase: bool = False
    max_lines: int = 3
    # Optional soft shadow for legibility over busy artwork.
    shadow: bool = False
    shadow_color: str = "#00000055"
    shadow_offset: tuple[int, int] = (0, 3)

    @classmethod
    def from_dict(cls, d: dict) -> "TextStyle":
        d = dict(d)
        d["box"] = Box.from_list(d["box"])
        if "shadow_offset" in d:
            d["shadow_offset"] = tuple(d["shadow_offset"])
        return cls(**d)


@dataclass(frozen=True)
class ThumbnailSpec:
    """Full layout: canvas -> artwork -> frame overlay -> text."""

    # Etsy recommends at least 2000px on the shortest side.
    canvas_w: int = 2000
    canvas_h: int = 2000
    background: str = "#FFFFFF"

    # Where the artwork sits. Defaults to the whole canvas.
    art_box: Box | None = None
    # "cover" fills the box and crops the overflow; "contain" fits it whole.
    art_fit: Literal["cover", "contain"] = "cover"

    # Branded frame/border exported from Canva as a transparent PNG, drawn
    # over the artwork. None = no frame.
    frame_path: str | None = None

    title: TextStyle | None = None
    subtitle: TextStyle | None = None

    def resolved_art_box(self) -> Box:
        return self.art_box or Box(0, 0, self.canvas_w, self.canvas_h)

    @classmethod
    def from_dict(cls, d: dict) -> "ThumbnailSpec":
        d = dict(d)
        if d.get("art_box"):
            d["art_box"] = Box.from_list(d["art_box"])
        for key in ("title", "subtitle"):
            if d.get(key):
                d[key] = TextStyle.from_dict(d[key])
        return cls(**d)

    @classmethod
    def load(cls, path: str | Path) -> "ThumbnailSpec":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


DEFAULT_SPEC = ThumbnailSpec()
