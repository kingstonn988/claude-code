#!/bin/bash
# Q&A split.  $1=workdir (already analysed)  $2=talk title
cd /home/user/claude-code/dhamma-audio-toolkit
W="$1"; TITLE="$2"; SRC="$3"
# Regenerate the working audio if a previous run cleaned it up, so the
# pipeline can be restarted without hand-holding.
if [ ! -f "$W/full.wav" ] && [ -n "$SRC" ]; then
  echo "  (re-decoding $W)"
  mkdir -p "$W"
  python3 01_analyze.py "$SRC" "$W" > "$W/reanalyze.log" 2>&1
fi
if [ ! -f "$W/full.wav" ]; then echo "  SKIP $TITLE -- no audio"; exit 0; fi
python3 - "$W" <<'PY'
import sys,json,numpy as np,soundfile as sf,subprocess
W=sys.argv[1]
x,sr=sf.read(W+'/full.wav',dtype='float32')
segs=json.load(open(W+'/segs.json')); lv=json.load(open(W+'/levels.json'))
thr=lv['faint_thr']; TARGET=lv['teacher_dbfs']-6.0; H=int(0.025*sr)
runs=[]
for s in segs:
    if s['odb']>=thr: continue
    if runs and s['s']-runs[-1][1]<=2.5: runs[-1][1]=s['e']
    else: runs.append([s['s'],s['e']])
runs=[r for r in runs if r[1]-r[0]>=0.9]
for qs,qe in runs:
    a,b=max(0.0,qs-0.55),min(len(x)/sr,qe+0.55); i0=int(a*sr)
    seg=x[i0:int(b*sr)].copy(); nf=len(seg)//H
    if nf<4: continue
    d=20*np.log10(np.sqrt((seg[:nf*H].reshape(nf,H)**2).mean(1))+1e-9)
    loud=d>thr; k=6
    if loud.any(): loud=np.convolve(loud.astype(float),np.ones(2*k+1),mode='same')>0
    quiet=~loud
    core=quiet.copy(); core[:int((qs-a)/0.025)]=False; core[int((qe-a)/0.025):]=False
    dq=d[core] if core.sum()>=4 else d[quiet]
    if len(dq)<2: continue
    G=float(np.clip(TARGET-float(np.median(dq[dq>=np.percentile(dq,60)])),0,26))
    if G<1.0: continue
    g=np.where(quiet,G,0.0); w=5; win=np.hanning(w+2)[1:-1]; win/=win.sum()
    g=np.convolve(np.pad(g,(w,w),mode='edge'),win,mode='same')[w:w+nf]
    gs=np.interp(np.arange(len(seg)),np.arange(nf)*H+H/2,g).astype(np.float32)
    sf.write('/tmp/_qi.wav',seg*(10**(gs/20)).astype(np.float32),sr,subtype='FLOAT')
    subprocess.run(['ffmpeg','-v','error','-y','-i','/tmp/_qi.wav','-af',
        'highpass=f=75,alimiter=limit=0.891:attack=4:release=60:level=disabled',
        '-c:a','pcm_f32le','/tmp/_qo.wav'],check=True)
    p,_=sf.read('/tmp/_qo.wav',dtype='float32'); L=min(len(p),len(seg)); p=p[:L]
    r=int(0.30*sr); wg=np.ones(L,dtype=np.float32)
    wg[:r]=np.linspace(0,1,r,dtype=np.float32)**2; wg[-r:]=np.linspace(1,0,r,dtype=np.float32)**2
    x[i0:i0+L]=p*wg+x[i0:i0+L]*(1-wg)
sf.write(W+'/boosted.wav',x,sr,subtype='FLOAT')
PY
# skip a talk whose videos are already all present
ALREADY=$(ls /tmp/qa/"$(echo "$TITLE" | tr " " "_" | tr -d "'")"_*.mp4 2>/dev/null | wc -l)
if [ "$ALREADY" -gt 0 ] && [ -f "$W/exchanges.json" ]; then
  WANT=$(python3 -c "import json;print(len(json.load(open('$W/exchanges.json'))['items']))")
  if [ "$ALREADY" -ge "$WANT" ]; then echo "  already done: $TITLE"; exit 0; fi
fi
python3 06_split_exchanges.py "$W" > "$W/exchanges.txt" 2>&1
python3 -u /tmp/qa_render.py "$W" "$TITLE"
rm -f "$W"/full.wav "$W"/boosted.wav "$W"/w16.wav "$W"/w16n.wav
