"""Cut a comic/storyboard grid image into its panels.

Finds the gutters automatically (white or dark, uniform rows/columns), then writes
panels as NN.png starting at --start.

    python3 -I crop_grid.py grid.png out_dir [--rows 3 --cols 3 --start 1]
"""
import argparse, os
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("out_dir")
ap.add_argument("--rows", type=int, default=3)
ap.add_argument("--cols", type=int, default=3)
ap.add_argument("--start", type=int, default=1)
ap.add_argument("--inset", type=int, default=4, help="extra pixels trimmed inside each panel")
a = ap.parse_args()

im = Image.open(a.image).convert("RGB")
g = np.asarray(im.convert("L")).astype(float)


def runs(mask):
    out, s = [], None
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        if not v and s is not None:
            out.append((s, i)); s = None
    if s is not None:
        out.append((s, len(mask)))
    return out


def gutters(axis, n_panels):
    """columns (axis=0) or rows (axis=1) that are uniform: gutter or panel border"""
    mean, std = g.mean(axis), g.std(axis)
    uniform = (std < 6) & ((mean > 225) | (mean < 45))     # gutters are flat; dark artwork is not
    rs = runs(uniform)
    size = g.shape[1] if axis == 0 else g.shape[0]
    # merge runs that are close together (gutter + border lines)
    merged = []
    for r in rs:
        if merged and r[0] - merged[-1][1] < 12:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    # keep edges plus the n-1 runs closest to the expected inner gutter positions
    edges = [r for r in merged if r[0] == 0 or r[1] == size]
    inner = [r for r in merged if r not in edges]
    cuts = []
    for k in range(1, n_panels):
        exp = size * k / n_panels
        if inner:
            best = min(inner, key=lambda r: abs((r[0] + r[1]) / 2 - exp))
            if abs((best[0] + best[1]) / 2 - exp) < size * 0.06:
                cuts.append(best); continue
        cuts.append((int(exp) - 1, int(exp) + 1))
    lo = next((r[1] for r in edges if r[0] == 0), 0)
    hi = next((r[0] for r in edges if r[1] == size), size)
    bounds, prev = [], lo
    for c in cuts:
        bounds.append((prev, c[0])); prev = c[1]
    bounds.append((prev, hi))
    return bounds


xs = gutters(0, a.cols)
ys = gutters(1, a.rows)


def trim(x0, y0, x1, y1, limit=16):
    """drop the panel's own border lines: rows/columns at its edges that are almost all pure
    black ink or pure white (one anti-aliased line in between is allowed)"""
    def border(line):
        return (line < 40).mean() > 0.9 or (line > 225).mean() > 0.9

    def edge(get, n):
        k = 0
        while k < limit and (border(get(k)) or (k < 3 and (border(get(k + 1)) or border(get(k + 2))))):
            k += 1
        return k
    l = edge(lambda k: g[y0:y1, x0 + k], 0)
    r = edge(lambda k: g[y0:y1, x1 - 1 - k], 0)
    t = edge(lambda k: g[y0 + k, x0:x1], 0)
    b = edge(lambda k: g[y1 - 1 - k, x0:x1], 0)
    return l, t, r, b


os.makedirs(a.out_dir, exist_ok=True)
boxes = [(x0, y0, x1, y1) for y0, y1 in ys for x0, x1 in xs]
# border thickness is the same for every panel; the median keeps dark artwork intact
trims = [trim(*bx) for bx in boxes]
tl, tt, tr, tb = (sorted(v)[len(v) // 2] for v in zip(*trims))   # median: ignores odd panels
print(f"border trimmed: left {tl}, top {tt}, right {tr}, bottom {tb} px   (per panel: {trims})")
for k, (x0, y0, x1, y1) in enumerate(boxes, a.start):
    x0, y0, x1, y1 = x0 + tl, y0 + tt, x1 - tr, y1 - tb
    p = im.crop((x0 + a.inset, y0 + a.inset, x1 - a.inset, y1 - a.inset))
    p.save(os.path.join(a.out_dir, f"{k:02d}.png"))
    print(f"{k:02d}.png  x {x0}-{x1}  y {y0}-{y1}  size {p.size}")
