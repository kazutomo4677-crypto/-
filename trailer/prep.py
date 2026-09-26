"""Cut the character-sheet drawings out of their paper background.

Each crop is flood-filled from its border over paper-coloured pixels, so only
the paper connected to the edge is removed; the cream kimono survives because
it is enclosed by line art. Output: assets/<name>.png with alpha.

    python3 prep.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = Path(__file__).parent / "src"
OUT = Path(__file__).parent / "assets"
OUT.mkdir(exist_ok=True)

# name: (source, box (l, t, r, b), paper tolerance, extra seeds)
CROPS = {
    # merchant sheet — expressions row (labels excluded)
    "m_smile": ("merchant_sheet.png", (28, 688, 245, 900), 26),
    "m_tease": ("merchant_sheet.png", (255, 688, 475, 900), 26),
    "m_surprise": ("merchant_sheet.png", (478, 688, 700, 900), 26),
    "m_wet": ("merchant_sheet.png", (705, 688, 930, 900), 26),
    "m_gentle": ("merchant_sheet.png", (930, 688, 1150, 900), 26),
    "m_front": ("merchant_sheet.png", (240, 60, 482, 632), 22),
    "box_open": ("merchant_sheet.png", (1138, 348, 1398, 614), 20),
    "box_closed": ("merchant_sheet.png", (1150, 62, 1398, 342), 20),
    # rough sketch sheet — big faces and back view
    "m_face_big": ("merchant_sketch.jpg", (60, 0, 560, 470), 22),
    "m_wink_big": ("merchant_sketch.jpg", (0, 470, 560, 1232), 22),
    "m_back": ("merchant_sketch.jpg", (560, 0, 928, 1232), 22),
    # fox sheet
    "f_front": ("fox_sheet.png", (100, 170, 450, 548), 22),
    "f_sad": ("fox_sheet.png", (18, 690, 262, 905), 22),
    "f_pout": ("fox_sheet.png", (276, 640, 472, 905), 22),
    "f_surprise": ("fox_sheet.png", (468, 660, 668, 905), 22),
    "f_happy": ("fox_sheet.png", (668, 660, 878, 905), 22),
    "f_bottle": ("fox_sheet.png", (925, 655, 1205, 915), 22),
    "bottle_cloud": ("merchant_sheet.png", (1162, 450, 1236, 580), 0),
    "f_curled": ("fox_sheet.png", (1230, 660, 1525, 910), 22),
}


def cutout(img, tol, enclosed=0):
    rgb = np.asarray(img.convert("RGB")).astype(np.int16)
    h, w, _ = rgb.shape
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    paper = np.median(border, axis=0)
    close = (np.abs(rgb - paper).max(-1) <= tol)
    # flood from every paper-coloured border pixel
    m = Image.fromarray((close * 255).astype(np.uint8)).copy()
    for x in range(0, w, 3):
        for y in (0, h - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128, thresh=0)
    for y in range(0, h, 3):
        for x in (0, w - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128, thresh=0)
    bg = np.asarray(m) == 128
    if enclosed:
        # paper trapped between hair strands: drop paper-coloured islands too
        tight = (np.abs(rgb - paper).max(-1) <= enclosed) & ~bg
        lab = Image.fromarray((tight * 255).astype(np.uint8)).copy()
        arr = np.asarray(lab).copy()
        ys, xs = np.nonzero(arr == 255)
        for y, x in zip(ys, xs):
            if lab.getpixel((int(x), int(y))) != 255:
                continue
            ImageDraw.floodfill(lab, (int(x), int(y)), 100, thresh=0)
            comp = np.asarray(lab) == 100
            if comp.sum() >= 60:
                bg |= comp
            lab.paste(0, mask=Image.fromarray((comp * 255).astype(np.uint8)))
    alpha = Image.fromarray(((~bg) * 255).astype(np.uint8))
    # close pinholes, then soften the edge a touch
    alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out


if __name__ == "__main__":
    cache = {}
    for name, (src, box, tol) in CROPS.items():
        if src not in cache:
            cache[src] = Image.open(SRC / src).convert("RGB")
        crop = cache[src].crop(box)
        enclosed = 10 if name.startswith("m_") else 0
        piece = crop.convert("RGBA") if tol == 0 else cutout(crop, tol, enclosed)
        piece.save(OUT / f"{name}.png")
        print(name, piece.size)
