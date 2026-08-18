"""Pick the text treatment from the background itself."""
from PIL import Image, ImageFilter
import numpy as np

W, H = 1080, 1920
TEXT_TOP, TEXT_BOT = 820, 1600

def _crop(path):
    im = Image.open(path).convert('RGB')
    sc = max(W / im.width, H / im.height)
    r = im.resize((max(W, round(im.width * sc)), max(H, round(im.height * sc))), Image.LANCZOS)
    x, y = (r.width - W) // 2, (r.height - H) // 2
    return r.crop((x, y, x + W, y + H))

def measure(path):
    c = _crop(path)
    g = c.convert('L')
    band = np.asarray(g, np.float32)[TEXT_TOP:TEXT_BOT]
    busy = np.asarray(g.filter(ImageFilter.FIND_EDGES), np.float32)[TEXT_TOP:TEXT_BOT].mean()
    top = np.asarray(g, np.float32)[96:800].mean()
    return dict(lum=float(band.mean()), busy=float(busy), top=float(top))

def treatment(path):
    """Returns the cfg keys to merge for this background."""
    m = measure(path)
    lum, busy = m['lum'], m['busy']
    if lum < 72:
        t = dict(halo=0.0, glow=0.60, scrim=(1230, 470, 0.45))
    elif lum < 118:
        t = dict(halo=0.55, halo_r=30, glow=0.40, scrim=(1230, 470, 0.38))
    elif lum < 165:
        t = dict(halo=0.85, halo_r=34, glow=0.22, scrim=(1230, 470, 0.28))
    else:
        t = dict(halo=0.90, halo_r=34, halo_passes=2, glow=0.15, scrim=None)
    if busy > 14:
        t['halo'] = min(1.0, t['halo'] + 0.25)
        t['bg_blur'] = True
    t['_measured'] = m
    return t
