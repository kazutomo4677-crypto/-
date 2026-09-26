"""Synthesised soundtrack for the 30s trailer, cued to index.html's scenes.
Gentle music box / koto in D major pentatonic, evening ambience, a comic
rain gag, and rain that outlives the music at the end.
    python3 sound.py [out.wav]
"""
import sys
import wave

import numpy as np

SR = 44100
DUR = 30.0
N = int(SR * DUR)
rng = np.random.default_rng(12)
mix = np.zeros((N, 2))


def t_arr(sec):
    return np.arange(int(sec * SR)) / SR


def add(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N or len(sig) == 0:
        return
    sig = sig[: N - i]
    l, r = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    mix[i:i + len(sig), 0] += sig * gain * l
    mix[i:i + len(sig), 1] += sig * gain * r


def lowpass_fft(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def bandnoise(dur, lo, hi):
    n = rng.standard_normal(int(dur * SR))
    X = np.fft.rfft(n)
    f = np.fft.rfftfreq(len(n), 1 / SR)
    X *= ((f > lo) & (f < hi)).astype(float)
    y = np.fft.irfft(X, len(n))
    return y / (np.abs(y).max() + 1e-9)


def musicbox(freq, dur=2.2):
    t = t_arr(dur)
    parts = [(1, 1, 2.2), (3.0, .35, 5), (5.2, .12, 8), (2.0, .2, 3.5)]
    s = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d) for r, a, d in parts)
    return s * (1 - np.exp(-t * 900))


def pluck(freq, dur=1.4, damp=.996):
    n = int(SR / freq)
    buf = rng.uniform(-1, 1, n)
    out = np.empty(int(dur * SR))
    idx = 0
    for i in range(len(out)):
        nxt = (idx + 1) % n
        out[i] = buf[idx]
        buf[idx] = 0.5 * (buf[idx] + buf[nxt]) * damp
        idx = nxt
    t = t_arr(dur)
    return out * np.exp(-t * 2.5)


def pad(freqs, dur, attack=.8):
    t = t_arr(dur)
    s = sum(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * .3 * t) * .3) + .3 * np.sin(2 * np.pi * f * 2.003 * t) for f in freqs)
    env = np.minimum(1, t / attack) * np.minimum(1, (dur - t) / .8)
    return s / len(freqs) * env


def bell(freq, dur=2.0):
    t = t_arr(dur)
    parts = [(1, 1, 1.4), (2.76, .45, 3), (5.4, .25, 5), (8.93, .1, 7)]
    return sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d) for r, a, d in parts) * (1 - np.exp(-t * 500))


def pop(dur=.25):
    t = t_arr(dur)
    f = 180 + 620 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 18) + rng.standard_normal(len(t)) * np.exp(-t * 120) * .3


def whoosh(dur=.5, rise=True):
    t = t_arr(dur)
    n = bandnoise(dur, 300, 5000)
    env = np.sin(np.pi * t / dur) ** 2 if rise else np.exp(-t * 6)
    return n * env


def clack(dur=.08, f=1500):
    t = t_arr(dur)
    return (np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 1.6 * t)) * np.exp(-t * 70) + rng.standard_normal(len(t)) * np.exp(-t * 150) * .4


def thunder(dur=2.5):
    t = t_arr(dur)
    n = lowpass_fft(rng.standard_normal(len(t)), 180)
    n /= np.abs(n).max()
    return n * (np.exp(-t * 1.6) * (1 - np.exp(-t * 20)))


def rain(dur, heavy=1.0):
    n = bandnoise(dur, 900, 9000) * .6 + bandnoise(dur, 200, 900) * .4 * heavy
    t = t_arr(dur)
    # droplet ticks
    ticks = np.zeros(len(t))
    for _ in range(int(dur * 60 * heavy)):
        i = rng.integers(0, len(t) - 400)
        ticks[i:i + 400] += rng.uniform(.2, .6) * np.exp(-np.arange(400) / 40) * np.sin(np.arange(400) * rng.uniform(.3, .9))
    return (n + ticks) * .5


def cicada(dur):
    # distant higurashi "kana-kana"
    t = t_arr(dur)
    s = np.zeros(len(t))
    for start in np.arange(.3, dur - 1.5, 2.6):
        tt = t - start
        m = (tt > 0) & (tt < 1.4)
        chirp = np.sin(2 * np.pi * (4300 - 500 * tt) * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 11 * tt)) ** 3
        s[m] += chirp[m] * np.exp(-tt[m] * 1.6)
    return s


D4 = 293.66
SCALE = [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2, 9 / 4, 5 / 2]  # D E F# A B D' E' F#'
beat = 60 / 84

# ---- ambience ----
wind = lowpass_fft(rng.standard_normal(int(9.2 * SR)), 400)
wind /= np.abs(wind).max()
add(wind * np.minimum(1, t_arr(9.2) / 1.5), 0, .12)
add(cicada(9.0), 0.4, .05, .6)

# ---- intro theme: music box (0–9) ----
theme = [(0, 5), (1, 4), (2, 3), (3, 4), (4, 2), (6, 3), (7, 1), (8, 0), (9, 1), (10, 2)]
for b, deg in theme:
    add(musicbox(D4 * SCALE[deg] * 2), .6 + b * beat, .22, .2)
add(pad([D4 / 2, D4 * 3 / 4, D4 * 5 / 8], 9.0, 2.0), .3, .08)
add(bell(D4 * 4), 3.2, .08)  # scene change shimmer
# ---- box opens (9.4–12.2) ----
for i in range(4):
    add(clack(.07, 900 + i * 80), 9.40 + i * .075, .25, -.2)
add(whoosh(.35), 9.45, .35)
for j, deg in enumerate([0, 2, 3, 5, 7]):
    add(bell(D4 * 2 * SCALE[deg], 2.5), 9.72 + j * .06, .12, -.5 + j * .25)
for i, deg in enumerate([3, 5, 7]):
    add(musicbox(D4 * 2 * SCALE[deg], 2.5), 10.6 + i * .35, .25, -.5 + i * .5)
add(pad([D4 / 2, D4 * 3 / 4, D4 * 9 / 8], 4.4, 1.0), 9.8, .09)
# ---- playful pizzicato under the dialogue (12.2–14.9) ----
pizz = [0, 2, 4, 2, 5, 4, 2, 3]
for i, deg in enumerate(pizz):
    add(pluck(D4 * SCALE[deg]), 12.2 + i * beat / 2 * 1.3, .3, (-1) ** i * .3)
# ---- the flip (14.9–16.4) ----
add(whoosh(.25), 14.85, .5, .3)
add(pop(), 15.3, .8)
add(whoosh(.6), 15.7, .5, .1)
# ---- downpour: comic silence, just rain (16.4–20.6) ----
add(thunder(), 16.5, .35)
r1 = rain(1.9, 1.3)
add(r1 * np.minimum(1, t_arr(1.9) / .08), 16.5, .85)
r2 = rain(2.4, 1.6)
add(r2, 18.2, 1.0)
# deadpan two-note "womp" under 気前がいいね
for j, f in enumerate([D4 / 2 * 3 / 2, D4 / 2 * 4 / 3]):
    add(pad([f], .7, .05) * 1.4, 18.9 + j * .55, .25)
add(clack(.1, 2200) * .8, 19.7, .3, .6)  # the fox inset pops in
add(bell(D4 * 4 * 5 / 4, .6), 19.72, .08, .6)
# ---- bloom (20.6–23) ----
for j, deg in enumerate([0, 1, 2, 3, 4, 5, 6, 7]):
    add(pluck(D4 * SCALE[deg] * 2, 1.2, .997), 20.85 + j * .045, .22, -.6 + j * .17)
add(bell(D4 * 4, 3), 21.2, .15)
add(pad([D4 / 2, D4 * 3 / 4, D4 * 5 / 4], 5.8, 1.2), 21.0, .12)
for b, deg in enumerate([5, 4, 3, 1]):
    add(musicbox(D4 * SCALE[deg] * 2, 2.6), 21.9 + b * beat, .2, .2)
# ---- walking off with his own cloud (23–26.4) ----
for i in range(7):
    add(clack(.06, 700 + (i % 2) * 120) * .9, 23.2 + i * .45, .16, (-1) ** i * .2)  # geta steps
add(rain(3.4, .4), 23.0, .22, .1)
add(pop(.15) * .8, 24.45, .35, .3)  # tiny umbrella opens
add(musicbox(D4 * 2 * SCALE[7], 1.5), 24.5, .1, .3)
# ---- title (26.4–30): resolve, then only rain remains ----
add(pad([D4 / 2, D4 * 3 / 4, D4 * 5 / 4, D4], 3.0, .4), 26.5, .16)
for j, deg in enumerate([0, 3, 5, 7]):
    add(musicbox(D4 * SCALE[deg] * 2, 3.0), 26.6 + j * .11, .2, -.3 + j * .2)
end_rain = rain(3.6, .8)
tt = t_arr(3.6)
add(end_rain * np.minimum(1, tt / 1.2) * np.minimum(1, (3.6 - tt) / 1.0), 26.4, .45)

# ---- master: small hall + soft limiter ----
ir_t = t_arr(1.6)
ir = rng.standard_normal((len(ir_t), 2)) * np.exp(-ir_t * 3.5)[:, None]
L = N + len(ir_t)
wet = np.stack([np.fft.irfft(np.fft.rfft(mix[:, c], L) * np.fft.rfft(ir[:, c], L), L)[:N] for c in range(2)], 1)
wet /= np.abs(wet).max() + 1e-9
out = mix / (np.abs(mix).max() + 1e-9) + wet * .22
out = np.tanh(out * 1.2)
out = out / np.abs(out).max() * .9

path = sys.argv[1] if len(sys.argv) > 1 else "sound.wav"
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote", path)
