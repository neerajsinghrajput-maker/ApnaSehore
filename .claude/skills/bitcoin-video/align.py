#!/usr/bin/env python3
"""Fallback word timing when no speech-to-text is available.

Usage:  python align.py voiceover.mp3 script.txt words.json

script.txt is the Roman-Hinglish script the voiceover was generated from.
Speech stretches are found with ffmpeg silencedetect; each sentence is placed
on the stretch(es) in order and words get time in proportion to their length.
Good enough for karaoke subtitles; prefer a real transcript (ElevenLabs Scribe)
when one is available.
"""
import json, re, subprocess, sys


def speech_segments(audio, noise="-35dB", d=0.3):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", audio, "-af", f"silencedetect=noise={noise}:d={d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    dur = int(h) * 3600 + int(m) * 60 + float(s)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    segs, cur = [], 0.0
    for s, e in zip(starts, ends + [dur] * (len(starts) - len(ends))):
        if s > cur + 0.05:
            segs.append([cur, s])
        cur = e
    if cur < dur - 0.05:
        segs.append([cur, dur])
    return segs


def main():
    audio, script, out = sys.argv[1:4]
    words = open(script, encoding="utf-8").read().split()
    segs = speech_segments(audio)
    total = sum(e - s for s, e in segs)
    weight = [len(w) + 2 + (4 if w[-1] in ".?!" else 2 if w[-1] in "," else 0) for w in words]
    unit = total / sum(weight)
    # walk the speech timeline; sentence ends snap to the next pause when close
    res, si, t = [], 0, segs[0][0]
    for w, wt in zip(words, weight):
        d = wt * unit
        while si < len(segs) and t + d * 0.5 > segs[si][1]:
            si += 1
            if si < len(segs):
                t = max(t, segs[si][0])
        if si >= len(segs):
            si = len(segs) - 1
        end = min(t + d, segs[si][1]) if w[-1] in ".?!" else t + d
        res.append({"text": w, "start": round(t, 3), "end": round(end, 3)})
        t = end
        if w[-1] in ".?!" and si + 1 < len(segs) and segs[si + 1][0] - t < 1.2:
            si += 1
            t = segs[si][0]
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(res)} words over {len(segs)} speech segments -> {out}")


if __name__ == "__main__":
    main()
