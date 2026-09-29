"""Soundtrack for the lyric video (lyric.html): a lo-fi piano ballad at 80 BPM on
the 王道進行 (IV-V-iii-vi) in D. The band drops out for the rain and the end
leaves only rain.
    python3 sound_lyric.py [out.wav]
"""
import sys
import wave

import numpy as np

SR = 44100
DUR = 33.0
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


BEAT = 0.75  # 80 BPM
BAR = 3.0
D4 = 293.66


def note(n):
    """semitones from D4"""
    return D4 * 2 ** (n / 12)


def piano(freq, dur=3.0, vel=1.0):
    # additive piano: slightly stretched partials, faster decay up high, hammer thump
    t = t_arr(dur)
    s = np.zeros(len(t))
    for k in range(1, 9):
        f = freq * k * (1 + .0004 * k * k)
        if f > 16000:
            break
        s += (1 / k ** 1.3) * np.sin(2 * np.pi * f * t) * np.exp(-t * (1.1 + k * .5 + freq / 900))
    ham = bandnoise(dur, 200, 2500) * np.exp(-t * 80) * .15
    env = (1 - np.exp(-t * 600))
    return (s + ham) * env * vel


def crackle(dur):
    out = np.zeros(int(dur * SR))
    for _ in range(int(dur * 25)):
        i = rng.integers(0, len(out) - 60)
        out[i:i + 60] += rng.uniform(-1, 1) * np.exp(-np.arange(60) / 8)
    return out * .5 + bandnoise(dur, 3000, 9000) * .03


def kick(dur=.4):
    t = t_arr(dur)
    f = 42 + 70 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)


def snare(dur=.3):
    t = t_arr(dur)
    return bandnoise(dur, 1200, 6000) * np.exp(-t * 18) * .7 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * .4


def hat(dur=.06):
    t = t_arr(dur)
    return bandnoise(dur, 7000, 14000) * np.exp(-t * 70)


# 王道進行 in D: G  A  F#m  Bm   (IV V iii vi); chord tones as semitones from D4
CH = {
    "G": [-7, -3, 0, 4], "A": [-5, -1, 2, 7], "F#m": [-8, -5, -1, 4], "Bm": [-3, 0, 4, 9], "D": [-12, -5, 0, 4], "Gmaj7": [-7, -3, 0, 4, 9],
}
PROG = ["G", "A", "F#m", "Bm"]


def chord_at(bar):
    return PROG[bar % 4]


def comp(bar, at, style="arp", vel=.5):
    c = CH[chord_at(bar)]
    root = c[0] - 12
    add(piano(note(root), 3.2, vel * 1.1), at, .5, -.1)
    if style == "arp":
        pat = [c[1], c[2], c[3], c[2], c[1] + 12, c[2], c[3], c[2]]
        for i, n in enumerate(pat):
            add(piano(note(n), 1.6, vel * .55), at + i * BEAT / 2, .35, .25 if i % 2 else -.05)
    elif style == "block":
        for n in c[1:]:
            add(piano(note(n), 2.8, vel * .5), at, .35, .1)
    elif style == "stab":
        for j in range(4):
            for n in c[1:]:
                add(piano(note(n + 12), .5, vel * .45) * np.exp(-t_arr(.5) * 6), at + j * BEAT, .3, .1)


# ---- bar 0 (0–3): intro, just a broken Gmaj7 ----
for i, n in enumerate([-7, -3, 2, 9, 7, 2]):
    add(piano(note(n), 3.0, .5), .3 + i * .4, .35, -.2 + i * .08)
add(crackle(33.0), 0, .05)

# ---- bars 1–4 (3–15): verse, arpeggios + soft beat from bar 2 ----
melody = {  # bar: [(beat, semitone), ...]
    1: [(0, 9), (1, 7), (2, 4), (3, 2)],
    2: [(0, 4), (1.5, 7), (2, 9), (3, 7)],
    3: [(0, 11), (1, 9), (2, 7), (2.5, 4), (3, 2)],
    4: [(0, 2), (1, 4), (2, 7), (3, 9)],
    8: [(0, 14), (1, 12), (2, 11), (3, 9)],
}
for bar in range(1, 5):
    at = bar * BAR
    comp(bar, at, "arp", .55)
    if bar >= 2:
        for b in range(4):
            add(kick(), at + b * BEAT, .35 if b % 2 == 0 else .0)
            if b % 2 == 1:
                add(snare(), at + b * BEAT, .18)
            add(hat(), at + b * BEAT + BEAT / 2, .06, .3)
for bar, notes in melody.items():
    for b, n in notes:
        add(piano(note(n + 12), 2.2, .6), bar * BAR + b * BEAT, .4, .1)
# box shimmer
for j, n in enumerate([7, 11, 14, 19, 21]):
    add(piano(note(n + 12), 2.5, .35), 13.0 + j * .12, .3, -.4 + j * .2)

# ---- bar 5 (15–18): playful staccato, quickened ----
comp(5, 15.0, "stab", .6)
for i, n in enumerate([9, 11, 9, 7, 4, 2, 4, 7]):
    add(piano(note(n + 12), .5, .5) * np.exp(-t_arr(.5) * 5), 15.0 + i * BEAT / 2, .35, .2)
for b in range(4):
    add(kick(), 15.0 + b * BEAT, .3)
    add(hat(), 15.0 + b * BEAT + BEAT / 2, .07)
add(snare(.4) * 1.2, 17.25, .35)  # the flip

# ---- bars 6–7 (18–24): rain. the band drops out; single low notes ----
tt = t_arr(6.2)
add(bandnoise(6.2, 900, 9000) * .5 * np.minimum(1, tt / .3) * np.minimum(1, (6.2 - tt) / .6)
    + bandnoise(6.2, 200, 900) * .35 * np.minimum(1, tt / .3) * np.minimum(1, (6.2 - tt) / .6), 18.0, .5)
for i, n in enumerate([-3, -8]):
    add(piano(note(n), 3.5, .6), 18.2 + i * 1.5, .45)
for i, n in enumerate([4, 2, 0, -1]):
    add(piano(note(n + 12), 2.4, .45), 21.3 + i * BEAT, .35, .15)
add(piano(note(-3), 3.0, .5), 21.3, .35)

# ---- bar 8 (24–27): bloom — full band, higher melody ----
comp(8, 24.0, "arp", .65)
for b in range(4):
    add(kick(), 24.0 + b * BEAT, .4 if b % 2 == 0 else .15)
    if b % 2 == 1:
        add(snare(), 24.0 + b * BEAT, .2)
    add(hat(), 24.0 + b * BEAT + BEAT / 2, .07, .3)
for j, n in enumerate([14, 16, 19, 21, 23, 26]):
    add(piano(note(n + 12), 1.8, .3), 25.3 + j * .06, .25, -.5 + j * .2)

# ---- bars 9–10 (27–33): title — resolve on D, then only rain ----
for n in CH["D"]:
    add(piano(note(n), 5.0, .6), 27.6, .45, .05)
for i, n in enumerate([9, 14, 16, 21]):
    add(piano(note(n + 12), 3.5, .35), 28.0 + i * .5, .3, -.3 + i * .2)
tt = t_arr(4.4)
add((bandnoise(4.4, 900, 9000) * .5 + bandnoise(4.4, 200, 900) * .3) * np.minimum(1, tt / 1.2) * np.minimum(1, (4.4 - tt) / .9), 28.6, .4)

# ---- master: small hall + soft limiter ----
ir_t = t_arr(1.6)
ir = rng.standard_normal((len(ir_t), 2)) * np.exp(-ir_t * 3.5)[:, None]
L = N + len(ir_t)
wet = np.stack([np.fft.irfft(np.fft.rfft(mix[:, c], L) * np.fft.rfft(ir[:, c], L), L)[:N] for c in range(2)], 1)
wet /= np.abs(wet).max() + 1e-9
out = mix / (np.abs(mix).max() + 1e-9) + wet * .22
out = np.tanh(out * 1.9)  # gentle saturation: lifts the average level ~4 dB
out = out / np.abs(out).max() * .9

path = sys.argv[1] if len(sys.argv) > 1 else "sound.wav"
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote", path)
