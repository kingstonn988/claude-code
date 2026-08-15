#!/usr/bin/env python3
"""Raise faint audience questions to near the teacher's level.

Only for talks where 01_analyze.py reported TWO CLUSTERS.

The method is Audacity's Amplify, applied automatically: one flat gain per
question, no compression and no noise reduction. The one refinement is that
loud moments inside a question window -- the teacher answering back into the
mic, a knock -- keep their original level. A flat gain across the whole
window would turn those into a blast. This is the equivalent of selecting
only the quiet passage by hand before hitting Amplify.

Deliberately lands the questions a few dB UNDER the teacher: matching him
exactly needs more gain, and gain costs noise.

Usage:  python3 05_boost_questions.py <talk.mp3> [workdir]
"""
import sys, os, json, subprocess
import numpy as np
import soundfile as sf

WORK = sys.argv[2] if len(sys.argv) > 2 else "work"

# Thresholds come from 01_analyze.py, which measured where this recording's
# two clusters actually divide. Falls back to sensible defaults if absent.
_lv = {}
if os.path.exists(os.path.join(WORK, "levels.json")):
    _lv = json.load(open(os.path.join(WORK, "levels.json")))
QUIET_THR = _lv.get("split_dbfs", -20.0)   # utterances below this are questioners
LOUD_THR  = QUIET_THR                      # inside a window, leave anything above alone
UNDER     =   3.0    # how far below the teacher to land
MAXGAIN   =  26.0    # ceiling; beyond this the noise is worse than the gain is worth
PAD, XF, DILATE = 0.55, 0.12, 0.15

x, sr = sf.read(os.path.join(WORK, "full.wav"), dtype="float32")
db = np.load(os.path.join(WORK, "db25.npy"))
segs = json.load(open(os.path.join(WORK, "segs.json")))
H = int(0.025 * sr)

teacher = float(np.median([s["odb"] for s in segs if s["odb"] >= QUIET_THR]))
target = teacher - UNDER
print("teacher %.1f dBFS -> target for questions %.1f dBFS" % (teacher, target))

# group consecutive quiet utterances into question windows
runs = []
for s in segs:
    if s["odb"] >= QUIET_THR:
        continue
    if runs and s["s"] - runs[-1][1] <= 2.5:
        runs[-1][1] = s["e"]
    else:
        runs.append([s["s"], s["e"]])
runs = [r for r in runs if r[1] - r[0] >= 0.9]
print("%d question windows" % len(runs))

report = []
for qs, qe in runs:
    a, b = max(0.0, qs - PAD), min(len(x) / sr, qe + PAD)
    i0 = int(a * sr)
    seg = x[i0:int(b * sr)].copy()
    nf = len(seg) // H
    d = 20 * np.log10(np.sqrt((seg[:nf * H].reshape(nf, H) ** 2).mean(1)) + 1e-9)

    loud = d > LOUD_THR
    k = int(round(DILATE / 0.025))
    if loud.any():                                   # widen so transients are fully spared
        loud = np.convolve(loud.astype(float), np.ones(2 * k + 1), mode="same") > 0
    quiet = ~loud

    core = quiet.copy()
    core[:int((qs - a) / 0.025)] = False
    core[int((qe - a) / 0.025):] = False
    dq = d[core] if core.sum() >= 4 else d[quiet]
    level = float(np.median(dq[dq >= np.percentile(dq, 60)]))
    gain = float(np.clip(target - level, 0, MAXGAIN))

    g = np.where(quiet, gain, 0.0)
    wlen = int(round(XF / 0.025)) | 1
    win = np.hanning(wlen + 2)[1:-1]
    win /= win.sum()
    g = np.convolve(np.pad(g, (wlen, wlen), mode="edge"), win, mode="same")[wlen:wlen + nf]
    gs = np.interp(np.arange(len(seg)), np.arange(nf) * H + H / 2, g).astype(np.float32)

    tmp_i = os.path.join(WORK, "_q_in.wav")
    tmp_o = os.path.join(WORK, "_q_out.wav")
    sf.write(tmp_i, seg * (10 ** (gs / 20)).astype(np.float32), sr, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_i, "-af",
                    "highpass=f=75,alimiter=limit=0.891:attack=4:release=60:level=disabled",
                    "-c:a", "pcm_f32le", tmp_o], check=True)
    p, _ = sf.read(tmp_o, dtype="float32")
    L = min(len(p), len(seg))
    p = p[:L]

    r = int(0.30 * sr)                               # blend back in, inside silence
    wgt = np.ones(L, dtype=np.float32)
    wgt[:r] = np.linspace(0, 1, r, dtype=np.float32) ** 2
    wgt[-r:] = np.linspace(1, 0, r, dtype=np.float32) ** 2
    x[i0:i0 + L] = p * wgt + x[i0:i0 + L] * (1 - wgt)
    report.append((qs, qe, level, gain))

for f in ("_q_in.wav", "_q_out.wav"):
    p = os.path.join(WORK, f)
    if os.path.exists(p):
        os.remove(p)

out = os.path.join(WORK, "boosted.wav")
sf.write(out, x, sr, subtype="FLOAT")
print("\npeak after: %.2f dBFS" % (20 * np.log10(np.abs(x).max())))
print("\n   start     was     gain")
for qs, qe, level, gain in report:
    print("  %3d:%02d  %6.1f   +%4.1f dB" % (int(qs) // 60, int(qs) % 60, level, gain))
print("\nwritten to", out)
