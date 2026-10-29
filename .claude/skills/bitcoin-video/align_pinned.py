"""Pinned word timing: one phrase per line in phrases.txt, one line per speech segment.

Usage:  python align_pinned.py voiceover.mp3 phrases.txt words.json

More exact than align.py when no transcript is available: split the script at the
voiceover's pauses (the script prints each segment next to its phrase to check).
"""
import json, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from align import speech_segments
segs = speech_segments(sys.argv[1])
lines = [l.split() for l in open(sys.argv[2], encoding='utf-8').read().splitlines() if l.strip()]
assert len(segs) == len(lines), (len(segs), len(lines))
out = []
for (s, e), ws in zip(segs, lines):
    wt = [len(w) + 2 + (2 if w[-1] in ',.?!' else 0) for w in ws]
    u, t = (e - s) / sum(wt), s
    for w, k in zip(ws, wt):
        out.append({"text": w, "start": round(t, 3), "end": round(t + k * u, 3)}); t += k * u
json.dump(out, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for (s, e), ws in zip(segs, lines): print(f"{s:6.2f}-{e:6.2f} {' '.join(ws)}")
