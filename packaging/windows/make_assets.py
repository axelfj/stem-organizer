"""Draws the MSIX logo PNGs (placeholder artwork until there is a real icon)."""
import os
import sys

from PIL import Image, ImageDraw

SIZES = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
}
BG = (17, 17, 17, 255)
BARS = [(0.55, (255, 90, 95)), (0.85, (255, 190, 70)), (0.40, (80, 200, 160)),
        (0.70, (90, 150, 255))]


def draw(w, h):
    img = Image.new("RGBA", (w, h), BG)
    d = ImageDraw.Draw(img)
    side = min(w, h)
    pad = side * 0.18
    left = (w - side) / 2 + pad
    usable = side - 2 * pad
    bar_w = usable / (len(BARS) * 1.6)
    for i, (frac, color) in enumerate(BARS):
        x = left + i * bar_w * 1.6 + bar_w * 0.3
        top = pad + usable * (1 - frac)
        d.rounded_rectangle([x, top, x + bar_w, pad + usable], radius=bar_w / 3, fill=color)
    return img


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, (w, h) in SIZES.items():
        draw(w, h).save(os.path.join(out_dir, name))


if __name__ == "__main__":
    main(sys.argv[1])
