#!/usr/bin/env python3
"""Find natural break points so a long talk can be published in parts.

Cuts land in the longest pause near each target boundary, so a part ends
where the teacher actually stopped rather than mid-sentence. Silence is
measured, so this does not depend on transcript quality at all.

If no decent pause can be found near a boundary, the talk is left whole --
better one long video than a cut through a sentence.

Usage:  python3 07_natural_breaks.py <workdir> [target_minutes]
"""
import sys, os, json
import numpy as np

WORK = sys.argv[1]
TARGET = float(sys.argv[2]) * 60 if len(sys.argv) > 2 else 22 * 60
SEARCH = 180.0      # how far either side of a target to hunt for a pause
MIN_GAP = 1.6       # a pause shorter than this is not a break
MIN_PART = 6 * 60   # do not leave a stub at the end

segs = json.load(open(os.path.join(WORK, "segs.json")))
dur = max(s["e"] for s in segs)

gaps = []
prev = 0.0
for s in segs:
    if s["s"] - prev >= MIN_GAP:
        gaps.append((prev, s["s"], s["s"] - prev))
    prev = s["e"]

if dur <= TARGET * 1.35:
    print("%.1f min -- short enough to leave whole" % (dur / 60))
    json.dump([[0.0, round(dur, 2)]], open(os.path.join(WORK, "parts.json"), "w"))
    sys.exit(0)

n = max(2, int(round(dur / TARGET)))
cuts = []
for k in range(1, n):
    tgt = dur * k / n
    near = [g for g in gaps if abs((g[0] + g[1]) / 2 - tgt) <= SEARCH]
    if not near:
        print("  no pause within %.0f min of %s -- leaving whole" % (SEARCH / 60, tgt))
        json.dump([[0.0, round(dur, 2)]], open(os.path.join(WORK, "parts.json"), "w"))
        sys.exit(0)
    best = max(near, key=lambda g: g[2])          # the longest pause nearby
    cuts.append(((best[0] + best[1]) / 2, best[2]))

parts, pos = [], 0.0
for c, glen in cuts:
    parts.append([round(pos, 2), round(c, 2)])
    pos = c
parts.append([round(pos, 2), round(dur, 2)])
if parts[-1][1] - parts[-1][0] < MIN_PART and len(parts) > 1:
    parts[-2][1] = parts[-1][1]
    parts.pop()

json.dump(parts, open(os.path.join(WORK, "parts.json"), "w"))


def mm(t):
    return "%d:%02d" % (int(t) // 60, int(t) % 60)


print("%.1f min -> %d parts" % (dur / 60, len(parts)))
for i, (a, b) in enumerate(parts):
    g = ""
    for c, glen in cuts:
        if abs(c - b) < 0.01:
            g = "   (cut in a %.1fs pause)" % glen
    print("  part %d  %s - %s   %s%s" % (i + 1, mm(a), mm(b), mm(b - a), g))
