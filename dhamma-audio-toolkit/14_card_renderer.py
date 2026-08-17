from PIL import Image, ImageDraw, ImageFilter, ImageFont
W,H=1920,1080; OCHRE=(0xf0,0xbe,0x55)
D='/usr/share/fonts/truetype/dejavu/'
f_k=ImageFont.truetype(D+'DejaVuSans-Bold.ttf',26)
def qf(s): return ImageFont.truetype(D+'DejaVuSerif-Bold.ttf',s)
def wrapt(dr,s,f,mw):
    out=[];cur=""
    for wd in s.split():
        t=(cur+" "+wd).strip()
        if dr.textlength(t,font=f)<=mw: cur=t
        else:
            if cur: out.append(cur)
            cur=wd
    if cur: out.append(cur)
    return out
def track(dr,xy,s,f,fill,sp,sw,sf,right=False):
    x,y=xy
    if right: x-=sum(dr.textlength(c,font=f)+sp for c in s)-sp
    for ch in s: dr.text((x,y),ch,font=f,fill=fill,stroke_width=sw,stroke_fill=sf); x+=dr.textlength(ch,font=f)+sp

def card(photo,q,path,side='left',colfrac=0.42,maxh=0.86,maxlines=5):
    src=Image.open(photo).convert('RGB')
    sc=max(W/src.width,H/src.height)
    im=src.resize((round(src.width*sc),round(src.height*sc)),Image.LANCZOS)
    img=im.crop(((im.width-W)//2,(im.height-H)//2,(im.width-W)//2+W,(im.height-H)//2+H))
    M=96; COLW=int(W*colfrac); HB=int(H*maxh)
    g=Image.new('L',(W,1)); px=g.load(); edge=M+COLW+170
    for x in range(W):
        t=(1.0-(x/edge)) if side=='left' else (1.0-((W-1-x)/edge))
        px[x,0]=int(165*max(0.0,t)**1.25)
    img.paste(Image.new('RGB',(W,H),(6,5,4)),(0,0),g.resize((W,H)))
    dr=ImageDraw.Draw(img)
    # grow the type to the largest size that still fits the column and the height budget
    best=None
    for sz in range(215,25,-3):
        f=qf(sz); lines=wrapt(dr,q,f,COLW); lh=int(sz*1.16)
        if len(lines)<=maxlines and len(lines)*lh<=HB and all(dr.textlength(l,font=f)<=COLW for l in lines):
            best=(f,lines,lh,sz); break
    f,lines,lh,sz=best
    blk=len(lines)*lh; top=(H-blk)//2+10
    sh=Image.new('RGBA',(W,H),(0,0,0,0)); sd=ImageDraw.Draw(sh); y=top
    for ln in lines:
        x=M if side=='left' else W-M-dr.textlength(ln,font=f)
        sd.text((x,y),ln,font=f,fill=(0,0,0,165),stroke_width=16,stroke_fill=(0,0,0,165)); y+=lh
    img=Image.alpha_composite(img.convert('RGBA'),sh.filter(ImageFilter.GaussianBlur(18))).convert('RGB')
    dr=ImageDraw.Draw(img); y=top
    for i,ln in enumerate(lines):
        col=OCHRE if (len(lines)>1 and i==len(lines)-1) else (255,255,255)
        x=M if side=='left' else W-M-dr.textlength(ln,font=f)
        dr.text((x,y),ln,font=f,fill=col,stroke_width=max(5,sz//11),stroke_fill=(0,0,0)); y+=lh
    track(dr,(M if side=='left' else W-M,top-56),"AJAHN PANNAVADDHO",f_k,(255,255,255),7,4,(0,0,0),side=='right')
    dr.rectangle([0,0,11,H] if side=='left' else [W-11,0,W,H],fill=OCHRE)
    img.save(path); return sz,len(lines)
