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

| Histogram | Meaning | What to do |
|---|---|---|
| **Two clusters with a gap** | Questioners far off-mic, 16–31 dB down | `05_boost_questions.py` finds and raises every one automatically |
| **One broad hump** | Questioners near the mic, within a few dB | Nothing to amplify. Questions can't be located by level — split from timestamps or a transcript |

Both cases turned up in the first two talks, so do not assume.

Run the cluster test on a **whole talk**, not an excerpt — it needs at least
25 seconds of speech on each side of the valley before it will call two
clusters, so a few minutes of audio will read as one.

The verdicts are heuristics, not proof. They were calibrated against two
known files: *Essentials of Practice* (processed, two clusters) and *Right
Effort* (raw, one cluster). Treat a borderline result as a prompt to listen,
not as an answer.

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

## Environment notes

- `huggingface.co`, Google hosts and the ElevenLabs API are blocked by the
  egress policy. `github.com` and `raw.githubusercontent.com` are reachable,
  which is why the models come from the k2-fsa release mirror.
- Images pasted into a conversation reach the assistant as vision content and
  never land on disk. **Zip them** to get the actual bytes through.
- Containers are temporary. This directory is the durable part.
