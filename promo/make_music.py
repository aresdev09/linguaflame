"""Generate the promo soundtrack: an original 15-second lo-fi loop.

Everything is synthesised from scratch with numpy, so the track is
royalty-free by construction: no samples, no third-party recordings.

    python promo/make_music.py
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44_100
DUR = 15.0
BPM = 82.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
N = int(SR * DUR)
OUT = Path(__file__).resolve().parent / "audio" / "soundtrack.wav"

RNG = np.random.default_rng(20261022)


def midi(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def adsr(
    n: int, attack: float = 0.01, decay: float = 0.25, sustain: float = 0.5, release: float = 0.4
) -> np.ndarray:
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    env = np.ones(n, dtype=np.float64)
    a = min(a, n)
    env[:a] = np.linspace(0.0, 1.0, a) ** 0.6
    d = min(d, max(0, n - a))
    if d:
        env[a : a + d] = np.linspace(1.0, sustain, d)
    if a + d < n:
        env[a + d :] = sustain
    r = min(r, n)
    if r:
        env[-r:] *= np.linspace(1.0, 0.0, r) ** 1.4
    return env


def rhodes(freq: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """Warm electric-piano-ish tone: sine carrier with a soft bell attack."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = (
        np.sin(2 * np.pi * freq * t)
        + 0.34 * np.sin(2 * np.pi * freq * 2.001 * t + 0.3)
        + 0.12 * np.sin(2 * np.pi * freq * 3.002 * t)
    )
    bell = 0.22 * np.sin(2 * np.pi * freq * 4.01 * t) * np.exp(-t * 11.0)
    env = (1 - np.exp(-t * 90.0)) * np.exp(-t * 1.35)
    return (body * env + bell * env) * vel * 0.42


def kick(dur: float = 0.32, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = 58 + 82 * np.exp(-t * 34.0)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t * 9.5)
    click = RNG.normal(0, 1, n) * np.exp(-t * 240.0) * 0.28
    return np.tanh((body + click) * 1.7) * vel * 0.55


def snare(dur: float = 0.22, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = RNG.normal(0, 1, n)
    # cheap high-pass to keep it crisp
    noise = np.diff(np.concatenate([[0.0], noise]))
    tone = np.sin(2 * np.pi * 185 * t) * 0.35
    env = np.exp(-t * 22.0)
    return (noise * 0.5 + tone) * env * vel * 0.55


def hat(dur: float = 0.06, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = RNG.normal(0, 1, n)
    noise = np.diff(np.concatenate([[0.0], noise]))
    return noise * np.exp(-t * 70.0) * vel * 0.34


def add(buf: np.ndarray, sig: np.ndarray, at: float, pan: float = 0.0, gain: float = 1.0) -> None:
    start = int(at * SR)
    if start >= buf.shape[0]:
        return
    end = min(buf.shape[0], start + len(sig))
    chunk = sig[: end - start] * gain
    left = np.sqrt(0.5 * (1 - pan))
    right = np.sqrt(0.5 * (1 + pan))
    buf[start:end, 0] += chunk * left
    buf[start:end, 1] += chunk * right


def crackle(n: int) -> np.ndarray:
    """Vinyl surface noise: a soft hiss bed plus random pops."""
    bed = RNG.normal(0, 1, n)
    kernel = np.ones(24) / 24
    bed = np.convolve(bed, kernel, mode="same") * 2.6
    pops = np.zeros(n)
    for _ in range(int(DUR * 26)):
        pos = int(RNG.uniform(0, n - 400))
        size = int(RNG.uniform(20, 120))
        pops[pos : pos + size] += (
            RNG.normal(0, 1, size)
            * RNG.uniform(0.15, 0.5)
            * np.exp(-np.arange(size) / (size * 0.35))
        )
    return bed * 0.05 + pops * 0.16


def build() -> np.ndarray:
    buf = np.zeros((N, 2), dtype=np.float64)

    progression = [
        [45, 60, 64, 67],  # Am7
        [41, 57, 60, 64],  # Fmaj7
        [48, 52, 55, 59],  # Cmaj7
        [43, 59, 62, 64],  # G6
    ]

    # Chords: one per bar, lightly strummed.
    bars = int(np.ceil(DUR / BAR))
    for bar in range(bars):
        at = bar * BAR
        chord = progression[bar % len(progression)]
        for i, note in enumerate(chord):
            offset = at + i * 0.026
            sig = rhodes(midi(note), min(BAR * 0.95, DUR - offset), vel=0.9 - i * 0.05)
            add(buf, sig, offset, pan=(-0.25, 0.15, 0.3, -0.1)[i], gain=0.9)

    # Bass on the downbeat and the third beat.
    for bar in range(bars):
        at = bar * BAR
        root = progression[bar % len(progression)][0] - 12
        for beat in (0, 2):
            start = at + beat * BEAT
            n = int(min(BEAT * 1.6, DUR - start) * SR)
            if n <= 0:
                continue
            t = np.arange(n) / SR
            sig = (
                np.sin(2 * np.pi * midi(root) * t) + 0.3 * np.sin(2 * np.pi * midi(root) * 2 * t)
            ) * np.exp(-t * 2.2)
            add(buf, sig * 0.2, start, pan=0.0)

    # Airy music-box arpeggio an octave above the chords: it carries the melody
    # on phone speakers, where everything below ~200 Hz disappears.
    for bar in range(bars):
        voices = progression[bar % len(progression)][1:]
        for step in range(8):
            at = bar * BAR + step * BEAT / 2
            if at >= DUR:
                break
            note = voices[step % len(voices)] + 12
            n = int(min(0.8, DUR - at) * SR)
            if n <= 0:
                continue
            tt = np.arange(n) / SR
            f = midi(note)
            sig = (np.sin(2 * np.pi * f * tt) + 0.45 * np.sin(2 * np.pi * f * 2 * tt)) * np.exp(
                -tt * 6.2
            )
            vel = 0.75 if step % 2 == 0 else 0.45
            add(buf, sig * 0.1 * vel, at, pan=0.38 if step % 2 else -0.38)

    # Drums.
    for beat_index in range(int(np.ceil(DUR / BEAT))):
        at = beat_index * BEAT
        in_bar = beat_index % 4
        if in_bar in (0, 2):
            add(buf, kick(), at, pan=0.0, gain=1.0)
        if in_bar in (1, 3):
            add(buf, snare(), at, pan=0.05, gain=0.85)
        add(buf, hat(vel=0.9 if in_bar % 2 == 0 else 0.6), at + BEAT * 0.5, pan=0.3)
        add(buf, hat(vel=0.45), at + BEAT * 0.25, pan=-0.2)

    # Vinyl noise, very low.
    add(buf, crackle(N), 0.0, pan=0.0, gain=0.55)

    # Gentle sidechain pump on the music bed, keyed to the kick.
    duck = np.ones(N)
    for beat_index in range(int(np.ceil(DUR / BEAT))):
        if beat_index % 4 in (0, 2):
            start = int(beat_index * BEAT * SR)
            length = int(0.24 * SR)
            end = min(N, start + length)
            envelope = 1 - 0.22 * np.exp(-np.arange(end - start) / (0.055 * SR))
            duck[start:end] = np.minimum(duck[start:end], envelope)
    buf *= duck[:, None]

    # Master: soft clip, fades, normalise.
    buf = np.tanh(buf * 1.25)
    fade_in = int(0.12 * SR)
    fade_out = int(1.1 * SR)
    buf[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    buf[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 1.3

    peak = float(np.max(np.abs(buf))) or 1.0
    buf = buf / peak * 0.82
    return buf


def write(buf: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(buf * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(pcm.tobytes())
    print(f"audio: {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    write(build(), OUT)
