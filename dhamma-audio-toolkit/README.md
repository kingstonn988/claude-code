# Dhamma talk audio & video pipeline

Tools for turning archive recordings of Dhamma talks into publishable audio
and video, built while processing *The Essentials of Practice* (Ajahn
Panyavaddho) into 21 question-and-answer videos.

    ./setup.sh                              # ~5 min on a fresh container
    python3 01_analyze.py talk.mp3          # ALWAYS run this first

## Run 01_analyze.py first, every time

It answers three things before any processing decision is made.

**Has the file already been treated?** Crest factor near 3–5 dB means someone
has limited and normalized it; a noise floor with under ~1.5 dB of variation
means it has been noise-suppressed. This matters — running spectral noise
reduction over already-suppressed audio is what produces the watery, metallic
artefacts. The second pass has no noise left to remove and chews on the first
pass's residue instead.

**What is the source actually capable of?** An 11 kHz, 18 kbps file has nothing
above 5.2 kHz and never will. No amount of processing recovers it; only a
generative speech-enhancement model can plausibly reconstruct it.

**Do the questioners separate from the teacher by level?** This decides
everything downstream, and there are two cases:

| Verdict | Meaning | What to do |
|---|---|---|
| **Faint speech present** | Audience questions 10–30 dB below the teacher | `05_boost_questions.py` finds and raises every one |
| **No faint speech** | Solo talk, or questioners sitting near the mic | Nothing to raise. Split by content if you want sections |

Do not test for a bimodal distribution. An earlier version of this looked for
two humps with a valley between them, and got two of four talks wrong: where
several questioners sit at several distances, the valley fills in and the
histogram reads as one hump even though the talk plainly contains questions
15–25 dB down. What matters is only whether there is a meaningful amount of
speech well below the teacher.

Calibrated against six recordings, correct on all six:

| Talk | Faint speech | Verdict |
|---|---|---|
| Essentials of Practice | 380 s | present — 20 questions |
| Introduction to the Sangha | 466 s | present |
| Curing Discontent | 194 s | present — "I have a question" at 17:32 |
| The Five Precepts | 161 s | present |
| Mindfulness | 16 s | none — solo talk |
| Right Effort | 17 s | none — questioners near the mic |

Still a heuristic. Transcribe the faint passages before processing to confirm
they are questions rather than a cough or a passing motorbike.

## The scripts

| | Purpose |
|---|---|
| `01_analyze.py` | Diagnose. Run first, always. |
| `02_transcribe.py` | Whisper base.en with timestamps. Rough — see below. |
| `03_propose_cuts.py` | Flag dead air and possible chitchat → `cuts.json` |
| `04_trim_and_join.py` | Remove approved passages, rejoin seamlessly |
| `05_boost_questions.py` | Flat amplification of faint questions |

### Cutting chitchat and rejoining

Not every talk is worth publishing whole. `03_propose_cuts.py` writes
`cuts.json` with every candidate marked `"keep": true`. Review it, set
`"keep": false` on what should go, then run `04_trim_and_join.py`.

**Nothing is ever removed without that approval step.** Deciding what is
off-topic in a Dhamma talk is a judgement about content, not something a
script should do on its own.

The rejoin is inaudible because each cut boundary is nudged to the quietest
point nearby — so it lands in silence rather than mid-word — and the seam gets
a 120 ms equal-power crossfade so the room tone doesn't jump. Dead air is
shortened to about 2 seconds rather than closed completely; a talk with every
breath removed sounds hurried.

### On amplifying questions

`05_boost_questions.py` is Audacity's Amplify, automated: one flat gain per
question, no compression, no noise reduction. Two refinements matter.

Loud moments *inside* a question window keep their original level. When the
teacher answers back into the mic mid-question — which he does often — a flat
+23 dB across the window turns that into a blast. The script leaves anything
above −22 dBFS alone, with a 0.15 s margin so nothing is clipped mid-word.

Questions land ~3 dB *under* the teacher, not level with him. Matching exactly
costs several more dB of gain, and gain costs noise.

## Order of operations

Do the level work on the **untouched** original, then clean:

    raise questions  →  noise suppression  →  normalize  →  limit

Suppressing first means the suppressor has to judge a question sitting 30 dB
down, barely above the floor it is trying to remove — and whatever it leaves
behind then gets amplified 25 dB. The first talk was processed in the reverse
order and the faintest questions suffered for it.

## Transcripts

`02_transcribe.py` runs Whisper `base.en` — the largest model reachable from
this environment, since huggingface.co is blocked by the egress policy and the
k2-fsa GitHub release mirror is what carries the weights.

**YouTube's captions are better.** If the talk is going to YouTube anyway,
upload it, download the `.sbv`, and correct that instead — with `GLOSSARY.md`
pasted above it, which lists the Pali terms and names in these talks along
with how ASR actually mangles them.

Watch for phrase repetition in the output ("it's a curse" 28 times over). That
is Whisper collapsing on audio it cannot handle, and it means the file needs
enhancing before any transcript is worth having.

## Starting a new session

Containers do not persist. To pick this work up again:

1. Open a new Claude Code session on this repository
2. Attach the talk (**MP3 attaches directly; zip any images** — pictures pasted
   into a conversation reach the assistant as vision content and never land on
   disk, so the bytes have to arrive as a zip)
3. Paste the prompt below

---

> Read `dhamma-audio-toolkit/README.md` first, then run
> `dhamma-audio-toolkit/setup.sh` to restore the environment (~5 min; ffmpeg,
> python packages, and the speech models from the k2-fsa GitHub mirror —
> huggingface.co is blocked here).
>
> Then run `01_analyze.py` on the attached talk and **tell me the verdict
> before processing anything**. I want to know whether the file has already
> been treated, and whether the questioners separate from the teacher by
> level — that decides what can be done with it.
>
> Context: these are Dhamma talks by Ajahn Panyavaddho being published to
> YouTube as separate question-and-answer videos. Audio work only — no noise
> reduction unless the file has never had any, and questions get flat
> amplification (Audacity's Amplify), never compression. If I ask for chitchat
> to be cut, propose the passages and wait for me to approve them.

---

Attach `GLOSSARY.md` too if the session will be correcting a YouTube `.sbv`.

## Environment notes

- `huggingface.co`, Google hosts and the ElevenLabs API are blocked by the
  egress policy. `github.com` and `raw.githubusercontent.com` are reachable,
  which is why the models come from the k2-fsa release mirror.
- Images pasted into a conversation reach the assistant as vision content and
  never land on disk. **Zip them** to get the actual bytes through.
- Containers are temporary. This directory is the durable part.
