"""Start time of every script line (= one scene) from align.py's words.json.

    python3 -I scene_times.py script.txt words.json

Prints "line_no  start  text" — use the starts as the "t" of each scene in plan.json
(the first scene always starts at 0).
"""
import json, sys

lines = [l.split() for l in open(sys.argv[1], encoding="utf-8").read().splitlines() if l.strip()]
words = json.load(open(sys.argv[2], encoding="utf-8"))
i = 0
for n, line in enumerate(lines, 1):
    start = 0.0 if n == 1 else max(words[i]["s"] - 0.1, 0)
    print(f"{n:2d}  {start:6.2f}  {' '.join(line)}")
    # align.py splits "a—b" and "a...b" into separate tokens; walk by the same rule
    toks = " ".join(line).replace("—", "— ").replace("...", "... ").split()
    i += len(toks)
