"""A damped pendulum driven by signals (third-party-style example, M4 gate).

- The motion is computed first (plain numerical integration), then played by setting a
  ``Signal``; ``computed`` derives the bob position and ``bind`` keeps the rod, bob and
  readout attached (no hand-written updaters).
- ``demo.param``: drag length and damping in the Studio's Demo tab; exports use the
  defaults.
- ``project.theme()`` colours it (``.manim-stage/project.json``).

    manim-stage studio pendulum.py Pendulum
"""

import math

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Axes,
    Circle,
    Create,
    DecimalNumber,
    FadeIn,
    Line,
    Text,
    TracedPath,
    linear,
)

from manim_stage import Signal, StageScene, bind, computed, demo, project, tween

G = 9.81


def simulate(length: float, damping: float, theta0: float, seconds: float, fps: int = 120):
    """Angles over time (semi-implicit Euler); returns (times, thetas)."""
    dt = 1 / fps
    theta, omega = theta0, 0.0
    out = [theta]
    for _ in range(int(seconds * fps)):
        omega += (-G / length * math.sin(theta) - damping * omega) * dt
        theta += omega * dt
        out.append(theta)
    return np.linspace(0, seconds, len(out)), np.array(out)


class Pendulum(StageScene):
    def construct(self):
        theme = project.theme()
        length = demo.param("length", 2.5, min=1.0, max=3.5, description="rod length (m)")
        damping = demo.param("damping", 0.25, min=0.0, max=1.5, description="air friction")
        seconds = 6.0
        times, thetas = simulate(length, damping, math.radians(50), seconds)

        pivot = np.array([-3.0, 2.6, 0.0])
        angle = Signal(float(thetas[0]), name="theta")
        bob_pos = computed(
            lambda: pivot + length * np.array([math.sin(angle()), -math.cos(angle()), 0.0])
        )

        rod = Line(pivot, bob_pos(), color=theme.muted)
        bob = Circle(0.18, color=theme.accent, fill_opacity=1).move_to(bob_pos())
        bind(rod, update=lambda m: m.put_start_and_end_on(pivot, bob_pos()))
        bind(bob, position=bob_pos)
        trail = TracedPath(
            bob.get_center, stroke_color=theme.accent, stroke_opacity=0.4, dissipating_time=1.2
        )

        axes = Axes(
            x_range=[0, seconds, 1], y_range=[-1, 1, 0.5], x_length=6, y_length=2.6, tips=False
        ).to_corner(UP + RIGHT)
        curve = axes.plot_line_graph(
            times[::6], thetas[::6], add_vertex_dots=False, line_color=theme.primary
        )
        readout = DecimalNumber(
            math.degrees(angle()), num_decimal_places=1, mob_class=Text, font_size=30
        ).next_to(axes, DOWN)
        bind(readout, value=lambda: math.degrees(angle()))
        label = Text("θ (°)", font_size=26).next_to(readout, LEFT)

        self.next_section("Setup")
        self.play(FadeIn(rod), FadeIn(bob), Create(axes), FadeIn(label), FadeIn(readout))
        self.add(trail)
        self.next_section("Swing")
        self.cue("release")
        self.play(
            tween(seconds, lambda t: angle.set_value(float(np.interp(t * seconds, times, thetas)))),
            Create(curve, rate_func=linear, run_time=seconds),
        )
        self.wait(0.5)
