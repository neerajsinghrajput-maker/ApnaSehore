# ApnaSehore repo — notes for Claude

This repository is the **www.apnasehore.in** website (static HTML on GitHub Pages). It also holds
the user's Instagram reel workflows as project skills in `.claude/skills/` (Jekyll does not publish
dot-folders, so they never appear on the site).

## One-word requests
- Message is **"bitcoin"** (or "bitcoin part N", "socho agar") → use the `bitcoin-reel` skill.
- Message is **"shareer"**, "sharir" or "शरीर की बात" (optionally + a topic) → use the `shareer-reel` skill.
Attached grid images / voiceover MP3 / script in the same message are that skill's inputs.

## Rules for reel work
- Talk to the user in Hinglish.
- Work in the session scratchpad; do not edit the website's HTML/CSS for reel tasks, and never commit
  videos, audio, or uploaded images to this repo.
- Deliver finished videos with SendUserFile.
