#!/usr/bin/env python3
"""Work out where each question-and-answer exchange starts and ends.

An exchange runs from just before a question to just after the answer that
follows it. Boundaries land in silence: the start is pulled back to a short
lead-in before the question (never into the previous answer), and the end sits
shortly after the teacher's last words before the next question.

Anything before the first question is treated as the opening talk.

Usage:  python3 06_split_exchanges.py <workdir>
"""
import sys, os, json
import numpy as np

WORK = sys.argv[1]
LEAD_IN, TAIL, JOIN = 2.5, 1.5, 2.5
# A published exchange is a question plus a real answer. Anything much shorter
# is a brief interjection -- "yes", a murmur, a half-sentence aside -- and
# belongs with the exchange it interrupts rather than in a video of its own.
MIN_EXCHANGE = 100.0

# A question has to be an utterance, not a fragment: long enough to be speech,
# clearly below the teacher, and clearly ABOVE the noise floor. Without that
# last condition the detector fires on room noise -- an early version found 81
# "questions" in a talk that has about 17, most of them one-second fragments at
# -69 dB (noise) or right at the teacher's own level as he trailed off.
MIN_Q       = 2.5    # seconds; a real question is not shorter than this
BELOW_TEACHER = 12.0 # dB below the teacher to count as a questioner
ABOVE_FLOOR   = 10.0 # dB above the noise floor, else it is not speech at all

segs = json.load(open(os.path.join(WORK, "segs.json")))
lv = json.load(open(os.path.join(WORK, "levels.json")))
db = np.load(os.path.join(WORK, "db25.npy"))
teacher = lv["teacher_dbfs"]
floor = float(np.percentile(db, 3))
hi, lo = teacher - BELOW_TEACHER, floor + ABOVE_FLOOR
print("teacher %.1f dBFS, noise floor %.1f -- questions sought between %.1f and %.1f"
      % (teacher, floor, lo, hi))
dur = max(s["e"] for s in segs)

runs = []
for s in segs:
    faint = lo < s["odb"] < hi
    if runs and runs[-1]["faint"] == faint and s["s"] - runs[-1]["e"] <= JOIN:
        runs[-1]["e"] = s["e"]
        runs[-1]["sp"] += s["e"] - s["s"]
        runs[-1]["odb"].append(s["odb"])
    else:
        runs.append({"faint": faint, "s": s["s"], "e": s["e"],
                     "sp": s["e"] - s["s"], "odb": [s["odb"]]})


def prune(rs):
    """Drop faint runs too short to be a question. Only faint runs -- applying
    the minimum to the teacher's runs as well merges his short remarks into
    whatever precedes them and destroys the structure."""
    out = []
    for r in rs:
        # span, not summed speech: a question broken into short bursts by the
        # voice detector still spans long enough to be a question
        if r["faint"] and (r["e"] - r["s"]) < MIN_Q and out:
            out[-1]["e"] = r["e"]
            continue
        if out and out[-1]["faint"] == r["faint"]:
            out[-1]["e"] = r["e"]
            out[-1]["sp"] += r["sp"]
            out[-1]["odb"] += r["odb"]
            continue
        out.append(r)
    return out


for _ in range(3):
    runs = prune(runs)
qi = [i for i, r in enumerate(runs) if r["faint"]]
if not qi:
    print("No question runs found."); sys.exit(1)

starts = []
for i in qi:
    prev_end = runs[i - 1]["e"] if i > 0 else 0.0
    lo, hi = prev_end + 0.35, runs[i]["s"] - 0.2
    starts.append(max(0.0, min(max(lo, runs[i]["s"] - LEAD_IN), hi)
                      if lo <= hi else (prev_end + runs[i]["s"]) / 2))

items = []
first_loud_end = max([r["e"] for r in runs if not r["faint"] and r["e"] <= starts[0]] + [0])
if starts[0] > 30:                                  # an opening worth keeping
    items.append({"n": 0, "kind": "talk", "s": 0.0,
                  "e": round(min(first_loud_end + TAIL, starts[0]), 2), "q": []})
for k, i in enumerate(qi):
    st = starts[k]
    nxt = starts[k + 1] if k + 1 < len(starts) else dur
    ends = [r["e"] for r in runs if not r["faint"] and st < r["e"] <= nxt]
    items.append({"n": k + 1, "kind": "qa", "s": round(st, 2),
                  "e": round(min(max(ends) + TAIL, nxt), 2) if ends else round(nxt, 2),
                  "q": [[round(runs[i]["s"], 2), round(runs[i]["e"], 2),
                         round(float(np.median(runs[i]["odb"])), 2)]]})
merged = []
for it in items:
    if merged and it["kind"] == "qa" and it["e"] - it["s"] < MIN_EXCHANGE:
        merged[-1]["e"] = it["e"]
        merged[-1]["q"] += it["q"]
    else:
        merged.append(it)
offset = 0 if merged and merged[0]["kind"] == "talk" else 1
for i, it in enumerate(merged):
    it["n"] = i + offset
items = merged

json.dump({"items": items, "teacher_dbfs": lv["teacher_dbfs"]},
          open(os.path.join(WORK, "exchanges.json"), "w"), indent=1)


def mm(t):
    return "%d:%02d" % (int(t) // 60, int(t) % 60)


print("%d pieces (%d raw questions merged to %d)" % (len(items), len(qi), sum(1 for i in items if i["kind"]=="qa")))
for it in items:
    q = "  question %s-%s at %.0f dB" % (mm(it["q"][0][0]), mm(it["q"][0][1]),
                                         it["q"][0][2]) if it["q"] else ""
    print("  %2d %-4s %s -> %s  (%s)%s" % (it["n"], it["kind"], mm(it["s"]),
                                           mm(it["e"]), mm(it["e"] - it["s"]), q))
