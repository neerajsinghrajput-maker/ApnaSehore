"""Rough forced alignment (no speech model needed).

Fits the script's phrases onto the voiceover's speech segments (found with ffmpeg silencedetect),
then spreads the words inside each segment by their estimated spoken length.

    python3 -I align.py voice.mp3 script.txt words.json

Prints one line per segment ("start-end  phrase") — read it to check that every phrase landed
on a sensible stretch of audio. Output: [{"w": word, "s": start, "e": end}, ...]
"""
import json, re, subprocess, sys

VOICE, SCRIPT_FILE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SCRIPT = " ".join(open(SCRIPT_FILE, encoding="utf-8").read().split())

# words whose spelling is far from how they sound (extend when a new script needs it)
SPOKEN = {"TDS": "tee dee es", "P2P": "pee too pee", "UPI": "yoo pee aai", "KYC": "kay vaai see",
          "IP": "aai pee", "PAN": "pain", "iPhone": "aai phone", "BP": "bee pee"}


def spoken_len(word):
    core = re.sub(r"[.,?!…—।]+$", "", word).rstrip(".")
    if core in SPOKEN:
        n = len(SPOKEN[core])
    elif re.search(r"\d", core):
        digits = re.sub(r"\D", "", core)
        n = 5 + 3 * len(digits)                      # "chaar", "assi hazaar" ...
        n += 7 if "₹" in core else 0                 # "rupaye"
        n += 7 if "%" in core else 0                 # "percent"
    elif re.fullmatch(r"[A-Z]{2,4}", core):
        n = 3 * len(core)                           # spelled-out acronym
    else:
        n = len(core)
    return n + 2.5                                   # small per-word overhead


# words with phrase-break flags
words = SCRIPT.replace("—", "— ").replace("...", "... ").split()
phrases, cur = [], []
for w in words:
    cur.append(w)
    if re.search(r"(\.\.\.|[.,?!—।…])$", w):
        phrases.append(cur); cur = []
if cur:
    phrases.append(cur)

log = subprocess.run(["ffmpeg", "-hide_banner", "-i", VOICE, "-af", "silencedetect=n=-35dB:d=0.18",
                      "-f", "null", "-"], capture_output=True, text=True).stderr
ss = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
se = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
dur = float(re.search(r"Duration: (\d+):(\d+):([0-9.]+)", log).group(3)) + 60 * int(
    re.search(r"Duration: (\d+):(\d+)", log).group(2))
segs, t0 = [], 0.0
for a, b in zip(ss, se):
    if a - t0 > 0.05:
        segs.append((t0, a))
    t0 = b
if dur - t0 > 0.1:
    segs.append((t0, dur))

plen = [sum(spoken_len(w) for w in p) for p in phrases]
rate = sum(plen) / sum(b - a for a, b in segs)          # chars per second
P, S = len(phrases), len(segs)
print("phrases", P, "segments", S, "rate", round(rate, 2))

# DP: split phrases into S contiguous groups (a group may also span several segments
# when there are more segments than phrases: allow a phrase group to cover k segments)
INF = 1e18
best = [[INF] * (S + 1) for _ in range(P + 1)]
back = [[None] * (S + 1) for _ in range(P + 1)]
best[0][0] = 0
pre = [0]
for l in plen:
    pre.append(pre[-1] + l)
for i in range(P + 1):
    for j in range(S + 1):
        if best[i][j] >= INF:
            continue
        for i2 in range(i + 1, min(P, i + 6) + 1):
            for j2 in range(j + 1, min(S, j + 4) + 1):
                if i2 - i > 1 and j2 - j > 1:
                    continue      # many-to-many is not allowed
                d = segs[j2 - 1][1] - segs[j][0]
                exp = (pre[i2] - pre[i]) / rate
                c = best[i][j] + (exp - d) ** 2 / max(d, 0.5)
                if c < best[i2][j2]:
                    best[i2][j2] = c; back[i2][j2] = (i, j)
i, j = P, S
groups = []
while i > 0:
    pi, pj = back[i][j]
    groups.append((pi, i, pj, j)); i, j = pi, pj
groups.reverse()

out = []
for (a, b, sa, sb) in groups:
    ws = [w for p in phrases[a:b] for w in p]
    # speech time inside these segments (skip the inner silences)
    spans = segs[sa:sb]
    total = sum(e - s for s, e in spans)
    lens = [spoken_len(w) for w in ws]
    L = sum(lens)

    def at(frac):
        x = frac * total
        for s, e in spans:
            if x <= e - s:
                return s + x
            x -= e - s
        return spans[-1][1]
    acc = 0
    for w, l in zip(ws, lens):
        out.append({"w": w, "s": round(at(acc / L), 3), "e": round(at((acc + l) / L), 3)})
        acc += l
    print(f"{spans[0][0]:6.2f}-{spans[-1][1]:6.2f}  {' '.join(ws)}")

json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=0)
