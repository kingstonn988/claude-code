#!/usr/bin/env python3
"""Render finished videos: a still card over the talk audio.

With exchanges.json present, produces one video per question-and-answer
exchange plus an opening talk. Without it, produces a single video of the
whole talk -- which is what a solo talk with no audience questions needs.

Topic titles come from topics.json (a list of strings, one per piece) if it
exists; otherwise pieces are numbered.

Usage:
  python3 07_make_videos.py <workdir> <photo.png> "<Talk Title>" <outdir> [audio.wav]
"""
import sys, os, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WORK, PHOTO, TITLE, OUTDIR = sys.argv[1:5]
AUDIO = sys.argv[5] if len(sys.argv) > 5 else os.path.join(WORK, "full.wav")
W, H = 1920, 1080
PART_MINUTES = 22          # keeps each file comfortably under the 30 MiB limit
OCHRE, CREAM, MUTED = (0xdd, 0x9a, 0x45), (0xf8, 0xf3, 0xea), (0xcd, 0xbe, 0xab)
D = "/usr/share/fonts/truetype/dejavu/"
LB = "/usr/share/fonts/truetype/liberation/"
os.makedirs(OUTDIR, exist_ok=True)
cards = os.path.join(WORK, "cards")
os.makedirs(cards, exist_ok=True)

f_kick = ImageFont.truetype(D + "DejaVuSans-Bold.ttf", 26)
f_who = ImageFont.truetype(LB + "LiberationSerif-Italic.ttf", 36)
f_big = ImageFont.truetype(D + "DejaVuSerif.ttf", 66)
f_sm = ImageFont.truetype(D + "DejaVuSerif.ttf", 54)

src = Image.open(PHOTO).convert("RGB")
sc = max(W / src.width, H / src.height)
im = src.resize((round(src.width * sc), round(src.height * sc)), Image.LANCZOS)
im = im.crop(((im.width - W) // 2, (im.height - H) // 2,
              (im.width - W) // 2 + W, (im.height - H) // 2 + H))
dim = Image.new("L", (1, H))
px = dim.load()
for y in range(H):                       # light overall, weighted to the text area
    px[0, y] = int(35 + 185 * max(0.0, (y / H - 0.30) / 0.70) ** 1.7)
base = im.copy()
base.paste(Image.new("RGB", (W, H), (9, 7, 5)), (0, 0), dim.resize((W, H)))


def track(d, xy, s, f, fill, sp):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + sp


def wrap(d, s, f, mw):
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= mw:
            cur = t
        else:
            out.append(cur); cur = w
    if cur:
        out.append(cur)
    return out


def card(path, label, topic):
    img = base.copy()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 10, H], fill=OCHRE)
    f = f_big
    lines = wrap(d, topic, f, W - 340)
    if len(lines) > 2:
        f = f_sm
        lines = wrap(d, topic, f, W - 340)
    lh = int(f.size * 1.34)
    top = H - 150 - lh * len(lines)
    track(d, (150, top - 150), "AJAHN PANYAVADDHO", f_kick, MUTED, 7)
    d.text((150, top - 104), label, font=f_who, fill=OCHRE)
    y = top
    for ln in lines:
        d.text((150, y), ln, font=f, fill=CREAM)
        y += lh
    img.save(path)


ex_path = os.path.join(WORK, "exchanges.json")
if os.path.exists(ex_path):
    items = json.load(open(ex_path))["items"]
else:
    import soundfile as sf
    info = sf.info(AUDIO)
    items = [{"n": 0, "kind": "talk", "s": 0.0, "e": info.frames / info.samplerate, "q": []}]

topics = []
tp = os.path.join(WORK, "topics.json")
if os.path.exists(tp):
    topics = json.load(open(tp))

# one static gain for the whole talk: to -14 LUFS, but never past -1 dBTP
p1 = subprocess.run(["ffmpeg", "-v", "info", "-hide_banner", "-i", AUDIO, "-af",
                     "loudnorm=I=-14:TP=-1.0:LRA=20:print_format=json", "-f", "null", "-"],
                    capture_output=True, text=True)
import re
j = json.loads(re.findall(r'\{[^{}]*"input_i"[\s\S]*?\}', p1.stderr)[-1])
gain = min(-14.0 - float(j["input_i"]), -1.0 - float(j["input_tp"]))
print("talk gain %+.2f dB" % gain)

for k, it in enumerate(items):
    n = it["n"]
    label = "Opening Talk" if (it["kind"] == "talk" and len(items) > 1) else (
        "Talk" if it["kind"] == "talk" else "Question and Answer")
    topic = topics[k] if k < len(topics) else (
        TITLE if it["kind"] == "talk" else "Question %d" % n)
    cp = os.path.join(cards, "%02d.png" % n)
    card(cp, label, topic)
    slug = "%02d_%s" % (n, "".join(c if c.isalnum() else "_" for c in topic)[:48].strip("_"))
    # Long pieces are cut into parts: chat delivery caps at 30 MiB, and at
    # roughly 1.1 MB per minute that is about 22 minutes of video.
    total = it["e"] - it["s"]
    nparts = max(1, int(np.ceil(total / (PART_MINUTES * 60))))
    for p in range(nparts):
        a = it["s"] + p * total / nparts
        d = total / nparts
        name = slug if nparts == 1 else "%s_part%d_of_%d" % (slug, p + 1, nparts)
        out = os.path.join(OUTDIR, name + ".mp4")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "1",
            "-i", cp, "-ss", str(a), "-t", str(d), "-i", AUDIO,
            "-af", "volume=%.3fdB" % gain,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-r", "30",
            "-x264-params", "keyint=1800:min-keyint=1800:scenecut=0:bframes=3",
            "-c:a", "aac", "-b:a", "128k", "-ac", "1", "-ar", "44100",
            "-metadata", "title=%s" % topic, "-metadata", "artist=Ajahn Panyavaddho",
            "-metadata", "album=%s" % TITLE,
            "-movflags", "+faststart", "-shortest", out], capture_output=True, text=True)
        print(("  ok  %-50s %5.1f MiB" % (name, os.path.getsize(out) / 1048576))
              if not r.returncode else "  FAIL %s %s" % (name, r.stderr[-200:]), flush=True)
