import sys,os,json,re,subprocess
sys.path.insert(0,'/tmp')
from bigcard import card
SIDES=json.load(open('/tmp/photos/sides.json')); PHOTOS=sorted(SIDES)
T=json.load(open('/tmp/titles/dual.json'))
m=json.load(open('/tmp/file2talk.json'))
ILL='<>:"/\\|?*'
def safe(s): return re.sub(r'\s+',' ',''.join(c for c in s if c not in ILL)).strip().rstrip('. ')
talks=sorted({t for t,_ in m.values()})
pick={t:PHOTOS[i%len(PHOTOS)] for i,t in enumerate(talks)}
# key -> seconds to keep
CUTS={
 "Knowing_Ones_Character_13":148,
 "Advice_for_New_Monks_05":118,
 "Renouncing_the_World_14":160,
 "Fragment_of_a_Teaching":425,
 "Introduction_to_the_Sangha_part4_of_4":1010,
 "The_Heart_vs_the_Brain_03":380,
 "00_Kamma_and_Rebirth_part2_of_2":785,
}
srcs={}
for d in ('/tmp/qa','/tmp/final','/tmp/out_solo'):
    import glob
    for f in glob.glob(d+'/*.mp4'): srcs[os.path.basename(f)[:-4]]=f
for key,keep in CUTS.items():
    talk=re.sub(r'_(part\d+_of_\d+|\d+)$','',key)
    idx=re.search(r'(\d+)$',key); n=int(idx.group(1)) if idx else 0
    pm=re.search(r'part(\d+)_of_',key)
    if pm: n=int(pm.group(1))
    name="%02d %s"%(n,safe(T[key]["file"]))
    out='/tmp/final_out/%s.mp4'%name
    old=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',srcs[key]],
                       capture_output=True,text=True).stdout.strip()
    cp='/tmp/_c2.png'; card('/tmp/photos/%s.png'%pick[talk], T[key]["card"], cp, side=SIDES[pick[talk]])
    r=subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','2','-i',cp,
        '-t',str(keep),'-i',srcs[key],'-map','0:v','-map','1:a',
        '-af','afade=t=out:st=%.1f:d=2.0'%(keep-2.0),
        '-c:v','libx264','-tune','stillimage','-preset','medium','-crf','30','-r','2',
        '-pix_fmt','yuv420p','-x264-params','keyint=3000:min-keyint=3000:scenecut=0',
        '-c:a','aac','-b:a','80k','-shortest','-movflags','+faststart',out],capture_output=True,text=True)
    if r.returncode: print("FAIL",key,r.stderr[:120]); continue
    mb=os.path.getsize(out)/1048576
    print("%-38s %5.1f -> %4.1f min   %4.1f MiB"%(key,float(old)/60,keep/60,mb))
