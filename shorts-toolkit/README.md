# No Ajahn Chah — Shorts toolkit

Builds vertical YouTube Shorts from the reflections in *No Ajahn Chah*.
Written to be re-runnable years from now: the code and the text are here,
the media (photographs, music) is not — keep that yourself and point the
scripts at it.

## What is here

| file | does |
|---|---|
| `shorts.py` | the renderer — text masks, gold fill, outline, box, glow, light sweep, and the ffmpeg composite |
| `beats.py` | splits a reflection into beats and line breaks, decides build-and-stay vs beats-and-recap |
| `clip.py` | one finished clip: photo or backdrop, header, verse, music |
| `sets.py` | three publishing sets (A generated light, B photographs, C ready-made templates) |
| `backdrops.py` | generates the moving light backdrops — no photographs, no AI imagery |
| `panel.py` | finds the empty text panel in a ready-made template |
| `auto.py` | picks the text treatment from how bright the background is |
| `check_bg.py` | vets candidate photographs before use |
| `music.py`, `ambience.py` | synthesised beds — kept for reference; real music sounds better |
| `storyboard.py` | frame-by-frame contact sheets, for judging timing without rendering |
| `FORMAT.md` | the agreed format: sizes, positions, timings |
| `data/reflections.json` | all 194 reflections, parsed from the PDF with the Pali restored |
| `data/shorts_candidates.txt` | the 71 that are 40 words or fewer |
| `assets/logo_clean.png` | the medallion, re-cut as a true circle at 1024 px |

## Media you need to supply

- `photos_all/` — portrait photographs, at least 1254x2227
- `music_lib/` — audio, loudness-normalised to -23 LUFS
- `gpt/` — the ready-made templates, if you use set C

## Notes

- Fonts come from Google Fonts (Playfair Display, Cinzel, Lora, Cormorant
  Garamond, Marcellus, Anton, Bebas Neue, Inter) into `fonts/`.
- The reflections were parsed from the book's own PDF. Its text layer drops
  ligatures and renders Pali accents as separate glyphs — `saṁsāra` came out
  as `sa\x01msﬂara`. `data/reflections.json` has this repaired throughout.
- Following Ajahn Chah's wish, the book is for free distribution only. Keep
  that line in every description.
