---
name: bitcoin-video
description: Make a vertical explainer video for the "Every Rupee Leaves a Trail" Hinglish money-trail series (Bitcoin / crypto / black-money story, "Bitcoin part N", "Part 4", etc.) from a comic panel sheet and an ElevenLabs voiceover, in the series' fixed house style — illustration scenes with a CASH/BANK/SUSPICION HUD and karaoke subtitles, cut with cream and dark kinetic-typography cards, a "PART N" title card and a "PART N+1 · KAL" end card. Use for every video in this series.
---

# Every Rupee Leaves a Trail — video skill

Every video in this series must look like the reference episodes (Part 1 "₹2 crore",
Part 2 "UDAO"). Do not invent a new look; reuse `render.py` and only write a new spec.

Inputs the user normally gives: one comic sheet (a grid of panels, e.g. 3×3) and one
ElevenLabs voiceover mp3. Output: 1080×1920, 30 fps H.264 + AAC, same length as the voiceover.

## The look (do not drift from this)

**Palette**: cream `#EAE6DC` cards, near-black `#15100D` cards, one accent pink `#F45C88`.
Ink on cream `#15100D`; paper text on dark `#ECE8DE`; muted text `#7A7068` (cream) / `#968C84` (dark).
No other colours; never use gradients, emoji or icons on cards.

**Type**: Inter Display ExtraBold for titles and big numbers (tight tracking); Inter Bold for card
lines and subtitles; JetBrains Mono, UPPERCASE, wide letter-spacing, small and muted for kickers
and HUD labels (e.g. `PROBLEM 2 · PROPERTY`, `DAY 2 · WHERE YOU STAND`, `EVERY RUPEE LEAVES A TRAIL`).

**Three scene families, alternated roughly every 3–8 s, hard cuts between them:**

1. **Illustration scene** (`type: panel`) — one comic panel full-bleed with a slow Ken Burns push
   (1.00→1.10, or reverse), darkened top and bottom.
   - HUD across the top: three dark translucent rounded boxes, mono label + bold value.
     Default boxes `CASH`, `BANK`, `SUSPICION` (pink %). For crypto episodes a box may become `BTC`.
     The HUD carries the story's running numbers and must stay consistent across parts.
   - Karaoke subtitle at ~64% height, centred, Inter Bold, white: words already spoken are solid
     white, words still to come are dim (≈38%). Subtitles appear **only** on illustration scenes.
2. **Cream card** (`type: card`, `theme: light`) — the explainer beats. A kicker at the top, then
   lines that build up one by one in sync with the narration (fade + small rise):
   bold question/headline (`Flat?`), black fact lines, ↓ arrows, pink consequence lines
   (`PAN dena padega`), pink rotated outlined stamps (`NOT ALLOWED`, `JEWELLER: NO`,
   `PHIR SE PAN`), big numbers that count up (`₹5,000 / din`, `3,941 din`), a huge pink payoff
   (`11 SAAL`). Also the **"where you stand" ledger** (`DAY N · WHERE YOU STAND`: Cash you can't touch /
   Spent so far / Suspicion % with pink bar) and bar charts with a dashed pink limit line.
3. **Dark card** (`type: card`, `theme: dark`) — dramatic beats and named threats:
   white headline + pink second word (`INFORMER` / `SCHEME`, `PATTERN` / `FLAGGED`), a short
   sub-line, a stamp (`INAAM`, `REPORT → FIU-IND`), and a suspicion meter low on the card that animates
   upward. Also list cards (`PAISA KISI AUR KE NAAM PE?` → Mummy / Chacha / Driver Raju rows).

**Fixed structure of an episode:**
1. Cold open, 4–7 s: illustration scene with HUD + subtitles (the hook line).
2. Title card (dark): kicker `EVERY RUPEE LEAVES A TRAIL`, then `PART N` in paper and the episode
   word in pink below it (`UDAO`, `CHHUPAO`…), 1.5–2.5 s.
3. Body: illustration ↔ cream card ↔ dark card, each card visualising exactly what the voice is
   saying at that moment (numbers, rules, consequences). Insert a ledger card when the money
   position changes; animate the suspicion % up.
4. End card (dark): kicker `EVERY RUPEE LEAVES A TRAIL`, `PART N+1` + pink `KAL`, a question
   (`Kiske naam pe?`), `Comment karo` and/or two buttons (`CHHUPAO` ya `UDAO`), and a muted line
   `Majority Part N+1 likhegi.` / `Part N+1 mein dekhte hain…`. Hold until the audio ends.

Copy is Roman Hinglish, short and punchy, numbers in Indian format (`₹1,96,96,000`).

## Workflow

1. **Inspect inputs**: `ffprobe` the mp3 for duration; view the comic sheet. `render.py` splits the
   sheet into panels automatically by its light gutters (reading order, 1-based).
2. **Get word timings** → `words.json` (list of `{"text","start","end"}` in seconds, Roman Hinglish):
   - Preferred: ElevenLabs `creative_transcribe_audio` (create flow → asset upload → PUT bytes →
     finalize → transcribe → poll `creative_get_flow_run_status`, read `words`). If it returns
     Devanagari, rewrite each word's `text` in Roman Hinglish but keep its timing.
   - Fallback (connector unavailable): ask the user to paste the voiceover script. Write it to
     `examples/partN.script.txt` **one phrase per line, breaking exactly where the voice pauses**, then
     `python align.py voiceover.mp3 partN.script.txt partN.words.json`. When the line count equals the
     number of speech segments, each line is pinned to its own segment (accurate); otherwise it prints
     the segment list — compare durations to phrase lengths, merge/split lines, and re-run.
     Attach dashes to the previous word (`bazaar—`) so they don't show as separate subtitle words.
3. **Write the story beats**: read the transcript, mark where each sentence starts, and decide per
   beat: panel (which one) vs cream card vs dark card. Every panel should be used at least once;
   cards carry the numbers and rules. Keep HUD values continuous with the previous part — see
   `series.md` and update it at the end.
4. **Write `spec.json`** (format below). Time every card item's `at` to the word where the
   narrator says it.
5. **Preview** before the full render, and look at it:
   `python render.py spec.json preview.png --preview 2,6.5,12,20,…` (one frame per scene).
6. **Render**: `python render.py spec.json Bitcoin_PartN.mp4` (≈2–4 min for 60–70 s).
   Spot-check a few frames, then send the mp4 to the user.
7. **Remember the story** (the container is wiped after each session, so this is the only memory):
   - Save the part's full voiceover script to `scripts/partN.md` (Roman Hinglish + the original
     transcript), and its `words.json` + `spec.json` to `examples/`.
   - Update `series.md` with the ending numbers, episode word and cliffhanger.
   - Commit and push these files.

**Before starting any new part, read `series.md` and every file in `scripts/`** so the story,
names, amounts and HUD values continue from where the previous part ended.

Run with any Python 3 that has Pillow + numpy (`pip install pillow numpy`); ffmpeg must be on PATH.
Fonts: Inter / Inter Display and JetBrains Mono (system paths, or drop the files into `fonts/`).

## spec.json format

```json
{
  "sheet": "comic.png", "audio": "voiceover.mp3", "words": "words.json", "duration": 68.2,
  "hud": [{"label": "Cash", "value": "₹1,96,96,000"}, {"label": "Bank", "value": "₹2,94,000"},
          {"label": "Suspicion", "value": "65%", "accent": true}],
  "scenes": [
    {"type": "panel", "start": 0, "end": 5.2, "panel": 1, "zoom": [1.0, 1.1], "focus": [0.5, 0.4]},
    {"type": "card", "theme": "dark", "start": 5.2, "end": 7.4, "top": 0.27,
     "kicker": "Every rupee leaves a trail",
     "items": [{"kind": "title", "text": "PART 3\nBHAAGO", "at": 5.3}]},
    {"type": "card", "theme": "light", "start": 7.4, "end": 12, "kicker": "Problem 1 · Mixer",
     "items": [{"kind": "head", "text": "Crypto mixer?", "at": 7.5},
               {"kind": "line", "text": "₹50 lakh BTC", "at": 8.4},
               {"kind": "arrow", "at": 8.9},
               {"kind": "line", "text": "Trail hide?", "color": "pink", "at": 9.2},
               {"kind": "stamp", "text": "SCAM", "at": 10.6}]}
  ]
}
```

Scene keys: `start`/`end` in seconds (scenes must tile 0 → `duration` with no gaps).
Panel scene: `panel` (1-based), optional `zoom` [from, to], `focus` [x, y] 0–1 (where the push
lands), `hud` (overrides the global HUD for this scene; `[]` hides it — use on panels whose own text sits
under the HUD), `subtitles: false`, `sub_y` (0–1, default 0.64; move subtitles off text in the art).
Check every panel in the preview: if the HUD or subtitle covers words drawn in the comic, fix it.
Card scene: `theme` light/dark, `kicker`, `top` (0–1, default 0.21), `items`.

Card item kinds (all take `at` = absolute second when it appears; optional `color`: `pink`/`muted`;
optional `size`):
- `title` — huge headline; `\n` splits lines, line 2+ pink (`accent_second: false` to disable).
- `head` — big question/headline (`Flat?`). `big` — big number; add `"count": [from, to]`,
  `prefix`, `suffix`, `count_dur` to count up (Indian commas).
- `line` — bold fact line. `small` — sub-line (muted unless `color`). `arrow` — ↓. `gap` — `h` px.
- `stamp` — pink rotated outlined label, pops in (`rotate`, `fill`).
- `meter` — SUSPICION % with bar animating `from` → `value`; `y` (0–1) pins it low on dark cards.
- `ledger` — row `label` + `value`; `new_value` + `change_at` swaps the value; with `"meter": true`
  it is the pink suspicion row (`from` → `value` at `change_at`).
- `rows` — list of `{"text", "at", "strike"?, "dim"?}` (name lists).
- `buttons` — `[{"text": "CHHUPAO"}, {"sep": "ya"}, {"text": "UDAO", "pink": true}]`.
- `bars` — `n` bars appearing every `step` s, `label`, dashed pink `limit` line text.

`examples/part3.spec.json` is the full spec for Part 3; start new parts by copying it.
