import sys, json, subprocess
sys.path.insert(0, '/tmp/shorts')
from PIL import Image, ImageDraw
import shorts as S, beats as B

BGV = '/tmp/shorts/assets/bg_rays.mp4'
LOGO = '/tmp/shorts/assets/logo_clean.png'
PACE = 1.45
# fixed header, matching the reference: title, small subtitle, then the logo
BRAND = dict(
    brand='NO AJAHN CHAH', brand_font='PlayfairDisplay', brand_var='Black',
    brand_size=58, brand_track=1, brand_y=58, brand_t=0.0,
    sub='REFLECTIONS', sub_font='Cinzel', sub_var='Regular',
    sub_size=27, sub_track=2, sub_y=138, sub_t=0.0,
    logo=LOGO, logo_w=600, logo_pos='top', logo_y=196,
)

def cfg_for(text, n):
    mode, lines = B.plan(text)
    c = dict(BRAND, lines=lines, anim=mode, recap_text=text,
             font='PlayfairDisplay', var='Black',
             size=112 if mode == 'rise' else 100,
             recap_size=84, glow_r=32, glow=0.6,
             scrim=(1230, 470, 0.55), shift=258, pace=PACE, recap_maxh=680,
             attrib='no. %d' % n, attrib_size=38, attrib_gap=90,
             bg=('video', BGV))
    if mode == 'rise':
        c['shimmer'] = 0.45
    return c, mode, lines

def board(n, out, cols=4, scale=0.30):
    items = json.load(open('/tmp/shorts/book/items.json'))
    it = next(i for i in items if i['n'] == n)
    c, mode, lines = cfg_for(it['text'], n)
    sh = S.Short(c)
    bg = Image.open('/tmp/shorts/assets/bg_still.png').convert('RGBA')

    marks = []
    if mode == 'deck':
        for i, t in enumerate(sh.beat_t):
            marks.append((t + sh.dwell[i] * 0.55, 'beat %d' % (i + 1)))
        marks.append((sh.deck_end + 0.9, 'all together'))
        marks.append((sh.total / S.FPS - 0.6, 'hold / loop'))
    else:
        for i, t in enumerate(sh.t_in):
            marks.append((t + 0.5, 'line %d' % (i + 1)))
        marks.append((sh.reveal_end + 0.9, 'light sweep'))
        marks.append((sh.total / S.FPS - 0.6, 'hold / loop'))

    tw, th = int(S.W * scale), int(S.H * scale)
    rows = -(-len(marks) // cols)
    sheet = Image.new('RGB', (cols * (tw + 16) + 16, rows * (th + 56) + 16), (12, 10, 9))
    d = ImageDraw.Draw(sheet)
    for k, (t, label) in enumerate(marks):
        fr = min(sh.total - 1, max(0, int(t * S.FPS)))
        im = Image.alpha_composite(bg, sh.frame(fr)).convert('RGB').resize((tw, th), Image.LANCZOS)
        x = 16 + (k % cols) * (tw + 16); y = 16 + (k // cols) * (th + 56)
        sheet.paste(im, (x, y))
        d.rectangle((x, y, x + tw, y + th), outline=(80, 66, 44))
        d.text((x + 4, y + th + 8), '%5.1fs   %s' % (t, label), fill=(230, 196, 120))
    sheet.save(out)
    return sh.total / S.FPS, mode, len(lines)

if __name__ == '__main__':
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '3', '-i', BGV,
                    '-frames:v', '1', '-vf', 'scale=1080:1920',
                    '/tmp/shorts/assets/bg_still.png'], check=True)
    for n, name in ((30, 'board_short.png'), (25, 'board_long.png')):
        print(n, board(n, '/tmp/shorts/' + name))
