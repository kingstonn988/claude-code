"""Check candidate background photos for the Shorts format.

Usage: python3 check_bg.py <dir-or-files...>
Reports, per image: whether it survives the 9:16 crop plus the slow push-in,
how bright and how busy it is behind the text, and what to do about it.
"""
import sys, os, glob
from PIL import Image, ImageFilter
import numpy as np

W, H = 1080, 1920
ZOOM = 1.16                      # the Ken Burns push
NEED_W, NEED_H = int(W * ZOOM), int(H * ZOOM)
TEXT_TOP, TEXT_BOT = 560, 1560   # where the verse sits
LOGO_TOP, LOGO_BOT = 96, 520     # logo + NO AJAHN CHAH

def crop916(im):
    sc = max(W / im.width, H / im.height)
    r = im.resize((max(W, round(im.width * sc)), max(H, round(im.height * sc))), Image.LANCZOS)
    x, y = (r.width - W) // 2, (r.height - H) // 2
    return r.crop((x, y, x + W, y + H))

def report(path):
    try:
        im = Image.open(path).convert('RGB')
    except Exception as e:
        return path, 'unreadable (%s)' % e, []
    w, h = im.size
    notes, verdict = [], 'good'

    if w < NEED_W or h < NEED_H:
        sc = max(NEED_W / w, NEED_H / h)
        if sc > 1.6:
            verdict = 'too small'
            notes.append('%dx%d — needs %.1fx upscaling, will look soft' % (w, h, sc))
        else:
            notes.append('%dx%d — slight upscale (%.2fx), acceptable' % (w, h, sc))
    if w / h > 1.2:
        notes.append('landscape %.2f:1 — the 9:16 crop keeps only the middle %d%% of the width'
                     % (w / h, round(100 * (h * 9 / 16) / w)))
        if verdict == 'good': verdict = 'check crop'

    c = crop916(im)
    a = np.asarray(c.convert('L'), np.float32)
    band = a[TEXT_TOP:TEXT_BOT]
    lum = band.mean()
    busy = np.asarray(c.convert('L').filter(ImageFilter.FIND_EDGES), np.float32)[TEXT_TOP:TEXT_BOT].mean()
    top = a[LOGO_TOP:LOGO_BOT].mean()

    notes.append('behind the text: brightness %.0f/255, detail %.1f' % (lum, busy))
    if lum > 150:
        notes.append('bright — needs a heavy scrim, which will mute the picture')
        if verdict == 'good': verdict = 'bright'
    elif lum < 30:
        notes.append('very dark — the picture will barely read; fine if that is the intent')
    if busy > 14:
        notes.append('busy behind the text — blur it, or move the verse')
        if verdict == 'good': verdict = 'busy'
    if top > 165:
        notes.append('bright at the top — the logo may not read against it')
    return path, verdict, notes

def main(args):
    files = []
    for a in args:
        if os.path.isdir(a):
            for e in ('jpg', 'jpeg', 'png', 'webp', 'JPG', 'JPEG', 'PNG'):
                files += glob.glob(os.path.join(a, '**', '*.' + e), recursive=True)
        else:
            files.append(a)
    files = sorted(set(files))
    if not files:
        print('no images found'); return
    tally = {}
    for f in files:
        p, v, ns = report(f)
        tally[v] = tally.get(v, 0) + 1
        print('\n%-10s %s' % ('[' + v + ']', os.path.basename(p)))
        for n in ns: print('           ', n)
    print('\n%d images:' % len(files),
          ', '.join('%s %d' % (k, v) for k, v in sorted(tally.items())))

if __name__ == '__main__':
    main(sys.argv[1:] or ['.'])
