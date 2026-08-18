#!/usr/bin/env python3
"""Propose passages to cut, for a human to approve.

Not every talk has questions, and most have material that does not belong in
the published version: arranging things, greetings, tea and coffee, someone
arriving, dead air while the recorder runs. This finds candidates and writes
them to cuts.json with `"keep": true` set on every one.

You then review cuts.json, flip the ones you want removed to "keep": false,
and run 04_trim_and_join.py. Nothing is ever removed without that step.

Usage:  python3 03_propose_cuts.py <talk.mp3> [workdir]
"""
import sys, os, json, subprocess
import numpy as np

SRC = sys.argv[1]
WORK = sys.argv[2] if len(sys.argv) > 2 else "work"
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

LONG_SILENCE = 6.0     # dead air longer than this is a candidate
KEEP_PAUSE   = 2.0     # what a trimmed pause is shortened to

db = np.load(os.path.join(WORK, "db25.npy"))
segs = json.load(open(os.path.join(WORK, "segs.json")))


def mmss(t):
    return "%d:%02d" % (int(t) // 60, int(t) % 60)


# ---- 1. dead air -----------------------------------------------------------
cands, prev = [], 0.0
for s in segs:
    if s["s"] - prev > LONG_SILENCE:
        cands.append({"kind": "dead air", "s": round(prev + 0.6, 2),
                      "e": round(s["s"] - 0.6, 2), "text": "",
                      "why": "%.0fs of silence" % (s["s"] - prev), "keep": True})
    prev = s["e"]

# ---- 2. transcribe, so passages can be judged by content -------------------
tr_path = os.path.join(WORK, "transcript.json")
if not os.path.exists(tr_path):
    print("No transcript yet -- run 02_transcribe.py first for content-based candidates.")
    transcript = []
else:
    transcript = json.load(open(tr_path))

# Words that tend to mark administrative talk rather than teaching. These only
# raise a candidate for review; they never cause a cut on their own.
MARKERS = ("recording", "microphone", "tape", "battery", "can you hear",
           "is it on", "tea", "coffee", "lunch", "meal", "o'clock", "tomorrow",
           "see you", "goodbye", "excuse me", "come in", "sit down", "the door",
           "the light", "photograph", "camera")

for r in transcript:
    low = r["t"].lower()
    hits = [m for m in MARKERS if m in low]
    if hits:
        cands.append({"kind": "possible chitchat", "s": round(r["s"], 2),
                      "e": round(r["e"], 2), "text": r["t"][:220],
                      "why": "mentions: " + ", ".join(hits), "keep": True})

cands.sort(key=lambda c: c["s"])
json.dump(cands, open(os.path.join(WORK, "cuts.json"), "w"), indent=1)

print("%d candidates written to %s/cuts.json\n" % (len(cands), WORK))
for c in cands:
    print("%-18s %s - %s  (%s)" % (c["kind"], mmss(c["s"]), mmss(c["e"]), c["why"]))
    if c["text"]:
        print("    %s" % c["text"])
print("\nEvery candidate is marked \"keep\": true. Set \"keep\": false on the ones")
print("to remove, then run:  python3 04_trim_and_join.py %s %s" % (SRC, WORK))
