"""Prepare the promo assets: a mascot cut-out and the bot QR image.

The mascot art ships on a dark navy backdrop. We matte it out with a
flood-fill from the corners (so dark details *inside* the cat, like the eyes,
stay opaque) and rebuild the warm glow in the renderer.

Run once, or whenever the source art changes::

    python promo/prepare_assets.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC_MASCOT = ROOT / "Avatars" / "photo_2026-10-21_19-09-38.jpg"
SRC_QR = ROOT / "presentation" / "assets" / "bot_qr.png"
ASSETS = Path(__file__).resolve().parent / "assets"


def cut_out(source: Image.Image, threshold: int = 200) -> Image.Image:
    """Return RGBA art with the navy backdrop removed (flood fill from corners).

    The backdrop glow ramps smoothly from navy to orange, but the red channel
    steps sharply at the cat's silhouette (about 140 -> 250), so red is a much
    cleaner key than luminance.
    """
    rgb = np.asarray(source.convert("RGB"), dtype=np.int32)
    solid = Image.fromarray(((rgb[:, :, 0] >= threshold) * 255).astype(np.uint8), "L").copy()

    # Anything connected to the border is backdrop; enclosed dark pixels stay.
    for corner in (
        (0, 0),
        (solid.width - 1, 0),
        (0, solid.height - 1),
        (solid.width - 1, solid.height - 1),
    ):
        if solid.getpixel(corner) == 0:
            ImageDraw.floodfill(solid, corner, 128, thresh=0)

    alpha = solid.point(lambda v: 0 if v == 128 else 255)
    alpha = alpha.filter(ImageFilter.MinFilter(3))  # shave the keyed fringe
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.3))

    art = source.convert("RGBA")
    art.putalpha(alpha)
    return art


def trim(art: Image.Image, padding: int = 8) -> Image.Image:
    box = art.getbbox()
    if box:
        x0, y0, x1, y1 = box
        art = art.crop(
            (
                max(0, x0 - padding),
                max(0, y0 - padding),
                min(art.width, x1 + padding),
                min(art.height, y1 + padding),
            )
        )
    side = max(art.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return canvas


def build_mascot() -> Path:
    source = Image.open(SRC_MASCOT).convert("RGB")
    art = trim(cut_out(source))
    target = ASSETS / "mascot.png"
    art.save(target)
    print(f"mascot: {target} {art.size}")
    return target


def build_qr() -> Path:
    qr = Image.open(SRC_QR).convert("RGB")
    target = ASSETS / "qr.png"
    qr.save(target)
    print(f"qr: {target} {qr.size}")
    return target


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_mascot()
    build_qr()


if __name__ == "__main__":
    main()
