---
name: shareer-reel
description: Make a "शरीर की बात" (Shareer Ki Baat) Hindi health-fact Instagram reel — write the script and image prompts for a topic, or turn two 3x3 grid images + a Hindi voiceover into the finished 9:16 video. Use when the user's message is just "shareer" / "sharir" / "शरीर की बात" (optionally with a topic), or they attach health-reel grids + voiceover, or ask to edit one of these reels.
---

# "शरीर की बात" health reel

The user runs an Instagram page **"शरीर की बात"** (@shareer.ki.baat): 60–90 s Hindi reels that
explain why the body does something ("खड़े होते ही आंखों के आगे अंधेरा क्यों?"). Talk to the user in
**Hinglish**. Health facts must be accurate and safe; always end with a "doctor से मिलें" style line
when symptoms can be serious.

Look (built into `scripts/render_health.py`): one semi-realistic illustration per scene (Indian
people, dark muted backgrounds), slow Ken Burns motion, a bold Teko headline top-left — small cream
line + big red (#E5483B, for problems/warnings) or orange (#F0A23A) line that slides up — vignette,
film grain, folded-paper crease and punch-hole dots, 0.3 s crossfades, soft ambient bed under the voice.

## Mode A — the user gives only a topic (or just "shareer")
If no topic, ask for one in one line (suggest 3 catchy ones). Then deliver, in chat:
1. **18-scene script** (~60 s, ~150 Hindi words): for each scene the VO line (Devanagari) and the
   screen text (small line ≤ 3 words + big line ≤ ~14 chars). Hook question first, then the "why"
   (simple biology), then causes, then 2–3 safe tips, then a doctor line, then "फॉलो करें".
2. **Two grid prompts** (scenes 1–9 and 10–18) for ChatGPT/Gemini image generation, in English:
   "Create ONE single vertical 9:16 image that is a storyboard grid of 9 equal panels arranged 3 columns
   x 3 rows. Every panel is itself vertical 9:16. Separate panels with thin straight dark gutters (about
   8px, color #111111)… CONSISTENT STYLE FOR ALL PANELS: semi-realistic digital illustration like a premium
   health-explainer reel, soft cinematic lighting, dark muted solid backgrounds (deep brown, charcoal, dark
   teal, maroon), Indian skin tones, subtle film grain, faint folded-paper crease texture, minimal clean
   composition, main subject placed in the lower two-thirds, the top third of every panel left EMPTY plain
   background for text. ABSOLUTELY NO text, letters, numbers, labels or watermarks anywhere." + Panel 1–9 lines.
   Tip: upload the first grid when generating the second and say "same style as this image".
3. **Voiceover script**: just the VO lines (pauses as blank lines / "..."), with ElevenLabs tips
   (Multilingual v2, a warm Hindi voice e.g. "Roopa", stability ~40 %, style ~30 %).
4. Tell them: generate both grids + the MP3, then send them here (with the script) for the video.

## Mode B — grids + voiceover (+ script) → video
Work in the session scratchpad (never inside this website repo; never commit media).
`SK=<this skill's folder>` (`.claude/skills/shareer-reel` in the repo).

1. **Cut**: `python3 -I $SK/scripts/crop_grid.py grid1.png panels --start 1` and
   `… grid2.png panels --start 10` → `panels/01..18.png`. Look at a contact sheet of all panels.
2. **Watermark**: Gemini puts a translucent 4-point star bottom-right of each grid (panels 09 and 18).
   `python3 -I $SK/scripts/dewatermark.py panels/09.png --inspect c.png`, read c.png, then
   `--star CX CY R` (centre and centre→tip radius in panel pixels). Same for 18. Check again.
3. **Script → scenes**: one line per scene in `script.txt` (same order as the panels). If the user
   gave the VO text as a paragraph, split it into as many lines as there are panels, at sentence breaks.
4. **Timing**: `python3 -I $SK/scripts/align.py voice.mp3 script.txt words.json` (check the printed
   segments), then `python3 -I $SK/scripts/scene_times.py script.txt words.json` → scene start times.
   You cannot listen; tell the user timing comes from the voice's pauses.
5. **plan.json** (copy `$SK/reference/plan_andhera.json`): per scene `t`, `panel`, `small`, `big`,
   `accent` ("red" problems/warnings, "orange" otherwise — alternate so both appear), `motion`
   (vary: in, out, pan_r, pan_l, up, down, in_low; use `in_tl` for panels 09/18 to keep the corner out).
6. **Preview**: `python3 -I $SK/scripts/render_health.py plan.json voice.mp3 panels out.mp4 --preview t1 t2 …`
   for a handful of scenes; read them; fix headlines that cover faces or overflow.
7. **Render** (~3–4 min, run in background): same command without `--preview`; add `--music track.mp3`
   if the user sent copyright-free music (otherwise a quiet synthesised pad is used). Verify with ffprobe
   and send the MP4 with SendUserFile.
8. **Reply** in Hinglish: what's in it, the timing caveat, offer caption + hashtags.

## Channel kit (reuse when asked)
- Bio: "शरीर में ऐसा क्यों होता है? 🤔 / 60 सेकंड में आसान हिंदी हेल्थ फैक्ट्स 🩺 / रोज़ नई रील | फॉलो करें 👇 /
  ⚠️ सिर्फ जानकारी के लिए, इलाज के लिए डॉक्टर से मिलें"
- Profile photo: 1080², dark brown paper texture, centred Teko "शरीर की" (cream) + big "बात" (orange), thin red bar.
- Caption: hook question + 😵/🤔 + "वजह जानकर हैरान रह जाएंगे" + #healthfacts #hindi #health #sehat
  #reels #healthtips #hindireels #reelsindia #explore (+ topic tags) + a one-line "doctor से सलाह" disclaimer.
- Done so far: "खड़े होते ही आंखों के आगे अंधेरा क्यों?" (orthostatic hypotension) — see reference/.
