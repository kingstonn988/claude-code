#!/usr/bin/env python3
"""Transcribe the talk with timestamps.

Whisper base.en is used because it is the largest model reachable here --
huggingface.co is blocked by the egress policy, and this is what the
k2-fsa GitHub mirror carries. On a clean recording it is good enough to
find question boundaries and name topics. On a poor one (low sample rate,
low bitrate, <20 dB signal-to-noise) it degrades badly and will repeat
phrases in a loop; treat that as a signal the file needs enhancing first.

YouTube's own captions are better than this. If the talk is going to
YouTube anyway, prefer downloading the .sbv and correcting it with
GLOSSARY.md.

Usage:  python3 02_transcribe.py <talk.mp3> [workdir] [n_jobs]
"""
import sys, os, json, subprocess
import numpy as np

SRC = sys.argv[1]
WORK = sys.argv[2] if len(sys.argv) > 2 else "work"
JOBS = int(sys.argv[3]) if len(sys.argv) > 3 else max(1, (os.cpu_count() or 4))
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
CHUNK = 22.0        # whisper takes 30 s at a time; leave headroom

if os.environ.get("SHARD") is None:
    import wave
    w = wave.open(os.path.join(WORK, "w16n.wav"), "rb")
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    H = int(0.02 * sr)
    nf = len(x) // H
    e = 20 * np.log10(np.sqrt((x[:nf * H].reshape(nf, H) ** 2).mean(1)) + 1e-9)
    dur, cuts, t = len(x) / sr, [0.0], 0.0
    while t < dur - 1.0:                     # cut chunks at the quietest nearby point
        tgt = min(t + CHUNK, dur)
        if dur - tgt < 4.0:
            cuts.append(dur); break
        lo, hi = int((tgt - 3.5) / 0.02), int((tgt + 3.5) / 0.02)
        ct = (lo + int(np.argmin(e[lo:hi]))) * 0.02
        if ct <= t + 5:
            ct = tgt
        cuts.append(round(ct, 3)); t = ct
    if cuts[-1] < dur:
        cuts.append(round(dur, 3))
    json.dump([[cuts[i], cuts[i + 1]] for i in range(len(cuts) - 1)],
              open(os.path.join(WORK, "chunks.json"), "w"))
    print("%d chunks; running %d workers" % (len(cuts) - 1, JOBS))
    procs = [subprocess.Popen([sys.executable, __file__, SRC, WORK, str(JOBS)],
             env={**os.environ, "SHARD": str(i)}) for i in range(JOBS)]
    for p in procs:
        p.wait()
    out = []
    for i in range(JOBS):
        out += json.load(open(os.path.join(WORK, "asr_%d.json" % i)))
    out.sort(key=lambda r: r["i"])
    db = np.load(os.path.join(WORK, "db25.npy"))
    for r in out:                            # tag each line with its original level
        win = db[int(r["s"] / 0.025):int(r["e"] / 0.025)]
        r["odb"] = round(float(np.median(win[win > np.percentile(win, 60)])), 1) if len(win) else -99
    json.dump(out, open(os.path.join(WORK, "transcript.json"), "w"))
    with open(os.path.join(WORK, "transcript.txt"), "w") as f:
        for r in out:
            f.write("%02d:%02d-%02d:%02d [%6.1f] %s\n" % (
                int(r["s"]) // 60, int(r["s"]) % 60, int(r["e"]) // 60, int(r["e"]) % 60,
                r["odb"], r["t"]))
    print("written to %s/transcript.txt" % WORK)
else:
    import wave, sherpa_onnx
    shard, M = int(os.environ["SHARD"]), os.path.join(MODELS, "sherpa-onnx-whisper-base.en")
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=os.path.join(M, "base.en-encoder.int8.onnx"),
        decoder=os.path.join(M, "base.en-decoder.int8.onnx"),
        tokens=os.path.join(M, "base.en-tokens.txt"),
        num_threads=1, decoding_method="greedy_search", language="en", task="transcribe")
    w = wave.open(os.path.join(WORK, "w16n.wav"), "rb")
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    res = []
    for i, (a, b) in enumerate(json.load(open(os.path.join(WORK, "chunks.json")))):
        if i % JOBS != shard:
            continue
        s = rec.create_stream()
        s.accept_waveform(sr, x[int(a * sr):int(b * sr)])
        rec.decode_stream(s)
        res.append({"i": i, "s": a, "e": b, "t": s.result.text.strip()})
    json.dump(res, open(os.path.join(WORK, "asr_%d.json" % shard), "w"))
