"""Draws the app icon (a monitor with an orange calculator in front) into assets/.

    python -I tools/make_icon.py      (needs Pillow; only for whoever changes the icon)

Writes assets/app.ico (16 to 256 px, each size drawn on its own so small ones stay sharp) and
assets/app.png (256 px, the window's icon). 40 px and up are drawn on a 128-unit grid, like the
design canvas. 16, 20, 24 and 32 px (the title bar, the taskbar, Explorer's lists) are laid out
by hand in whole pixels: every edge on the pixel grid (only the rounded corners are blended, so
nothing is fuzzy) and every part at least a pixel inside the tile (at 16-24 px the scaled
calculator ran into the tile's rounded corner and looked cut off).
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "assets")

TILE = (17, 22, 28, 255)       # #11161c
MONITOR = (90, 102, 117, 255)  # #5a6675
CALC = (255, 122, 61, 255)     # #ff7a3d
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
SS = 8                         # Supersampling

# The small sizes in their own pixels: (x0, y0, x1, y1, corner radius) with x1/y1 just past
# the last pixel, and the monitor's line width. The same design as the 128-unit grid below.
SMALL = {
    16: dict(tile=(1, 1, 15, 15, 3), monitor=(2, 3, 11, 10, 0.75), stroke=1,
             calc=(7, 5, 13, 13, 1), screen=None),
    20: dict(tile=(1, 1, 19, 19, 3.5), monitor=(3, 4, 13, 12, 1), stroke=2,
             calc=(9, 7, 16, 17, 1.5), screen=None),
    24: dict(tile=(1, 1, 23, 23, 5), monitor=(3, 4, 16, 14, 1), stroke=2,
             calc=(11, 8, 20, 21, 2), screen=(12, 10, 19, 14, 0.5)),
    32: dict(tile=(1, 1, 31, 31, 7), monitor=(4, 6, 21, 18, 1.5), stroke=2,
             calc=(15, 10, 27, 28, 2.5), screen=(17, 12, 25, 18, 1)),
}


def draw_small(size):
    """A hand-laid small size: drawn 8x on whole pixels, then box-averaged (no ringing)"""
    g = SMALL[size]
    im = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def box(part):
        x0, y0, x1, y1, r = part
        return [x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1], r * SS

    b, r = box(g["tile"])
    d.rounded_rectangle(b, radius=r, fill=TILE)
    b, r = box(g["monitor"])
    d.rounded_rectangle(b, radius=r, outline=MONITOR, width=g["stroke"] * SS)
    b, r = box(g["calc"])
    d.rounded_rectangle(b, radius=r, fill=CALC)
    if g["screen"]:
        b, r = box(g["screen"])
        d.rounded_rectangle(b, radius=r, fill=TILE)  # Its screen
    return im.reduce(SS)


def draw(size):
    if size in SMALL:
        return draw_small(size)
    big = size * SS
    k = big / 128.0
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def box(x, y, w, h):
        return [x * k, y * k, (x + w) * k, (y + h) * k]

    d.rounded_rectangle(box(6, 6, 116, 116), radius=26 * k, fill=TILE)
    stroke = 6 if size >= 48 else 8
    d.rounded_rectangle(box(18, 24, 66, 48), radius=6 * k, outline=MONITOR, width=max(1, round(stroke * k)))
    d.rounded_rectangle(box(60, 42, 48, 70), radius=9 * k, fill=CALC)
    d.rounded_rectangle(box(67, 50, 34, 22), radius=3 * k, fill=TILE)  # Its screen
    if size >= 48:
        for cy in (84, 97):
            for cx in (74, 84, 94):
                r = 3.5 * k
                d.ellipse([cx * k - r, cy * k - r, cx * k + r, cy * k + r], fill=TILE)
    return im.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    images = [draw(s) for s in SIZES]
    images[-1].save(os.path.join(OUT, "app.png"))
    images[-1].save(os.path.join(OUT, "app.ico"), sizes=[(s, s) for s in SIZES],
                    append_images=images[:-1])
    print("wrote", os.path.join(OUT, "app.ico"), "and app.png")


if __name__ == "__main__":
    main()
