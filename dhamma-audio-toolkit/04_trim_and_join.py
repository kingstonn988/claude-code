#!/usr/bin/env python3
"""Remove the approved passages and rejoin the talk seamlessly.

Two things make a join inaudible:
  - cut inside silence, not mid-word: each boundary is nudged to the quietest
    point within a short search window
  - equal-power crossfade across the seam, so the room tone does not jump

Dead-air regions are shortened to KEEP_PAUSE rather than closed completely --
a talk with every breath removed sounds hurried and unnatural.

Usage:  python3 04_trim_and_join.py <talk.mp3> [workdir] [out.wav]
"""
import sys, os, json
import numpy as np
import soundfile as sf

WORK = sys.argv[2] if len(sys.argv) > 2 else "work"
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(WORK, "joined.wav")

XFADE = 0.12       # seconds of crossfade across each seam
SEARCH = 0.60      # how far to hunt for a quiet spot to cut on
KEEP_PAUSE = 2.0   # dead air is shortened to this, not removed outright

x, sr = sf.read(os.path.join(WORK, "full.wav"), dtype="float32")
db = np.load(os.path.join(WORK, "db25.npy"))
cuts = [c for c in json.load(open(os.path.join(WORK, "cuts.json"))) if not c.get("keep", True)]
if not cuts:
    print("Nothing marked for removal. Set \"keep\": false on the passages you want cut.")
    sys.exit(0)


def quietest(t):
    """Nudge a cut point to the quietest 25 ms frame nearby, so it lands in silence."""
    lo = max(0, int((t - SEARCH) / 0.025))
    hi = min(len(db), int((t + SEARCH) / 0.025))
    return t if hi <= lo else (lo + int(np.argmin(db[lo:hi]))) * 0.025


spans = []
for c in cuts:
    a, b = quietest(c["s"]), quietest(c["e"])
    if c["kind"] == "dead air":          # shorten rather than close entirely
        b = max(a, b - KEEP_PAUSE)
    if b > a:
        spans.append((a, b))
spans.sort()

merged = []
for a, b in spans:
    if merged and a <= merged[-1][1] + 0.05:
        merged[-1][1] = max(merged[-1][1], b)
    else:
        merged.append([a, b])

n = int(XFADE * sr)
fi = np.linspace(0, 1, n, dtype=np.float32) ** 0.5      # equal power
fo = fi[::-1]
pieces, pos, removed = [], 0.0, 0.0
for a, b in merged:
    head = x[int(pos * sr):int(a * sr)]
    if len(head) > n:
        head = head.copy()
        head[-n:] *= fo
    pieces.append(head)
    removed += b - a
    pos = b
tail = x[int(pos * sr):]
if len(tail) > n:
    tail = tail.copy()
    tail[:n] *= fi
pieces.append(tail)

out = np.concatenate(pieces)
sf.write(OUT, out, sr, subtype="FLOAT")
print("removed %d passages, %.1f min" % (len(merged), removed / 60))
print("%.1f min -> %.1f min" % (len(x) / sr / 60, len(out) / sr / 60))
print("written to", OUT)
