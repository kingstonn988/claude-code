# Ajahn Panyavaddho video pipeline — every setting

All numbers below are what actually produced your videos. Nothing here is
aspirational; it is the working configuration.

---

## 1. The decision that comes first

Every talk goes down one of two roads. The test is **is there faint speech
in this recording** — i.e. did the audience get recorded at all.

    FAINT_BELOW = 10.0   # dB below the teacher's speech level
    MIN_RUN     = 2.0    # a candidate stretch must last this long
    MIN_TOTAL   = 20.0   # and all candidates must total this much

Measure the teacher's speech level, set `faint_thr = teacher - 10 dB`, find
every stretch quieter than that, drop the ones under 2 s, sum the rest.

- **20 s or more** → faint speech present → **Q&A split**
- **less than 20 s** → no audience on tape → **natural-break parts**

Do not use "is the level histogram bimodal" for this. I tried it and it got
2 of 4 talks wrong. Presence of faint speech is the right question.

---

## 2. Raising the questions

The one thing you had not done yourself. The rule you set: **flat gain only,
no compression, no noise reduction**, and **the teacher untouched**.

    TARGET  = teacher_dbfs - 6.0     # questions land 6 dB under him
    CEILING = 26.0                   # dB, maximum gain applied

Method, per question window:

1. Take the window with 0.55 s of padding either side.
2. Measure in 25 ms frames. Mark frames **above** `faint_thr` as loud.
3. Dilate the loud mask by ±0.15 s (6 frames) so a loud syllable's edges
   are protected too.
4. Compute gain from the **quiet** frames only:
   `G = clip(TARGET - median(loudest 40% of quiet frames), 0, 26)`
5. Apply `G` to quiet frames, **0 dB to loud frames**, smoothed with a
   5-frame Hann window so the gain never steps.
6. Post-filter: `highpass=f=75, alimiter=limit=0.891`
7. Crossfade the treated window back in over **0.30 s, squared** either end.

Why gain is gated on level: a loud interjection inside a question window
would otherwise be lifted too and clip. Early versions hit +24.8 dBFS peaks
this way.

**Why the ceiling is 26 and not higher.** I tried 36. It measured +10 dB
louder and you judged it no clearer, just noisier — the faintest questions
sit only 12–20 dB above the room noise, so gain lifts the hiss with the
voice. More gain is not the missing piece; that needs generative speech
enhancement on the originals.

**Proof the teacher is untouched:** 84–96% of samples bit-identical,
0.00 dB level change, measured across six talks.

---

## 3. Splitting into videos

### Q&A talks

    LEAD_IN      = 2.5   # s of answer tail before the question
    TAIL         = 1.5   # s after the answer ends
    JOIN         = 2.5   # gap under this merges two question runs
    MIN_EXCHANGE = 120.0 # s — no video shorter than 2 minutes

The merge rule matters and is easy to get wrong:

    # absorb the next piece ONLY while the current one is still under the floor
    for it in items:
        if merged and it.kind == 'qa' and (merged[-1].e - merged[-1].s) < MIN_EXCHANGE:
            merged[-1].e = it.e
        else:
            merged.append(it)

Without the `< MIN_EXCHANGE` guard the first piece cascades and swallows the
whole talk. Without the rule at all you get 81 "questions" and 13-second
videos.

### Talks with no audience

Split at the longest pause near each **~22 minute** target. Snap to the
quietest 25 ms frame within ±3.5 s.

### The fragment rule

Reject a candidate cut if another pause follows within **12 s** — otherwise
you cut 8 seconds before the question instead of right before it. This is
the fix for what you caught in Curing Discontent.

---

## 4. Chitchat

Level-based splitting is deaf to content. It will happily open a talk on
water tanks. The only reliable check is to **read the opening**.

Cut points found this way, for reference:

| Talk | Cut |
|---|---|
| Body, Citta and Self | first 16 min |
| The True Nature of Perception | first 4:35 |
| The Internal Senses | first 2:11 |
| Practice of the Ajaans | first 51 s |
| Advice for New Monks | first 46 s |
| The Nature of Delusion | first 33 s |

Snap every cut to the quietest 25 ms frame within ±6 s so it never clips a
word.

---

## 5. Video encode

    1920x1080, still image
    -c:v libx264 -tune stillimage -preset medium -crf 27
    -r 5                      # 5 fps is plenty for a still
    -pix_fmt yuv420p
    -c:a aac -b:a 96k         # 80k if the piece runs over 25 min
    -movflags +faststart

If a file still lands over 30 MiB, re-encode **video only** and copy the
audio so it does not lose quality twice:

    -crf 34 -r 2 -g 240 -c:a copy

That took a 32.7 MiB file to 23.1 MiB with no further audio loss.

### The cards

Photo: `photo3/img_clean.png` — the three monks — on every Q&A talk.

    left ochre bar, 10 px
    margin 150 px
    AJAHN PANYAVADDHO     letter-spaced 7 px, muted grey, serif caps
    Question and Answer   italic, ochre        (Q&A talks)
    <talk name>           large serif, cream

For parts-based talks the card carries **the name only** — no topic line.

**Put nothing else on the card.** The `_00`, `_01` in the filenames is for
ordering on disk and must never reach the card. A "(2)" disambiguator did
reach one card and it was immediately obvious as wrong.

Topics belong in the YouTube title, not burned into the picture.

---

## 6. Audio chain order, if you ever start from raw

You asked about this. The correct order is:

1. **Raise the questions** (while the noise floor is still where the
   recorder left it)
2. Noise suppression
3. Loudness normalisation
4. Limiter

Doing it in your usual order — suppress, normalise, limit, then hand it to
me — means I am amplifying the *residue* of your noise reduction, which is
why spectral denoising on my side made things worse rather than better. It
was chewing on artefacts, not on the original hiss.

**Crest factor** tells you whether a file has already been limited:

    short-term crest = p99(all frames) - median(speech frames)
    > 7 dB  → untouched
    < 6 dB  → already limited

Use the *short-term* crest, not absolute peak. Absolute peak called a
known-processed file "untouched".

A limiter only acts above its threshold. That is why running one over a
whole file flattens the teacher and never touches a distant questioner —
and why the level gap you asked about was already in your originals before
I did anything.

---

## 7. Delivery

- **30 MiB per file**, both directions. Check every file before sending.
- Always run a **full decode** before delivery:
  `ffmpeg -v error -i FILE -f null -` must print nothing. A file whose
  encoder is still writing will look fine by size and be truncated.
- Images only reach me as vision content. To get one onto disk, **zip it**.

---

## 8. Transcription

Models come from the k2-fsa GitHub release mirror; huggingface.co is
blocked from this environment.

| Model | Speed (4 cores) | Verdict |
|---|---|---|
| base.en | 4.2x realtime | fast, invents sentences |
| distil-small.en | 3.8x realtime | middling |
| **small.en** | 1.5x realtime | **clearly best of the three** |
| medium.en | untested | too slow here |

Whisper of any size is worse than YouTube's own transcriber on this audio.
Your existing habit — upload, pull the `.sbv` — remains the better source.

Whatever transcript you use, paste `GLOSSARY.md` alongside it. It lists the
actual mis-hearings from these recordings: kilesas heard as "chelaces",
citta as "Twitter", khandhas as "Kundas", parikamma as "paracumb", pīti and
sukha as "PT and so-called", and Than Ajahn Mahā Boowa as **"Donald Trump"**.
