"""Write a placeholder ``narration.wav`` for the bubble-sort demo.

manim-stage never synthesises speech (spec F04): record your own narration, or use
any TTS tool, and save it as ``narration.wav``. This script writes a deterministic,
speech-like placeholder (syllable bursts with pauses) so the demo runs out of the box.

    python make_audio.py            # 30 s  -> narration.wav
    python make_audio.py 35 v2.wav  # 35 s take, e.g. to try re-timing cues
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from manim_stage import audio


def speech_like(seconds: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * audio.RATE)) / audio.RATE
    env = np.zeros_like(t)
    s = 0.3
    while s < seconds - 0.5:
        word = rng.uniform(0.15, 0.35)
        env += np.exp(-(((t - s) / (word / 2)) ** 2)) * rng.uniform(0.4, 1.0)
        s += word + rng.uniform(0.05, 0.2) + (0.7 if rng.random() < 0.12 else 0.0)
    pitch = 140 + 30 * np.sin(2 * np.pi * 0.3 * t)
    voice = np.sin(2 * np.pi * np.cumsum(pitch) / audio.RATE) + 0.3 * rng.normal(0, 1, t.size)
    mono = (voice * env * 0.25).astype(np.float32)
    return np.stack([mono, mono], axis=1)


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("narration.wav")
    audio.write_wav(out, speech_like(seconds))
    print(f"wrote {out} ({seconds:g} s)")
