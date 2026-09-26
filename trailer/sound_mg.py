"""Soundtrack for the motion-graphics cut (mg.html), cued to its 100 BPM grid.
    python3 sound_mg.py [out.wav]
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
SCALE = [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2, 9 / 4, 5 / 2]
B = 0.6  # 100 BPM


def kick(dur=.35):
    t = t_arr(dur)
    f = 45 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def shaker(dur=.07):
    t = t_arr(dur)
    return bandnoise(dur, 5000, 12000) * np.exp(-t * 60)


def clap(dur=.18):
    t = t_arr(dur)
    return bandnoise(dur, 900, 4000) * np.exp(-t * 30)


def in_gag(at):
    return 15.6 <= at < 19.8


# ---- groove: soft kick + shaker from 2.4 to 25.8, dropped for the rain gag ----
for i in range(int(30 / B * 2)):
    at = i * B / 2
    if not (2.4 <= at < 25.8) or in_gag(at):
        continue
    if i % 2 == 0:
        add(kick(), at, .5 if i % 4 == 0 else .3)
    add(shaker(), at, .10 if i % 2 else .06, .4 if i % 2 else -.4)
    if i % 4 == 2:
        add(clap(), at, .18)
# ---- bass: plucked roots, I–vi–IV–V in D ----
roots = [1, 5 / 6, 2 / 3, 3 / 4]
for bar in range(int(30 / (B * 4)) + 1):
    for j in (0, 1.5, 2.5):
        at = bar * 4 * B + j * B
        if not (2.4 <= at < 25.8) or in_gag(at):
            continue
        add(pluck(D4 / 2 * roots[bar % 4], .9, .994), at, .32)
# ---- music box melody over the story ----
for i, deg in enumerate([5, 4, 3, 4, 2, 3, 1, 0, 1, 2, 4, 3, 2, 1, 2, 0]):
    at = 2.4 + i * B
    if not in_gag(at):
        add(musicbox(D4 * SCALE[deg] * 2, 1.8), at, .2, .2)
for i, deg in enumerate([3, 5, 7, 5, 4, 3, 2, 0]):
    add(musicbox(D4 * SCALE[deg] * 2, 1.8), 19.8 + i * B * .75, .2, -.2)

# ---- opening: line swish, sun pop, tick ratchet ----
add(whoosh(.5), .05, .35)
add(pop(.3) * .9, .8, .5)
add(bell(D4 * 4, 2.5), .82, .14)
for i in range(12):
    add(clack(.03, 3200) * .6, 1.1 + i * .06, .08, -.6 + i * .1)
add(whoosh(.4), 2.0, .5)
add(pad([D4 / 2, D4 * 3 / 4], 2.4, .5), 0, .08)
# ---- scene hits ----
add(whoosh(.3), 4.5, .5, -.3)
for i in range(3):
    add(clack(.05, 1300 + i * 200), 4.8 + i * .08, .25, -.4 + i * .4)
add(whoosh(.35), 7.2, .4)
for j, deg in enumerate([0, 2, 3, 5, 7]):
    add(bell(D4 * 2 * SCALE[deg], 2.5), 8.1 + j * .05, .14, -.5 + j * .25)
for i, deg in enumerate([3, 5, 7]):
    add(pop(.2) * .6, 9.0 + i * .3, .35, -.5 + i * .5)
    add(musicbox(D4 * 2 * SCALE[deg] * 2, 1.5), 9.0 + i * .3, .15, -.5 + i * .5)
add(whoosh(.35), 10.45, .5)
add(bell(D4 * 6, 1.2), 12.35, .2)        # the drop lands
add(whoosh(.2), 13.8, .5, .3)             # flip
add(pop(), 14.1, .9)                      # ぽんっ
add(whoosh(.5), 15.1, .6)                 # cloud swallows the frame
# ---- the downpour: groove stops, rain + deadpan womp ----
add(thunder(), 15.62, .45)
add(rain(4.3, 1.5) * np.minimum(1, t_arr(4.3) / .05), 15.6, .9)
add(clap(.25) * 1.2, 16.35, .35)          # 土砂降り slam
for j, f in enumerate([D4 / 2 * 3 / 2, D4 / 2 * 4 / 3]):
    add(pad([f], .6, .04) * 1.4, 18.2 + j * .5, .28)
add(clack(.1, 2200), 19.0, .3, .6)
add(bell(D4 * 5, .6), 19.02, .1, .6)
# ---- bloom ----
for j in range(8):
    add(pluck(D4 * SCALE[j] * 2, 1.2, .997), 20.3 + j * .04, .22, -.6 + j * .17)
add(bell(D4 * 4, 3), 20.4, .16)
add(pad([D4 / 2, D4 * 3 / 4, D4 * 5 / 4], 5.4, 1.0), 20.2, .1)
# ---- walking off ----
for i in range(6):
    add(clack(.06, 700 + (i % 2) * 120) * .9, 22.9 + i * .45, .16, (-1) ** i * .2)
add(rain(3.0, .3), 22.8, .2, .1)
add(pop(.15) * .8, 24.0, .4, .3)
add(whoosh(.35), 25.45, .45)
# ---- title: resolve, then only rain ----
add(pop(.3), 25.8, .4)
add(pad([D4 / 2, D4 * 3 / 4, D4 * 5 / 4, D4], 3.0, .3), 25.9, .16)
for j, deg in enumerate([0, 3, 5, 7]):
    add(musicbox(D4 * SCALE[deg] * 2, 3.0), 26.4 + j * .14, .2, -.3 + j * .2)
tt = t_arr(3.8)
add(rain(3.8, .8) * np.minimum(1, tt / 1.2) * np.minimum(1, (3.8 - tt) / 1.0), 26.2, .45)

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
