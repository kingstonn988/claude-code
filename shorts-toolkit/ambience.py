"""Ambience beds — filtered noise, which is what synthesis is actually good at."""
import numpy as np, subprocess
SR = 44100
rng = np.random.default_rng(11)

def fftconv(x, k):
    n = len(x) + len(k) - 1
    N = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(k, N), N)[:len(x)]
    return y

def sinc_lp(fc, taps=1023, sr=SR):
    m = (taps - 1) / 2
    n = np.arange(taps) - m
    h = np.sinc(2 * fc / sr * n) * np.hamming(taps)
    return h / h.sum()

def bp(x, lo, hi, taps=1023):
    return fftconv(x, sinc_lp(hi, taps) - sinc_lp(lo, taps))

def lp(x, fc, taps=1023):
    return fftconv(x, sinc_lp(fc, taps))

def rain(dur=45, density=2600, bright=0.55):
    n = int(dur * SR); t = np.arange(n) / SR
    hiss = bp(rng.normal(0, 1, n), 300, 7000)
    hiss *= 0.75 + 0.25 * lp(rng.normal(0, 1, n), 1.5)[:n] * 4
    # individual drops: sparse impulses through a short resonant tail
    imp = np.zeros(n)
    k = rng.integers(0, n, int(density * dur / 10))
    imp[k] = rng.normal(0, 1, len(k)) * rng.random(len(k)) ** 2
    tail = np.exp(-np.arange(int(0.05 * SR)) / (0.008 * SR))
    tail *= np.sin(2 * np.pi * rng.uniform(900, 2600) * np.arange(len(tail)) / SR)
    drops = fftconv(imp, tail)
    out = 0.65 * hiss + bright * 0.5 * bp(drops, 600, 6000)
    return out

def wind(dur=45):
    n = int(dur * SR); t = np.arange(n) / SR
    base = rng.normal(0, 1, n)
    slow = lp(rng.normal(0, 1, n), 0.35)
    slow = slow / (np.abs(slow).max() + 1e-9)
    gust = 0.45 + 0.55 * (0.5 + 0.5 * slow)
    low = bp(base, 60, 420) * gust
    mid = bp(base, 400, 1400) * (0.25 * gust ** 2)
    return 0.9 * low + mid

def stream(dur=45):
    n = int(dur * SR)
    w = bp(rng.normal(0, 1, n), 500, 5200)
    mod = 0.8 + 0.2 * lp(rng.normal(0, 1, n), 2.0) * 3
    return w * mod

def mix(*parts):
    n = min(len(p) for p, _ in parts)
    out = np.zeros(n)
    for p, g in parts: out += g * p[:n]
    return out / (np.abs(out).max() + 1e-9)

def fade(x, sec=2.5):
    k = int(sec * SR); x = x.copy()
    x[:k] *= np.linspace(0, 1, k); x[-k:] *= np.linspace(1, 0, k)
    return x

def write(x, path, gain_db=-9.0):
    x = fade(np.asarray(x, np.float32)) * (10 ** (gain_db / 20))
    st = np.stack([x, np.roll(x, 137)], 1).ravel()      # slight stereo spread
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR),
                          '-ac', '2', '-i', 'pipe:0', '-c:a', 'aac', '-b:a', '128k', path],
                         stdin=subprocess.PIPE)
    p.communicate(st.astype(np.float32).tobytes())
    return path

if __name__ == '__main__':
    write(mix((rain(), 1.0), (wind(), 0.35)), '/tmp/shorts/amb_rain.m4a')
    write(mix((wind(), 1.0), (stream(), 0.22)), '/tmp/shorts/amb_forest.m4a')
    print('done')
