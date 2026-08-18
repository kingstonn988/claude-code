#!/usr/bin/env python3
"""Apply this speaker's vocabulary to a rough transcript.

Mechanical only: it fixes the Pali terms and names that ASR reliably mangles
in these talks, consistently across every file. It does NOT rewrite sentences
or recover passages the recogniser lost -- see GLOSSARY.md for why a corrected
YouTube transcript beats a corrected Whisper one.

Usage:  python3 08_correct_transcript.py <workdir> [out.txt]
"""
import sys, os, re

# Only high-confidence substitutions. Anything ambiguous is left alone -- a
# wrong "correction" is worse than a recognisable mis-hearing.
SUBS = [
    (r"\b(chelac[ei]s|chelates|keylaces|kilesis|qelasas|kelases|kaylaises|kilesals|chelays(orizer)?)\b", "kilesas"),
    (r"\b(khandas|kundas|candours|counters)\b", "khandhas"),
    (r"\b(nabano|nibana|nibbana)\b", "Nibbāna"),
    (r"\b(paracumbs?|paracoms?|parakams?|paracamals?|pericums?|parakamas?|paracumbers)\b", "parikamma"),
    (r"\b(pudhoe|bouto|buto|budhoe)\b", "Buddho"),
    (r"\b(samadhi|samaji|samadi)\b", "samādhi"),
    (r"\b(jhana)\b", "jhāna"),
    (r"\b(panyar|panya)\b", "paññā"),
    (r"\b(kamatana|kammatana|kammathana)\b", "kammaṭṭhāna"),
    (r"\b(dukker|ducro|dukkha)\b", "dukkha"),
    (r"\b(anapanasati)\b", "ānāpānasati"),
    (r"\b(sotapanna)\b", "sotāpanna"),
    (r"\b(arahant|arahat)\b", "arahant"),
    (r"\b(vinnana|vin[nñ]ana)\b", "viññāṇa"),
    (r"\b(sangha)\b", "Sangha"),
    (r"\b(dhamma|damma)\b", "Dhamma"),
    (r"\b(kiriya|crea)\b", "kiriya"),
    (r"(tuncha mahabore|thomas john mahabore|tanachan|thanachan|tanishana|"
     r"janet chan,? my boy|tuncha|tunc ha)", "Than Ajahn Mahā Boowa"),
    (r"\b(ajaan panya|ajahn pannavaddho|ajaan pannavaddho)\b", "Ajahn Panyavaddho"),
]

WORK = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(WORK, "transcript_corrected.txt")
text = open(os.path.join(WORK, "transcript.txt")).read()

counts = {}
for pat, rep in SUBS:
    text, n = re.subn(pat, rep, text, flags=re.I)
    if n:
        counts[rep] = counts.get(rep, 0) + n
open(OUT, "w").write(text)
print("%s -> %s" % (WORK, OUT))
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print("   %-24s %d" % (k, v))
print("   total %d substitutions" % sum(counts.values()))
