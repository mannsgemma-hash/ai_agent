"""Render a sample thumbnail so the layout can be eyeballed before wiring
real artwork in.

Generates a placeholder artwork and a placeholder frame (the frame is what you
will replace with your Canva export), then composites them.

    python scripts/demo_thumbnail.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.thumbnails import make_thumbnail  # noqa: E402
from app.thumbnails.spec import ThumbnailSpec  # noqa: E402

OUT = Path("out")
ASSETS = Path("assets")


def placeholder_art(size: int = 2000) -> Image.Image:
    """Stand-in artwork: a soft vertical wash with a few botanical shapes."""
    img = Image.new("RGB", (size, size), "#E8DCCB")
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(size):
        t = y / size
        draw.line(
            [(0, y), (size, y)],
            fill=(
                int(233 + (214 - 233) * t),
                int(221 + (198 - 221) * t),
                int(205 + (211 - 205) * t),
            ),
        )
    for cx, cy, r, col in [
        (700, 780, 330, (196, 148, 142, 120)),
        (1250, 700, 260, (168, 176, 150, 120)),
        (980, 1080, 380, (208, 172, 156, 110)),
    ]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    return img


def placeholder_frame(size: int = 2000) -> Image.Image:
    """Stand-in for your Canva frame export: a border plus a bottom band.

    Replace assets/frame.png with a transparent PNG designed in Canva.
    """
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    # Bottom band the title/subtitle sit on.
    draw.rectangle([0, 1520, size, size], fill=(251, 247, 240, 240))
    # Thin inner keyline.
    draw.rectangle([60, 60, size - 60, 1460], outline=(58, 50, 44, 90), width=6)
    draw.line([(760, 1548), (1240, 1548)], fill=(122, 110, 99, 160), width=4)
    return frame


def main() -> None:
    OUT.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)

    frame_path = ASSETS / "frame.png"
    if not frame_path.exists():
        placeholder_frame().save(frame_path)
        print(f"wrote placeholder {frame_path} (replace with your Canva export)")

    spec_path = Path("thumbnail_spec.json")
    spec = ThumbnailSpec.load(spec_path) if spec_path.exists() else ThumbnailSpec()

    samples = [
        ("Pressed Wildflower Print", "Botanical Collection"),
        ("Vintage Rose Study No. 3", "Heritage Florals"),
        ("Meadow in Bloom — A very long product title that must wrap", "Spring 2026"),
    ]
    art = placeholder_art()
    for i, (title, subtitle) in enumerate(samples, 1):
        img = make_thumbnail(art, title=title, subtitle=subtitle, spec=spec)
        out = OUT / f"sample_{i}.jpg"
        img.save(out, quality=92)
        print(f"wrote {out}  ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
