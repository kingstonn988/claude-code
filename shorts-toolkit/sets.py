"""Two publishing sets: same words, different look, one per channel."""
import sys, os, json, shutil, subprocess
sys.path.insert(0, '/tmp/shorts')
import clip as C, shorts as S, beats as B, panel as P
import glob

TEMPLATES = sorted(glob.glob('/tmp/shorts/gpt/*/*.png'))
SAFE_BOT = 1620

def template_config(n, template, emph=None, pace=1.45):
    """set C — the ready-made templates: header and panel are in the picture,
    so only the words are drawn, fitted to the panel we detect."""
    it = C.ITEMS[n]
    text = it['text']
    if emph: text = text.replace(emph, '*%s*' % emph)
    mode, lines = B.plan(text)
    box, _ = P.detect(template)
    x0, y0, x1, y1 = box
    y1 = min(y1, SAFE_BOT)
    cy = (y0 + y1) // 2
    return dict(lines=lines, anim=mode, recap_text=text,
                font='PlayfairDisplay', var='Black',
                size=132 if mode == 'rise' else 108, recap_size=92,
                per_line_fit=(mode == 'rise'),
                margin=(S.W - (x1 - x0)) // 2 + 24,
                shift=cy - S.H // 2,
                recap_maxh=(y1 - y0) - 40,
                box=0.0, outline=0.0, glow=0.34, glow_r=34, scrim=None,
                attrib=None, brand=None, sub=None, logo=None,
                t0=0.35, pace=pace, dur_in=0.5, text_pop=0.84,
                bg=('image', template), zoom=1.08, warm=0.0,
                bg_bright=-0.02, bg_sat=1.0), mode, lines

SETS = {
    # channel A — generated light, no box, silent
    'A': dict(backdrop_cycle=['rays_amber', 'rays_gold', 'rays_wide'],
              photo=False, music=None, box=False,
              folder='/tmp/shorts/publish/setA'),
    # channel B — photographs, box where the picture needs it, music
    'B': dict(backdrop_cycle=None,
              photo=True, music=['f05', 'm22', 'm12', 'f02', 'm26'], box=None,
              folder='/tmp/shorts/publish/setB'),
    # channel C — the ready-made templates, words dropped into the panel
    'C': dict(template=True, music=['m12', 'm26', 'm22'],
              folder='/tmp/shorts/publish/setC'),
}

def safe(t):
    for a, b in [('"', "'"), ('?', ''), (':', ' -'), ('/', '-'), ('\\', '-'),
                 ('*', ''), ('<', ''), ('>', ''), ('|', '-')]:
        t = t.replace(a, b)
    return ' '.join(t.split())[:110].rstrip(' .,-')

def title_for(it):
    """the sentence that carries the point — the last one, or the whole thing"""
    t = it['text'].strip().strip('“”"')
    parts = [p.strip() for p in t.replace('!', '.').replace('?', '.').split('.') if p.strip()]
    if not parts: return t
    best = max(parts, key=lambda p: (len(p.split()) >= 4, -abs(len(p.split()) - 9)))
    return safe(best)

def build_one(n, which, index, emph=None):
    cfg = SETS[which]
    os.makedirs(cfg['folder'], exist_ok=True)
    it = C.ITEMS[n]
    if cfg.get('template'):
        tpl = TEMPLATES[index % len(TEMPLATES)]
        conf, mode, lines = template_config(n, tpl, emph)
        out = os.path.join(cfg['folder'], '%s - Ajahn Chah.mp4' % title_for(it))
        tmp = out + '.tmp.mp4'
        S.render(conf, tmp)
        name = cfg['music'][index % len(cfg['music'])]
        mi = [i for i, f in enumerate(C.MUSIC) if os.path.basename(f).startswith(name)][0]
        C.add_music(tmp, C.MUSIC[mi], out)
        os.remove(tmp)
        return out
    backdrop = (cfg['backdrop_cycle'][index % len(cfg['backdrop_cycle'])]
                if cfg['backdrop_cycle'] else None)
    photo_i = (index % len(C.PHOTOS)) + 1 if cfg['photo'] else None
    mus = None
    if cfg['music']:
        name = cfg['music'][index % len(cfg['music'])]
        mus = [i for i, f in enumerate(C.MUSIC) if os.path.basename(f).startswith(name)][0]
    out = os.path.join(cfg['folder'], '%s - Ajahn Chah.mp4' % title_for(it))
    C.build(n, photo_i, mus, emph, out=out, box=cfg['box'], backdrop=backdrop)
    if mus is None:                       # silent set: make sure a quiet track is present
        tmp = out + '.tmp.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out,
                        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac',
                        '-b:a', '64k', '-shortest', tmp], check=True)
        shutil.move(tmp, out)
    return out

if __name__ == '__main__':
    for which in ('A', 'B', 'C'):
        print(which, build_one(7, which, 0), flush=True)
