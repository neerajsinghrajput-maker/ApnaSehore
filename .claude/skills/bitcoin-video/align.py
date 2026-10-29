#!/usr/bin/env python3
"""Fallback word timing when no speech-to-text is available.

Usage:  python align.py voiceover.mp3 script.txt words.json

script.txt is the Roman-Hinglish script the voiceover was generated from.
Best: write it one phrase per line, breaking lines exactly where the voice pauses
(the script prints the pause list if the line count does not match) — then each
line is pinned to its own speech segment.
Otherwise speech stretches are found with ffmpeg silencedetect; each sentence is placed
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


def weight_of(w):
    return len(w) + 2 + (4 if w[-1] in ".?!" else 2 if w[-1] in "," else 0)


def phrase_align(phrases, segs):
    """One script line per speech segment: spread each line's words across its own segment."""
    res = []
    for line, (s, e) in zip(phrases, segs):
        ws = line.split()
        unit = (e - s) / sum(weight_of(w) for w in ws)
        t = s
        for w in ws:
            d = weight_of(w) * unit
            res.append({"text": w, "start": round(t, 3), "end": round(t + d, 3)})
            t += d
    return res


def main():
    audio, script, out = sys.argv[1:4]
    text = open(script, encoding="utf-8").read()
    segs = speech_segments(audio)
    phrases = [l.strip() for l in text.splitlines() if l.strip()]
    if len(phrases) == len(segs):
        # script written one phrase per line, matching the voiceover's pauses exactly
        json.dump(phrase_align(phrases, segs), open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"{len(phrases)} lines matched to {len(segs)} speech segments -> {out}")
        return
    if len(phrases) > 1:
        print(f"note: {len(phrases)} lines vs {len(segs)} speech segments; using proportional timing")
        print("speech segments (s): " + "  ".join(f"{s:.2f}-{e:.2f}" for s, e in segs))
    words = text.split()
    total = sum(e - s for s, e in segs)
    weight = [weight_of(w) for w in words]
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
