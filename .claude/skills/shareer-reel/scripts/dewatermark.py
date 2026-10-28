"""Remove the semi-transparent 4-point-star watermark Gemini puts in the bottom-right corner.

Step 1, find it:   python3 -I dewatermark.py panel.png --inspect corner.png
                   (writes a 3x zoom of the bottom-right corner with pixel ticks; read it and note
                    the star centre x, y and its radius = centre-to-tip distance, in panel pixels)
Step 2, remove it: python3 -I dewatermark.py panel.png --star CX CY R [--out fixed.png]

The star is white blended at a constant alpha, so the original pixels are recovered exactly by
undoing the blend; only the anti-aliased rim is inpainted. Alpha is estimated automatically.
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("panel")
ap.add_argument("--inspect")
ap.add_argument("--star", nargs=3, type=float, metavar=("CX", "CY", "R"))
ap.add_argument("--out")
a = ap.parse_args()

im = Image.open(a.panel).convert("RGB")
W, H = im.size

if a.inspect:
    box = 180
    c = im.crop((W - box, H - box, W, H)).resize((box * 3, box * 3), Image.NEAREST)
    d = ImageDraw.Draw(c)
    for v in range(0, box, 10):
        X = v * 3
        d.line([(X, 0), (X, 8)], fill="yellow"); d.line([(0, X), (8, X)], fill="cyan")
        if v % 30 == 0:
            d.text((X + 2, 10), str(W - box + v), fill="yellow")
            d.text((10, X - 5), str(H - box + v), fill="cyan")
    c.save(a.inspect)
    print("inspect image:", a.inspect, "(labels are panel pixel coordinates)")
    raise SystemExit

cx, cy, r = a.star
px = np.asarray(im).astype(float)


def coverage(cx, cy, r, ss=4):
    Y, X = np.mgrid[0:H * ss, 0:W * ss]
    X = (X + .5) / ss - .5; Y = (Y + .5) / ss - .5
    s = ((np.abs(X - cx) / r) ** (2 / 3) + (np.abs(Y - cy) / r) ** (2 / 3) <= 1).astype(float)
    return s.reshape(H, ss, W, ss).mean((1, 3))


# estimate alpha: the right value makes pixels just inside the star edge match those just outside
th = np.linspace(0, 2 * np.pi, 720, endpoint=False)
ux, uy = np.sign(np.cos(th)) * np.abs(np.cos(th)) ** 3, np.sign(np.sin(th)) * np.abs(np.sin(th)) ** 3


def sample(scale):
    x = np.clip(np.round(cx + r * scale * ux).astype(int), 0, W - 1)
    y = np.clip(np.round(cy + r * scale * uy).astype(int), 0, H - 1)
    return px[y, x]


keep = (np.abs(ux) > 0.08) & (np.abs(uy) > 0.08)          # skip the thin tips
inside, outside = sample(0.82)[keep], sample(1.22)[keep]
best = min(np.arange(0.25, 0.751, 0.01),
           key=lambda al: np.median(np.abs((inside - al * 255) / (1 - al) - outside)))
alpha = float(best)
print(f"alpha ≈ {alpha:.2f}")


def diffuse(img, mask, iters):
    out = img.copy(); out[mask] = 0
    for _ in range(iters):
        avg = (np.roll(out, 1, 0) + np.roll(out, -1, 0) + np.roll(out, 1, 1) + np.roll(out, -1, 1)) / 4
        out[mask] = avg[mask]
    return out


cov = coverage(cx, cy, r)[..., None] * alpha
out = (px - cov * 255) / (1 - cov)
rim_cov = coverage(cx, cy, r + 1.5)
cb = np.asarray(Image.fromarray((rim_cov * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6))).astype(float) / 255
rim = (cb > 0.01) & (cb < 0.99) & ~(coverage(cx, cy, r - 2.5) > 0.5)
out = diffuse(out, rim, 400)
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(a.out or a.panel)
print("saved", a.out or a.panel)
