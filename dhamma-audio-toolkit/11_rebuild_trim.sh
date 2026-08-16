#!/bin/bash
# $1=workdir  $2=title  $3=src  $4=approx cut seconds
set -e
cd /home/user/claude-code/dhamma-audio-toolkit
W="$1"; TITLE="$2"; SRC="$3"; CUT="$4"
cp "$W/exchanges.json" "$W/exchanges.orig.json" 2>/dev/null || true
python3 01_analyze.py "$SRC" "$W" > "$W/re.log" 2>&1
python3 /tmp/_boost.py "$W"
python3 - "$W" "$CUT" <<'PY'
import sys,json,numpy as np,soundfile as sf
W,cut=sys.argv[1],float(sys.argv[2])
x,sr=sf.read(W+'/boosted.wav',dtype='float32')
H=int(0.025*sr)
lo,hi=int((cut-6)*sr),int((cut+6)*sr); lo=max(0,lo)
seg=x[lo:hi]; nf=len(seg)//H
d=np.sqrt((seg[:nf*H].reshape(nf,H)**2).mean(1))
snap=(lo+int(np.argmin(d))*H)/sr
j=json.load(open(W+'/exchanges.orig.json')); items=j['items']
items=[it for it in items if it['e']>snap+30]
items[0]['s']=snap
for i,it in enumerate(items): it['n']=i
j['items']=items
json.dump(j,open(W+'/exchanges.json','w'))
print("  cut at %.1f s (%.1f min)"%(snap,snap/60))
for it in items[:3]: print("  %02d %7.1f -> %7.1f (%.1f min)"%(it['n'],it['s'],it['e'],(it['e']-it['s'])/60))
PY
slug=$(echo "$TITLE" | tr ' ' '_' | tr -d "'")
rm -f "/tmp/qa/${slug}_"*.mp4
python3 -u /tmp/qa_render.py "$W" "$TITLE"
rm -f "$W"/full.wav "$W"/boosted.wav "$W"/w16.wav "$W"/w16n.wav
