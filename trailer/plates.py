"""Build full-frame, colour-graded background plates for the lyric video.

Each plate places one cut-out drawing on a dusk gradient, adds a soft bloom
of the drawing itself, a vignette, and writes a sharp and a defocused
version (for rack-focus transitions). Output: plates/<name>.jpg, <name>_b.jpg

    python3 plates.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

ROOT = Path(__file__).parent
A = ROOT / "assets"
OUT = ROOT / "plates"
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080

# name: sprite, centre x, centre y, height, gradient stops (top → bottom), bloom strength, mirror
PLATES = {
    "fox": ("f_sad", 1300, 660, 960, ["#1c1f3a", "#6a4a6a", "#e59a6a", "#f6cf9a"], .45, False),
    "face": ("m_face_big", 1240, 560, 1180, ["#1a1c36", "#5e4668", "#d98a64", "#f3c894"], .4, False),
    "box": ("box_open", 1180, 600, 1000, ["#140f1c", "#3a2436", "#8a4a3a", "#d9955a"], .6, False),
    "tease": ("m_tease", 700, 560, 1120, ["#1c1f3a", "#6a4a6a", "#e59a6a", "#f6cf9a"], .4, False),
    "flip": ("f_bottle", 1250, 600, 980, ["#1a1d34", "#4a3e62", "#b77a6e", "#e8b48c"], .4, False),
    "front": ("m_front", 960, 600, 1000, ["#0e1426", "#1f2a48", "#3e4a6e", "#6a6e8a"], .25, False),
    "wet": ("m_wet", 1180, 560, 1160, ["#0c1222", "#1c2744", "#34426a", "#58648a"], .25, False),
    "gentle": ("m_gentle", 1220, 560, 1180, ["#2a2340", "#8a5a6a", "#f0a870", "#fbe0ae"], .55, False),
    "happy": ("f_happy", 560, 740, 820, ["#2a2340", "#8a5a6a", "#f0a870", "#fbe0ae"], .5, False),
    "back": ("m_back", 960, 640, 820, ["#1a1c36", "#6a4a6a", "#e59a6a", "#f8d7a4"], .35, False),
}


def gradient(stops):
    cols = [np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float) for c in stops]
    y = np.linspace(0, 1, H)[:, None]
    seg = np.clip(y * (len(cols) - 1), 0, len(cols) - 1 - 1e-6)
    i = seg.astype(int)
    f = seg - i
    img = np.zeros((H, 1, 3))
    for k in range(len(cols) - 1):
        m = (i == k)
        img += m[..., None] * (cols[k] * (1 - f[..., None]) + cols[k + 1] * f[..., None])
    return Image.fromarray(np.repeat(img, W, 1).astype(np.uint8))


def vignette(img, strength=.55):
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    v = 1 - strength * np.clip(d - .45, 0, 1) ** 1.4
    a = np.asarray(img).astype(float) * v[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def build(name, sprite, cx, cy, h, stops, bloom, mirror):
    base = gradient(stops)
    spr = Image.open(A / f"{sprite}.png").convert("RGBA")
    w = round(spr.width * h / spr.height)
    spr = spr.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.5))
    if mirror:
        spr = spr.transpose(Image.FLIP_LEFT_RIGHT)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(spr, (cx - w // 2, cy - h // 2), spr)
    # tint the drawing toward the scene light so it sits in the plate
    tint = Image.new("RGB", (W, H), stops[-1])
    rgb = Image.blend(layer.convert("RGB"), ImageChops.multiply(layer.convert("RGB"), tint), .35)
    comp = base.copy()
    comp.paste(rgb, (0, 0), layer.split()[3])
    # let the drawing dissolve into haze toward the bottom edge (hides crop lines)
    fog = np.clip((np.arange(H) - (H - 260)) / 260, 0, 1) ** 1.5
    fog_mask = Image.fromarray((np.repeat(fog[:, None], W, 1) * 235).astype(np.uint8))
    comp.paste(base, (0, 0), fog_mask)
    # bloom: blurred highlights screened back on
    glow = comp.filter(ImageFilter.GaussianBlur(40))
    glow = ImageEnhance.Brightness(glow).enhance(1.1)
    comp = Image.blend(comp, ImageChops.screen(comp, glow), bloom)
    comp = vignette(comp)
    comp.save(OUT / f"{name}.jpg", quality=92)
    comp.filter(ImageFilter.GaussianBlur(22)).save(OUT / f"{name}_b.jpg", quality=88)


if __name__ == "__main__":
    for name, args in PLATES.items():
        build(name, *args)
        print(name)
