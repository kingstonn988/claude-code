"""Generate simple original music beds — no library, no licensing."""
import numpy as np, subprocess, sys
SR = 44100

def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))

def bowl(f0, dur, sr=SR, partials=(1.0, 2.75, 5.38, 8.93), amps=(1.0, .45, .22, .10),
         taus=(6.0, 3.4, 2.0, 1.2)):
    n = int(dur * sr); t = np.arange(n) / sr
    out = np.zeros(n)
    for p, a, tau in zip(partials, amps, taus):
        beat = 1.0 + 0.004 * np.sin(2 * np.pi * 0.7 * t)     # slight shimmer
        out += a * np.sin(2 * np.pi * f0 * p * t * beat) * env_exp(n, tau)
    atk = np.minimum(1.0, np.arange(n) / (0.012 * sr))
    return out * atk

def drone(f0, dur, sr=SR, detune=0.35):
    n = int(dur * sr); t = np.arange(n) / sr
    a = np.sin(2 * np.pi * f0 * t) + np.sin(2 * np.pi * (f0 + detune) * t)
    a += 0.5 * (np.sin(2 * np.pi * f0 * 2 * t) + np.sin(2 * np.pi * (f0 * 2 + detune) * t))
    a += 0.25 * np.sin(2 * np.pi * f0 * 3 * t)
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * 0.045 * t)
    return a * swell / 3.0

def reverb(x, sr=SR, taps=((0.031,.5),(0.057,.38),(0.089,.3),(0.131,.22),(0.197,.15))):
    out = x.copy()
    for d, g in taps:
        k = int(d * sr)
        out[k:] += g * x[:-k]
    return out

def norm(x, peak=0.72):
    return x / (np.abs(x).max() + 1e-9) * peak

def bed_bowls(dur=45, root=108.0, every=9.0):
    n = int(dur * SR); out = np.zeros(n + SR * 8)
    out[:n] += 0.38 * drone(root / 2, dur)
    steps = [1.0, 1.5, 1.335, 1.0, 1.78]
    t = 0.6; i = 0
    while t < dur - 1:
        b = bowl(root * steps[i % len(steps)], 10.0)
        s = int(t * SR); out[s:s + len(b)] += 0.55 * b
        t += every * (0.9 + 0.2 * ((i * 7) % 5) / 5.0); i += 1
    out = reverb(out)[:n]
    return norm(out, 0.66)

def bed_air(dur=45, root=96.0):
    n = int(dur * SR); t = np.arange(n) / SR
    out = 0.55 * drone(root, dur)
    rng = np.random.default_rng(3)
    for k, f in enumerate((root * 3, root * 4.5, root * 6)):
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * (0.017 + 0.011 * k) * t + k)
        out += (0.10 / (k + 1)) * np.sin(2 * np.pi * f * t) * lfo
    hiss = rng.normal(0, 1, n)
    b = np.convolve(hiss, np.ones(220) / 220, 'same')
    out += 0.05 * b * (0.5 + 0.5 * np.sin(2 * np.pi * 0.03 * t))
    return norm(reverb(out), 0.60)

def fade(x, sec=2.0):
    k = int(sec * SR)
    x[:k] *= np.linspace(0, 1, k); x[-k:] *= np.linspace(1, 0, k)
    return x

def write(x, path, gain_db=-6.0):
    x = fade(np.asarray(x, np.float32)) * (10 ** (gain_db / 20))
    st = np.stack([x, x], 1).ravel()
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR),
                          '-ac', '2', '-i', 'pipe:0', '-c:a', 'aac', '-b:a', '128k', path],
                         stdin=subprocess.PIPE)
    p.communicate(st.astype(np.float32).tobytes())
    return path

if __name__ == '__main__':
    write(bed_bowls(45), '/tmp/shorts/music_bowls.m4a')
    write(bed_air(45),   '/tmp/shorts/music_air.m4a')
    print('done')
