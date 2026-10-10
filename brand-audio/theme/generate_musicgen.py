"""Sparked theme: real-sounding R&B instrumentals via Meta MusicGen (runs on CPU).

Generates several 30s takes from style prompts (no artist names), then makes a
"slowed + reverb" version of each (slow_reverb.py: hall reverb, not echo).

Usage:  python generate_musicgen.py [--set v6] [--rate 0.86] [--wet 0.45] [--model small|medium] [--melody ref.mp3] [--seconds 30]
Output: out/<set>_take<N>.mp3 and out/<set>_take<N>_slowrev.mp3 (MP3: Media Player opens these reliably)
"""
import argparse
import os
import subprocess

import numpy as np
import torch
from scipy.io import wavfile
from slow_reverb import slow_reverb
from transformers import AutoProcessor, AutoTokenizer, MusicgenForConditionalGeneration, MusicgenMelodyForConditionalGeneration

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

PROMPT_SETS = {
    # v2: too dark/intense for the brand (user feedback 2026-10-03), kept for reference
    "v2": [
        "smooth sensual late-night R&B instrumental, dark moody synth pads drenched in reverb, warm electric piano, "
        "deep sliding 808 bass, crisp trap hi-hat rolls, finger snaps, slow 70 bpm, minor key, polished studio mix",
        "slowed and reverbed 2010s R&B slow jam instrumental, dreamy washed-out synths, soft plucked guitar, "
        "heavy reverb, deep sub bass, laid-back drums, romantic and seductive, 65 bpm, high quality",
        "cinematic dark R&B instrumental, seductive minor key synth chords, low male choir hum in the background, "
        "deep 808, big reverberant drums, smooth and confident, 72 bpm, luxurious modern production",
    ],
    # v3: smooth, flirty, playful, light
    "v3": [
        "smooth flirty R&B instrumental, warm mellow Rhodes electric piano chords, soft finger snaps, "
        "gentle bouncy drums, light round bass, playful and charming, feel-good romantic mood, major key, 85 bpm, clean mix",
        "chill playful R&B groove, sweet jazzy electric piano, clean funky guitar licks, soft kick and rimshot, "
        "smooth bassline, light and flirty, sunny and relaxed, 90 bpm, high quality studio recording",
        "laid-back smooth R&B love song instrumental, soft warm keys, airy synth pad, gentle snaps and claps, "
        "mellow bass, easygoing, charming and confident, soft and light, 80 bpm, polished mix",
        "lo-fi smooth R&B beat, mellow electric piano, gentle swing drums, warm bass, soft vinyl texture, "
        "playful flirty vibe, calm and cool, 82 bpm",
    ],
    # v4: v3's smooth flirty vibe + more energy (user: "a bit more energy", ref The Weeknd "Popular" vibe)
    "v4": [
        "upbeat smooth R&B pop instrumental, glossy shimmering synths, warm Rhodes chords, punchy drums with crisp claps, "
        "pulsing synth bass, confident and flirty, danceable, 100 bpm, polished modern radio mix",
        "energetic sleek R&B instrumental, driving groove, bright airy synth melody, tight snappy drums, "
        "groovy round bassline, playful and seductive, feel-good night out, 102 bpm, high quality studio production",
        "modern synth R&B groove, smooth electric piano, bouncy upbeat drums with claps and open hi-hats, "
        "pulsing bass, charming, stylish and confident, 98 bpm, clean punchy mix",
        "upbeat flirty R&B instrumental, funky clean guitar, warm keys, sparkling synths, punchy kick and clap, "
        "groovy bass, smooth but energetic, 104 bpm, polished",
    ],
    # v6: Sparked theme (electric, fire, chemistry) + golden-hour sunset date, smooth talker serenading (daygame, not late night).
    # User refs (style only, never in prompts): Drake "Passionfruit", Bobby Caldwell, Chris Brown "No Guidance", Bobby V "Slow Down"
    "v6": [
        "smooth sunset R&B instrumental with electric chemistry, warm Rhodes chords, sparkling glittering synth arpeggios, "
        "soft muted guitar plucks, light tropical bounce, warm pulsing bass, romantic and magnetic, 96 bpm, lush reverb",
        "sultry smooth soul R&B instrumental, silky Rhodes, shimmering tremolo electric guitar, soft crackling fire ambience, "
        "groovy bass guitar, finger snaps, golden hour serenade, warm and passionate, 92 bpm, warm analog recording",
        "electric smooth R&B groove, warm buzzing synth bass, bright sparkling synth plucks, crisp claps and snaps, "
        "mellow guitar loop, flirty heat and attraction, evening date, 94 bpm, polished spacious mix",
        "warm fiery R&B slow jam instrumental, glowing electric piano, sizzling hi-hats, plucked guitar, sparkle chimes, "
        "smooth deep bass, passionate yet smooth, sunset romance, 90 bpm, high quality",
    ],
    # v7 FAILED: musicgen-melody takes came out shrill (31-75% energy >1.5 kHz, user: "ear rape"); qa music-harshness now gates this.
    # v7: melody-conditioned on v4_take1 (user favourite; v5/v6 text-only takes sounded "generic, not a real tune").
    # Adds the missing dating feel + "cool" (confident swagger) + Sparked chemistry + polarity (masc/fem push-pull).
    "v7": [
        "cool confident smooth R&B love song instrumental, romantic sunset date, push and pull tension between a deep "
        "grounded bassline and a light airy melody, warm Rhodes, soft guitar licks, tight bouncy drums, flirty swagger, "
        "catchy memorable melody, polished radio mix",
        "romantic smooth R&B serenade with swagger, call and response between deep masculine bass and sweet airy "
        "feminine synth melody, silky keys, crisp claps, cool and confident, sparks of chemistry, tension and release, "
        "100 bpm, high quality",
        "sleek cool R&B pop instrumental, magnetic attraction, contrast of dark low bass and bright sparkling plucks, "
        "glossy synths, punchy drums, catchy hook melody, golden hour date, flirty romantic chemistry, smooth and stylish",
    ],
    # v8: text-only on musicgen-medium (better musicality than small). Built from v4_take1's prompt (user favourite)
    # + dating feel + cool + polarity. Avoids "bright/sparkling/shimmering", which pushed takes shrill.
    "v8": [
        "upbeat smooth R&B instrumental, warm Rhodes chords, warm glossy synths, punchy drums with soft claps, "
        "deep pulsing bass, cool and confident, flirty romantic date at sunset, catchy smooth melody, 100 bpm, warm mellow mix",
        "smooth R&B love song instrumental, deep grounded bassline with a soft airy melody answering it, warm electric piano, "
        "groovy drums, mellow guitar, romantic chemistry, cool swagger, 96 bpm, warm polished studio mix",
        "romantic upbeat R&B groove, warm Rhodes, smooth bass guitar, tight laid-back drums, soft finger snaps, "
        "magnetic attraction, confident and charming serenade, golden hour, 98 bpm, warm smooth mix",
    ],
}


def melody_chroma(wav, sr, n_fft=16384, hop=4096, n_chroma=12):
    """Port of MusicgenMelodyFeatureExtractor._torch_extract_fbank_features without torchaudio:
    power spectrogram (hann, centred, window-normalised) -> chroma bank -> one-hot argmax per frame."""
    from transformers.audio_utils import chroma_filter_bank

    win = torch.hann_window(n_fft)
    spec = torch.stft(wav, n_fft, hop, n_fft, win, center=True, pad_mode="reflect", return_complex=True)
    spec = (spec.abs() / win.pow(2).sum().sqrt()) ** 2
    bank = torch.from_numpy(chroma_filter_bank(sampling_rate=sr, num_frequency_bins=n_fft, tuning=0, num_chroma=n_chroma)).float()
    chroma = torch.nn.functional.normalize(bank @ spec, p=float("inf"), dim=-2, eps=1e-6).T  # (time, chroma)
    onehot = torch.zeros_like(chroma).scatter_(-1, chroma.argmax(-1, keepdim=True), 1.0)
    return onehot.unsqueeze(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="small", choices=["small", "medium"])
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--rate", type=float, default=0.86, help="slowed-version speed")
    ap.add_argument("--wet", type=float, default=0.45, help="slowed-version reverb amount")
    ap.add_argument("--melody", help="audio file whose melody/chords condition the takes (uses musicgen-melody)")
    ap.add_argument("--set", default="v8", choices=list(PROMPT_SETS))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    prompts = PROMPT_SETS[args.set]
    if args.melody:
        name, cls = "facebook/musicgen-melody", MusicgenMelodyForConditionalGeneration
    else:
        name, cls = f"facebook/musicgen-{args.model}", MusicgenForConditionalGeneration
    # melody mode: tokenizer only; chroma is computed by melody_chroma() (the HF processor needs torchaudio,
    # which has no build for torch 2.14)
    processor = (AutoTokenizer if args.melody else AutoProcessor).from_pretrained(name)
    model = cls.from_pretrained(name)
    sr = model.config.audio_encoder.sampling_rate
    tokens = int(args.seconds * model.config.audio_encoder.frame_rate)

    torch.manual_seed(11)
    if args.melody:
        pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", args.melody, "-t", str(args.seconds), "-ac", "1",
                              "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        mel = torch.from_numpy(np.frombuffer(pcm, np.float32).copy())
        inputs = processor(prompts, padding=True, return_tensors="pt")
        inputs["input_features"] = melody_chroma(mel, sr).repeat(len(prompts), 1, 1)
    else:
        inputs = processor(text=prompts, padding=True, return_tensors="pt")
    with torch.no_grad():
        audio = model.generate(**inputs, do_sample=True, guidance_scale=3.5, max_new_tokens=tokens)

    for i, a in enumerate(audio[:, 0].numpy(), 1):
        a = a / (np.max(np.abs(a)) + 1e-9) * 0.9
        raw = os.path.join(OUT, f"_{args.set}_take{i}_raw.wav")
        wavfile.write(raw, sr, a.astype(np.float32))
        base = os.path.join(OUT, f"{args.set}_take{i}")
        fade = f"afade=t=in:d=0.5,afade=t=out:st={args.seconds - 2.5}:d=2.5"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                        f"{fade},alimiter=limit=0.5:level=false,loudnorm=I=-14:TP=-1", "-ar", "44100", "-b:a", "320k", base + ".mp3"], check=True)
        slow_reverb(base + ".mp3", base + "_slowrev.mp3", args.rate, args.wet)
        os.remove(raw)
        print("wrote", base + ".mp3", "and _slowrev.mp3")

    # quality gate: harshness + loudness (qa/checks_audio.py); never hand a failing take to the user
    outs = [os.path.join(OUT, f"{args.set}_take{i}{sfx}.mp3") for i in range(1, len(prompts) + 1) for sfx in ("", "_slowrev")]
    qa = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "qa", "run_checks.py")
    subprocess.run(["python", qa, "--level", "full", *outs])


if __name__ == "__main__":
    main()
