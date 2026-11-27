"""Scenes exercising replay determinism. Line numbers matter."""

import random
import time

import numpy as np
from manim import Dot, FadeIn, Scene, VGroup

AT_IMPORT = random.random()  # runs at import, before Manim seeds


class Seeded(Scene):
    """Uses random and numpy.random inside construct: deterministic with a seed."""

    def construct(self):
        dots = VGroup(
            *[Dot([random.uniform(-6, 6), np.random.uniform(-3, 3), 0]) for _ in range(40)]
        )
        self.play(FadeIn(dots, lag_ratio=0.1), run_time=1)


class WallClock(Scene):
    def construct(self):
        x = (time.time() % 1) * 4 - 2
        self.play(FadeIn(Dot([x, 0, 0])), run_time=0.3)
