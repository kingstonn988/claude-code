import sys,os,json,re,subprocess,glob
sys.path.insert(0,'/tmp')
from bigcard import card
SIDES=json.load(open('/tmp/photos/sides.json')); PHOTOS=sorted(SIDES)
T=json.load(open('/tmp/titles/dual.json')); m=json.load(open('/tmp/file2talk.json'))
ILL='<>:"/\\|?*'
def safe(s): return re.sub(r'\s+',' ',''.join(c for c in s if c not in ILL)).strip().rstrip('. ')
talks=sorted({t for t,_ in m.values()})
pick={t:PHOTOS[i%len(PHOTOS)] for i,t in enumerate(talks)}
srcs={}
for d in ('/tmp/qa','/tmp/final','/tmp/out_solo'):
    for f in glob.glob(d+'/*.mp4'): srcs[os.path.basename(f)[:-4]]=f
def outname(key):
    talk=re.sub(r'_(part\d+_of_\d+|\d+)$','',key)
    i=re.search(r'(\d+)$',key); n=int(i.group(1)) if i else 0
    pm=re.search(r'part(\d+)_of_',key)
    if pm: n=int(pm.group(1))
    return '/tmp/final_out/%02d %s.mp4'%(n,safe(T[key]["file"])), talk
def splice(key, cut_start, cut_end):
    out,talk=outname(key); src=srcs[key]
    XF=0.5
    af=("[0:a]atrim=0:%.2f,asetpts=N/SR/TB,afade=t=out:st=%.2f:d=%.2f[a0];"
        "[0:a]atrim=%.2f,asetpts=N/SR/TB,afade=t=in:st=0:d=%.2f[a1];"
        "[a0][a1]concat=n=2:v=0:a=1[a]")%(cut_start,cut_start-XF,XF,cut_end,XF)
    tmp='/tmp/_spliced.m4a'
    r=subprocess.run(['ffmpeg','-v','error','-y','-i',src,'-filter_complex',af,'-map','[a]',
                      '-c:a','aac','-b:a','80k',tmp],capture_output=True,text=True)
    if r.returncode: print("audio fail",r.stderr[:200]); return
    cp='/tmp/_c3.png'; card('/tmp/photos/%s.png'%pick[talk], T[key]["card"], cp, side=SIDES[pick[talk]])
    r=subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','2','-i',cp,'-i',tmp,
        '-map','0:v','-map','1:a','-c:v','libx264','-tune','stillimage','-preset','medium','-crf','30',
        '-r','2','-pix_fmt','yuv420p','-x264-params','keyint=3000:min-keyint=3000:scenecut=0',
        '-c:a','copy','-shortest','-movflags','+faststart',out],capture_output=True,text=True)
    if r.returncode: print("mux fail",r.stderr[:200]); return
    d=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',out],
                     capture_output=True,text=True).stdout.strip()
    print("%-34s cut %.1f-%.1f min  ->  %.1f min  %.1f MiB"%(key,cut_start/60,cut_end/60,
          float(d)/60,os.path.getsize(out)/1048576))
if __name__=='__main__':
    splice("Freedom_in_Dhamma_part2_of_4", 603.0, 855.0)
