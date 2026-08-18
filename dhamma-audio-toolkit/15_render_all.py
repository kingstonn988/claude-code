import sys, os, json, re, glob, subprocess
sys.path.insert(0,'/tmp')
from bigcard import card
SIDES=json.load(open('/tmp/photos/sides.json'))
PHOTOS=sorted(SIDES)                       # p01..p10
T=json.load(open('/tmp/titles/dual.json'))
OUT='/tmp/final_out'; os.makedirs(OUT,exist_ok=True)
ILL='<>:"/\\|?*'
def safe(s):
    s=''.join(c for c in s if c not in ILL)
    return re.sub(r'\s+',' ',s).strip().rstrip('. ')
srcs={}
for d in ('/tmp/qa','/tmp/final','/tmp/out_solo'):
    for f in glob.glob(d+'/*.mp4'): srcs[os.path.basename(f)[:-4]]=f
# one photo per talk, cycled
talks=sorted({re.sub(r'_(part\d+_of_\d+|\d+)$','',k) for k in srcs})
pick={t:PHOTOS[i%len(PHOTOS)] for i,t in enumerate(talks)}
done=err=0
for key in sorted(srcs):
    if key not in T: continue
    talk=re.sub(r'_(part\d+_of_\d+|\d+)$','',key)
    ph=pick[talk]; side=SIDES[ph]
    idx=re.search(r'(\d+)$',key)
    n=int(idx.group(1)) if idx else 0
    m=re.search(r'part(\d+)_of_(\d+)',key)
    if m: n=int(m.group(1))
    name="%02d %s"%(n,safe(T[key]["file"]))
    out=os.path.join(OUT,name+".mp4")
    if os.path.exists(out): done+=1; continue
    cp='/tmp/_card.png'
    try: card('/tmp/photos/%s.png'%ph, T[key]["card"], cp, side=side)
    except Exception as e:
        print("CARD FAIL",key,e,flush=True); err+=1; continue
    r=subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','2','-i',cp,
        '-i',srcs[key],'-map','0:v','-map','1:a','-c:v','libx264','-tune','stillimage',
        '-preset','medium','-crf','30','-r','2','-pix_fmt','yuv420p',
        '-x264-params','keyint=3000:min-keyint=3000:scenecut=0',
        '-c:a','copy','-shortest','-movflags','+faststart',out],capture_output=True,text=True)
    if r.returncode!=0:
        print("FFMPEG FAIL",key,r.stderr[:150],flush=True); err+=1; continue
    mb=os.path.getsize(out)/1048576
    done+=1
    if done%25==0: print("  %d done"%done,flush=True)
    if mb>=30: print("  OVERSIZE %.1f MiB  %s"%(mb,name),flush=True)
print("FINISHED  rendered=%d errors=%d"%(done,err))
