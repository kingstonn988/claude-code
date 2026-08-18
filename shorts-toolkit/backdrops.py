"""Generated backdrops — abstract light, not photographs and not AI imagery.
Every one is dark and warm, so text sits on it without a box."""
import numpy as np, math, os, subprocess, shutil
from PIL import Image, ImageDraw, ImageFilter

W, H = 540, 960          # rendered small, ffmpeg scales up; it is all soft anyway
FPS  = 30

def _grid(W, H):
    return np.mgrid[0:H, 0:W].astype(np.float32)

def rays(t, cx=0.5, cy=0.34, n1=7, n2=13, hue=(205, 132, 34), warmth=1.0):
    yy, xx = _grid(W, H)
    px, py = W * cx, H * cy
    r = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
    ang = np.arctan2(yy - py, xx - px)
    glow = np.exp(-(r / (W * 0.62)) ** 2)
    b = 0.5 + 0.5 * np.sin(ang * n1 + t * 0.30)
    b *= 0.5 + 0.5 * np.sin(ang * n2 - t * 0.19)
    v = glow * (0.42 + 0.58 * b) * np.exp(-(r / (W * 1.05)) ** 2)
    img = np.zeros((H, W, 3), np.float32)
    for i, c in enumerate(hue):
        img[..., i] = (14 if i == 0 else 10 if i == 1 else 6) + c * v * warmth
    return img

def mist(t, hue=(190, 120, 44)):
    rng = np.random.default_rng(4)
    yy, xx = _grid(W, H)
    v = np.zeros((H, W), np.float32)
    for k, (gw, gh, amp, sp) in enumerate(((3, 6, 0.6, 0.6), (6, 11, 0.3, 1.1), (11, 21, 0.15, 1.9))):
        a = rng.random((gh, gw)).astype(np.float32)
        im = Image.fromarray((np.concatenate([a, a], 1) * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC)
        arr = np.asarray(im, np.float32) / 255.0
        off = int((t * sp * 12) % W)
        v += amp * arr[:, off:off + W]
    v = (v - v.min()) / (v.max() - v.min() + 1e-6)
    band = np.exp(-((yy - H * 0.42) / (H * 0.42)) ** 2)
    v = v * band
    img = np.zeros((H, W, 3), np.float32)
    for i, c in enumerate(hue):
        img[..., i] = 8 + c * v
    return img

def embers(t, hue=(210, 140, 50)):
    yy, xx = _grid(W, H)
    r = np.sqrt((xx - W * 0.5) ** 2 + (yy - H * 0.62) ** 2)
    base = np.exp(-(r / (W * 0.85)) ** 2) * 0.55
    img = np.zeros((H, W, 3), np.float32)
    for i, c in enumerate(hue):
        img[..., i] = 8 + c * base * 0.5
    return img

def add_motes(img, t, n=48, seed=7, size=(4, 15), warm=(255, 206, 120)):
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7))
    dr = ImageDraw.Draw(im, 'RGBA')
    rng = np.random.default_rng(seed)
    for i in range(n):
        mx = rng.uniform(0, W); my = rng.uniform(0, H)
        ms = rng.uniform(*size); sp = rng.uniform(.12, .5)
        al = rng.uniform(.15, .6); ph = rng.uniform(0, 6.28)
        y = (my - t * sp * 18) % (H + 80) - 40
        x = mx + 18 * math.sin(t * 0.5 + ph)
        a = int(255 * al * (0.45 + 0.55 * math.sin(t * 1.1 + ph) ** 2) * 0.5)
        dr.ellipse((x - ms, y - ms, x + ms, y + ms), fill=warm + (a,))
    return im.filter(ImageFilter.GaussianBlur(1.5))

STYLES = {
    'rays_gold':  lambda t: add_motes(rays(t), t),
    'rays_wide':  lambda t: add_motes(rays(t, cy=0.30, n1=5, n2=9), t, n=36, size=(6, 20)),
    'rays_amber': lambda t: add_motes(rays(t, hue=(224, 118, 26)), t, n=54, size=(3, 11)),
    'mist_gold':  lambda t: add_motes(mist(t), t, n=30, size=(5, 18), seed=12),
    'mist_deep':  lambda t: add_motes(mist(t, hue=(150, 92, 30)), t, n=40, size=(4, 14), seed=19),
    'embers':     lambda t: add_motes(embers(t), t, n=120, size=(2, 8), seed=23),
}

def still(name, t=3.0):
    return STYLES[name](t)

def clip(name, seconds=12, out=None, crf=21):
    d = '/tmp/shorts/_bgf'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    n = int(seconds * FPS)
    for f in range(n):
        STYLES[name](f / FPS).save('%s/%05d.png' % (d, f))
    out = out or '/tmp/shorts/assets/bg_%s.mp4' % name
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', d + '/%05d.png',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf),
                    '-pix_fmt', 'yuv420p', out], check=True)
    shutil.rmtree(d, ignore_errors=True)
    return out
