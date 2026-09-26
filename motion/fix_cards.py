"""Repaint the malformed playing cards in the key illustration.

The generated art has a spade/club hybrid on the front card and a garbled
index on the back card. This redraws both faces (A♠ in front, A♥ behind) in
the card's own skewed frame, and masks the geisha's fingers so they stay on
top. Coordinates below are in "zoom space": the crop (90,460)-(290,720) of
the 896x1344 original, scaled 4x.

    python3 fix_cards.py <in.jpg> <out.jpg> [cinzel900.ttf]
"""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC, DST = sys.argv[1], sys.argv[2]
FONT = sys.argv[3] if len(sys.argv) > 3 else "fonts/cinzel900.ttf"

CROP = (90, 460, 290, 720)
Z = 4
ZW, ZH = (CROP[2] - CROP[0]) * Z, (CROP[3] - CROP[1]) * Z
SS = 2  # supersampling of the card-local drawing

CREAM = (238, 227, 205)
RED = (200, 22, 18)
INK = (16, 15, 20)

# card frames: top-left corner, "u" = along the top edge, "v" = down the side
RIGHT = dict(tl=(295, 160), u=(315, -63), v=(87, 583))
LEFT = dict(tl=(92, 196), u=(315, -96), v=(174, 540))

# fingers overlapping the cards (kept from the original art)
HAND = [(336, 572), (350, 556), (362, 550), (415, 552), (485, 555), (530, 572), (560, 597), (600, 637),
        (650, 683), (690, 728), (760, 860), (760, 1040), (250, 1040), (280, 700), (287, 684),
        (350, 652), (352, 600), (343, 575)]


def suit_poly(kind, cx, cy, w):
    """Polygon for a heart or spade of width w centred on (cx, cy)."""
    pts = []
    for i in range(240):
        t = 2 * math.pi * i / 240
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x, y))
    s = w / 34
    if kind == "heart":
        return [(cx + x * s, cy + (y + 2) * s) for x, y in pts]
    # spade = heart flipped vertically
    return [(cx + x * s, cy - (y + 2) * s - 2 * s) for x, y in pts]


def draw_suit(d, kind, cx, cy, w, color):
    d.polygon(suit_poly(kind, cx, cy, w), fill=color)
    if kind == "spade":
        # flared stem
        s = w / 34
        d.polygon([(cx - 1.2 * s, cy + 6 * s), (cx + 1.2 * s, cy + 6 * s),
                   (cx + 7 * s, cy + 19 * s), (cx - 7 * s, cy + 19 * s)], fill=color)


def card_face(w, h, rank, suit, color, font_path, cream=CREAM):
    """Draw a card face in local (unskewed) space; returns (rgb, alpha)."""
    W, H = int(w * SS), int(h * SS)
    face = Image.new("RGB", (W, H), cream)
    alpha = Image.new("L", (W, H), 0)
    inset, rad = 7 * SS, 28 * SS
    ImageDraw.Draw(alpha).rounded_rectangle([inset, inset, W - inset, H - inset], rad, fill=255)
    d = ImageDraw.Draw(face)
    font = ImageFont.truetype(font_path, int(W * 0.2))

    def index(flip):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        x0, y0 = W * 0.14, H * 0.045
        ld.text((x0, y0), rank, font=font, fill=color, anchor="mt")
        draw_suit(ld, suit, x0, y0 + W * 0.29, W * 0.15, color)
        return layer.rotate(180) if flip else layer

    face.paste(index(False), (0, 0), index(False))
    face.paste(index(True), (0, 0), index(True))
    big = W * 0.5
    draw_suit(d, suit, W / 2, H * 0.44, big, color)
    # faint paper grain so the flat fill sits in the illustration
    arr = np.asarray(face).astype(np.float32)
    arr += np.random.default_rng(5).normal(0, 1.6, arr.shape[:2])[..., None]
    face = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return face, alpha


def to_zoom(img, card, mode, cream=CREAM):
    """Warp a local-space image into zoom space with the card's affine frame."""
    (tx, ty), (ux, uy), (vx, vy) = card["tl"], card["u"], card["v"]
    lw, lh = img.size
    # zoom = tl + (lx/lw)*u + (ly/lh)*v  → invert for PIL (zoom → local)
    a, b, c, d = ux / lw, vx / lh, uy / lw, vy / lh
    det = a * d - b * c
    ia, ib, ic, idd = d / det, -b / det, -c / det, a / det
    coeffs = (ia, ib, -(ia * tx + ib * ty), ic, idd, -(ic * tx + idd * ty))
    return img.transform((ZW, ZH), Image.AFFINE, coeffs,
                         resample=Image.BICUBIC, fillcolor=0 if mode == "L" else cream)


def card_len(card):
    return math.hypot(*card["u"]), math.hypot(*card["v"])


src = Image.open(SRC).convert("RGB")
crop = src.crop(CROP)
zoom_src = crop.resize((ZW, ZH), Image.LANCZOS)


def bool_img(a):
    return Image.fromarray((a * 255).astype(np.uint8)).copy()


def arr(im):
    return np.asarray(im) > 127


def grow(a, px):
    return arr(bool_img(a).filter(ImageFilter.MaxFilter(px * 2 + 1)))


def quad(card, inset=0.0):
    (tx, ty), (ux, uy), (vx, vy) = card["tl"], card["u"], card["v"]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    iu, iv = inset / lu, inset / lv
    pts = [(iu, iv), (1 - iu, iv), (1 - iu, 1 - iv), (iu, 1 - iv)]
    m = Image.new("L", (ZW, ZH), 0)
    ImageDraw.Draw(m).polygon([(tx + a * ux + b * vx, ty + a * uy + b * vy) for a, b in pts], fill=255)
    return arr(m)


def flood(light, seeds):
    """Pixels of `light` connected to any seed."""
    img = bool_img(light)
    for sx, sy in seeds:
        if img.getpixel((sx, sy)) == 255:
            ImageDraw.floodfill(img, (sx, sy), 128, thresh=0)
    return np.asarray(img) == 128


def fill_holes(region):
    inv = bool_img(~region)
    ImageDraw.floodfill(inv, (0, 0), 128, thresh=0)
    return region | (np.asarray(inv) == 255)


# light paper pixels, bounded by the dark card outlines
lum = np.asarray(zoom_src.convert("L")).astype(np.float32)
light = lum > 150
hand = Image.new("L", (ZW, ZH), 0)
ImageDraw.Draw(hand).polygon(HAND, fill=255)
hand = grow(arr(hand), 1)

front_flood = flood(light, [(450, 150), (650, 400), (400, 620), (620, 520), (560, 250)]) & quad(RIGHT, 2)
front_inner = fill_holes(front_flood) | quad(RIGHT, 14)
front_region = front_inner & ~hand
front_with_outline = grow(front_inner | quad(RIGHT, 6), 14)

back_flood = flood(light, [(180, 300), (250, 500), (300, 650), (200, 260)]) & quad(LEFT, -6) & ~quad(RIGHT, -3)
back_region = (fill_holes(back_flood) | quad(LEFT, 12)) & ~front_with_outline & ~hand & quad(LEFT, -4)

# card paper colour, sampled from the original
paper = np.median(np.asarray(zoom_src)[front_flood & (lum > 200)], axis=0)
CREAM_S = tuple(int(c) for c in paper)

zoom = zoom_src.copy()
mask = np.zeros((ZH, ZW), np.float32)
for card, rank, suit, color, region in [(LEFT, "A", "heart", RED, back_region), (RIGHT, "A", "spade", INK, front_region)]:
    w, h = card_len(card)
    face, _ = card_face(w, h, rank, suit, color, FONT, CREAM_S)
    warped = to_zoom(face, card, "RGB", CREAM_S)
    soft = bool_img(region).filter(ImageFilter.GaussianBlur(1.2))
    zoom.paste(warped, (0, 0), soft)

# stray red from the old back-card pip, trapped against the front card's edge
zs = np.asarray(zoom_src).astype(np.int16)
# the card outlines are dark and neutral; the old pips are saturated red
dark_src = (lum < 110) & (zs[..., 0] - zs[..., 1] < 40)
reddish = (zs[..., 0] - zs[..., 1] > 25) & quad(LEFT, -8) & ~quad(RIGHT, 4) & ~hand & ~back_region
reddish = grow(reddish, 3) & ~dark_src & ~hand & ~quad(RIGHT, 4) & ~back_region
# remnant of the old bottom-right index, just inside the front card's right edge
yy, xx = np.mgrid[0:ZH, 0:ZW]
box = (xx >= 658) & (xx <= 684) & (yy >= 538) & (yy <= 602)
leftover = box & (np.asarray(zoom.convert("L")) < 150) & quad(RIGHT, 1)
reddish |= grow(leftover, 1) & quad(RIGHT, 1) & box
za = np.asarray(zoom).copy()
za[reddish] = CREAM_S
zoom = Image.fromarray(za)

# The old red pip sat right on the front card's left edge, so that stretch
# of outline is broken. Fit the edge from the clean outline pixels and
# re-stroke it.
(tx, ty), _, (vx, vy) = RIGHT["tl"], RIGHT["u"], RIGHT["v"]
pts = []
for y in range(170, 552):
    x_edge = tx + (y - ty) * vx / vy
    lo, hi = int(x_edge - 14), int(x_edge + 8)
    row = dark_src[y, lo:hi]
    if row.any():
        pts.append((y, lo + np.flatnonzero(row).mean()))
ys, xs = np.array(pts).T
k, b0 = np.polyfit(ys, xs, 1)
outline_col = (38, 36, 40)
# leftovers hugging that edge: old index ink just inside, pink fringe just outside
edge_x = k * yy + b0
zc = np.asarray(zoom).astype(np.int16)
band_in = (xx > edge_x + 4) & (xx < edge_x + 18) & (yy > 170) & (yy < 552) & (zc.sum(-1) < 450)
band_out = (xx > edge_x - 16) & (xx < edge_x - 3) & (yy > 170) & (yy < 552) & (zc[..., 0] - zc[..., 1] > 12)
junk = (band_in | band_out) & ~hand
za = np.asarray(zoom).copy()
za[grow(junk, 1) & ~hand & (np.abs(xx - edge_x) > 3)] = CREAM_S
zoom = Image.fromarray(za)
reddish |= junk
stroke = Image.new("L", (ZW, ZH), 0)
ImageDraw.Draw(stroke).line([(k * 175 + b0, 175), (k * 552 + b0, 552)], fill=255, width=6)
stroke = stroke.filter(ImageFilter.GaussianBlur(0.8))
stroke = Image.fromarray(np.minimum(np.asarray(stroke), np.asarray(bool_img(~hand))))
zoom.paste(Image.new("RGB", (ZW, ZH), outline_col), (0, 0), stroke)
reddish |= np.asarray(stroke) > 0

fixed = zoom.resize(crop.size, Image.LANCZOS)
changed = bool_img(front_region | back_region | reddish).filter(ImageFilter.MaxFilter(9)).resize(crop.size, Image.LANCZOS)
out_crop = crop.copy()
out_crop.paste(fixed, (0, 0), changed)
src.paste(out_crop, CROP[:2])
src.save(DST, quality=95, subsampling=0)
print("wrote", DST, "paper", CREAM_S)
