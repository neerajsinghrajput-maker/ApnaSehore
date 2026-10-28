"""
"Socho Agar?" money-story reel renderer (₹5 Crore Bitcoin series style), driven by plan.json.

Look: comic panels with Ken Burns motion, a live 3-box HUD on top, word-by-word captions
(spoken words white, upcoming words dim), and typographic info cards (cream / dark, pink
accents) that build line by line with the voiceover. 1080x1920, 30 fps, H.264 + AAC.
Sound: voiceover 100 %, synthesised SFX mixed low (see plan["sfx"]). No whoosh by default.

    python3 -I render_reel.py plan.json voice.mp3 words.json panels_dir out.mp4
        [--preview t1 t2 ...]     only write still frames prev_TT.TT.jpg next to out.mp4
        [--remux old.mp4]         sound-only change: rebuild audio, reuse old.mp4's picture

See ../reference/plan_part2.json for a complete, real plan.
"""
import sys, os, json, wave, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import VideoClip, AudioFileClip, CompositeAudioClip
from moviepy.audio.AudioClip import AudioArrayClip

PLAN, VOICE, WORDS, PANELS, OUT = sys.argv[1:6]
PREVIEW = "--preview" in sys.argv
REMUX = sys.argv[sys.argv.index("--remux") + 1] if "--remux" in sys.argv else None
OUTDIR = os.path.dirname(os.path.abspath(OUT))
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts") + "/"

plan = json.load(open(PLAN, encoding="utf-8"))
words = json.load(open(WORDS, encoding="utf-8"))

W, H, FPS, SR = 1080, 1920, 30, 44100
XF = 0.16

COLORS = {"cream": (236, 231, 223), "dark": (27, 24, 23), "ink": (21, 19, 19), "white": (246, 243, 238),
          "pink": (232, 67, 122), "grey": (138, 131, 122), "dim": (170, 163, 155),
          "soft": (190, 183, 175), "mid": (110, 104, 98), "chip": (52, 47, 45), "chiptext": (220, 214, 206)}
CREAM, DARK, INK, WHITE, PINK, GREY = (COLORS[k] for k in ("cream", "dark", "ink", "white", "pink", "grey"))


def col(c):
    return tuple(c) if isinstance(c, (list, tuple)) else COLORS[c]


INTER = {w: [FD + f"inter-latin-{w}-normal.woff", FD + f"inter-latin-ext-{w}-normal.woff",
             FD + "mukta-devanagari-800-normal.woff"] for w in (500, 700, 800, 900)}
MONO = [FD + "jetbrains-mono-latin-500-normal.woff", FD + "inter-latin-ext-700-normal.woff"]

# ----------------------------------------------------------------------------- text helpers
_fcache, _gcache = {}, {}


def font(path, size):
    k = (path, size)
    if k not in _fcache:
        _fcache[k] = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    return _fcache[k]


def has_glyph(path, ch):
    k = (path, ch)
    if k not in _gcache:
        f = font(path, 40)
        a, b = f.getmask(ch), f.getmask("\U0001F600")
        _gcache[k] = ch == " " or not (a.size == b.size and bytes(a) == bytes(b))
    return _gcache[k]


def runs(text, chain):
    out = []
    for ch in text:
        p = next((p for p in chain if has_glyph(p, ch)), chain[0])
        if out and out[-1][1] == p:
            out[-1][0] += ch
        else:
            out.append([ch, p])
    return out


def text_img(text, size, chain, color, spacing=0, shadow=False):
    """Render text with per-character font fallback (Latin, ₹, Devanagari). Returns RGBA."""
    rs = runs(text, chain)
    widths = [font(p, size).getlength(r) + spacing * len(r) for r, p in rs]
    asc = max(font(p, size).getmetrics()[0] for p in [chain[0]] + [p for _, p in rs])
    desc = max(font(p, size).getmetrics()[1] for _, p in rs)
    pad = 24 if shadow else 4
    im = Image.new("RGBA", (int(sum(widths)) + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))

    def draw(layer, dx, dy, fill):
        d = ImageDraw.Draw(layer); x = pad + dx
        for (r, p), w in zip(rs, widths):
            f = font(p, size)
            y = pad + dy + asc - f.getmetrics()[0]
            if spacing:
                for ch in r:
                    d.text((x, y), ch, font=f, fill=fill); x += f.getlength(ch) + spacing
            else:
                d.text((x, y), r, font=f, fill=fill); x += w
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw(sh, 0, 4, (0, 0, 0, 220))
        im = sh.filter(ImageFilter.GaussianBlur(7))
        ol = Image.new("RGBA", im.size, (0, 0, 0, 0))
        for ox, oy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)]:
            draw(ol, ox, oy, (0, 0, 0, 255))
        im.alpha_composite(ol)
    draw(im, 0, 0, color + (255,) if len(color) == 3 else color)
    return im


def fit_width(img, maxw=W - 80):
    if img.width <= maxw:
        return img
    return img.resize((maxw, int(img.height * maxw / img.width)), Image.LANCZOS)


def with_alpha(img, alpha):
    a = np.asarray(img).copy(); a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
    return Image.fromarray(a)


def paste_center(base, img, cx, cy, alpha=1.0, dy=0):
    if alpha <= 0:
        return
    if alpha < 1:
        img = with_alpha(img, alpha)
    base.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2 + dy)))


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------- timeline
voice = AudioFileClip(VOICE)
DUR = round(voice.duration + plan.get("tail", 0.8), 2)
SCENES = sorted(plan["scenes"], key=lambda s: s["t"])
STARTS = [s["t"] for s in SCENES] + [DUR]


def scene_at(t):
    i = 0
    while i + 1 < len(SCENES) and t >= SCENES[i + 1]["t"]:
        i += 1
    return i


panels = {}


def panel(k):
    if k not in panels:
        im = Image.open(os.path.join(PANELS, f"{k:02d}.png")).convert("RGB").resize((H, H), Image.LANCZOS)
        panels[k] = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))
    return panels[k]


# ----------------------------------------------------------------------------- image scenes
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dist = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.72)) ** 2)
VIGN = np.clip(1 - 0.5 * dist ** 2.4, 0.4, 1)[..., None]
CAP_Y = 1190
CAPSHADE = (1 - 0.35 * np.exp(-((yy - CAP_Y) / 260) ** 2))[..., None]
IMG_SHADE = (VIGN * CAPSHADE).astype(np.float32)
_padded = {}


def padded(k, zmin):
    """panel centred on a blurred, darkened copy of itself, big enough to zoom out to zmin"""
    key = (k, zmin)
    if key not in _padded:
        big = int(H / zmin) + 8
        bg = panel(k).resize((big, big), Image.BILINEAR).filter(ImageFilter.GaussianBlur(45))
        bg = Image.eval(bg, lambda v: int(v * 0.45))
        bg.paste(panel(k), ((big - H) // 2, (big - H) // 2))
        _padded[key] = bg
    return _padded[key]


def ken_burns(sc, lt, dur):
    """sc: {"panel": n, "from": [x, y], "to": [x, y], "zoom": [z0, z1]}
    x, y = normalised centre in the square panel; zoom 1 = full panel height (crops the sides),
    zoom < 1 = whole panel visible with a blurred fill around it (use ~0.6 for text-heavy panels)."""
    (x1, y1), (x2, y2) = sc.get("from", [0.5, 0.5]), sc.get("to", sc.get("from", [0.5, 0.5]))
    z0, z1 = sc.get("zoom", [1.0, 1.06])
    e = ease(lt / dur)
    z = (z0 + (z1 - z0) * e) * (1 + 0.03 * (1 - ease(lt / 0.35)))     # small punch on the cut
    cx, cy = x1 + (x2 - x1) * e, y1 + (y2 - y1) * e
    img, off = panel(sc["panel"]), 0
    if min(z0, z1) < 1:
        img = padded(sc["panel"], round(min(z0, z1) * 0.97, 3))
        off = (img.width - H) / 2
    S = img.width; vh = H / z; vw = vh * W / H
    x0 = min(max(cx * H + off - vw / 2, 0), S - vw)
    y0 = min(max(cy * H + off - vh / 2, 0), S - vh)
    s = vh / H
    return img.transform((W, H), Image.AFFINE, (s, 0, x0, 0, s, y0), resample=Image.BICUBIC)


# HUD -------------------------------------------------------------------------
def inr(n):
    s = str(int(n))
    if len(s) <= 3:
        return "₹" + s
    head, tail, parts = s[:-3], s[-3:], []
    while len(head) > 2:
        parts.insert(0, head[-2:]); head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts) + "," + tail


def lerp_steps(t, steps):
    """steps: [[time, value], ...]; numbers count up/down over the 0.6 s before each time"""
    v = steps[0][1]
    for (ta, va), (tb, vb) in zip(steps, steps[1:]):
        if t >= tb:
            v = vb
        elif t > tb - 0.6 and isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            v = va + (vb - va) * ease((t - (tb - 0.6)) / 0.6)
    return v


HUD = plan.get("hud", [])
_hud_cache = {}


def hud(t):
    vals = []
    for box in HUD:
        v = lerp_steps(t, box["steps"])
        if isinstance(v, str):
            vals.append(v)
        elif box.get("type") == "pct":
            vals.append(int(round(v)))
        else:
            vals.append(int(round(v / 10000) * 10000))
    key = tuple(vals)
    if key in _hud_cache:
        return _hud_cache[key]
    lay = Image.new("RGBA", (W, 230), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    widths = [b.get("width", 300) for b in HUD]
    x = (W - sum(widths) - 16 * (len(HUD) - 1)) // 2
    for box, v, bw in zip(HUD, vals, widths):
        if isinstance(v, str):
            txt, c = v, PINK
        elif box.get("type") == "pct":
            txt, c = f"{v}%", PINK if v >= 40 else WHITE
        else:
            txt, c = inr(v), WHITE
        d.rounded_rectangle((x, 90, x + bw, 196), 18, fill=(18, 16, 16, 205))
        lay.alpha_composite(text_img(box["label"].upper(), 22, MONO, (150, 143, 135), spacing=3), (x + 18, 98))
        lay.alpha_composite(fit_width(text_img(txt, 40, INTER[800], c), bw - 24), (x + 16, 128))
        if box.get("type") == "pct" and not isinstance(v, str):
            d.rounded_rectangle((x + 20, 182, x + bw - 20, 187), 3, fill=(70, 64, 62, 255))
            d.rounded_rectangle((x + 20, 182, x + 20 + int((bw - 40) * min(v, 100) / 100), 187), 3, fill=PINK + (255,))
        x += bw + 16
    _hud_cache[key] = lay
    return lay


# captions --------------------------------------------------------------------
def build_chunks():
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if w["w"][-1] in ".,?!—" or len(cur) >= 4:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        e = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else DUR
        out.append((c[0]["s"], min(e, c[-1]["e"] + 0.6), c))
    return out


CHUNKS = build_chunks()
_cap_cache = {}


def caption(t):
    ch = next((c for c in CHUNKS if c[0] - 0.05 <= t < c[1]), None)
    if not ch:
        return None
    s, e, ws = ch
    n = sum(1 for w in ws if t >= w["s"] - 0.04)
    key = (s, n)
    if key not in _cap_cache:
        imgs = [text_img(w["w"].rstrip("—").replace("...", "…"), 66, INTER[800],
                         WHITE + (255,) if i < n else (246, 243, 238, 105), shadow=True)
                for i, w in enumerate(ws)]
        gap = -26
        lay = Image.new("RGBA", (sum(im.width for im in imgs) + gap * (len(imgs) - 1),
                                 max(im.height for im in imgs)), (0, 0, 0, 0))
        x = 0
        for im in imgs:
            lay.alpha_composite(im, (x, 0)); x += im.width + gap
        _cap_cache[key] = fit_width(lay, W - 60)
    return _cap_cache[key]


def render_img_scene(i, t):
    sc = SCENES[i]
    dur = STARTS[i + 1] - sc["t"] + XF
    fr = np.asarray(ken_burns(sc, t - sc["t"], dur)).astype(np.float32) * IMG_SHADE
    im = Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).convert("RGBA")
    if HUD and sc.get("hud", True):
        im.alpha_composite(hud(t), (0, 0))
    if sc.get("captions", True):
        cap = caption(t)
        if cap is not None:
            im.alpha_composite(cap, ((W - cap.width) // 2, CAP_Y - cap.height // 2))
    return im


# ----------------------------------------------------------------------------- cards
def T(txt, size, c, w=800):
    return fit_width(text_img(txt, size, INTER[w], col(c)))


def stamp(txt, angle=-6):
    t = text_img(txt, 44, INTER[900], PINK, spacing=2)
    box = Image.new("RGBA", (t.width + 36, t.height + 18), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((3, 3, box.width - 4, box.height - 4), 10, outline=PINK + (255,), width=5)
    box.alpha_composite(t, (18, 9))
    return box.rotate(angle, resample=Image.BICUBIC, expand=True)


def pill(txt, bg, fg, size=46):
    t = text_img(txt, size, INTER[900], col(fg))
    box = Image.new("RGBA", (t.width + 56, t.height + 26), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, box.height - 1), 14, fill=col(bg) + (255,))
    box.alpha_composite(t, (28, 13))
    return box


def build_element(el, dark):
    """turns one plan element into (image, centre x or None)"""
    kind = el["type"]
    if kind == "label":
        return text_img(el["text"].upper(), 24, MONO, (120, 113, 106) if dark else GREY, spacing=5), None
    if kind == "small":
        return text_img(el["text"], 30, MONO, (150, 143, 135) if dark else GREY, spacing=2), None
    if kind == "arrow":
        return T("↓", 56, (120, 113, 106) if dark else GREY, 700), None
    if kind == "text":
        return T(el["text"], el.get("size", 72), el.get("color", "white" if dark else "ink"), el.get("weight", 800)), None
    if kind == "stamp":
        return stamp(el["text"], el.get("angle", -6)), None
    if kind == "pill":
        return pill(el["text"], el.get("bg", "pink"), el.get("fg", "white"), el.get("size", 46)), None
    if kind == "choice":   # two options: "A  ya  B" — first cream, second pink
        a, b = el["options"]
        size = el.get("size", 44)
        p1, p2 = pill(a, "cream", "ink", size), pill(b, "pink", "white", size)
        ya = T(el.get("joiner", "ya"), int(size * 0.85), "dim", 700)
        row = Image.new("RGBA", (p1.width + p2.width + ya.width + 48, max(p1.height, p2.height)), (0, 0, 0, 0))
        row.alpha_composite(p1, (0, 0))
        row.alpha_composite(ya, (p1.width + 24, (row.height - ya.height) // 2))
        row.alpha_composite(p2, (p1.width + ya.width + 48, 0))
        return fit_width(row), None
    if kind == "row":      # "where you stand" table row: small label + big value (+ optional bar)
        row = Image.new("RGBA", (880, 170), (0, 0, 0, 0))
        dd = ImageDraw.Draw(row)
        row.alpha_composite(text_img(el["label"], 26, MONO, GREY, spacing=1), (0, 6))
        row.alpha_composite(fit_width(text_img(el["value"], 76, INTER[900], col(el.get("color", "ink"))), 860), (0, 46))
        dd.line((0, 165, 880, 165), fill=(205, 198, 188, 255) if not dark else (70, 64, 62, 255), width=3)
        if "bar" in el:
            dd.rounded_rectangle((250, 92, 880, 108), 8, fill=(214, 207, 197, 255) if not dark else (70, 64, 62, 255))
            dd.rounded_rectangle((250, 92, 250 + int(630 * el["bar"]), 108), 8, fill=PINK + (255,))
        return row, None
    raise ValueError(f"unknown card element type: {kind}")


def build_cards():
    cards = {}
    for name, card in plan.get("cards", {}).items():
        dark = card.get("bg", "dark") == "dark"
        els = []
        for el in card["els"]:
            if el["type"] == "tiles":   # n money tiles appearing one after another (e.g. 5 x ₹80k)
                n, stagger = el.get("n", 5), el.get("stagger", 0.16)
                step = min(170, (W - 120) // n)
                x0 = W / 2 - step * (n - 1) / 2
                for k in range(n):
                    tile = Image.new("RGBA", (step - 20, 260), (0, 0, 0, 0))
                    ImageDraw.Draw(tile).rounded_rectangle((0, 0, step - 21, 259), 14, fill=(48, 43, 41, 255) if dark else (214, 207, 197, 255))
                    tl = fit_width(text_img(el["text"], 34, INTER[800], WHITE if dark else INK), step - 30)
                    tile.alpha_composite(tl, ((step - 20 - tl.width) // 2, 24))
                    ImageDraw.Draw(tile).rounded_rectangle((20, 90, step - 41, 238), 10, fill=PINK + (255,))
                    els.append((el["t"] + stagger * k, tile, el["y"], x0 + step * k))
                continue
            img, cx = build_element(el, dark)
            els.append((el["t"], img, el["y"], el.get("x", cx)))
        cards[name] = (col(card.get("bg", "dark")), els)
    return cards


CARDS = build_cards()
_bg = {}


def render_card(i, t):
    sc = SCENES[i]
    bg, els = CARDS[sc["card"]]
    if bg not in _bg:
        _bg[bg] = Image.new("RGBA", (W, H), bg + (255,))
    im = _bg[bg].copy()
    for t0, img, cy, cx in els:
        a = ease((t - t0) / 0.28)
        if a > 0:
            paste_center(im, img, cx if cx is not None else W / 2, cy, a, (1 - a) * 22)
    s = 1 / (1 + 0.025 * ease((t - sc["t"]) / max(STARTS[i + 1] - sc["t"], 0.1)))   # slow push-in
    return im.transform((W, H), Image.AFFINE, (s, 0, W * (1 - s) / 2, 0, s, H * (1 - s) / 2),
                        resample=Image.BILINEAR)


# ----------------------------------------------------------------------------- frames
rng = np.random.default_rng(11)
GRAIN = [rng.normal(0, 4.5, (H, W, 1)).astype(np.float32) for _ in range(4)]


def render_scene(i, t):
    return render_card(i, t) if "card" in SCENES[i] else render_img_scene(i, t)


def make_frame(t):
    i = scene_at(t)
    fr = np.asarray(render_scene(i, t).convert("RGB")).astype(np.float32)
    if i > 0 and t - SCENES[i]["t"] < XF:
        a = ease((t - SCENES[i]["t"]) / XF)
        fr = fr * a + np.asarray(render_scene(i - 1, t).convert("RGB")).astype(np.float32) * (1 - a)
    fr += GRAIN[int(t * FPS) % 4]
    if t < 0.25:
        fr *= t / 0.25
    if t > DUR - 0.5:
        fr *= max(DUR - t, 0) / 0.5
    return np.clip(fr, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------- sound design
def norm(x, peak=0.9):
    return x / (np.abs(x).max() + 1e-9) * peak


def whoosh(length=0.7):
    n = int(SR * length); t = np.linspace(0, 1, n); noise = rng.normal(0, 1, n)
    out = np.zeros(n); y1 = y2 = 0.0
    for k in range(n):                       # band-pass sweep over white noise
        w0 = 2 * np.pi * (300 + 3500 * np.sin(np.pi * t[k]) ** 2) / SR
        al = np.sin(w0) / 4.0
        y = (al * noise[k] + 2 * np.cos(w0) * y1 - (1 - al) * y2) / (1 + al)
        y2, y1 = y1, y; out[k] = y
    return norm(out * np.sin(np.pi * t) ** 1.5 * np.exp(-1.2 * t))


def pop(length=0.12):
    n = int(SR * length); t = np.arange(n) / SR
    return norm(np.sin(2 * np.pi * np.cumsum(900 * np.exp(-t * 35) + 180) / SR) * np.exp(-t * 40), 0.8)


def boom(length=1.6):
    n = int(SR * length); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t * 1.5) + 38) / SR) * np.exp(-t * 2.6)
    return norm(body + rng.normal(0, 1, n) * np.exp(-t * 60) * 0.5)


def chime(length=0.5):
    n = int(SR * length); t = np.arange(n) / SR
    a = np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 9)
    b = np.sin(2 * np.pi * 1760 * t) * np.exp(-np.clip(t - 0.08, 0, None) * 9) * (t > 0.08)
    return norm(a + b, 0.7)


def thud(length=0.35):
    n = int(SR * length); t = np.arange(n) / SR
    return norm(np.sin(2 * np.pi * np.cumsum(110 * np.exp(-t * 8) + 55) / SR) * np.exp(-t * 14), 0.8)


def tick(length=0.03):
    n = int(SR * length); t = np.arange(n) / SR
    x = np.convolve(rng.normal(0, 1, n) * np.exp(-t * 300), np.ones(4) / 4, mode="same")
    return norm(x + 0.5 * np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 250), 0.6)


def alert(length=0.5):
    n = int(SR * length); t = np.arange(n) / SR
    gate = ((t < 0.09) | ((t > 0.17) & (t < 0.26))).astype(float)
    return norm(np.sin(2 * np.pi * 880 * t) * gate * np.exp(-t * 2), 0.6)


SFX = plan.get("sfx", {})
SOUNDS = {"pop": pop(), "boom": boom(), "chime": chime(), "thud": thud(), "tick": tick(), "alert": alert()}
if SFX.get("cut") == "whoosh":
    SOUNDS["whoosh"] = whoosh()
track = np.zeros(int(SR * (DUR + 2)))


def place(name, at, gain=1.0):
    sig = SOUNDS[name]
    if name == "whoosh":
        at -= 0.33                      # so the whoosh peaks on the cut
    i = max(int(at * SR), 0); j = min(i + len(sig), len(track))
    track[i:j] += sig[: j - i] * gain


if SFX.get("intro_boom", 0.5):
    place("boom", 0.0, SFX.get("intro_boom", 0.5))
img_ranges = [(SCENES[i]["t"], STARTS[i + 1]) for i in range(len(SCENES)) if "card" not in SCENES[i]]
for sc in SCENES[1:]:
    if SFX.get("cut", "thud"):
        place(SFX.get("cut", "thud"), sc["t"], SFX.get("cut_gain", 0.5))         # every cut
    if "card" in sc and SFX.get("card_pop", 0.35):
        for t0, *_ in CARDS[sc["card"]][1]:
            if t0 > sc["t"] + 0.05:
                place("pop", t0, SFX.get("card_pop", 0.35))                       # every card line
if SFX.get("caption_tick", 0.35):
    for s, e, ws in CHUNKS:
        if any(a <= s < b for a, b in img_ranges):
            place("tick", s, SFX.get("caption_tick", 0.35))                       # every caption change
for acc in SFX.get("accents", []):
    place(acc["sound"], acc["t"], acc.get("gain", 0.6))
track = np.clip(track, -1, 1) * SFX.get("volume", 0.18)

# ----------------------------------------------------------------------------- render
if PREVIEW:
    for t in [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:] if not x.startswith("--")]:
        Image.fromarray(make_frame(t)).save(os.path.join(OUTDIR, f"prev_{t:05.2f}.jpg"), quality=85)
    sys.exit()

sfx = AudioArrayClip(np.stack([track, track], 1)[: int(SR * DUR)], fps=SR)
audio = CompositeAudioClip([voice.with_volume_scaled(1.0), sfx]).with_duration(DUR)
if REMUX:
    mix = os.path.join(OUTDIR, "mix.m4a")
    audio.write_audiofile(mix, fps=SR, codec="aac", bitrate="192k", logger=None)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", REMUX, "-i", mix, "-map", "0:v", "-map", "1:a",
                    "-c", "copy", "-movflags", "+faststart", OUT], check=True)
    print("done", OUT); sys.exit()

video = VideoClip(make_frame, duration=DUR).with_audio(audio)
video.write_videofile(OUT, fps=FPS, codec="libx264", audio_codec="aac", audio_bitrate="192k",
                      preset="slow", ffmpeg_params=["-crf", "22", "-maxrate", "9M", "-bufsize", "18M",
                                                    "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
                      threads=4, logger=None)
print("done", OUT)
