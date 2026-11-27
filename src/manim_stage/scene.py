"""manim-stage authoring APIs on Manim scenes (spec F03; ADR-0006, ADR-0013).

Use :class:`StageScene` instead of ``Scene``, or mix :class:`StageMixin` into any
Manim scene class (``MovingCameraScene``, ``ThreeDScene``, ``ZoomedScene``, …)::

    from manim import *
    from manim_stage import StageScene

    class Lesson(StageScene):
        def construct(self):
            self.play(Create(Square()))
            self.cue("explain_square", at=3.0, description="'this is a square'")
            self.play(FadeOut(Square()))

    class CameraLesson(StageMixin, MovingCameraScene):
        ...

Everything else is plain Manim; ``manim render`` works unchanged and reads the cue
sidecar, so headless renders match the Studio preview.
"""

from __future__ import annotations

import inspect
import logging
import os
from pathlib import Path
from typing import Any

from manim import Scene, config

from . import _compat
from .cues import CueRecord, CueResolver, load, sidecar_path

_PKG = Path(__file__).resolve().parent
_MANIM = Path(inspect.getfile(Scene)).resolve().parents[1]  # site-packages/manim
log = logging.getLogger("manim_stage")


def _user_source() -> dict[str, Any] | None:
    """File and line of the scene code that called into manim-stage."""
    frame = inspect.currentframe()
    try:
        while frame is not None:
            p = Path(frame.f_code.co_filename)
            if not str(p).startswith("<"):
                resolved = p.resolve()
                if not resolved.is_relative_to(_PKG) and not resolved.is_relative_to(_MANIM):
                    return {"path": resolved.name, "line": frame.f_lineno, "file": str(resolved)}
            frame = frame.f_back
        return None
    finally:
        del frame


class StageMixin:
    """Adds ``cue()`` (and later manim-stage APIs) to a Manim ``Scene`` subclass."""

    _stage_resolver_obj: CueResolver | None = None

    # -- cues -------------------------------------------------------------------------

    def _stage_resolver(self) -> CueResolver:
        if self._stage_resolver_obj is None:
            override = os.environ.get("MANIM_STAGE_CUES")
            path = Path(override) if override else sidecar_path(inspect.getfile(type(self)))
            self._stage_resolver_obj = CueResolver(
                type(self).__name__, float(config.frame_rate), load(path)
            )
            self._stage_cue_file = path
        return self._stage_resolver_obj

    def cue(
        self,
        name: str,
        *,
        at: float | None = None,
        after: float | None = None,
        description: str | None = None,
    ) -> CueRecord:
        """Wait until the named cue (a ``wait`` whose end time can be edited).

        - ``at``: default target, absolute seconds from the scene start.
        - ``after``: default target, seconds after this call (like ``wait(after)``).
        - neither: the cue is a marker; it waits 0 s unless the sidecar moves it.

        The Studio timeline (or ``.manim-stage/cues.json``) can override the target.
        Raises :class:`~manim_stage.cues.CueError` for a duplicate name or a target
        before the current time (a negative wait).
        """
        resolver = self._stage_resolver()
        fps = float(config.frame_rate)
        call_frame = _compat.scene_frame(self, fps)
        rec = resolver.resolve(
            name, call_frame, at=at, after=after, description=description, source=_user_source()
        )
        if rec.wait_frames > 0:
            rec.play_index = _compat.scene_play_count(self)
            self.wait(rec.wait_frames / fps)
        return rec

    @property
    def stage_cues(self) -> list[CueRecord]:
        """Cues reached so far in this run, in call order."""
        return list(self._stage_resolver_obj.records) if self._stage_resolver_obj else []

    def stage_orphan_cues(self) -> list[str]:
        """Sidecar overrides this run never reached (renamed or removed cues)."""
        if self._stage_resolver_obj is None:
            return []
        return self._stage_resolver_obj.orphans()

    def tear_down(self) -> None:  # Manim hook, called after construct()
        for name in self.stage_orphan_cues():
            log.warning(
                "cue %r in %s is in the sidecar but no longer reached (orphan)",
                name,
                type(self).__name__,
            )
        super().tear_down()  # type: ignore[misc]


class StageScene(StageMixin, Scene):
    """A Manim ``Scene`` with manim-stage authoring APIs (``cue``)."""
