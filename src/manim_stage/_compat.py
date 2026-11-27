"""The only module allowed to touch Manim internals or version-specific APIs.

Everything else in manim_stage goes through the names defined here, so a Manim
upgrade (see docs/upstream-sync.md) only needs changes in this file and its tests.
Capabilities are detected by feature, not version: Manim's main branch still
reports 0.22.1 while carrying 0.30 APIs (ADR-0003).
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any


class UnsupportedManimError(RuntimeError):
    """The installed Manim lacks an API manim-stage requires."""


@dataclass(frozen=True)
class ManimCapabilities:
    version: str
    evaluate: bool
    """``Manager.evaluate`` (run a scene without encoding)."""
    timeline_capture: bool
    """``Manager.evaluate(capture_timeline=True)`` and ``manim.Timeline``."""
    frame_callbacks: bool
    """``Manager.evaluate(frame_times=..., on_frame=...)``."""

    def missing(self) -> list[str]:
        return [
            name
            for name in ("evaluate", "timeline_capture", "frame_callbacks")
            if not getattr(self, name)
        ]


@cache
def capabilities() -> ManimCapabilities:
    import manim

    manager = getattr(manim, "Manager", None)
    evaluate = getattr(manager, "evaluate", None)
    params = set(inspect.signature(evaluate).parameters) if evaluate else set()
    return ManimCapabilities(
        version=getattr(manim, "__version__", "unknown"),
        evaluate=evaluate is not None,
        timeline_capture="capture_timeline" in params and hasattr(manim, "Timeline"),
        frame_callbacks={"frame_times", "on_frame"} <= params,
    )


def require_supported() -> ManimCapabilities:
    caps = capabilities()
    if missing := caps.missing():
        raise UnsupportedManimError(
            f"manim {caps.version} lacks {', '.join(missing)}. manim-stage needs the "
            "Manim 0.30 line; see docs/architecture-decisions.md (ADR-0003)."
        )
    return caps


# --- Run-loop tap (private Manim API: manim._run.loop, Manager._use_loop) -------------
# Manim has no public listener registration. Until it does (proposed upstream, see
# docs/backlog.md), we subclass Manager and add one listener to the loop it builds.


@dataclass(frozen=True)
class PlayRecord:
    """One play or wait call, as observed by the run loop."""

    index: int
    first_frame: int
    frame_count: int
    run_time: float
    frozen: bool
    animations: tuple[Any, ...]


@dataclass(frozen=True)
class Evaluation:
    timeline: dict[str, Any]
    """Manim's own timeline export (``manim.timeline`` v1), unmodified."""
    plays: tuple[PlayRecord, ...]
    end_frame: int


def frame_count(duration: float, frame_rate: float) -> int:
    """Frames whose start time lies before ``duration``; mirrors manim._run.frames."""
    return max(0, math.ceil(duration * frame_rate - 1e-9))


def evaluate(
    scene: Any,
    *,
    frame_times: Sequence[float] | None = None,
    on_frame: Callable[[Any], None] | None = None,
) -> Evaluation:
    """Run ``scene`` without encoding, capturing Manim's timeline and every play.

    Call inside the ``tempconfig`` the scene was constructed under.
    """
    require_supported()
    from manim import Manager
    from manim._run.loop import _RunListener

    plays: list[PlayRecord] = []

    class _PlayTap(_RunListener):
        def __init__(self, manager: Any) -> None:
            self._manager = manager

        def play_finished(self, play: Any) -> None:
            plays.append(
                PlayRecord(
                    index=play.index,
                    first_frame=play.first_frame,
                    frame_count=self._manager._execution.frame - play.first_frame,
                    run_time=play.run_time,
                    frozen=play.frozen,
                    animations=play.animations,
                )
            )

    class _TappedManager(Manager):
        def _use_loop(self, loop: Any) -> None:
            loop.listeners = (*loop.listeners, _PlayTap(self))
            super()._use_loop(loop)

    manager = _TappedManager(scene)
    kwargs: dict[str, Any] = {}
    if frame_times is not None:
        kwargs.update(frame_times=list(frame_times), on_frame=on_frame)
    manager.evaluate(capture_timeline=True, **kwargs)
    return Evaluation(
        timeline=manager.timeline.to_dict(),
        plays=tuple(plays),
        end_frame=manager._execution.frame,
    )


# --- Nested animation timing (mirrors Scene.update_to_time / AnimationGroup.interpolate) --


@dataclass(frozen=True)
class AnimationSpan:
    """Frames, relative to the start of the play, during which an animation runs."""

    label: str
    start: int
    end: int
    children: tuple[AnimationSpan, ...]


def animation_label(animation: Any) -> str:
    label = str(animation)
    if label.startswith("_MethodAnimation("):
        label = ".animate" + label[len("_MethodAnimation") :]
    return label


def _is_group(animation: Any) -> bool:
    return hasattr(animation, "anims_with_timings") and hasattr(animation, "max_end_time")


def _spans(animation: Any, alphas: Any, begun: Any) -> AnimationSpan:
    """``alphas[k]``: the animation's own alpha at play frame k (1.0 once done).
    ``begun[k]``: whether the animation has started by frame k (AnimationGroup's
    ``time >= start`` rule). The span covers frames that are begun and not done."""
    import numpy as np

    n = len(alphas)
    begun_idx = np.nonzero(begun)[0]
    running = np.nonzero(begun & (alphas < 1.0))[0]
    if len(running):
        start, end = int(running[0]), int(running[-1] + 1)
    else:
        start = end = int(begun_idx[0]) if len(begun_idx) else n
    children: list[AnimationSpan] = []
    if _is_group(animation) and animation.max_end_time > 0:
        rate = np.vectorize(animation.rate_func, otypes=[float])
        group_time = rate(alphas) * animation.max_end_time
        for row in animation.anims_with_timings:
            child, s, e = row["anim"], float(row["start"]), float(row["end"])
            child_begun = begun & (group_time >= s)
            if e > s:
                child_alpha = np.clip((group_time - s) / (e - s), 0.0, 1.0)
            else:
                child_alpha = child_begun.astype(float)
            children.append(_spans(child, child_alpha, child_begun))
    return AnimationSpan(animation_label(animation), start, end, tuple(children))


def animation_spans(play: PlayRecord, frame_rate: float) -> tuple[AnimationSpan, ...]:
    """Frame spans of a play's animations and, recursively, of group members."""
    import numpy as np

    if play.frozen or play.frame_count == 0:
        return ()
    offsets = np.arange(play.frame_count) / frame_rate
    spans = []
    for animation in play.animations:
        rt = animation.run_time
        alphas = np.minimum(offsets / rt, 1.0) if rt > 0 else np.ones(play.frame_count)
        spans.append(_spans(animation, alphas, np.ones(play.frame_count, dtype=bool)))
    return tuple(spans)
