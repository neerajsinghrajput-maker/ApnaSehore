---
name: bitcoin-reel
description: Make the next "Socho Agar?" ₹5 Crore Bitcoin story reel (Hinglish money / tax / cyber-crime series) from a 3x3 comic grid image, an ElevenLabs voiceover MP3 and the script. Use when the user's message is just "bitcoin" (or "bitcoin part N", "socho agar"), or they attach a comic grid + voiceover + script for this series, or ask to edit/re-render one of these reels.
---

# Bitcoin story reel ("Socho Agar?" series)

The user runs an Instagram page **"Socho Agar?"** (@socho.agar) with a Hinglish story series:
*"₹500 ke purane laptop mein ₹5 Crore ke Bitcoin mile… ab kya?"* Each part is a 9:16 reel of
~75–85 s. They give you the files; you deliver a finished MP4 that looks exactly like the earlier
parts. Talk to the user in **Hinglish**, short and friendly.

Look of every part (all of it is built into `scripts/render_reel.py`):
- comic panels with slow Ken Burns zoom/pan, cuts every ~2.5–5 s on the voiceover's pauses
- top HUD: 3 dark boxes, e.g. BITCOIN ₹… / BANK ₹… or FROZEN / RISK %, values animate with the story
- word-by-word captions near 62 % height (spoken words white, upcoming words dim)
- typographic info cards: cream (#ECE7DF) or near-black (#1B1817) background, Inter bold text,
  pink accent #E8437A, mono labels, rubber stamps ("NO KYC", "+ JAIL"), pills, "where you stand" rows
- ends with a dark "PART N+1" card: "Comment karo" + two option pills (from the script's question)
- sound: voiceover 100 %; **no whoosh** (the user asked to remove it); every effect very low
  (overall 18 %): soft thud on cuts, faint tick per caption, light pop per card line, a few accents
  (boom for danger, chime for money in, alert beep for "tracked/spotted")

## The 30-part series bible
`reference/series_30_parts.md` ("THE ₹5 CRORE HARD DRIVE — Every Click Leaves a Trace") is the
user's complete plan: 6 arcs × 5 parts, and for every part the **HUD stats**, the **first-3-second
hook** and the **complete audio script**. Use it:
- "bitcoin part N" with no script attached → take Part N's "Complete Audio Script" as the script.
  If a script *is* attached, the attached one wins (the recorded voiceover can differ from the bible —
  e.g. the recorded Part 2 starts with "Aap logon ne bola— Cash Deal"); always align against what was voiced.
- HUD: follow that part's "HUD Stats" line (start → end values). Boxes are short labels, e.g.
  WALLET / BANK (or CASH / GOLD / LOCATION / STATUS as the part needs) / CYBER RADAR %.
  Text values (FROZEN, SEIZED, DRAINED, DUBAI…) are allowed and show in pink.
- Cards: pull the real rules and numbers the part explains (PMLA, FEMA limits, 30 % TDS, VARA, CRS…)
  into the cards; end card = "PART N+1" + the two options the script asks people to comment.
- If the user asks for **image prompts** for Part N: write one 3x3 grid prompt — "ONE single square image,
  comic storyboard grid of 9 equal panels, 3x3, thin white gutters and black panel borders, bold
  outlined Indian comic style, moody purple/blue/pink night lighting; recurring hero: a man with a plain
  white round ball head, simple dot eyes, blue checked shirt, jeans; no captions or speech bubbles except
  short on-screen UI text" + 9 panel lines following the script's beats in order.

## Inputs (ask only for what is missing)
1. **Grid image**: a 3x3 comic grid (any size; white or dark gutters). Panels are the story in order.
2. **Voiceover**: ElevenLabs MP3 (voice "Prayan – Mystery/Crime Documentary").
3. **Script**: the exact voiceover text. Blank lines / paragraph breaks in it mark story beats.
   If missing, use the part's script from the series bible (ask which part if it isn't clear).

If the user only typed "bitcoin", reply in one line asking them for the part number + grid image + MP3.
Uploaded files arrive as paths in the message; images can also land in a session `images/` folder.

## Workflow
Work in the session scratchpad (never inside this website repo; never commit videos or uploads).
`SK=<this skill's folder>` (`.claude/skills/bitcoin-reel` in the repo).

1. **Setup**: `python3 -c "import moviepy" || pip install -q moviepy`. ffmpeg and Pillow (with raqm)
   are already present. Fonts are bundled in `$SK/fonts`.
2. **Cut the grid**: `python3 -I $SK/scripts/crop_grid.py grid.png panels` → `panels/01..09.png`.
   Make a contact sheet and look at every panel so you know what each shows and where the faces,
   phones and on-screen text are (normalised x, y in the square panel).
3. **Remove the Gemini star watermark** (bottom-right of the last panel, sometimes others):
   `python3 -I $SK/scripts/dewatermark.py panels/09.png --inspect corner.png`, read corner.png,
   note the star's centre and radius (centre→tip) in panel pixels, then
   `python3 -I $SK/scripts/dewatermark.py panels/09.png --star CX CY R`. Inspect again; it should be clean.
4. **Timing**: save the script to `script.txt`, then
   `python3 -I $SK/scripts/align.py voice.mp3 script.txt words.json`. It prints each speech segment
   with the phrase it was matched to — check that it reads sensibly (add a token to `SPOKEN` in
   align.py if some acronym/number is badly estimated). Phrase start times are your cut points.
   You cannot listen to audio; tell the user captions are timed from the pauses.
5. **Write `plan.json`** (copy `$SK/reference/plan_part2.json` and adapt; `script_part2.txt` is its
   script). Rules that made the earlier parts work:
   - Alternate image scenes and cards; a new visual every 2.5–5 s; every scene starts at a phrase start.
   - Use all 9 panels in story order; long beats get a wide shot then a close-up of the same panel.
   - Image scene: `{"t", "panel", "from":[x,y], "to":[x,y], "zoom":[z0,z1]}`. Wide: zoom 1.0→1.06 with a
     sideways pan between the two subjects. Close-up: zoom 1.3–1.7. **Panels with text across their full
     width** (signs, split screens like "CASH DEAL | DUBAI PLAN"): zoom 0.60→0.66 (whole panel + blurred fill).
   - Captions sit at 62 % of the frame height: in close-ups place the important on-screen text/face
     above that: `cy = y_subject − (0.40 − 0.5) / zoom`.
   - Cards: one per explanation beat (problem, numbers, plan, catch, where-you-stand, end). Element
     types: `label` (mono caps, y≈520), `text` (size/color/weight), `small`, `arrow`, `stamp`, `pill`,
     `choice` (two options), `row` (label + value [+ bar]), `tiles` (n money tiles). Each element
     appears at its `t` = the word time it illustrates; stack y from ~520 to ~1250 (≈80–150 px apart).
     Keep big pink words ≤ ~11 chars at size 120+, longer lines at 64–80. Colors: ink, white, pink,
     grey, dim, soft, mid.
   - First card after the hook: "PART N" + the part's theme. End card: "PART N+1" + `choice` with the
     two options the script asks the audience to comment.
   - HUD steps follow the story (money moving, BANK "FROZEN", risk rising/falling); the next part
     starts from where the previous one ended (Part 2 ended at ₹4,94,00,000 / FROZEN / 99 %).
   - `sfx`: keep `"cut": "thud"`, `"volume": 0.18`; add accents only on real story hits.
6. **Preview**: `python3 -I $SK/scripts/render_reel.py plan.json voice.mp3 words.json panels out.mp4 --preview t1 t2 …`
   for ~15 times (one per scene), tile them into one contact sheet and read it. Fix text overflow,
   captions covering key on-screen text, crops that cut words. Repeat until clean.
7. **Render** (background, ~7 min): same command without `--preview`. Then verify with ffprobe
   (1080x1920, h264+aac, duration ≈ voiceover + 0.8 s) and send the MP4 with SendUserFile.
   Sound-only change later: `--remux previous.mp4` rebuilds just the audio in seconds.
8. **Reply** (Hinglish): what is in the video (cards, HUD, sounds), the timing caveat, and offer the
   Instagram caption + hashtags. Keep it short.

## Instagram caption pattern
Hook line with the money + emoji → 3–4 "❌ problem" lines → cliffhanger → "💬 Comment karo: A ya B?
Majority jo bolegi, wahi Part N+1 mein" → "⚠️ Ye ek kaalpanik kahani hai, sirf jaankari ke liye…".
Hashtags: #bitcoin #crypto #cryptotax #incometax #cybercrime #cybercell #moneyfacts #finance
#paisa #hindireels #reelsindia #storytime #partN #viralreels #explore (+ topic-specific ones).

## Story so far (videos already made; the rest follows the series bible)
- Part 1: ₹500 laptop → ₹5 Cr Bitcoin → exchange needs Aadhaar/PAN + 1 % TDS → 30 % tax, 78 % penalty →
  P2P: 5 × ₹80,000 = ₹4 lakh → scammer's money → bank FROZEN by cyber cell. Options: Cash Deal / Dubai Plan.
- Part 2 (Cash Deal): Telegram grey-market dealer (10 % commission, irreversible, gun) → anonymous gift
  cards (₹2 lakh, iPhone delivered home → IP/address tracked) → blockchain is public; the real owner
  (hacker/mafia) sees the dormant wallet move. ₹4.94 Cr left. Options: Crypto Mixer / Desh Chhod Do.
