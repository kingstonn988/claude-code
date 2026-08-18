"""Find the empty dark panel in a ready-made template."""
from PIL import Image
import numpy as np

W, H = 1080, 1920

def crop916(path):
    im = Image.open(path).convert('RGB')
    sc = max(W / im.width, H / im.height)
    r = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
    x, y = (r.width - W) // 2, (r.height - H) // 2
    return r.crop((x, y, x + W, y + H))

def _runs(row):
    """longest run of True in a bool row -> (start, end)"""
    best = (0, 0, 0); s = None
    for i, v in enumerate(row):
        if v and s is None: s = i
        elif not v and s is not None:
            if i - s > best[0]: best = (i - s, s, i)
            s = None
    if s is not None and len(row) - s > best[0]: best = (len(row) - s, s, len(row))
    return best

def detect(path, thresh=70, min_w=620, top=760, inset=26):
    im = crop916(path)
    a = np.asarray(im.convert('L'), np.int16)
    dark = a < thresh
    rows = []
    for y in range(top, H):
        w, s, e = _runs(dark[y])
        if w >= min_w: rows.append((y, s, e))
    if not rows: return None, im
    ys = [r[0] for r in rows]
    # keep the largest contiguous band of qualifying rows
    band, cur = [], [rows[0]]
    for prev, r in zip(rows, rows[1:]):
        if r[0] - prev[0] <= 3: cur.append(r)
        else:
            if len(cur) > len(band): band = cur
            cur = [r]
    if len(cur) > len(band): band = cur
    y0, y1 = band[0][0], band[-1][0]
    x0 = int(np.median([r[1] for r in band]))
    x1 = int(np.median([r[2] for r in band]))
    return (x0 + inset, y0 + inset, x1 - inset, y1 - inset), im

if __name__ == '__main__':
    import glob, sys
    from PIL import ImageDraw
    fs = sorted(glob.glob('/tmp/shorts/gpt/*/*.png'))
    tw, th = 190, 338
    sheet = Image.new('RGB', (10 * (tw + 8) + 8, 2 * (th + 8) + 8), (12, 10, 9))
    d0 = ImageDraw.Draw(sheet)
    for k, f in enumerate(fs):
        box, im = detect(f)
        d = ImageDraw.Draw(im)
        if box:
            d.rectangle(box, outline=(255, 60, 60), width=6)
            print('%2d  %s  panel %s  %dx%d' % (k + 1, f.split('/')[-1][:28], box,
                                                box[2] - box[0], box[3] - box[1]))
        else:
            print('%2d  %s  NO PANEL FOUND' % (k + 1, f.split('/')[-1][:28]))
        px = 8 + (k % 10) * (tw + 8); py = 8 + (k // 10) * (th + 8)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (px, py))
        d0.text((px + 4, py + 4), str(k + 1), fill=(255, 230, 150))
    sheet.save('/tmp/shorts/panels.png')
