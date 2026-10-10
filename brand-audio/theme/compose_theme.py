"""Sparked theme song: synthesized from code, no samples.

Concept: flirty R&B (neo-soul Rhodes, sub bass, swung hats, half-time snare)
with a hint of Viking (war-horn call, taiko/frame-drum hits, low male choir drone),
mixed clean and spacious for a high-end feel. D minor (Dorian colour), 76 BPM.

Usage:  python compose_theme.py            -> out/sparked_theme.{wav,mp3}, out/sparked_sting.{wav,mp3}
"""
import os
import subprocess

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
BPM = 76
B = 60 / BPM  # seconds per beat
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
rng = np.random.default_rng(7)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(n):
    return np.arange(n) / SR


def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, kind, fs=SR, output="sos"), x, axis=0)


def release_env(t, dur, rel):
    return np.where(t < dur, 1.0, np.exp(-(t - dur) / rel))


# ---------------------------------------------------------------- instruments
def rhodes(m, dur, vel):
    f = mtof(m)
    n = int((dur + 1.0) * SR)
    t = tt(n)
    idx = (0.5 + 1.6 * vel) * np.exp(-t / 0.22) + 0.12
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    y += 0.10 * vel * np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t / 0.04)  # tine bark
    amp = np.exp(-t / (1.9 * (220 / f) ** 0.3)) * np.clip(t / 0.002, 0, 1)
    return y * amp * release_env(t, dur, 0.12) * vel


def sub_bass(m, dur, vel=1.0):
    f = mtof(m)
    n = int((dur + 0.3) * SR)
    t = tt(n)
    y = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t)
    y = np.tanh(1.6 * y) / np.tanh(1.6)
    amp = np.clip(t / 0.006, 0, 1) * (0.75 + 0.25 * np.exp(-t / 0.3))
    return y * amp * release_env(t, dur, 0.06) * vel


def kick(vel=1.0):
    n = int(0.6 * SR)
    t = tt(n)
    f = 46 + 85 * np.exp(-t / 0.028)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.32)
    y[:150] += rng.standard_normal(150) * 0.25 * np.linspace(1, 0, 150)
    return np.tanh(1.4 * y) * vel


def snare(vel=1.0):
    n = int(0.5 * SR)
    t = tt(n)
    noise = filt(rng.standard_normal(n), "bandpass", [1400, 7000])
    env = np.zeros(n)
    for k, off in enumerate((0.0, 0.011, 0.022)):  # soft clap flam
        i = int(off * SR)
        env[i:] += np.exp(-(t[: n - i]) / (0.012 if k < 2 else 0.14))
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
    y = 0.55 * noise * env / 2 + 0.35 * tone
    return y / np.max(np.abs(y)) * vel


def hat(vel=1.0, open_=False):
    n = int((0.35 if open_ else 0.08) * SR)
    t = tt(n)
    y = filt(rng.standard_normal(n), "highpass", 7500) * np.exp(-t / (0.11 if open_ else 0.022))
    return y / np.max(np.abs(y)) * vel


def taiko(vel=1.0):
    """Viking war drum: deep pitched skin + felt thump."""
    n = int(1.8 * SR)
    t = tt(n)
    f = 62 + 48 * np.exp(-t / 0.05)
    skin = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    thump = filt(rng.standard_normal(n), "lowpass", 900) * np.exp(-t / 0.05)
    y = np.tanh(1.8 * (skin + 0.6 * thump))
    return y / np.max(np.abs(y)) * vel


def crash(vel=1.0):
    n = int(2.6 * SR)
    t = tt(n)
    y = filt(rng.standard_normal(n), "highpass", 4500) * np.exp(-t / 0.8)
    return y / np.max(np.abs(y)) * vel


def riser(beats, vel=1.0):
    n = int(beats * B * SR)
    t = tt(n)
    y = filt(rng.standard_normal(n), "bandpass", [2000, 9000]) * (t / t[-1]) ** 2.5
    return y / np.max(np.abs(y)) * vel


def horn(m, dur, vel=1.0, detune_cents=0.0):
    """Lur / war horn: additive brass with a scoop, opening brightness and late vibrato."""
    f0 = mtof(m) * 2 ** (detune_cents / 1200)
    n = int((dur + 0.4) * SR)
    t = tt(n)
    cents = -55 * np.exp(-t / 0.05) + 11 * np.sin(2 * np.pi * 5.0 * t) * np.clip((t - 0.45) / 0.4, 0, 1)
    phase = 2 * np.pi * np.cumsum(f0 * 2 ** (cents / 1200)) / SR
    bright = np.clip(t / 0.09, 0, 1) * (0.4 + 0.6 * np.exp(-t / 0.5))
    y = np.zeros(n)
    for k in range(1, 30):
        if f0 * k > 8000:
            break
        y += k ** -1.0 * np.exp(-(k - 1) / (0.6 + 6.0 * bright)) * np.sin(k * phase)
    env = np.clip(t / 0.06, 0, 1) * release_env(t, dur, 0.22)
    y = y * env
    return y / np.max(np.abs(y)) * vel


VOWELS = {
    "ah": [(700, 1.0, 110), (1220, 0.5, 120), (2600, 0.22, 170)],
    "oh": [(450, 1.0, 80), (800, 0.6, 95), (2830, 0.08, 160)],
    "lead": [(420, 1.0, 120), (1050, 0.45, 160), (2650, 0.2, 220)],
}


def formant_gain(freq, vowel):
    return sum(a * np.exp(-(((freq - F) / bw) ** 2)) for F, a, bw in VOWELS[vowel]) + 0.03


def voice(f0, n, vowel, vib_rate, vib_depth, vib_delay, phase0):
    t = tt(n)
    cents = vib_depth * np.sin(2 * np.pi * vib_rate * t + phase0) * np.clip((t - vib_delay) / 0.3, 0, 1)
    phase = 2 * np.pi * np.cumsum(f0 * 2 ** (cents / 1200)) / SR
    y = np.zeros(n)
    for k in range(1, 60):
        fk = f0 * k
        if fk > 5000:
            break
        y += formant_gain(fk, vowel) * np.sin(k * phase) / k ** 0.5
    return y


def choir(m, dur, vowel="ah", vel=1.0):
    """Low male choir, 4 voices, returns stereo."""
    n = int((dur + 1.4) * SR)
    t = tt(n)
    out = np.zeros((n, 2))
    for det, pan in zip((-9, -3, 4, 10), (-0.6, -0.2, 0.2, 0.6)):
        v = voice(mtof(m) * 2 ** (det / 1200), n, vowel, rng.uniform(4.7, 5.6), 9, 0.2, rng.uniform(0, 6.28))
        a = (pan + 1) * np.pi / 4
        out += np.stack([v * np.cos(a), v * np.sin(a)], 1)
    env = np.sin(np.clip(t / 0.9, 0, 1) * np.pi / 2) ** 2 * release_env(t, dur, 0.9)
    out = filt(out * env[:, None], "lowpass", 4500)
    return out / np.max(np.abs(out)) * vel


def lead(m, dur, vel=1.0):
    """Soft, vocal-ish lead: the flirty hook voice."""
    n = int((dur + 0.4) * SR)
    t = tt(n)
    y = voice(mtof(m), n, "lead", 5.4, 16, 0.28, 0.0)
    y += 0.6 * np.sin(2 * np.pi * np.cumsum(np.full(n, mtof(m))) / SR)
    y += 0.02 * filt(rng.standard_normal(n), "highpass", 3000) * np.exp(-t / 0.05)  # breath
    env = np.clip(t / 0.03, 0, 1) * release_env(t, dur, 0.12)
    y = y * env
    return y / np.max(np.abs(y)) * vel


# ---------------------------------------------------------------- mixer
class Mix:
    def __init__(self, seconds):
        self.n = int(seconds * SR)
        self.dry = np.zeros((self.n, 2))
        self.rev = np.zeros((self.n, 2))
        self.dly = np.zeros((self.n, 2))

    def add(self, sig, beat, gain=1.0, pan=0.0, rev=0.2, delay=0.0):
        if sig.ndim == 1:
            a = (pan + 1) * np.pi / 4
            sig = np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2)
        i = int(round(beat * B * SR))
        if i >= self.n:
            return
        sig = sig[: self.n - i] * gain
        self.dry[i : i + len(sig)] += sig
        self.rev[i : i + len(sig)] += sig * rev
        self.dly[i : i + len(sig)] += sig * delay

    def chord(self, notes, beat, dur, vel, gain):
        """Rhodes chord with stereo tremolo locked to song time."""
        sig = sum(rhodes(m, dur * B, vel * rng.uniform(0.92, 1.0)) for m in notes)
        start = beat * B
        lfo = np.sin(2 * np.pi * 4.2 * (start + tt(len(sig))))
        st = np.stack([sig * (1 + 0.28 * lfo), sig * (1 - 0.28 * lfo)], 1)
        self.add(st, beat, gain=gain, rev=0.3, delay=0.05)

    def render(self):
        # reverb: decorrelated noise IR, ~2.6s RT60, damped highs, 25ms predelay
        ir_n = int(3.2 * SR)
        ir_t = tt(ir_n)
        ir = rng.standard_normal((ir_n, 2)) * np.exp(-ir_t / 0.38)[:, None]
        ir = filt(ir, "lowpass", 5500)
        ir = np.concatenate([np.zeros((int(0.025 * SR), 2)), ir]) / np.sqrt(np.sum(ir**2) / 2)
        wet = np.stack([fftconvolve(self.rev[:, c], ir[:, c])[: self.n] for c in range(2)], 1)
        # ping-pong dotted-eighth delay
        d = filt(self.dly, "lowpass", 3800)
        echo = np.zeros_like(d)
        step = int(0.75 * B * SR)
        for k in range(1, 6):
            sh = np.zeros_like(d)
            sh[k * step :] = d[: -k * step]
            g = 0.5 * 0.42 ** (k - 1)
            echo += sh * (np.array([1.0, 0.35]) if k % 2 else np.array([0.35, 1.0])) * g
        wet += 0.35 * np.stack([fftconvolve(echo[:, c], ir[:, c])[: self.n] for c in range(2)], 1)
        y = self.dry + 0.45 * wet + echo
        y = filt(y, "highpass", 28)
        y /= np.max(np.abs(y)) + 1e-9
        y = np.tanh(1.4 * y) / np.tanh(1.4)  # gentle glue
        fade = int(0.6 * SR)
        y[-fade:] *= np.linspace(1, 0, fade)[:, None]
        return y.astype(np.float32)


# ---------------------------------------------------------------- score
DM9, GM9, BBMAJ9 = [53, 57, 60, 64], [57, 58, 62, 65], [57, 60, 62, 65]
A7SUS, A7B9 = [55, 57, 62, 64], [55, 58, 61, 64]
PROG = [  # (rhodes voicing, bass root, choir notes)
    ("Dm9", DM9, 38, (50, 57)),
    ("Gm9", GM9, 31, (55, 50)),
    ("Bbmaj9", BBMAJ9, 34, (53, 58)),
    ("A7", None, 33, (52, 57)),
]
HOOK_A = [
    [(1.0, 69, 0.5), (1.5, 72, 0.5), (2.0, 74, 1.75)],
    [(0.5, 77, 0.5), (1.0, 76, 0.5), (1.5, 74, 0.5), (2.0, 72, 1.0), (3.0, 74, 0.75)],
    [(1.0, 69, 0.5), (1.5, 72, 0.5), (2.0, 74, 0.5), (2.5, 77, 1.25)],
    [(0.0, 76, 1.0), (1.5, 73, 0.5), (2.0, 76, 1.5)],
]
HOOK_B = HOOK_A[:2] + [
    [(1.0, 69, 0.5), (1.5, 72, 0.5), (2.0, 74, 0.5), (2.5, 81, 1.25)],
    [(0.0, 79, 0.75), (0.75, 77, 0.5), (1.25, 76, 0.75), (2.0, 73, 0.5), (2.5, 76, 0.5), (3.0, 76, 0.5), (3.5, 73, 0.5)],
]
HORN_CALL = [(0.0, 62, 1.5), (1.5, 65, 0.5), (2.0, 69, 2.0), (4.0, 67, 0.5), (4.5, 65, 0.5), (5.0, 62, 2.5)]


def play_horn(mx, notes, at, gain):
    for b, m, d in notes:
        mx.add(horn(m, d * B, 1.0, -6), at + b, gain=gain, pan=-0.25, rev=0.45)
        mx.add(horn(m, d * B, 1.0, +6), at + b, gain=gain, pan=0.25, rev=0.45)


VOICE_LINE = "Sparked... Thor."
VOICE = "en-US-AndrewNeural"  # warm, confident; slowed + pitched down for a smooth read


def voice_tag():
    """TTS 'Sparked Thor' (cached in out/), returned as mono float at SR."""
    os.makedirs(OUT, exist_ok=True)
    mp3, wav = os.path.join(OUT, "_voice.mp3"), os.path.join(OUT, "_voice.wav")
    if not os.path.exists(mp3):
        subprocess.run(["python", "-m", "edge_tts", "--voice", VOICE, "--rate=-18%", "--pitch=-12Hz",
                        "--text", VOICE_LINE, "--write-media", mp3], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
                    "-af", "silenceremove=start_periods=1:start_threshold=-45dB,lowshelf=g=3:f=180", wav], check=True)
    sr, v = wavfile.read(wav)
    v = v.astype(np.float64) / (32768.0 if v.dtype == np.int16 else 1.0)
    return v / np.max(np.abs(v))


def compose_theme():
    """30s: 1-bar Viking intro, 6-bar R&B groove, outro hit with the voice tag."""
    mx = Mix(30.0)

    # Intro (bar 0): choir drone, war drums, horn call, Rhodes swell into the groove
    mx.add(choir(50, 4 * B, "oh"), 0, gain=0.30, rev=0.5)
    mx.add(choir(57, 4 * B, "oh"), 0, gain=0.22, rev=0.5)
    mx.add(choir(38, 4 * B, "oh"), 0, gain=0.18, rev=0.3)
    for b, v in [(0, 1.0), (2.0, 0.6), (3.0, 0.6), (3.5, 0.85)]:
        mx.add(taiko(v), b, gain=0.55, rev=0.4)
    play_horn(mx, HORN_CALL[:3], 0, 0.20)
    mx.chord(A7B9, 2.5, 1.5, 0.5, 0.15)
    mx.add(riser(2), 2, gain=0.10, rev=0.3)

    # Groove (bars 1-6): Dm9 Gm9 Bbmaj9 A7 | Bbmaj9 A7 (lift)
    for bar in range(1, 7):
        at = bar * 4
        pidx = (bar - 1) % 4 if bar <= 4 else bar - 3
        name, voicing, root, ch = PROG[pidx]
        second = bar >= 5
        if voicing:
            mx.chord(voicing, at, 2.3, 0.75, 0.16)
            mx.chord(voicing, at + 2.5, 1.3, 0.55, 0.13)
        else:
            mx.chord(A7SUS, at, 1.9, 0.75, 0.16)
            mx.chord(A7B9, at + 2, 1.9, 0.65, 0.15)
        for b, d, m, v in [(0, 1.5, root, 1.0), (1.75, 0.5, root, 0.8), (2.5, 0.9, root, 0.9), (3.5, 0.4, root + 12, 0.6)]:
            mx.add(sub_bass(m, d * B, v), at + b, gain=0.42, rev=0.0)
        for m in ch:
            mx.add(choir(m, 4.2 * B, "ah"), at, gain=0.09 if second else 0.06, rev=0.5)
        # drums: half-time R&B pocket, swung 16ths
        for b in [0, 1.75] + ([2.5] if bar % 2 else [2.75]):
            mx.add(kick(), at + b, gain=0.55, rev=0.02)
        mx.add(snare(), at + 2, gain=0.30, rev=0.35)
        if bar % 2 == 0:
            mx.add(snare(0.3), at + 3.75, gain=0.30, rev=0.3)
        for i in range(16):
            b = i * 0.25 + (0.06 if i % 2 else 0.0)
            if i == 14 and bar % 2 == 0:
                mx.add(hat(0.6, True), at + b, gain=0.07, pan=0.3, rev=0.15)
                continue
            mx.add(hat([0.75, 0.3, 0.5, 0.3][i % 4] * rng.uniform(0.85, 1.0)), at + b, gain=0.08, pan=0.3, rev=0.1)
        # Viking accents
        if bar % 2 == 1:
            mx.add(taiko(0.9 if bar == 1 else 0.6), at, gain=0.40, rev=0.4)
        if second:
            mx.add(taiko(0.45), at + 2, gain=0.35, rev=0.4)
        # hook
        phrase = HOOK_A[pidx] if not second else HOOK_B[pidx]
        for b, m, d in phrase:
            mx.add(lead(m, d * B, 0.9), at + b, gain=0.20, rev=0.3, delay=0.22)
    mx.add(crash(0.8), 4, gain=0.06, pan=-0.2, rev=0.3)
    mx.add(crash(0.7), 20, gain=0.05, pan=0.2, rev=0.3)
    play_horn(mx, [(20, 65, 2.0), (22, 67, 1.8), (24, 64, 1.9), (26, 61, 1.9)], 0, 0.08)
    for b, v in [(27, 0.5), (27.25, 0.6), (27.5, 0.75), (27.75, 0.95)]:
        mx.add(taiko(v), b, gain=0.42, rev=0.4)

    # Outro (beat 28 = 22.1s): big Dm9 resolve, horn answers, voice tag, ring out
    at = 28
    mx.add(taiko(1.0), at, gain=0.6, rev=0.5)
    mx.add(kick(), at, gain=0.55)
    mx.add(crash(1.0), at, gain=0.08, rev=0.4)
    mx.chord([50, 57, 60, 64, 69], at, 6, 0.8, 0.13)
    mx.add(sub_bass(38, 6 * B), at, gain=0.40, rev=0.0)
    for m in (50, 57, 62):
        mx.add(choir(m, 6 * B, "ah"), at, gain=0.07, rev=0.55)
    play_horn(mx, HORN_CALL[:3], at, 0.10)
    mx.add(voice_tag(), at + 1.25, gain=0.95, rev=0.12, delay=0.06)
    return mx.render()


def compose_sting():
    mx = Mix(4 * B + 3.0)
    mx.add(taiko(1.0), 0, gain=0.6, rev=0.5)
    mx.add(choir(50, 4 * B, "oh"), 0, gain=0.22, rev=0.5)
    mx.add(choir(57, 4 * B, "oh"), 0, gain=0.16, rev=0.5)
    play_horn(mx, [(0.0, 62, 0.75), (0.75, 65, 0.25), (1.0, 69, 2.6)], 0, 0.22)
    mx.add(kick(), 1, gain=0.5)
    mx.add(crash(0.9), 1, gain=0.07, rev=0.4)
    mx.chord([50, 57, 60, 64, 69], 1, 3, 0.8, 0.18)
    mx.add(sub_bass(38, 3 * B), 1, gain=0.4, rev=0.0)
    mx.add(lead(74, 2.0 * B, 0.9), 1.5, gain=0.18, rev=0.35, delay=0.3)
    return mx.render()


def export(y, name):
    os.makedirs(OUT, exist_ok=True)
    raw = os.path.join(OUT, f"_{name}_raw.wav")
    wavfile.write(raw, SR, y)
    base = os.path.join(OUT, name)
    norm = "loudnorm=I=-14:TP=-1.0:LRA=11"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", norm, "-ar", str(SR), "-c:a", "pcm_s24le", base + ".wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", base + ".wav", "-b:a", "320k", base + ".mp3"], check=True)
    os.remove(raw)
    print(f"{name}: {len(y) / SR:.1f}s -> {base}.wav / .mp3")


if __name__ == "__main__":
    export(compose_theme(), "sparked_theme")
    export(compose_sting(), "sparked_sting")
