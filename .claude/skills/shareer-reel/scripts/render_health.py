"""
"शरीर की बात" Hindi health-fact reel renderer, driven by plan.json.

Look: one semi-realistic illustration per scene with slow Ken Burns motion, a bold Teko headline
at the top-left (small cream line + big red/orange line that slides up), vignette, film grain,
folded-paper crease and punch-hole dots, 0.3 s crossfades. 1080x1920, 30 fps, H.264 + AAC.
Audio: voiceover peak-normalised, plus a very soft background (user's music if given, otherwise
a synthesised ambient pad).

    python3 -I render_health.py plan.json voice.mp3 panels_dir out.mp4 [--music track.mp3]
        [--preview t1 t2 ...]      only write still frames prev_TT.T.jpg next to out.mp4

See ../reference/plan_andhera.json for a complete, real plan.
"""
import sys, os, json, re, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PLAN, VOICE, PANELS, OUT = sys.argv[1:5]
PREVIEW = "--preview" in sys.argv
MUSIC = sys.argv[sys.argv.index("--music") + 1] if "--music" in sys.argv else None
OUTDIR = os.path.dirname(os.path.abspath(OUT))
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts") + "/"
FONT = FD + "teko-devanagari-700-normal.woff"
FONT_LATIN = FD + "teko-latin-700-normal.woff"
LATIN_CHARS = set("?-!.,:%0123456789")

plan = json.load(open(PLAN, encoding="utf-8"))
W, H, FPS = 1080, 1920, 30
XFADE = 0.3
CREAM, RED, ORANGE = (237, 228, 211), (229, 72, 59), (240, 162, 58)
ACCENT = {"red": RED, "orange": ORANGE}


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return float(out.strip())


VO_DUR = probe_duration(VOICE)
END = round(VO_DUR + plan.get("tail", 1.2), 2)
SCENES = sorted(plan["scenes"], key=lambda s: s["t"])
for i, sc in enumerate(SCENES):
    sc.setdefault("panel", i + 1)
starts = [s["t"] for s in SCENES] + [END]
N = len(SCENES)


def font(sz, path=FONT):
    return ImageFont.truetype(path, sz, layout_engine=ImageFont.Layout.RAQM)


def runs(txt):
    # punctuation and digits are missing from the Devanagari subset: draw them with the Latin font
    out = []
    for ch in txt:
        latin = ch in LATIN_CHARS
        if out and out[-1][1] == latin:
            out[-1][0] += ch
        else:
            out.append([ch, latin])
    return out


def text_width(txt, f):
    fl = font(f.size, FONT_LATIN)
    return sum((fl if latin else f).getlength(r) for r, latin in runs(txt))


def render_line(txt, f, col):
    fl = font(f.size, FONT_LATIN)
    b = f.getbbox("अ")[3]
    pad = 40
    size = (int(text_width(txt, f)) + pad * 2, int(b * 1.4) + pad * 2)

    def draw(layer, dx, dy, fill):
        d = ImageDraw.Draw(layer)
        x = pad + dx
        for r, latin in runs(txt):
            ff = fl if latin else f
            d.text((x, pad + dy), r, font=ff, fill=fill)
            x += ff.getlength(r)

    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    draw(sh, 4, 6, (0, 0, 0, 190))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    draw(sh, 0, 0, col + (255,))
    return sh


def text_layer(small, big, accent):
    """[(RGBA layer, x, y, delay)] for the headline lines"""
    layers, x, y = [], 74, 250
    if small:
        layers.append((render_line(small, font(84), CREAM), x, y, 0.0))
        y += 92
    sz = 168
    while text_width(big, font(sz)) > W - 2 * x and sz > 90:
        sz -= 4
    layers.append((render_line(big, font(sz), accent), x, y - 10, 0.12 if small else 0.0))
    return layers


def cover(img):
    sc = max(W / img.width, H / img.height)
    im = img.resize((round(img.width * sc), round(img.height * sc)), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x0, y0, x0 + W, y0 + H))


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def motion(kind, p):
    """zoom, centre-x, centre-y (normalised) for progress p in [0,1]"""
    e = ease(p)
    return {
        "in": (1.0 + 0.10 * e, 0.5, 0.5),
        "out": (1.10 - 0.10 * e, 0.5, 0.5),
        "in_low": (1.02 + 0.10 * e, 0.5, 0.5 + 0.06 * e),
        "in_tl": (1.10 + 0.06 * e, 0.47, 0.47),      # keeps the bottom-right corner out of frame
        "up": (1.10, 0.5, 0.54 - 0.08 * e),
        "down": (1.10, 0.5, 0.46 + 0.08 * e),
        "pan_r": (1.12, 0.46 + 0.08 * e, 0.5),
        "pan_l": (1.12, 0.54 - 0.08 * e, 0.5),
    }.get(kind, (1.0, 0.5, 0.5))


def frame_image(base, kind, p):
    z, cx, cy = motion(kind, p)
    vw, vh = W / z, H / z
    x0 = min(max(cx * W - vw / 2, 0), W - vw)
    y0 = min(max(cy * H - vh / 2, 0), H - vh)
    s = 1 / z
    return base.transform((W, H), Image.AFFINE, (s, 0, x0, 0, s, y0), resample=Image.BICUBIC)


# ---------- static overlays ----------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.70)) ** 2)
vign = np.clip(1 - 0.55 * d ** 2.2, 0.35, 1)[..., None]
topg = np.clip(1 - 0.50 * np.clip(1 - yy / (H * 0.36), 0, 1) ** 1.6, 0, 1)[..., None]   # text readability
shade = (vign * topg).astype(np.float32)
paper = np.zeros((H, W), np.float32)
cx1 = W * 0.52
paper += 10 * np.exp(-((xx - cx1) / 2.0) ** 2)
paper -= 9 * np.exp(-((xx - cx1 - 14) / 14.0) ** 2)
cx2 = W * 0.06
paper += 5 * np.exp(-((xx - cx2) / 1.5) ** 2)
paper -= 5 * np.exp(-((xx - cx2 - 8) / 8.0) ** 2)
paper = paper[..., None]
dots = Image.new("L", (W, H), 0)
dd = ImageDraw.Draw(dots)
for i in range(1, 10):
    y = int(H * (0.1 * i)) - 30
    dd.ellipse((30, y, 44, y + 14), fill=150)
dots = np.asarray(dots.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)[..., None] / 255
dot_col = np.array([25, 18, 16], np.float32)
rng = np.random.default_rng(7)
grains = [rng.normal(0, 7, (H, W, 1)).astype(np.float32) for _ in range(4)]
mott = Image.fromarray((rng.random((H // 24, W // 24)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
mott = (np.asarray(mott).astype(np.float32)[..., None] / 255 - 0.5) * 10

bases, texts = [], []
for sc in SCENES:
    bases.append(cover(Image.open(os.path.join(PANELS, f"{sc['panel']:02d}.png")).convert("RGB")))
    texts.append(text_layer(sc.get("small", ""), sc["big"], ACCENT.get(sc.get("accent", "orange"), ORANGE)))


def render_scene(i, t_abs):
    st, en = starts[i], starts[i + 1]
    p = min(max((t_abs - st) / (en - st + XFADE), 0), 1)
    im = frame_image(bases[i], SCENES[i].get("motion", "in"), p).convert("RGBA")
    lt = t_abs - st
    for layer, x, y, delay in texts[i]:
        a = min(max((lt - 0.15 - delay) / 0.35, 0), 1)
        if a <= 0:
            continue
        a = ease(a)
        lay = layer
        if a < 1:
            arr = np.asarray(layer).copy(); arr[..., 3] = (arr[..., 3] * a).astype(np.uint8)
            lay = Image.fromarray(arr)
        im.alpha_composite(lay, (x - 40, y - 40 + int(26 * (1 - a))))
    return np.asarray(im.convert("RGB")).astype(np.float32)


def scene_at(t):
    i = 0
    while i + 1 < N and t >= starts[i + 1]:
        i += 1
    return i


def make_frame(fi):
    t = fi / FPS
    i = scene_at(t)
    fr = render_scene(i, t)
    if i > 0 and t - starts[i] < XFADE:
        a = ease((t - starts[i]) / XFADE)
        fr = fr * a + render_scene(i - 1, t) * (1 - a)
    fr = fr * shade + paper + mott + grains[fi % 4]
    fr = fr * (1 - dots * 0.8) + dot_col * dots * 0.8
    if t < 0.25:
        fr *= t / 0.25
    if t > END - 0.7:
        fr *= max(END - t, 0) / 0.7
    return np.clip(fr, 0, 255).astype(np.uint8)


if PREVIEW:
    for t in [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:] if not x.startswith("--")]:
        Image.fromarray(make_frame(int(t * FPS))).save(os.path.join(OUTDIR, f"prev_{t:04.1f}.jpg"), quality=88)
    sys.exit()

# ---------- audio ----------
tmp_a = os.path.join(OUTDIR, "_audio_mix.m4a")
log = subprocess.run(["ffmpeg", "-hide_banner", "-i", VOICE, "-af", "volumedetect", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
peak = float(re.search(r"max_volume: ([-0-9.]+) dB", log).group(1))
gain = min(-1.5 - peak, 12)                                           # peak-normalise the voice
if MUSIC:
    bg_in = ["-stream_loop", "-1", "-i", MUSIC]
    bg_chain = f"[1:a]aresample=44100,atrim=0:{END},afade=t=in:d=1.5,afade=t=out:st={END - 3}:d=3,volume=0.12[m]"
else:
    pad = ("0.20*sin(2*PI*110*t)*(0.7+0.3*sin(2*PI*0.11*t))+0.14*sin(2*PI*164.81*t)*(0.7+0.3*sin(2*PI*0.07*t+1))"
           "+0.12*sin(2*PI*220.6*t)*(0.6+0.4*sin(2*PI*0.09*t+2))+0.08*sin(2*PI*261.63*t)*(0.5+0.5*sin(2*PI*0.05*t+3))"
           "+0.06*sin(2*PI*329.2*t)*(0.5+0.5*sin(2*PI*0.13*t))")
    bg_in = ["-f", "lavfi", "-i", f"aevalsrc='{pad}':s=44100:d={END}"]
    bg_chain = (f"[1:a]lowpass=f=900,aecho=0.8:0.7:120|340:0.3|0.2,afade=t=in:d=2.5,"
                f"afade=t=out:st={END - 3}:d=3,volume=0.17[m]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", VOICE, *bg_in, "-filter_complex",
                f"[0:a]aresample=44100,apad=whole_dur={END},volume={gain:.1f}dB,alimiter=limit=0.89:level=false[v];"
                f"{bg_chain};[v][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "[a]", "-ac", "2", "-c:a", "aac", "-b:a", "192k", tmp_a], check=True)

# ---------- video ----------
total = int(END * FPS)
ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-i", tmp_a, "-map", "0:v", "-map", "1:a",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-maxrate", "9M", "-bufsize", "18M",
                       "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", OUT],
                      stdin=subprocess.PIPE)
for fi in range(total):
    ff.stdin.write(make_frame(fi).tobytes())
    if fi % 300 == 0:
        print(f"{fi}/{total}", flush=True)
ff.stdin.close()
ff.wait()
os.remove(tmp_a)
print("done", OUT)
