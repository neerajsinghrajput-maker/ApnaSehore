#!/usr/bin/env python3
"""Render an "Every Rupee Leaves a Trail" style vertical video from a scene spec.

Usage:  python render.py spec.json out.mp4 [--preview T1,T2,...]

The spec (JSON) describes the comic sheet, the voiceover, the word-timed
transcript and a list of timed scenes. See SKILL.md for the full format.
Paths inside the spec are resolved relative to the spec file.
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30

# ---------------------------------------------------------------- palette
CREAM = (234, 230, 220)
DARK = (21, 16, 13)
PINK = (244, 92, 136)
INK = (21, 16, 13)          # text on cream
PAPER = (236, 232, 222)     # text on dark
MUTED_L = (122, 112, 104)   # muted text on cream
MUTED_D = (150, 140, 132)   # muted text on dark
RULE_L = (213, 204, 195)
RULE_D = (60, 52, 47)

# ---------------------------------------------------------------- fonts
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/jetbrains-mono",
             os.path.join(os.path.dirname(__file__), "fonts")]
_font_cache = {}


def font(name, size):
    key = (name, size)
    if key not in _font_cache:
        for d in FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                _font_cache[key] = ImageFont.truetype(p, size)
                break
        else:
            _font_cache[key] = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    return _font_cache[key]


HEAD = "InterDisplay-ExtraBold.otf"   # PART 3 / INFORMER / big numbers
BOLD = "Inter-Bold.otf"               # card lines, subtitles
SEMI = "Inter-SemiBold.otf"
MONO = "JetBrainsMono-Regular.ttf"    # kickers, HUD labels
MONOB = "JetBrainsMono-Bold.ttf"      # stamps


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back_out(x):
    x = clamp(x)
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ---------------------------------------------------------------- text helpers
def text_w(f, s, spacing=0):
    if not s:
        return 0
    return f.getlength(s) + spacing * (len(s) - 1)


def draw_text(img, xy, s, f, fill, alpha=1.0, spacing=0, anchor="la"):
    """Draw text with alpha and optional letter spacing. anchor: la / ma (left/middle, ascender)."""
    if alpha <= 0 or not s:
        return
    x, y = xy
    tw = text_w(f, s, spacing)
    if anchor == "ma":
        x -= tw / 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = tuple(fill[:3]) + (int(255 * alpha),)
    if spacing:
        cx = x
        for ch in s:
            d.text((cx, y), ch, font=f, fill=col, anchor="la")
            cx += f.getlength(ch) + spacing
    else:
        d.text((x, y), s, font=f, fill=col, anchor="la")
    img.alpha_composite(layer)


def line_height(f):
    a, d = f.getmetrics()
    return a + d


# ---------------------------------------------------------------- comic panels
def split_panels(path, rows=None, cols=None):
    """Find panels on a comic sheet by scanning for light gutters. Returns PIL crops in reading order."""
    im = Image.open(path).convert("RGB")
    g = np.asarray(im.convert("L")).astype(float)
    light = g > 235

    def runs(profile, n):
        idx = np.where(profile < 0.6)[0]           # content lines
        segs, start = [], idx[0]
        for a, b in zip(idx[:-1], idx[1:]):
            if b != a + 1:
                segs.append((start, a)); start = b
        segs.append((start, idx[-1]))
        segs = [s for s in segs if s[1] - s[0] > n * 0.08]
        return segs

    ys = runs(light.mean(1), g.shape[0])
    xs = runs(light.mean(0), g.shape[1])
    pad = 5  # drop the black panel border
    out = []
    for y0, y1 in ys:
        for x0, x1 in xs:
            out.append(im.crop((x0 + pad, y0 + pad, x1 - pad, y1 - pad)))
    return out


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    r = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    l, t = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((l, t, l + w, t + h))


# ---------------------------------------------------------------- HUD
def draw_hud(img, hud, a=1.0):
    """hud: list of {label, value, accent?} — up to 3 boxes across the top."""
    n = len(hud)
    margin, gap, top, bh = 48, 22, 236, 104
    bw = (W - 2 * margin - gap * (n - 1)) / n
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, box in enumerate(hud):
        x = margin + i * (bw + gap)
        d.rounded_rectangle((x, top, x + bw, top + bh), 16, fill=(12, 10, 9, int(175 * a)))
    img.alpha_composite(layer)
    for i, box in enumerate(hud):
        x = margin + i * (bw + gap)
        draw_text(img, (x + 22, top + 16), box["label"].upper(), font(MONO, 17), (190, 182, 175), a, spacing=3)
        draw_text(img, (x + 22, top + 42), str(box["value"]), font(BOLD, 40),
                  PINK if box.get("accent") else (255, 255, 255), a)


# ---------------------------------------------------------------- subtitles
def chunk_words(words, max_words=5, max_w=W * 0.84):
    """Group word timings into on-screen subtitle lines (karaoke chunks)."""
    f = font(BOLD, 52)
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        txt = " ".join(x["text"] for x in cur)
        end_punct = w["text"][-1:] in ".?!,"
        gap = (nxt["start"] - w["end"]) if nxt else 9
        too_wide = nxt and text_w(f, txt + " " + nxt["text"]) > max_w
        if end_punct or gap > 0.35 or len(cur) >= max_words or too_wide or not nxt:
            chunks.append(cur); cur = []
    out = []
    for i, c in enumerate(chunks):
        end = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else c[-1]["end"] + 0.6
        end = min(end, c[-1]["end"] + 0.9)
        out.append({"words": c, "start": c[0]["start"], "end": end})
    return out


def draw_subtitle(img, chunks, t, y=0.64 * H):
    for c in chunks:
        if c["start"] <= t < c["end"]:
            break
    else:
        return
    f = font(BOLD, 52)
    sp = f.getlength(" ")
    total = sum(f.getlength(w["text"]) for w in c["words"]) + sp * (len(c["words"]) - 1)
    x = (W - total) / 2
    # soft shadow for legibility on busy art
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.text((x, y + 3), " ".join(w["text"] for w in c["words"]), font=f, fill=(0, 0, 0, 200))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    for w in c["words"]:
        spoken = t >= w["start"]
        draw_text(img, (x, y), w["text"], f, (255, 255, 255), 1.0 if spoken else 0.38)
        x += f.getlength(w["text"]) + sp


# ---------------------------------------------------------------- scenes
def render_panel(scene, t, ctx):
    p = ctx["panels"][scene["panel"] - 1]
    dur = scene["end"] - scene["start"]
    k = clamp((t - scene["start"]) / dur)
    z0, z1 = scene.get("zoom", [1.0, 1.10])
    z = z0 + (z1 - z0) * (k * k * (3 - 2 * k))
    base = ctx["panel_cache"].setdefault(scene["panel"], cover(p, W * 2, H * 2))
    cw, ch = base.width / z, base.height / z
    fx, fy = scene.get("focus", [0.5, 0.5])
    l = (base.width - cw) * fx
    tp = (base.height - ch) * fy
    frame = base.resize((W, H), Image.BILINEAR, box=(l, tp, l + cw, tp + ch)).convert("RGBA")
    frame.alpha_composite(ctx["vignette"])
    hud = scene.get("hud", ctx["spec"].get("hud"))
    if hud:
        draw_hud(frame, hud)
    if scene.get("subtitles", True):
        draw_subtitle(frame, ctx["chunks"], t)
    return frame


def el_alpha(el, t):
    at = el.get("at", 0)
    if t < at:
        return 0.0, 0.0
    k = (t - at) / 0.28
    return ease_out(k), (1 - ease_out(k)) * 28


def render_card(scene, t, ctx):
    dark = scene.get("theme", "light") == "dark"
    bg = DARK if dark else CREAM
    fg = PAPER if dark else INK
    muted = MUTED_D if dark else MUTED_L
    rule = RULE_D if dark else RULE_L
    img = Image.new("RGBA", (W, H), bg + (255,))
    y = scene.get("top", 0.21) * H
    if scene.get("kicker"):
        k_at = scene.get("kicker_at", scene["start"])
        a = ease_out((t - k_at) / 0.3) if t >= k_at else 0
        draw_text(img, (W / 2, y), scene["kicker"].upper(), font(MONO, 21), muted, a, spacing=9, anchor="ma")
        y += 66
    for el in scene.get("items", []):
        a, dy = el_alpha(el, t)
        y = draw_item(img, el, y, a, dy, t, fg, muted, rule, dark)
    return img


def count_value(el, t):
    """Animated number: {"count": [from, to], "fmt": "₹{:,}"}"""
    c0, c1 = el["count"]
    k = ease_out((t - el.get("at", 0)) / el.get("count_dur", 1.2))
    v = c0 + (c1 - c0) * k
    if el.get("indian", True):
        return el.get("prefix", "") + indian(int(round(v))) + el.get("suffix", "")
    return el.get("prefix", "") + f"{int(round(v)):,}" + el.get("suffix", "")


def indian(n):
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + s


def draw_item(img, el, y, a, dy, t, fg, muted, rule, dark):
    kind = el.get("kind", "line")
    txt = count_value(el, t) if "count" in el and a > 0 else el.get("text", "")
    color = {"pink": PINK, "muted": muted}.get(el.get("color"), fg)
    cx = W / 2
    if kind == "title":           # PART 3 / KAL — huge two-tone headline
        f = font(HEAD, el.get("size", 196))
        lh = el.get("size", 196) * 0.98
        for i, ln in enumerate(txt.split("\n")):
            col = PINK if (i > 0 and el.get("accent_second", True)) else color
            draw_text(img, (cx, y + dy), ln, f, col, a, spacing=-6, anchor="ma")
            y += lh
        return y + 28
    if kind == "head":            # "Flat?" / "Goa · 5★"
        f = font(HEAD, el.get("size", 112))
        draw_text(img, (cx, y + dy), txt, f, color, a, spacing=-3, anchor="ma")
        return y + el.get("size", 112) * 1.12 + 18
    if kind == "big":             # ₹2,00,000 / ₹5,000 / din
        f = font(HEAD, el.get("size", 120))
        draw_text(img, (cx, y + dy), txt, f, color, a, spacing=-3, anchor="ma")
        return y + el.get("size", 120) * 1.12 + 14
    if kind == "line":            # ₹2 lakh+ jewellery
        f = font(BOLD, el.get("size", 54))
        draw_text(img, (cx, y + dy), txt, f, color, a, spacing=-1, anchor="ma")
        return y + el.get("size", 54) * 1.25 + 10
    if kind == "small":
        f = font(SEMI, el.get("size", 32))
        draw_text(img, (cx, y + dy), txt, f, color if el.get("color") else muted, a, anchor="ma")
        return y + el.get("size", 32) * 1.35 + 8
    if kind == "arrow":
        f = font(BOLD, 40)
        draw_text(img, (cx, y - 4 + dy * 0.5), "↓", f, color, a, anchor="ma")
        return y + 54
    if kind == "stamp":           # pink rotated outlined label
        return draw_stamp(img, el, y, t, txt) if a > 0 else y + 100
    if kind == "meter":           # SUSPICION 40% + bar
        return draw_meter(img, el, y, a, t, fg, muted, rule)
    if kind == "ledger":          # label / value rows with rules
        return draw_ledger_row(img, el, y, a, dy, t, fg, muted, rule)
    if kind == "rows":            # Mummy / Chacha / Driver Raju list
        return draw_rows(img, el, y, t, fg, muted, dark)
    if kind == "buttons":         # CHHUPAO ya UDAO
        return draw_buttons(img, el, y, a, dy, dark)
    if kind == "bars":            # ₹49k bars under a dashed limit line
        return draw_bars(img, el, y, t, fg, muted)
    if kind == "gap":
        return y + el.get("h", 40)
    raise ValueError("unknown item kind: " + kind)


def draw_stamp(img, el, y, t, txt):
    k = (t - el.get("at", 0)) / 0.3
    s = 1.0 + 0.6 * (1 - back_out(k)) if k < 1 else 1.0
    a = ease_out(k * 1.6)
    f = font(MONOB, el.get("size", 34))
    tw = text_w(f, txt, 3)
    pw, ph = tw + 44, el.get("size", 34) + 34
    layer = Image.new("RGBA", (int(pw + 20), int(ph + 20)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((10, 10, 10 + pw, 10 + ph), 8, outline=PINK + (255,), width=4,
                        fill=PINK + (int(255 * el.get("fill", 0.10)),))
    cx = 10 + 22
    for ch in txt:
        d.text((cx, 10 + ph / 2), ch, font=f, fill=PINK + (255,), anchor="lm")
        cx += f.getlength(ch) + 3
    layer = layer.rotate(el.get("rotate", 4), resample=Image.BICUBIC, expand=True)
    if s != 1.0:
        layer = layer.resize((int(layer.width * s), int(layer.height * s)), Image.BICUBIC)
    if a < 1:
        al = layer.getchannel("A").point(lambda v: int(v * a))
        layer.putalpha(al)
    img.alpha_composite(layer, (int(W / 2 - layer.width / 2), int(y + 50 - layer.height / 2)))
    return y + ph + 50


def draw_meter(img, el, y, a, t, fg, muted, rule):
    x0, x1 = 64, W - 64
    v0, v1 = el.get("from", el.get("value", 0)), el.get("value", 0)
    k = ease_out((t - el.get("at", 0) - 0.15) / el.get("dur", 1.0))
    v = v0 + (v1 - v0) * k
    if "y" in el:
        y = el["y"] * H
    draw_text(img, (x0, y), el.get("label", "Suspicion").upper(), font(MONO, 18), muted, a, spacing=4)
    draw_text(img, (x0, y + 28), f"{int(round(v))}%", font(HEAD, 64), PINK, a)
    by = y + 112
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, by, x1, by + 10), 5, fill=rule + (int(255 * a),))
    if v > 0:
        d.rounded_rectangle((x0, by, x0 + (x1 - x0) * v / 100, by + 10), 5, fill=PINK + (int(255 * a),))
    img.alpha_composite(layer)
    return y + 150


def draw_ledger_row(img, el, y, a, dy, t, fg, muted, rule):
    x0, x1 = 48, W - 48
    draw_text(img, (x0, y + dy), el["label"], font(MONO, 22), muted, a, spacing=4)
    is_pct = el.get("meter")
    if is_pct:
        v0, v1 = el.get("from", el["value"]), el["value"]
        k = ease_out((t - el.get("change_at", el.get("at", 0))) / 0.9)
        v = v0 + (v1 - v0) * k
        draw_text(img, (x0, y + 36 + dy), f"{int(round(v))}%", font(HEAD, 74), PINK, a)
        by = y + 136
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((x0, by, x1, by + 12), 6, fill=rule + (int(255 * a),))
        d.rounded_rectangle((x0, by, x0 + (x1 - x0) * v / 100, by + 12), 6, fill=PINK + (int(255 * a),))
        img.alpha_composite(layer)
        return y + 180
    val = el["value"]
    if "change_at" in el and t >= el["change_at"]:
        val = el["new_value"]
    col = PINK if el.get("color") == "pink" else fg
    draw_text(img, (x0, y + 36 + dy), val, font(HEAD, 74), col, a, spacing=-1)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line((x0, y + 140, x1, y + 140), fill=rule + (int(255 * a),), width=2)
    img.alpha_composite(layer)
    return y + 168


def draw_rows(img, el, y, t, fg, muted, dark):
    x0, x1 = 90, W - 90
    for r in el["rows"]:
        a = ease_out((t - r["at"]) / 0.25) if t >= r["at"] else 0
        if a <= 0:
            y += 74; continue
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        box = (36, 30, 26) if dark else (222, 216, 205)
        d.rounded_rectangle((x0, y, x1, y + 62), 10, fill=box + (int(255 * a),))
        img.alpha_composite(layer)
        dim = r.get("dim")
        draw_text(img, (x0 + 26, y + 18), r["text"][0].upper(), font(MONOB, 22), muted, a)
        draw_text(img, (x0 + 70, y + 14), r["text"], font(BOLD, 30), muted if dim else fg, a)
        if r.get("strike"):
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).line((x0 + 64, y + 32, x0 + 80 + font(BOLD, 30).getlength(r["text"]), y + 32),
                                       fill=PINK + (int(255 * a),), width=4)
            img.alpha_composite(layer)
        y += 74
    return y + 10


def draw_buttons(img, el, y, a, dy, dark):
    f = font(HEAD, 34)
    parts = el["buttons"]  # [{"text":"CHHUPAO"}, {"sep":"ya"}, {"text":"UDAO","pink":true}]
    widths = [(f.getlength(p["text"]) + 40) if "text" in p else font(SEMI, 28).getlength(p["sep"]) for p in parts]
    gap = 20
    x = W / 2 - (sum(widths) + gap * (len(parts) - 1)) / 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for p, w in zip(parts, widths):
        if "text" in p:
            fill = PINK if p.get("pink") else ((236, 232, 222) if dark else INK)
            d.rounded_rectangle((x, y + dy, x + w, y + dy + 58), 10, fill=fill + (int(255 * a),))
        x += w + gap
    img.alpha_composite(layer)
    x = W / 2 - (sum(widths) + gap * (len(parts) - 1)) / 2
    for p, w in zip(parts, widths):
        if "text" in p:
            tc = (255, 255, 255) if p.get("pink") else (DARK if dark else CREAM)
            draw_text(img, (x + 20, y + dy + 10), p["text"], f, tc, a)
        else:
            draw_text(img, (x, y + dy + 14), p["sep"], font(SEMI, 28), MUTED_D, a)
        x += w + gap
    return y + 96


def draw_bars(img, el, y, t, fg, muted):
    n, label = el["n"], el.get("label", "₹49k")
    x0, x1 = 64, W - 64
    bw = (x1 - x0 - (n - 1) * 26) / n
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if el.get("limit"):
        for xx in range(int(x0), int(x1), 22):
            d.line((xx, y, xx + 12, y), fill=PINK + (255,), width=3)
    img.alpha_composite(layer)
    if el.get("limit"):
        draw_text(img, (x1 - text_w(font(MONO, 20), el["limit"], 3), y - 34), el["limit"], font(MONO, 20), PINK, 1, spacing=3)
    for i in range(n):
        at = el["at"] + i * el.get("step", 0.35)
        k = ease_out((t - at) / 0.35) if t >= at else 0
        if k <= 0:
            continue
        h = 260 * k
        bx = x0 + i * (bw + 26)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((bx, y + 20 + 260 - h, bx + bw, y + 280), 6, fill=INK + (255,))
        img.alpha_composite(layer)
        draw_text(img, (bx + 10, y + 20 + 260 - h + 12), label, font(BOLD, 22), (255, 255, 255), k)
    return y + 320


RENDERERS = {"panel": render_panel, "card": render_card}


# ---------------------------------------------------------------- main
def load(spec_path):
    base = os.path.dirname(os.path.abspath(spec_path))
    spec = json.load(open(spec_path))
    rp = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    words = json.load(open(rp(spec["words"]))) if spec.get("words") else []
    ctx = {
        "spec": spec,
        "panels": split_panels(rp(spec["sheet"])) if spec.get("sheet") else [],
        "panel_cache": {},
        "chunks": chunk_words(words),
        "audio": rp(spec["audio"]),
    }
    # bottom + top darkening so HUD and subtitles stay legible
    g = np.zeros((H, 1), np.float32)
    yy = np.arange(H) / H
    g[:, 0] = np.clip((yy - 0.55) / 0.45, 0, 1) ** 1.4 * 0.80 + np.clip((0.16 - yy) / 0.16, 0, 1) * 0.35
    v = np.zeros((H, W, 4), np.uint8)
    v[..., 3] = (np.repeat(g, W, 1) * 255).astype(np.uint8)
    ctx["vignette"] = Image.fromarray(v, "RGBA")
    return spec, ctx


def frame_at(spec, ctx, t):
    for sc in spec["scenes"]:
        if sc["start"] <= t < sc["end"]:
            img = RENDERERS[sc["type"]](sc, t, ctx)
            break
    else:
        img = Image.new("RGBA", (W, H), DARK + (255,))
    # global fade in/out
    dur = spec["duration"]
    a = min(clamp(t / 0.25), clamp((dur - t) / 0.4))
    if a < 1:
        img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, a)
    return img.convert("RGB")


def main():
    spec_path, out = sys.argv[1], sys.argv[2]
    spec, ctx = load(spec_path)
    if "--preview" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")]
        frames = [frame_at(spec, ctx, t).resize((W // 3, H // 3), Image.LANCZOS) for t in ts]
        sheet = Image.new("RGB", (W // 3 * len(frames), H // 3))
        for i, f in enumerate(frames):
            sheet.paste(f, (i * W // 3, 0))
        sheet.save(out)
        return
    n = int(round(spec["duration"] * FPS))
    ff = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", ctx["audio"], "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(frame_at(spec, ctx, i / FPS).tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out)


if __name__ == "__main__":
    main()
