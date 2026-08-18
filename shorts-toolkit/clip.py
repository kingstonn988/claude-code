"""Build one finished clip: photo + header + verse + music."""
import sys, os, json, glob, shutil, subprocess
sys.path.insert(0, '/tmp/shorts')
from PIL import Image, ImageFilter
import numpy as np
import shorts as S, beats as B

def brightness(photo):
    """how light the photo is where the verse will sit, after grading"""
    im = Image.open(photo).convert('RGB'); w, h = im.size
    sc = max(1080 / w, 1920 / h)
    r = im.resize((round(w * sc), round(h * sc)), Image.LANCZOS)
    x, y = (r.width - 1080) // 2, (r.height - 1920) // 2
    a = np.asarray(r.crop((x, y, x + 1080, y + 1920)), np.float32)
    a[..., 0] *= 1.10; a[..., 2] *= 0.86
    g = a.mean(axis=2, keepdims=True); a = g + (a - g) * 0.86; a *= 0.80
    L = np.clip(a, 0, 255).astype(np.uint8).mean(axis=2)[900:1600]
    return float(L.mean()), float(np.percentile(L, 90))

PHOTOS = sorted(glob.glob('/tmp/shorts/photos_all/*'))
MUSIC  = sorted(glob.glob('/tmp/shorts/music_lib/*.m4a'))
LOGO   = '/tmp/shorts/assets/logo_clean.png'
ITEMS  = {i['n']: i for i in json.load(open('/tmp/shorts/book/items.json'))}

HEADER = dict(
    brand='NO AJAHN CHAH', brand_font='PlayfairDisplay', brand_var='Black',
    brand_size=58, brand_track=1, brand_y=58, brand_t=0.0,
    sub='REFLECTIONS', sub_font='Cinzel', sub_var='Regular',
    sub_size=27, sub_track=2, sub_y=138, sub_t=0.0,
    logo=LOGO, logo_w=600, logo_pos='top', logo_y=196,
    top_scrim=(0.72, 780),
)

BACKDROPS = {n: '/tmp/shorts/assets/bg_%s.mp4' % n
             for n in ('rays_gold', 'rays_wide', 'rays_amber',
                       'mist_gold', 'mist_deep', 'embers')}

def config(n, photo, emph=None, pace=1.45, box=None, backdrop=None):
    it = ITEMS[n]
    text = it['text']
    if emph:                       # emph: the exact phrase to set in capitals
        text_marked = text.replace(emph, '*%s*' % emph)
    else:
        text_marked = text
    mode, lines = B.plan(text_marked)
    if backdrop:
        box = False if box is None else box
    else:
        mean, p90 = brightness(photo)
        if box is None:
            box = not (mean < 70 and p90 < 150)   # dark photo -> no box needed
    boxed = dict(box=1.0, box_border=3, box_pad=(46, 40), box_t=0.0,
                 box_in=0.75, box_dot=26, outline=0.06, glow=0.0, t0=0.95)
    bare = dict(box=0.0, outline=0.095, glow=0.34, glow_r=40, t0=0.35)
    lit  = dict(box=0.0, outline=0.0, glow=0.42, glow_r=38, t0=0.35,
                top_scrim=(0.35, 600))
    common = dict(text_pop=0.84, pop_overshoot=1.3)
    look = boxed if box else (lit if backdrop else bare)
    c = dict(HEADER, lines=lines, anim=mode, recap_text=text_marked,
             font='PlayfairDisplay', var='Black',
             size=132 if mode == 'rise' else 108, recap_size=88,
             per_line_fit=(mode == 'rise'),
             scrim=None, attrib=None,
             shift=250, recap_maxh=620, margin=96,
             pace=pace, dur_in=0.5,
             bg=(('video', BACKDROPS[backdrop]) if backdrop else ('image', photo)),
             zoom=1.12, warm=0.055,
             bg_bright=(-0.02 if backdrop else -0.10),
             bg_sat=(1.0 if backdrop else 0.88))
    c.update(look); c.update(common)
    if mode == 'rise':
        c['shimmer'] = 0.45
    return c, mode, lines

def add_music(video, track, out, gain=0.9, fade=1.5):
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'csv=p=0', video], capture_output=True,
                             text=True).stdout.strip())
    af = ('[1:a]atrim=0:%.2f,asetpts=N/SR/TB,afade=t=in:st=0:d=%.2f,'
          'afade=t=out:st=%.2f:d=%.2f,volume=%.2f[a]'
          % (d, fade, max(0.1, d - fade), fade, gain))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-stream_loop', '-1',
                    '-i', track, '-filter_complex', af, '-map', '0:v', '-map', '[a]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', out],
                   check=True)
    return out

def build(n, photo_i, music_i, emph=None, out=None, box=None, backdrop=None):
    photo = PHOTOS[photo_i - 1] if photo_i else PHOTOS[0]
    c, mode, lines = config(n, photo, emph, box=box, backdrop=backdrop)
    tmp = '/tmp/shorts/_clip_%d.mp4' % n
    dur = S.render(c, tmp)
    out = out or '/tmp/shorts/clip_%03d.mp4' % n
    if music_i is None:
        shutil.move(tmp, out)
    else:
        add_music(tmp, MUSIC[music_i], out)
        os.remove(tmp)
    return out, mode, len(lines), dur

if __name__ == '__main__':
    mi = [i for i, f in enumerate(MUSIC) if os.path.basename(f).startswith('f05')][0]
    print(build(25, None, mi, 'This is the finish', backdrop='rays_amber',
                out='/tmp/shorts/amber25_music.mp4'), flush=True)
