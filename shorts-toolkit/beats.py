"""Split a reflection into beats (one screen each) and wrap each beat."""
import re, textwrap

def clauses(text):
    sents = re.split(r'(?<=[.!?”"])\s+', text.strip())
    out = []
    for s in sents:
        if len(s.split()) <= 12:
            out.append(s); continue
        parts = re.split(r'(?<=[,;:–])\s+', s)
        buf = ''
        for p in parts:
            if buf and len((buf + ' ' + p).split()) > 12:
                out.append(buf); buf = p
            else:
                buf = (buf + ' ' + p).strip()
        if buf: out.append(buf)
    return [c for c in out if c.strip()]

def beats(text, cap=None):
    W = len(text.split())
    if cap is None: cap = 7 if W <= 20 else 11
    cs = clauses(text)
    out, buf = [], ''
    for c in cs:
        if buf and len((buf + ' ' + c).split()) > cap:
            out.append(buf); buf = c
        else:
            buf = (buf + ' ' + c).strip()
    if buf: out.append(buf)
    return out

def wrap(beat, chars=24):
    if len(beat) <= chars: return beat
    n = 2 if len(beat) <= chars * 2 else 3
    lines = textwrap.wrap(beat, width=max(chars, len(beat) // n + 4))
    return '\n'.join(lines)

def script(text, cap=None, chars=24):
    return [wrap(b, chars) for b in beats(text, cap)]

def balanced(text, chars=24):
    """wrap into lines of roughly equal length, none longer than `chars`"""
    words = text.split()
    if len(text) <= chars: return text
    n = max(2, -(-len(text) // chars))
    while n <= len(words):
        w = -(-len(text) // n) + 2
        lines = textwrap.wrap(text, width=w)
        if len(lines) <= n and max(len(l) for l in lines) <= chars + 2:
            return '\n'.join(lines)
        n += 1
    return '\n'.join(textwrap.wrap(text, width=chars))

def rebalance(lines):
    """Close and reopen *emphasis* markers that a line break split apart."""
    out, open_ = [], False
    for ln in lines:
        if open_: ln = '*' + ln
        if ln.count('*') % 2:
            ln += '*'; open_ = True
        else:
            open_ = False
        out.append(ln)
    return out

def cap_first(s):
    """Capitalise the first letter of a beat, leaving quotes and the rest alone."""
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.upper() + s[i+1:]
    return s

def plan(text, short_max=14):
    """Decide how a reflection should play.
    Short ones build up and stay; longer ones go one beat at a time
    and then assemble for the recap."""
    W = len(text.split())
    if W <= short_max:
        return 'rise', rebalance(balanced(text, 20).split('\n'))
    return 'deck', ['\n'.join(rebalance(balanced(cap_first(b), 26).split('\n')))
                    for b in beats(text)]
