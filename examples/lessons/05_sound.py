"""Lesson 05: Narration, bookmarks and sound effects.

Ideas from manim-voiceover (``with self.voiceover(...)`` and ``<bookmark/>`` tags) and
the Motion Canvas "Media" guide (an audio track that drives the timing). manim-stage
plays *recorded* audio through Manim's ``add_sound`` and ``add_subcaption``; bookmarks
become named cues that you can drag on the timeline.

The two scenes write placeholder ``.wav`` files on first run (speech-like bursts and a
click) so the lesson works out of the box. Replace ``narration_lesson.wav`` with your
own recording and the scene re-times itself.

    manim-stage studio 05_sound.py Narrated
    manim-stage studio 05_sound.py SoundEffects

Try in the Studio:
- the Audio lane shows the waveform; the Captions lane shows the subcaption;
- drag the ``intro.show_sum`` bookmark cue to match your recording;
- Add audio… (Ctrl+Shift+A) drops music under the scene without changing the code.
"""

from pathlib import Path

import numpy as np
from manim import DOWN, RIGHT, UP, Create, FadeIn, Square, Text, VGroup, Write

from manim_stage import StageScene, audio, project

HERE = Path(__file__).resolve().parent
VOICE = HERE / "narration_lesson.wav"
CLICK = HERE / "click.wav"


def placeholder_audio():
    """Deterministic stand-ins: 6 s of speech-like bursts, and a short click."""
    if not VOICE.exists():
        rng = np.random.default_rng(5)
        t = np.arange(int(6 * audio.RATE)) / audio.RATE
        env = np.zeros_like(t)
        s = 0.2
        while s < 5.6:
            word = rng.uniform(0.15, 0.35)
            env += np.exp(-(((t - s) / (word / 2)) ** 2)) * rng.uniform(0.4, 1.0)
            s += word + rng.uniform(0.05, 0.2)
        voice = np.sin(2 * np.pi * np.cumsum(140 + 30 * np.sin(2 * np.pi * 0.3 * t)) / audio.RATE)
        mono = (voice * env * 0.25).astype(np.float32)
        audio.write_wav(VOICE, np.stack([mono, mono], axis=1))
    if not CLICK.exists():
        t = np.arange(int(0.08 * audio.RATE)) / audio.RATE
        mono = (np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 60) * 0.5).astype(np.float32)
        audio.write_wav(CLICK, np.stack([mono, mono], axis=1))


class Narrated(StageScene):
    """Animations wait for words in the recording, not for hand-tuned seconds."""

    def construct(self):
        placeholder_audio()
        theme = project.theme()
        terms = VGroup(*[Text(s, font_size=60) for s in ("3", "+", "4", "=", "7")])
        terms.arrange(RIGHT, buff=0.4)
        terms[4].set_color(theme.accent)
        title = Text("narration + bookmarks", font_size=30, color=theme.muted).to_edge(UP)
        self.add(title)

        with self.narration(
            "intro",
            file=VOICE,
            text="Take three. <bookmark mark='add_four'/> Add four. "
            "<bookmark mark='show_sum'/> That makes seven.",
        ) as n:
            self.play(FadeIn(terms[0], shift=UP * 0.3))
            n.wait_until("add_four")
            self.play(FadeIn(terms[1]), FadeIn(terms[2], shift=UP * 0.3))
            n.wait_until("show_sum")
            self.play(FadeIn(terms[3]), Write(terms[4]))
        # leaving the block waited for the narration to end
        self.wait(0.3)


class SoundEffects(StageScene):
    """Plain Manim ``add_sound``: a click each time a square lands."""

    def construct(self):
        placeholder_audio()
        theme = project.theme()
        squares = VGroup(*[Square(0.9, color=theme.primary) for _ in range(5)])
        squares.arrange(RIGHT, buff=0.3)
        for k, sq in enumerate(squares):
            sq.set_fill(theme.primary if k % 2 else theme.secondary, 0.6)
            self.add_sound(str(CLICK), time_offset=0.3)  # lands at the end of the drop
            self.play(FadeIn(sq, shift=DOWN * 0.8), run_time=0.3)
        self.play(Create(squares[2].copy().set_color(theme.accent).scale(1.2)))
        label = Text("five clicks: one add_sound per landing", font_size=26)
        self.play(FadeIn(label.set_color(theme.muted).to_edge(DOWN)))
        self.wait(0.5)
