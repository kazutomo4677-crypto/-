"""Synthesised 15s soundtrack for the reel, cut to the same cue grid as the
visuals (120 BPM, hits in index.html's HITS). Writes sound.wav.
    python3 sound.py [out.wav]
"""
import sys
import wave

import numpy as np

SR = 44100
DUR = 15.0
N = int(SR * DUR)
rng = np.random.default_rng(3)
mix = np.zeros((N, 2))


def t_arr(sec):
    return np.arange(int(sec * SR)) / SR


def add(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    l, r = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    mix[i : i + len(sig), 0] += sig * gain * l
    mix[i : i + len(sig), 1] += sig * gain * r


def lowpass(x, a):
    # one-pole lowpass, a in (0,1): smaller = darker
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


def taiko(f0=110, f1=45, dec=5.0, dur=1.2, click=0.4):
    t = t_arr(dur)
    f = f1 + (f0 - f1) * np.exp(-t * 18)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * dec)
    n = rng.standard_normal(len(t)) * np.exp(-t * 60) * click
    return np.tanh((body + n) * 1.6)


def boom(dur=2.5):
    t = t_arr(dur)
    f = 32 + 90 * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    crack = lowpass(rng.standard_normal(len(t)), 0.25) * np.exp(-t * 14) * 0.8
    return np.tanh((sub + crack) * 1.8)


def whoosh(dur=0.5, rise=True):
    t = t_arr(dur)
    n = rng.standard_normal(len(t))
    env = (t / dur) ** 2.2 if rise else np.exp(-t * 6)
    bright = lowpass(n, 0.08) + lowpass(n, 0.35) * (t / dur if rise else 1 - t / dur)
    return bright * env * 0.9


def clack(dur=0.12):
    t = t_arr(dur)
    return (np.sin(2 * np.pi * 1800 * t) + 0.6 * np.sin(2 * np.pi * 2750 * t)) * np.exp(-t * 55) + \
        rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.5


def hat(dur=0.08, open_=False):
    t = t_arr(dur)
    n = rng.standard_normal(len(t))
    hp = n - lowpass(n, 0.5)
    return hp * np.exp(-t * (25 if open_ else 70))


def pluck(freq, dur=1.6, bright=0.5):
    # Karplus-Strong string: koto / shamisen-ish
    n = int(SR / freq)
    buf = rng.uniform(-1, 1, n)
    out = np.empty(int(dur * SR))
    idx = 0
    for i in range(len(out)):
        nxt = (idx + 1) % n
        out[i] = buf[idx]
        buf[idx] = 0.5 * (buf[idx] + buf[nxt]) * 0.998
        idx = nxt
    t = t_arr(dur)
    return out * np.exp(-t * 2.2) * (1 - np.exp(-t * 800))


def bell(freq, dur=3.0):
    t = t_arr(dur)
    parts = [(1, 1, 1.2), (2.76, .5, 2.5), (5.4, .3, 4), (8.93, .15, 6)]
    return sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d) for r, a, d in parts) * (1 - np.exp(-t * 400))


def gong(dur=3.5):
    t = t_arr(dur)
    sig = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t * d) * a
              for f, a, d in [(98, 1, .9), (147.5, .7, 1.1), (211, .5, 1.4), (263, .4, 1.6), (371, .3, 2.2), (517, .2, 3)])
    swell = 1 - np.exp(-t * 30)
    return sig * swell * 0.5


def riser(dur):
    t = t_arr(dur)
    f = 180 * (8 ** (t / dur))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
    n = rng.standard_normal(len(t))
    noise = (n - lowpass(n, 0.3)) * 0.6
    return (tone + noise) * (t / dur) ** 2.5


# ---------------- arrangement ----------------
D = 146.83  # D3
IN_SCALE = [1, 16 / 15, 4 / 3, 3 / 2, 8 / 5, 2]  # D Eb G A Bb D

# S1 — ignition
add(riser(0.5) * 0.5, 0.0)
add(boom(), 0.5, 1.0)
add(bell(D * 4, 2.5), 0.52, 0.18, 0.3)
# S2 — kanji slams
add(whoosh(0.35), 1.45, 0.7, -0.4)
add(taiko(120, 48, 4, 1.4, .6), 1.8, 1.0)
add(taiko(140, 55, 5, 1.2, .6), 2.3, 0.9)
add(whoosh(0.3), 2.72, 0.8, 0.5)
# S3 — reveal hit + koto phrase
add(taiko(90, 40, 3, 1.6), 3.0, 1.0)
add(whoosh(0.6, rise=False), 3.0, 0.6)
phrase = [(3.0, 0), (3.5, 2), (3.75, 3), (4.0, 4), (4.5, 3), (4.75, 5)]
# S4 — beat cuts get a pluck on every cut
phrase += [(5.0, 5), (5.5, 4), (6.0, 3), (6.5, 2), (6.75, 3), (7.0, 0)]
# S5 — card deal arpeggio
phrase += [(7.55 + i * 0.08, k) for i, k in enumerate([0, 2, 3, 4, 5])]
phrase += [(8.5, 5), (9.0, 4), (9.25, 3), (9.5, 2)]
# S6
phrase += [(10.0, 0), (10.5, 3), (11.0, 4), (11.5, 5)]
for at, deg in phrase:
    add(pluck(D * 2 * IN_SCALE[deg]), at, 0.35, rng.uniform(-.5, .5))
for h in [5.0, 5.5, 6.0, 6.5, 7.0]:
    add(taiko(130, 50, 6, 0.9, .5), h, 0.85)
    add(clack(), h, 0.4, 0.3)
add(whoosh(0.4), 6.2, 0.6, -0.6)
add(whoosh(0.45), 7.05, 0.8, 0.6)
# card flicks
for i in range(5):
    add(clack(0.05) * 0.8, 7.55 + i * 0.08, 0.35, -0.6 + i * 0.3)
add(taiko(110, 45, 4, 1.3), 7.5, 0.8)
add(boom(1.6), 8.5, 0.6)
# chip rain
for k in range(40):
    at = 8.5 + rng.uniform(0.1, 1.4)
    add(bell(rng.uniform(2200, 4200), 0.25) * 0.5, at, 0.12, rng.uniform(-.8, .8))
add(taiko(120, 50, 5, 1.1), 9.5, 0.7)
add(whoosh(0.45), 9.55, 0.7)
add(taiko(100, 42, 3, 1.5), 10.0, 1.0)
add(bell(D * 4 * 1.5, 2.5), 10.7, 0.12)
# groove: 8th-note hats and a pulsing sub from 3.0 to 12.4
for i in range(int((12.4 - 3.0) / 0.25)):
    at = 3.0 + i * 0.25
    add(hat(open_=(i % 4 == 2)), at, 0.18 if i % 2 else 0.1, 0.3 if i % 2 else -0.3)
bass_t = t_arr(12.45 - 3.0)
beat_phase = (bass_t % 0.5) / 0.5
bass = np.sin(2 * np.pi * D / 2 * bass_t) + 0.3 * np.sin(2 * np.pi * D * bass_t)
add(bass * (1 - np.exp(-beat_phase * 8)) * 0.22, 3.0)  # side-chain pump
# S6 → S7 riser, big hit, logo gong + chime
add(riser(1.15), 11.3, 0.7)
add(whoosh(0.4), 12.1, 0.9)
add(boom(3.0), 12.5, 1.1)
add(taiko(100, 38, 2.5, 2), 12.5, 0.8)
add(gong(), 13.5, 0.9)
for j, deg in enumerate([0, 3, 5]):
    add(bell(D * 4 * IN_SCALE[deg], 2.0), 13.6 + j * 0.12, 0.1, -0.4 + j * 0.4)

# ---------------- master ----------------
# short synthetic hall reverb via FFT convolution
ir_t = t_arr(1.8)
ir = rng.standard_normal((len(ir_t), 2)) * np.exp(-ir_t * 3.2)[:, None]
ir[:, 0] = lowpass(ir[:, 0], 0.3)
ir[:, 1] = lowpass(ir[:, 1], 0.3)
L = N + len(ir_t)
wet = np.stack([np.fft.irfft(np.fft.rfft(mix[:, c], L) * np.fft.rfft(ir[:, c], L), L)[:N] for c in range(2)], 1)
wet /= np.max(np.abs(wet)) + 1e-9
out = mix / (np.max(np.abs(mix)) + 1e-9) + wet * 0.18
out = np.tanh(out * 1.4)
fade = np.ones(N)
fade[-int(0.35 * SR):] = np.linspace(1, 0, int(0.35 * SR))
out *= fade[:, None]
out = out / np.max(np.abs(out)) * 0.93

path = sys.argv[1] if len(sys.argv) > 1 else "sound.wav"
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote", path)
