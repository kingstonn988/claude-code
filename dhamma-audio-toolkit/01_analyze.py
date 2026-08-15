#!/usr/bin/env python3
"""Diagnose a talk before doing anything to it.

Answers three questions:
  1. Has this file already been processed (limited / noise-suppressed)?
  2. What is the source quality actually capable of?
  3. Do the questioners separate from the teacher by level?

(3) is the one that decides everything downstream. Two clusters with a gap
between them means the questions can be found and raised automatically.
One broad hump means they can't -- see README.

Usage:  python3 01_analyze.py talk.mp3 [workdir]
"""
import sys, os, json, subprocess
import numpy as np

SRC = sys.argv[1]
WORK = sys.argv[2] if len(sys.argv) > 2 else "work"
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(WORK, exist_ok=True)


def run(*a):
    subprocess.run(list(a), check=True)


def probe(src):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=sample_rate,channels:format=duration,bit_rate",
         "-of", "default=nw=1", src], capture_output=True, text=True).stdout
    return dict(l.split("=") for l in out.strip().splitlines() if "=" in l)


print("== source ==")
info = probe(SRC)
sr_src = int(info.get("sample_rate", 0))
print("  sample rate %s Hz   bitrate %s bps   %.1f min" % (
    info.get("sample_rate"), info.get("bit_rate"), float(info["duration"]) / 60))
if sr_src < 22050:
    print("  ! low sample rate: nothing above %d Hz exists in this file" % (sr_src // 2))

full = os.path.join(WORK, "full.wav")
w16 = os.path.join(WORK, "w16.wav")
w16n = os.path.join(WORK, "w16n.wav")
run("ffmpeg", "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", "44100",
    "-c:a", "pcm_f32le", full)
run("ffmpeg", "-v", "error", "-y", "-i", full, "-ac", "1", "-ar", "16000",
    "-c:a", "pcm_s16le", w16)
# level-flattened copy: only for speech detection, never for output
run("ffmpeg", "-v", "error", "-y", "-i", w16, "-af",
    "highpass=f=70,dynaudnorm=f=200:g=17:p=0.9:m=40:s=8",
    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", w16n)

import soundfile as sf
x, sr = sf.read(full, dtype="float32")
H = int(0.025 * sr)
nf = len(x) // H
db = 20 * np.log10(np.sqrt((x[:nf * H].reshape(nf, H) ** 2).mean(1)) + 1e-12)
np.save(os.path.join(WORK, "db25.npy"), db)

peak = 20 * np.log10(np.abs(x).max())
speech = float(np.median(db[db >= np.percentile(db, 60)]))
floor = float(np.percentile(db, 3))
spread = float(db[db < np.percentile(db, 10)].std())
# short-term crest: loudest frames vs typical speech frames. Absolute peak is
# no good here -- one stray transient hides an otherwise heavily limited file.
crest = float(np.percentile(db, 99) - speech)

print("\n== has it been processed already? ==")
print("  peak            %6.2f dBFS %s" % (peak, "  ! clipped" if peak > 0 else ""))
print("  speech level    %6.1f dBFS" % speech)
print("  noise floor     %6.1f dBFS" % floor)
print("  speech-to-noise %6.1f dB" % (speech - floor))
print("  short-term crest%6.1f dB   (>7 = untouched, <6 = limited)" % crest)
print("  floor spread    %6.2f dB   (<1.5 = gated or noise-suppressed)" % spread)
verdict = []
if crest < 6.5:
    verdict.append("limited/normalized")
if spread < 1.5:
    verdict.append("noise-suppressed")
print("  -> %s" % (", ".join(verdict) if verdict else "looks untouched"))

print("\n== speaker separation ==")
import sherpa_onnx, wave

w = wave.open(w16n, "rb")
vsr = w.getframerate()
v = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
c = sherpa_onnx.VadModelConfig()
c.silero_vad.model = os.path.join(MODELS, "silero_vad.onnx")
c.silero_vad.threshold = 0.35
c.silero_vad.min_silence_duration = 0.35
c.silero_vad.min_speech_duration = 0.2
c.silero_vad.max_speech_duration = 25.0
c.sample_rate = 16000
vad = sherpa_onnx.VoiceActivityDetector(c, buffer_size_in_seconds=120)
segs = []


def drain():
    while not vad.empty():
        s = vad.front
        st = s.start / vsr
        segs.append({"s": round(st, 3), "e": round(st + len(s.samples) / vsr, 3)})
        vad.pop()


for i in range(0, len(v), 512):
    vad.accept_waveform(v[i:i + 512])
    drain()
vad.flush()
drain()

for s in segs:                      # measure each utterance on the ORIGINAL levels
    win = db[int(s["s"] / 0.025):int(s["e"] / 0.025)]
    s["odb"] = float(np.median(win[win >= np.percentile(win, 60)])) if len(win) else -99.0
json.dump(segs, open(os.path.join(WORK, "segs.json"), "w"))

d = np.array([s["odb"] for s in segs])
L = np.array([s["e"] - s["s"] for s in segs])
print("  %d utterances, %.1f min of speech" % (len(segs), L.sum() / 60))
print("\n  seconds of speech per 2.5 dB bin:")
hist, edges = np.histogram(d, bins=np.arange(-55, -5, 2.5), weights=L)
for i, val in enumerate(hist):
    if val > 0.4:
        print("   %6.1f..%6.1f %7.1fs %s" % (edges[i], edges[i + 1], val, "#" * int(val / 12)))

# What matters is not whether the distribution is bimodal, but simply whether
# there is a meaningful amount of speech well below the teacher. Testing for
# two distinct humps was wrong: talks with several questioners at several
# distances fill the valley in and read as one cluster, even when they plainly
# contain questions 15-25 dB down. Calibrated against six recordings.
FAINT_BELOW = 10.0   # dB below the teacher to count as "not the teacher"
MIN_RUN     = 2.0    # a candidate must be at least this long to be an utterance
MIN_TOTAL   = 20.0   # and there must be at least this much of it in total

faint_thr = speech - FAINT_BELOW
runs, total = [], 0.0
for s_ in segs:
    if s_["odb"] >= faint_thr:
        continue
    if runs and s_["s"] - runs[-1][1] <= 3.0:
        runs[-1][1] = s_["e"]
    else:
        runs.append([s_["s"], s_["e"]])
runs = [r for r in runs if r[1] - r[0] >= MIN_RUN]
total = sum(r[1] - r[0] for r in runs)

print("\n  teacher at %.1f dBFS; speech below %.1f dBFS:" % (speech, faint_thr))
print("  %d passages, %.0f seconds in total" % (len(runs), total))
if runs:
    lo = min(np.median([x["odb"] for x in segs
                        if x["s"] >= r[0] and x["e"] <= r[1]] or [0]) for r in runs)
    print("  quietest passage sits about %.0f dB below the teacher" % abs(lo - speech))
json.dump({"teacher_dbfs": round(speech, 2), "faint_thr": round(faint_thr, 2),
           "faint_runs": [[round(a, 2), round(b, 2)] for a, b in runs]},
          open(os.path.join(WORK, "levels.json"), "w"))

if total >= MIN_TOTAL:
    print("\n  -> FAINT SPEECH PRESENT. Very likely audience questions.")
    print("     Check what they are before processing:")
    print("       python3 02_transcribe.py %s %s" % (SRC, WORK))
    print("     Then raise them with:")
    print("       python3 05_boost_questions.py %s %s" % (SRC, WORK))
else:
    print("\n  -> NO FAINT SPEECH. Reads as a solo talk with no audience questions.")
    print("     Nothing to raise. Split by content if you want it in sections.")
