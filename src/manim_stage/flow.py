"""Flow helpers and in-scene transitions (spec F09, backlog 3.4; ADR-0013).

Motion Canvas composes generator "threads" with ``all``, ``sequence``, ``chain``,
``delay``, ``loop`` and ``tween``. In Manim the same ideas are animation groups; these
helpers give the Motion Canvas vocabulary and return ordinary Manim animations, so
they nest in ``self.play(...)``, ``AnimationGroup`` and ``LaggedStart`` like any other:

    self.play(all_of(FadeIn(a), FadeIn(b)))                  # together
    self.play(sequence(0.25, *(Create(x) for x in dots)))   # start every 0.25 s
    self.play(chain(Create(s), s.animate.shift(RIGHT)))     # one after another
    self.play(delay(1.0, Indicate(s)))                      # wait, then animate
    self.play(loop(3, lambda i: Rotate(s, PI / 2)))         # repeat
    self.play(tween(2.0, lambda t: dot.move_to(path(t)))) # any per-frame function

Scene enter/exit transitions (``enter(scene, "slide", LEFT)``) animate everything on
screen in or out; transitions *between* scenes are composed after rendering, see
:mod:`manim_stage.sequence`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Animation,
    AnimationGroup,
    FadeIn,
    FadeOut,
    Group,
    Mobject,
    Succession,
    Wait,
    config,
    linear,
)

# -- flow ------------------------------------------------------------------------------------


def all_of(*animations: Animation, **kwargs: Any) -> AnimationGroup:
    """Run animations together (Motion Canvas ``all``)."""
    return AnimationGroup(*animations, **kwargs)


def chain(*animations: Animation, **kwargs: Any) -> Succession:
    """Run animations one after another (Motion Canvas ``chain``)."""
    return Succession(*animations, **kwargs)


def delay(seconds: float, animation: Animation) -> Animation:
    """Wait ``seconds``, then run ``animation`` (Motion Canvas ``delay``)."""
    if seconds <= 0:
        return animation
    return Succession(Wait(run_time=seconds), animation)


def sequence(interval: float, *animations: Animation, **kwargs: Any) -> AnimationGroup:
    """Start each animation ``interval`` seconds after the previous one started
    (Motion Canvas ``sequence``). Unlike ``LaggedStart``'s ratio, the gap is exact
    seconds, whatever the animations' lengths."""
    return AnimationGroup(*(delay(i * interval, a) for i, a in enumerate(animations)), **kwargs)


def loop(times: int, factory: Callable[[int], Animation]) -> Succession:
    """Repeat ``factory(i)`` for i in 0..times-1 (Motion Canvas ``loop``)."""
    if times < 1:
        raise ValueError("loop needs at least one iteration")
    return Succession(*(factory(i) for i in range(times)))


class Tween(Animation):
    """Calls ``fn(t)`` every frame with t going 0 → 1 through ``rate_func``
    (Motion Canvas ``tween``). Use it to drive anything: positions along a path,
    ValueTrackers/Signals, colours."""

    def __init__(self, run_time: float, fn: Callable[[float], Any], **kwargs: Any) -> None:
        self.fn = fn
        super().__init__(Mobject(), run_time=run_time, **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        self.fn(self.rate_func(alpha))


def tween(run_time: float, fn: Callable[[float], Any], **kwargs: Any) -> Tween:
    return Tween(run_time, fn, **kwargs)


# -- in-scene enter / exit transitions ------------------------------------------------------

_DIRS = {"left": LEFT, "right": RIGHT, "up": UP, "down": DOWN}


def _everything(scene: Any, mobjects: Iterable[Mobject] | None) -> Group:
    mobs = list(mobjects) if mobjects is not None else list(scene.mobjects)
    return Group(*[m for m in mobs if m.has_points() or m.submobjects])


def enter(
    scene: Any,
    style: str = "fade",
    direction: Any = LEFT,
    *,
    mobjects: Iterable[Mobject] | None = None,
    run_time: float = 0.6,
) -> Animation:
    """Bring what is on screen in: ``fade``, ``slide`` (from ``direction``) or ``zoom``.

    Call after adding the scene's opening mobjects; ``self.play(enter(self, "slide"))``.
    """
    _check(style, "enter")
    group = _everything(scene, mobjects)
    if style == "fade":
        return FadeIn(group, run_time=run_time)
    if style == "slide":
        d = _dir(direction)
        offset = d * (config.frame_width if abs(d[0]) else config.frame_height)
        return FadeIn(group, shift=-offset, run_time=run_time, rate_func=_smooth())
    if style == "zoom":
        return FadeIn(group, scale=0.5, run_time=run_time)
    raise ValueError(f"unknown enter style {style!r} (fade, slide, zoom)")


def exit(
    scene: Any,
    style: str = "fade",
    direction: Any = LEFT,
    *,  # noqa: A001
    mobjects: Iterable[Mobject] | None = None,
    run_time: float = 0.6,
) -> Animation:
    """Take what is on screen out: ``fade``, ``slide`` (towards ``direction``) or ``zoom``."""
    _check(style, "exit")
    group = _everything(scene, mobjects)
    if style == "fade":
        return FadeOut(group, run_time=run_time)
    if style == "slide":
        d = _dir(direction)
        offset = d * (config.frame_width if abs(d[0]) else config.frame_height)
        return FadeOut(group, shift=offset, run_time=run_time, rate_func=_smooth())
    if style == "zoom":
        return FadeOut(group, scale=2.0, run_time=run_time)
    raise ValueError(f"unknown exit style {style!r} (fade, slide, zoom)")


def _check(style: str, what: str) -> None:
    if style not in ("fade", "slide", "zoom"):
        raise ValueError(f"unknown {what} style {style!r} (fade, slide, zoom)")


def _dir(direction: Any) -> np.ndarray:
    if isinstance(direction, str):
        return _DIRS[direction.lower()]
    return np.asarray(direction, dtype=float)


def _smooth() -> Callable[[float], float]:
    from manim import rate_functions

    return rate_functions.smooth


__all__ = [
    "Tween",
    "all_of",
    "chain",
    "delay",
    "enter",
    "exit",
    "loop",
    "sequence",
    "tween",
    "linear",
]
