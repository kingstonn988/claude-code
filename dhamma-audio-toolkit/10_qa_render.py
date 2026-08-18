import sys, os, json, subprocess
from PIL import Image, ImageDraw, ImageFont
WORK, TITLE = sys.argv[1], sys.argv[2]
S='/tmp/claude-0/-home-user-claude-code/a2158284-aaa7-5636-a736-2b61262780bf/scratchpad'
OUT='/tmp/qa'; os.makedirs(OUT, exist_ok=True)
items=json.load(open(WORK+'/exchanges.json'))['items']
W,H=1920,1080
OCHRE=(0xdd,0x9a,0x45); CREAM=(0xf8,0xf3,0xea); MUTED=(0xe0,0xd2,0xbe)
D='/usr/share/fonts/truetype/dejavu/'; LB='/usr/share/fonts/truetype/liberation/'
f_k=ImageFont.truetype(D+'DejaVuSans-Bold.ttf',26); f_w=ImageFont.truetype(LB+'LiberationSerif-Italic.ttf',36)
f_b=ImageFont.truetype(D+'DejaVuSerif.ttf',66); f_s=ImageFont.truetype(D+'DejaVuSerif.ttf',54)
src=Image.open(S+'/photo3/img_clean.png').convert('RGB')   # the monks photo from the Q&A set
sc=max(W/src.width,H/src.height)
im=src.resize((round(src.width*sc),round(src.height*sc)),Image.LANCZOS)
im=im.crop(((im.width-W)//2,(im.height-H)//2,(im.width-W)//2+W,(im.height-H)//2+H))
v=Image.new('L',(1,H)); px=v.load()
for y in range(H): px[0,y]=int(35+185*max(0.0,(y/H-0.30)/0.70)**1.7)
im.paste(Image.new('RGB',(W,H),(9,7,5)),(0,0),v.resize((W,H)))
def track(dr,xy,s,f,fill,sp):
    x,y=xy
    for ch in s: dr.text((x,y),ch,font=f,fill=fill); x+=dr.textlength(ch,font=f)+sp
def wrap(dr,s,f,mw):
    out=[];cur=""
    for wd in s.split():
        t=(cur+" "+wd).strip()
        if dr.textlength(t,font=f)<=mw: cur=t
        else: out.append(cur); cur=wd
    if cur: out.append(cur)
    return out
slug=TITLE.replace(' ','_').replace("'","")
M=150
for it in items:
    img=im.copy(); dr=ImageDraw.Draw(img); dr.rectangle([0,0,10,H],fill=OCHRE)
    f=f_b; lines=wrap(dr,TITLE,f,W-2*M-40)
    if len(lines)>2: f=f_s; lines=wrap(dr,TITLE,f,W-2*M-40)
    lh=int(f.size*1.34); top=H-150-lh*len(lines)
    track(dr,(M,top-150),"AJAHN PANYAVADDHO",f_k,MUTED,7)
    dr.text((M,top-104),"Question and Answer" if it['kind']=='qa' else "Opening Talk",font=f_w,fill=OCHRE)
    y=top
    for ln in lines: dr.text((M,y),ln,font=f,fill=CREAM); y+=lh
    cp='%s/qc_%d.png'%(WORK,it['n']); img.save(cp)
    name="%s_%02d"%(slug,it['n'])
    out='%s/%s.mp4'%(OUT,name); d=it['e']-it['s']
    br='80k' if d>1500 else '96k'
    r=subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','1','-i',cp,
        '-ss',str(it['s']),'-t',str(d),'-i',WORK+'/boosted.wav',
        '-c:v','libx264','-preset','veryfast','-tune','stillimage','-crf','27',
        '-pix_fmt','yuv420p','-profile:v','high','-r','5','-g','250',
        '-c:a','aac','-b:a',br,'-ac','1','-ar','44100',
        '-metadata','title=%s'%TITLE,'-metadata','artist=Ajahn Panyavaddho',
        '-movflags','+faststart','-shortest',out],capture_output=True,text=True)
    if r.returncode: print("  FAIL",name,flush=True); continue
    ok=subprocess.run(['ffmpeg','-v','error','-i',out,'-f','null','-'],capture_output=True).returncode==0
    mb=os.path.getsize(out)/1048576
    print("  %-40s %5.1f MiB %d:%02d %s"%(name,mb,int(d)//60,int(d)%60,
        "OK" if (ok and mb<29) else "!! CHECK"),flush=True)
