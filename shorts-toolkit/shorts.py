"""Vertical Shorts renderer for Dhamma verses.

Text is drawn as a transparent PNG overlay sequence; the background (looping
video or a still with a slow Ken Burns push) is composited underneath by
ffmpeg. Reveal styles: rise / fade / type (typewriter) / deck (one line at a
time). Optional light sweep across the finished verse.
"""
import os, re, math, shutil, subprocess
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np

W, H, FPS = 1080, 1920, 30
FD = '/tmp/shorts/fonts/'
GOLD_TOP = (255, 240, 196)
GOLD_BOT = (240, 180, 84)
GLOW     = (255, 176, 56)
PAD      = 60


def font(name, size, var=None):
    f = ImageFont.truetype(FD + name + '.ttf', size)
    if var:
        try: f.set_variation_by_name(var)
        except Exception: pass
    return f

def gradient(c1, c2, y0, y1):
    g = np.zeros((H, W, 3), np.uint8)
    ys = np.clip((np.arange(H) - y0) / max(1, y1 - y0), 0, 1)[:, None]
    for i in range(3):
        g[:, :, i] = (np.array(c1)[i] * (1 - ys) + np.array(c2)[i] * ys).astype(np.uint8)
    return Image.fromarray(g, 'RGB').convert('RGBA')

def tinted(mask, src):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    im.paste(src, (0, 0), mask)
    return im

def solid(c):
    return Image.new('RGBA', (W, H), tuple(c) + (255,))

def ease_out(t):    return 1 - (1 - t) ** 3
def ease_back(t, k=1.5):
    """ease-out with a small overshoot, so the box settles rather than stops"""
    t = t - 1.0
    return t * t * ((k + 1) * t + k) + 1.0
def ease_in_out(t): return 3 * t * t - 2 * t * t * t

def measure(text, f):
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    return max(d.textlength(l, font=f) for l in text.split('\n'))

def wrap_to_width(text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if cur and measure(strip_emph(t), f) > maxw:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur: lines.append(cur)
    return rebalance(lines)

def rebalance(lines):
    """Close and reopen *emphasis* markers that a line break split apart."""
    out, open_ = [], False
    for ln in lines:
        if open_: ln = '*' + ln
        n = ln.count('*')
        if n % 2:
            ln = ln + '*'; open_ = True
        else:
            open_ = False
        out.append(ln)
    return out

def fit_block(text, name, var, cap, maxw, maxh, floor=30):
    """largest size whose wrapped block fits maxw x maxh"""
    s = cap
    while s > floor:
        f = font(name, s, var)
        ls = wrap_to_width(text, f, maxw)
        if len(ls) * int(s * 1.34) <= maxh: return s, f, ls
        s -= 2
    f = font(name, floor, var)
    return floor, f, wrap_to_width(text, f, maxw)

def fit(text, name, var, cap, maxw, floor=26):
    """largest size <= cap whose rendering of `text` fits maxw"""
    s = cap
    while s > floor:
        f = font(name, s, var)
        if measure(text, f) <= maxw: return s, f
        s -= 2
    return floor, font(name, floor, var)

def tile(text, f, stroke=0, spacing=None):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    sp = spacing if spacing is not None else int(f.size * 0.34)
    multi = '\n' in text
    bb = (d0.multiline_textbbox((0, 0), text, font=f, stroke_width=stroke,
                                spacing=sp, align='center')
          if multi else d0.textbbox((0, 0), text, font=f, stroke_width=stroke))
    w, h = int(bb[2] - bb[0] + 0.5), int(bb[3] - bb[1] + 0.5)
    t = Image.new('L', (w + 2 * PAD, h + 2 * PAD), 0)
    d = ImageDraw.Draw(t)
    if multi:
        d.multiline_text((PAD - bb[0], PAD - bb[1]), text, font=f, fill=255,
                         stroke_width=stroke, stroke_fill=255, spacing=sp, align='center')
    else:
        d.text((PAD - bb[0], PAD - bb[1]), text, font=f, fill=255,
               stroke_width=stroke, stroke_fill=255)
    return t, w, h

EMPH = re.compile(r'\*([^*]+)\*')

def strip_emph(text):
    return EMPH.sub(lambda m: m.group(1).upper(), text)

def tile_split(text, f, stroke=0, spacing=None, outline=0):
    """Render a line into two masks: ordinary text, and *emphasised* text
    (set in capitals). Segments keep their exact spacing and punctuation."""
    sp = spacing if spacing is not None else int(f.size * 0.34)
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    lines = text.split('\n')
    segs = []                      # per line: [(chunk, is_emph)]
    for ln in lines:
        parts, i = [], 0
        for m in EMPH.finditer(ln):
            if m.start() > i: parts.append((ln[i:m.start()], False))
            parts.append((m.group(1).upper(), True))
            i = m.end()
        if i < len(ln): parts.append((ln[i:], False))
        segs.append(parts or [('', False)])
    widths = [sum(d0.textlength(t, font=f) for t, _ in r) for r in segs]
    plain = strip_emph(text)
    bb = (d0.multiline_textbbox((0, 0), plain, font=f, stroke_width=stroke, spacing=sp)
          if len(lines) > 1 else d0.textbbox((0, 0), plain, font=f, stroke_width=stroke))
    w, h = int(max(widths) + 0.5), int(bb[3] - bb[1] + 0.5)
    a = Image.new('L', (w + 2 * PAD, h + 2 * PAD), 0)
    b = Image.new('L', (w + 2 * PAD, h + 2 * PAD), 0)
    o = Image.new('L', (w + 2 * PAD, h + 2 * PAD), 0)
    da, db, do = ImageDraw.Draw(a), ImageDraw.Draw(b), ImageDraw.Draw(o)
    lh = f.size + sp
    for li, r in enumerate(segs):
        x = PAD + (w - widths[li]) / 2.0
        y = PAD - bb[1] + li * lh
        for chunk, em in r:
            if chunk.strip():
                (db if em else da).text((x, y), chunk, font=f, fill=255)
                if outline:
                    do.text((x, y), chunk, font=f, fill=0,
                            stroke_width=outline, stroke_fill=255)
            x += d0.textlength(chunk, font=f)
    return a, b, o, w, h

def blend_into(canvas, m, x, y):
    cx0, cy0 = max(0, x), max(0, y)
    cx1, cy1 = min(W, x + m.width), min(H, y + m.height)
    if cx1 <= cx0 or cy1 <= cy0: return
    sub = m.crop((cx0 - x, cy0 - y, cx1 - x, cy1 - y))
    reg = canvas.crop((cx0, cy0, cx1, cy1))
    canvas.paste(ImageChops.lighter(reg, sub), (cx0, cy0))


class Short:
    def __init__(self, cfg):
        self.c = dict(cfg)
        self.build()

    @staticmethod
    def _ow(c, size, kind='verse'):
        """outline width in px. Small type gets a proportionally thinner ring —
        a thin face swallowed by its own outline just reads as a black smudge."""
        if not (c.get('outline') or c.get('outline_px')): return 0
        if kind == 'small' and c.get('box'): return 0
        if c.get('outline_px') and kind == 'verse': return int(c['outline_px'])
        fr = c.get('outline', 0.0) if kind == 'verse' else min(c.get('outline', 0.0), 0.05)
        return max(1, int(round(size * fr))) if fr else 0

    # ------------------------------------------------------------------ setup
    def build(self):
        c = self.c
        self.anim = c.get('anim', 'rise')
        mg = c.get('margin', 88)
        maxw = W - 2 * mg
        self._cache = None

        if self.anim == 'deck':
            # one line at a time — each line sized on its own, as big as it fits
            self.deck_y = H // 2 + c.get('shift', 0)
            self.tiles = []
            for t in c['lines']:
                sz, f = fit(strip_emph(t), c['font'], c.get('var'), c['size'], maxw)
                ow = self._ow(c, sz)
                tl, te, to, iw, ih = tile_split(t, f, c.get('stroke', 0), outline=ow)
                self.tiles.append((tl, (W - iw) // 2 - PAD,
                                   self.deck_y - ih // 2 - PAD, iw, ih, te, to))
            # per-beat dwell: long lines stay up longer
            pace = c.get('pace', 1.0)
            self.dwell = [pace * max(c.get('dwell_min', 1.30),
                              c.get('dwell_base', 0.42) + c.get('dwell_per_word', 0.34) * len(t.split()))
                          for t in c['lines']]
            self.beat_t = []
            acc = c.get('t0', 0.7)
            for d in self.dwell:
                self.beat_t.append(acc); acc += d
            self.deck_end = acc
            # the whole verse, assembled, for the recap hold at the end
            self.recap = None
            if c.get('recap', True) and len(c['lines']) > 1:
                full = c.get('recap_text') or ' '.join(l.replace('\n', ' ') for l in c['lines'])
                rs, rf, rls = fit_block(full, c['font'], c.get('var'),
                                        c.get('recap_size', 92), maxw,
                                        c.get('recap_maxh', 880))
                rlh = int(rs * 1.34)
                rinks = [tile_split(t, rf, c.get('stroke', 0), outline=self._ow(c, rs))
                         for t in rls]
                rblk = rlh * len(rinks)
                rtop = self.deck_y - rblk // 2 + c.get('recap_shift', 0)
                self.recap = [(tl, te, to, (W - iw) // 2 - PAD, rtop + i * rlh - PAD)
                              for i, (tl, te, to, iw, ih) in enumerate(rinks)]
                self.recap_lines = rls
                anchor_top = rtop
                anchor_bot = rtop + rblk
            else:
                anchor_top = self.deck_y - 90
                anchor_bot = self.deck_y + 130
            self.lh = 0
        else:
            if c.get('per_line_fit'):
                # every line sized on its own, so short lines come out big
                inks, heights = [], []
                for t in c['lines']:
                    sz, f = fit(strip_emph(t), c['font'], c.get('var'), c['size'], maxw)
                    inks.append(tile_split(t, f, c.get('stroke', 0), outline=self._ow(c, sz)))
                    heights.append(int(sz * (c.get('lh_factor') or 1.30)))
                c['size'] = max(1, sum(heights) // len(heights))
                lh = None
                blk = sum(heights)
            else:
                longest = strip_emph(max(c['lines'], key=len))
                size, f = fit(longest, c['font'], c.get('var'), c['size'], maxw)
                c['size'] = size
                lh = c.get('lh') or int(size * 1.34)
                ow = self._ow(c, size)
                inks = [tile_split(t, f, c.get('stroke', 0), outline=ow) for t in c['lines']]
                heights = [lh] * len(inks)
                blk = lh * len(inks)
            top = c.get('top')
            if top is None: top = (H - blk) // 2 + c.get('shift', 0)
            self.tiles = []
            yy = top
            for i, (tl, te, to, iw, ih) in enumerate(inks):
                al = c.get('align', 'center')
                if al == 'center':  x = (W - iw) // 2 - PAD
                elif al == 'left':  x = mg - PAD
                else:               x = W - mg - iw - PAD
                self.tiles.append((tl, x, yy - PAD, iw, ih, te, to))
                yy += heights[i]
            self.top, self.blk, self.lh = top, blk, (lh or heights[0])
            anchor_top, anchor_bot = top, top + blk

        # attribution
        self.att = None
        if c.get('attrib'):
            fa = font(c.get('attrib_font', 'Marcellus-Regular'), c.get('attrib_size', 48))
            tl, _, to, iw, ih = tile_split(c['attrib'], fa,
                                           outline=self._ow(c, c.get('attrib_size', 48), 'small'))
            self.att = (tl, to, (W - iw) // 2 - PAD,
                        anchor_bot + c.get('attrib_gap', 70) - PAD)

        # kicker (a headline or a small label above the verse)
        self.kick = None
        if c.get('kicker'):
            fk = font(c.get('kicker_font', 'Inter'), c.get('kicker_size', 34),
                      c.get('kicker_var', 'SemiBold'))
            kt = c['kicker']
            if c.get('kicker_track'): kt = (' ' * c['kicker_track']).join(list(kt))
            tl, _, to, iw, ih = tile_split(kt, fk,
                                           outline=self._ow(c, c.get('kicker_size', 34), 'small'))
            self.kick = (tl, to, (W - iw) // 2 - PAD,
                         anchor_top - c.get('kicker_gap', 110) - PAD)

        # constant brand line (e.g. NO AJAHN CHAH) at a fixed height
        self.brand = None
        if c.get('brand'):
            fb = font(c.get('brand_font', 'Cinzel'), c.get('brand_size', 58),
                      c.get('brand_var', 'Black'))
            bt = c['brand']
            if c.get('brand_track'): bt = (' ' * c['brand_track']).join(list(bt))
            tl, _, to, iw, ih = tile_split(bt, fb,
                                           outline=self._ow(c, c.get('brand_size', 58), 'head'))
            self.brand = (tl, to, (W - iw) // 2 - PAD, c.get('brand_y', 330) - PAD)

        # small subtitle under the title (e.g. REFLECTIONS)
        self.sub = None
        if c.get('sub'):
            fs = font(c.get('sub_font', 'Cinzel'), c.get('sub_size', 30),
                      c.get('sub_var', 'Regular'))
            st = c['sub']
            if c.get('sub_track'): st = (' ' * c['sub_track']).join(list(st))
            tl, _, to, iw, ih = tile_split(st, fs,
                                           outline=self._ow(c, c.get('sub_size', 30), 'head'))
            self.sub = (tl, to, (W - iw) // 2 - PAD, c.get('sub_y', 400) - PAD)

        # gold gradient spans everything that gets painted
        g0 = anchor_top - ((c.get('kicker_gap', 110) + 120) if self.kick else 60)
        if self.brand: g0 = min(g0, c.get('brand_y', 330) - 60)
        if self.sub: g0 = min(g0, c.get('sub_y', 400) - 60)
        g1 = anchor_bot + ((c.get('attrib_gap', 70) + 140) if self.att else 90)
        self.fill = gradient(c.get('gold_top', GOLD_TOP), c.get('gold_bot', GOLD_BOT), g0, g1)

        # a fixed black panel behind the words, sized to everything that is drawn
        self.box = None
        if c.get('box'):
            xs0 = ys0 = 10 ** 6; xs1 = ys1 = -10 ** 6
            spans = [(x + PAD, y + PAD, x + PAD + iw, y + PAD + ih)
                     for (tl, x, y, iw, ih, te, to) in self.tiles]
            if getattr(self, 'recap', None):
                for (tl, te, to, x, y) in self.recap:
                    b = tl.getbbox()
                    if b: spans.append((x + b[0], y + b[1], x + b[2], y + b[3]))
            if self.att and c.get('box_include_no', True):
                tl, to, x, y = self.att
                b = tl.getbbox()
                if b: spans.append((x + b[0], y + b[1], x + b[2], y + b[3]))
            for a0, b0, a1, b1 in spans:
                xs0, ys0, xs1, ys1 = min(xs0, a0), min(ys0, b0), max(xs1, a1), max(ys1, b1)
            px, py = c.get('box_pad', (54, 44))
            if c.get('box_full_width'):
                xs0, xs1 = c.get('margin', 88) - 12, W - c.get('margin', 88) + 12
                px = 0
            self.box = (int(xs0 - px), int(ys0 - py), int(xs1 + px), int(ys1 + py))

        self.logo = None
        if c.get('logo') and os.path.exists(c['logo']):
            lg = Image.open(c['logo']).convert('RGBA')
            lw = c.get('logo_w', 190)
            self.logo = lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS)

        # ---- timings
        n = len(c['lines'])
        if self.anim == 'type':
            cps = c.get('cps', 30); lp = c.get('line_pause', 0.18)
            chars = sum(len(t) for t in c['lines'])
            self.reveal_end = c.get('t0', 0.6) + chars / cps + (n - 1) * lp
        elif self.anim == 'deck':
            self.reveal_end = self.deck_end + (c.get('recap_in', 0.5) * c.get('pace', 1.0) if self.recap else 0.0)
        else:
            self.t_in = []; acc = c.get('t0', 0.6)
            for t in c['lines']:
                self.t_in.append(acc)
                acc += c.get('pace', 1.0) * (c.get('step') or max(0.55, 0.30 + 0.28 * len(t.split())))
            self.reveal_end = self.t_in[-1] + c.get('dur_in', 0.55)
        words = sum(len(t.split()) for t in c['lines'])
        auto_hold = min(c.get('hold_max', 5.5),
                        max(c.get('hold_min', 2.6), 1.2 + 0.30 * words))
        hold = (c.get('hold') or auto_hold) * c.get('pace', 1.0)
        self.total = int(max(c.get('min_total', 7.0) * c.get('pace', 1.0),
                             self.reveal_end + hold + 0.4) * FPS)

    # ------------------------------------------------------------------ frame
    def _pref(self, key, s):
        if self._cache is None: self._cache = {}
        if key not in self._cache:
            f = font(self.c['font'], self.c['size'], self.c.get('var'))
            self._cache[key] = tile(s, f, self.c.get('stroke', 0))[0]
        return self._cache[key]

    def frame(self, fr):
        c = self.c
        t_now = fr / FPS
        canvas = Image.new('L', (W, H), 0)
        canvas_e = Image.new('L', (W, H), 0)
        canvas_o = Image.new('L', (W, H), 0)
        canvas_a = Image.new('L', (W, H), 0)
        def put(tl, te, x, y, a, to=None):
            m = tl if a > 0.995 else tl.point(lambda v, a=a: int(v * a))
            blend_into(canvas, m, x, y)
            if te is not None and te.getbbox():
                me = te if a > 0.995 else te.point(lambda v, a=a: int(v * a))
                blend_into(canvas_e, me, x, y)
            if to is not None and to.getbbox():
                mo = to if a > 0.995 else to.point(lambda v, a=a: int(v * a))
                blend_into(canvas_o, mo, x, y)

        def put_scaled(tl, te, x, y, a, to=None, sc=1.0):
            """same as put(), but grows the line about its own centre"""
            if abs(sc - 1.0) < 0.006:
                put(tl, te, x, y, a, to); return
            def rs(m):
                if m is None or not m.getbbox(): return None
                return m.resize((max(1, int(m.width * sc)), max(1, int(m.height * sc))),
                                Image.BILINEAR)
            cx, cy = x + tl.width / 2.0, y + tl.height / 2.0
            t2 = rs(tl)
            if t2 is None: return
            nx, ny = int(cx - t2.width / 2), int(cy - t2.height / 2)
            put(t2, rs(te), nx, ny, a, rs(to))

        if self.anim == 'deck':
            IN = 0.40
            rin = c.get('recap_in', 0.5) * c.get('pace', 1.0)
            if self.recap and t_now >= self.deck_end:
                a = min(1.0, max(0.0, (t_now - self.deck_end) / rin))
                for (tl, te, to, x, y) in self.recap:
                    put(tl, te, x, y + int((1 - a) * 30), a, to)
            else:
                last = len(self.tiles) - 1
                for i, (tl, x, y, iw, ih, te, to) in enumerate(self.tiles):
                    t = t_now - self.beat_t[i]
                    d = self.dwell[i]
                    if t < -IN or t > d: continue
                    if t < 0:
                        p = ease_out((t + IN) / IN); a, dy = p, int((1 - p) * 48)
                    elif t > d - IN and not (i == last and not self.recap):
                        p = ease_out((t - (d - IN)) / IN); a, dy = 1 - p, int(-p * 48)
                    else:
                        a, dy = 1.0, 0
                    if a <= 0.01: continue
                    pop = c.get('text_pop', 0.0)
                    if pop and 0 <= t < IN:
                        q = max(0.0, ease_back(min(1.0, (t + IN) / IN),
                                               c.get('pop_overshoot', 1.3)))
                        put_scaled(tl, te, x, y + dy, a, to, pop + (1 - pop) * q)
                    else:
                        put(tl, te, x, y + dy, a, to)

        elif self.anim == 'type':
            cps = c.get('cps', 30); lp = c.get('line_pause', 0.18)
            done = 0
            for i, (tl, x, y, iw, ih, te, to) in enumerate(self.tiles):
                txt = strip_emph(c['lines'][i])
                start = c.get('t0', 0.6) + done / cps + i * lp
                el = t_now - start
                if el <= 0: break
                k = min(len(txt), int(el * cps) + 1)
                blend_into(canvas, self._pref((i, k), txt[:k]), x, y)
                done += len(txt)
                if k < len(txt): break

        else:
            pop = c.get('text_pop', 0.0)
            for i, (tl, x, y, iw, ih, te, to) in enumerate(self.tiles):
                t = (t_now - self.t_in[i]) / c.get('dur_in', 0.55)
                if t < 0: continue
                p = ease_out(min(1.0, t))
                a = min(1.0, t / 0.55)
                dy = int((1 - p) * (18 if pop else 54)) if self.anim == 'rise' else 0
                if a <= 0.01: continue
                if pop and t < 1.0:
                    q = max(0.0, ease_back(min(1.0, t), c.get('pop_overshoot', 1.3)))
                    sc = pop + (1.0 - pop) * q
                    put_scaled(tl, te, x, y + dy, a, to, sc)
                else:
                    put(tl, te, x, y + dy, a, to)

        if self.brand:
            a = min(1.0, max(0.0, (t_now - c.get('brand_t', 0.1)) / 0.6))
            if a > 0:
                tl, to, x, y = self.brand
                put(tl, None, x, y, a, to)
        if self.sub:
            a = min(1.0, max(0.0, (t_now - c.get('sub_t', 0.25)) / 0.6))
            if a > 0:
                tl, to, x, y = self.sub
                put(tl, None, x, y, a, to)

        if self.kick:
            t = t_now - c.get('kicker_t', 0.2)
            if t > 0:
                a = min(1.0, t / 0.55)
                tl, to, x, y = self.kick
                put(tl, None, x, y + int((1 - a) * 26), a, to)

        if self.att:
            t = t_now - (self.reveal_end + c.get('attrib_delay', 0.3))
            if t > 0:
                a = min(1.0, t / 0.6)
                tl, to, x, y = self.att
                if c.get('attrib_c'):
                    m = tl if a > 0.995 else tl.point(lambda v, a=a: int(v * a))
                    blend_into(canvas_a, m, x, y + int((1 - a) * 20))
                    if to is not None and to.getbbox():
                        mo = to if a > 0.995 else to.point(lambda v, a=a: int(v * a))
                        blend_into(canvas_o, mo, x, y + int((1 - a) * 20))
                else:
                    put(tl, None, x, y + int((1 - a) * 20), a, to)

        # ---- paint: scrim, drop shadow, outer glow, gold fill, light sweep
        out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ts = c.get('top_scrim')
        if ts:
            amax, hh = ts
            col = np.clip(1.0 - np.arange(H) / float(hh), 0, 1) ** 1.6 * amax * 255
            a = np.tile(col[:, None], (1, W)).astype(np.uint8)
            out = Image.alpha_composite(out, tinted(Image.fromarray(a, 'L'),
                                                    solid(c.get('top_scrim_c', (0, 0, 0)))))
        sc = c.get('scrim')
        if sc:
            scy, sig, amax = sc
            col = np.exp(-((np.arange(H) - scy) / float(sig)) ** 2) * amax * 255
            a = np.tile(col[:, None], (1, W)).astype(np.uint8)
            out = Image.alpha_composite(out, tinted(Image.fromarray(a, 'L'),
                                                    solid(c.get('scrim_c', (0, 0, 0)))))
        if canvas_e.getbbox():
            canvas = ImageChops.lighter(canvas, canvas_e)
        ink = canvas
        if canvas_a.getbbox(): ink = ImageChops.lighter(ink, canvas_a)
        if canvas_o.getbbox(): ink = ImageChops.lighter(ink, canvas_o)
        if self.box:
            dur = max(0.01, c.get('box_in', 0.6))
            t = (t_now - c.get('box_t', 0.0)) / dur
            if t > 0.0:
                x0, y0, x1, y1 = self.box
                cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                fw, fh = x1 - x0, y1 - y0
                if t >= 1.0:
                    p, a = 1.0, 1.0
                    bx = self.box
                    rad = c.get('box_radius', 34)
                else:
                    # a dot that opens out into the panel
                    p = max(0.0, ease_back(t, c.get('box_overshoot', 1.4)))
                    a = min(1.0, t / 0.35)
                    dot = c.get('box_dot', 18)
                    w = dot + (fw - dot) * p
                    h = dot + (fh - dot) * p
                    bx = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                    rad = min(h, w) / 2.0 * (1 - p) + c.get('box_radius', 34) * p
                    rad = min(rad, min(w, h) / 2.0)
                panel = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                dp = ImageDraw.Draw(panel)
                col = tuple(c.get('box_c', (0, 0, 0))) + (int(255 * c['box'] * a),)
                dp.rounded_rectangle(bx, radius=rad, fill=col)
                bw = c.get('box_border', 0)
                if bw:
                    dp.rounded_rectangle(bx, radius=rad,
                                         outline=tuple(c.get('box_border_c', (214, 160, 60)))
                                         + (int(255 * a),), width=bw)
                if c.get('box_blur'):
                    panel = panel.filter(ImageFilter.GaussianBlur(c['box_blur']))
                out = Image.alpha_composite(out, panel)
        halo = c.get('halo', 0.0)
        if halo:
            # sprayed dark halo — two radii, so it is dense at the letter and
            # feathers out. Keeps gold text readable on a light photograph.
            wide = ink.filter(ImageFilter.GaussianBlur(c.get('halo_r', 34)))
            tight = ink.filter(ImageFilter.GaussianBlur(c.get('halo_r', 34) / 3.0))
            m = np.maximum(np.asarray(wide, np.float32), np.asarray(tight, np.float32) * 1.25)
            m = np.clip(m / 255.0, 0, 1)
            m = 1.0 - (1.0 - m) ** c.get('halo_gamma', 3.0)      # thicken near the letters
            m = (np.clip(m * halo, 0, 1) * 255).astype(np.uint8)
            for _ in range(c.get('halo_passes', 2)):
                out = Image.alpha_composite(out, tinted(Image.fromarray(m, 'L'),
                                                        solid(c.get('halo_c', (0, 0, 0)))))
        sh = ink.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.85))
        out = Image.alpha_composite(out, tinted(ImageChops.offset(sh, 0, 7), solid((0, 0, 0))))
        gl = ink.filter(ImageFilter.GaussianBlur(c.get('glow_r', 26)))
        out = Image.alpha_composite(out, tinted(gl.point(lambda v: int(v * c.get('glow', 0.55))),
                                                solid(c.get('glow_c', GLOW))))
        if canvas_o.getbbox():
            out = Image.alpha_composite(out, tinted(canvas_o, solid(c.get('outline_c', (0, 0, 0)))))
        out = Image.alpha_composite(out, tinted(canvas, self.fill))
        if canvas_a.getbbox():
            out = Image.alpha_composite(out, tinted(canvas_a, solid(c['attrib_c'])))
        if canvas_e.getbbox() and c.get('emph_colour', True):
            out = Image.alpha_composite(out, tinted(canvas_e, solid(c.get('emph_c', (255, 246, 214)))))

        sw = c.get('shimmer')
        if sw is not None:
            t = t_now - (self.reveal_end + sw)
            if 0 <= t <= 1.05:
                bx = -340 + (W + 680) * ease_in_out(min(1.0, t / 1.05))
                band = np.exp(-((np.arange(W) - bx) / 210.0) ** 2)
                m = (np.asarray(canvas, np.float32) / 255.0 * band[None, :] * 255).astype(np.uint8)
                out = Image.alpha_composite(out, tinted(Image.fromarray(m, 'L'),
                                                        solid((255, 252, 238))))

        if self.logo:
            lw, lhg = self.logo.size
            pos = c.get('logo_pos', 'top')
            if pos == 'top':  xy = ((W - lw) // 2, c.get('logo_y', 110))
            elif pos == 'br': xy = (W - lw - 56, H - lhg - c.get('logo_m', 150))
            else:             xy = (56, H - lhg - c.get('logo_m', 150))
            a = min(1.0, max(0.0, t_now / 0.7))
            lg = self.logo if a > 0.99 else Image.merge(
                'RGBA', (*self.logo.split()[:3],
                         self.logo.split()[3].point(lambda v, a=a: int(v * a))))
            halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            halo.alpha_composite(lg, xy)
            lhc = c.get('logo_halo_c') or ((0, 0, 0) if c.get('halo') else (255, 190, 90))
            for r, g in c.get('logo_glow', ((26, 0.55), (70, 0.45), (150, 0.30))):
                hb = halo.split()[3].filter(ImageFilter.GaussianBlur(r)).point(
                    lambda v, g=g: int(v * g * a))
                out = Image.alpha_composite(out, tinted(hb, solid(lhc)))
            out = Image.alpha_composite(out, halo)
        return out


# ---------------------------------------------------------------- driver
def _work(a):
    cfg, lo, hi, d = a
    s = Short(cfg)
    for fr in range(lo, hi):
        s.frame(fr).save('%s/%05d.png' % (d, fr))
    return hi - lo

def render(cfg, out, workers=4):
    # a temp dir per call, so two renders can never tread on each other
    d = '/tmp/shorts/_ov_%d' % os.getpid()
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    total = Short(cfg).total
    per = math.ceil(total / workers)
    chunks = [(cfg, i * per, min(total, (i + 1) * per), d)
              for i in range(workers) if i * per < total]
    with Pool(len(chunks)) as p: p.map(_work, chunks)

    bg = cfg['bg']
    if bg[0] == 'video':
        inputs = ['-stream_loop', '-1', '-i', bg[1]]
        vf = ("[0:v]fps=%d,scale=%d:%d:force_original_aspect_ratio=increase,"
              "crop=%d:%d,eq=brightness=%.3f:saturation=%.2f[b]" %
              (FPS, W, H, W, H, cfg.get('bg_bright', -0.05), cfg.get('bg_sat', 1.05)))
    elif bg[0] == 'image':
        inputs = ['-loop', '1', '-i', bg[1]]
        z = cfg.get('zoom', 1.16)
        vf = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
              "zoompan=z='min(1+%.6f*on,%.3f)':d=%d:x='iw/2-(iw/zoom/2)'"
              ":y='ih/2-(ih/zoom/2)':s=%dx%d:fps=%d,"
              "eq=brightness=%.3f:saturation=%.2f,"
              "colorbalance=rs=%.3f:bs=%.3f[b]" %
              (W * 2, H * 2, W * 2, H * 2, (z - 1) / total, z, total, W, H, FPS,
               cfg.get('bg_bright', -0.05), cfg.get('bg_sat', 1.05),
               cfg.get('warm', 0.0), -cfg.get('warm', 0.0) * 1.3))
    else:
        raise ValueError(bg[0])

    fc = vf + ";[b][1:v]overlay=0:0:shortest=1,format=yuv420p[v]"
    cmd = (['ffmpeg', '-v', 'error', '-y'] + inputs +
           ['-framerate', str(FPS), '-i', d + '/%05d.png',
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-filter_complex', fc, '-map', '[v]', '-map', '2:a', '-shortest',
            '-frames:v', str(total),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', out])
    subprocess.run(cmd, check=True)
    shutil.rmtree(d, ignore_errors=True)
    return total / FPS
