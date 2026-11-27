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

import contextlib
import inspect
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from manim import Scene, config

from . import _compat
from .cues import CueRecord, CueResolver, load, sidecar_path
from .deps import _system_roots

if TYPE_CHECKING:
    from .voiceover import Narration

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
                skip = (_PKG, _MANIM, *_system_roots())
                if not any(resolved.is_relative_to(r) for r in skip):
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
            if override:
                path = Path(override)
            else:
                try:
                    anchor = Path(inspect.getfile(type(self)))
                except (OSError, TypeError):  # defined in a notebook / `python -c`
                    anchor = Path.cwd() / "__scene__.py"
                path = sidecar_path(anchor)
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

    # -- narration (voiceover adapter) ---------------------------------------------------

    @contextlib.contextmanager
    def narration(
        self,
        name: str,
        *,
        file: str | os.PathLike[str] | None = None,
        text: str | None = None,
        bookmarks: dict[str, float] | None = None,
        words: Any = None,
        voiceover_cache: str | os.PathLike[str] | None = None,
        gain: float | None = None,
        captions: bool = True,
        wait: bool = True,
    ) -> Iterator[Narration]:
        """Play a recorded narration while the ``with`` block animates.

        - ``file``: the recording (any format PyAV reads). Or ``voiceover_cache``: a
          manim-voiceover ``cache.json``; the entry whose text matches is used.
        - ``text``: shown as a subcaption; may contain ``<bookmark mark='x'/>`` tags.
        - ``bookmarks``: explicit bookmark times (s from the narration start).
        - ``words``: word timings ``[(word, start, end), ...]`` or a transcript JSON path.
        - On exit, waits until the narration has finished (``wait=False`` to skip).

        ``n.wait_until("x")`` waits for a bookmark: the named cue ``<name>.x``.
        """
        from . import audio as audio_core
        from .voiceover import (
            Narration,
            bookmark_times,
            find_cached,
            load_voiceover_cache,
            load_words,
            strip_bookmarks,
        )

        word_list = (
            load_words(words) if isinstance(words, (str, os.PathLike)) else list(words or [])
        )
        if voiceover_cache is not None:
            entry = find_cached(load_voiceover_cache(voiceover_cache), text or "")
            if entry is None:
                raise FileNotFoundError(f"no entry for this text in {voiceover_cache}")
            file = entry.audio
            word_list = word_list or entry.words
        if file is None:
            raise ValueError("narration needs file= or voiceover_cache=")
        path = Path(file)
        if not path.is_absolute():
            path = Path.cwd() / path
        fps = float(config.frame_rate)
        duration = audio_core.duration_of(path)
        marks = bookmark_times(text or "", duration, bookmarks=bookmarks, words=word_list)
        start = _compat.scene_frame(self, fps)
        self.add_sound(str(path), gain=gain)  # type: ignore[attr-defined]
        clean = strip_bookmarks(text)[0] if text else ""
        if captions and clean:
            self.add_subcaption(clean, duration=duration)  # type: ignore[attr-defined]
        n = Narration(
            self,
            name,
            path,
            text=text,
            bookmarks=marks,
            start_frame=start,
            duration=duration,
            fps=fps,
            words=word_list,
        )
        log_ = getattr(self, "_stage_narrations", None)
        if log_ is None:
            log_ = self._stage_narrations = []
        log_.append(
            {
                "name": name,
                "file": str(path),
                "start_frame": start,
                "source": _user_source(),
                "duration": duration,
                "text": clean,
                "bookmarks": marks,
                "words": [list(w) for w in word_list],
            }
        )
        yield n
        if wait:
            n.wait_for_end()

    @property
    def stage_narrations(self) -> list[dict[str, Any]]:
        return list(getattr(self, "_stage_narrations", []) or [])

    # -- audio clips (.manim-stage/audio.json) -------------------------------------------

    def setup(self) -> None:  # Manim hook, called before construct()
        super().setup()  # type: ignore[misc]
        self._stage_add_audio_clips()

    def _stage_add_audio_clips(self) -> None:
        """Add the scene's audio-workspace clips as plain ``add_sound`` calls.

        Each clip is trimmed/faded/gained into a cached copy first, so Manim mixes
        exactly what the Studio previews. Muted clips are skipped; if any clip is
        soloed, only soloed clips play.
        """
        from . import audio

        try:
            anchor = Path(inspect.getfile(type(self)))
        except (OSError, TypeError):
            anchor = Path.cwd() / "__scene__.py"
        side = audio.sidecar_path(anchor)
        self._stage_audio_clips: list[dict[str, Any]] = []
        if not side.exists():
            return
        root = side.parent.parent
        for clip in audio.load(side).active(type(self).__name__):
            processed = audio.render_clip(clip, root)
            self.add_sound(str(processed), time_offset=clip.start)  # type: ignore[attr-defined]
            info = {k: v for k, v in clip.to_dict().items() if k != "id"}
            self._stage_audio_clips.append(
                {
                    "id": clip.id,
                    "processed": str(processed),
                    "label": clip.label or Path(clip.file).name,
                    **info,
                }
            )

    @property
    def stage_audio_clips(self) -> list[dict[str, Any]]:
        """Audio-workspace clips added to this run: id, processed file, label, settings."""
        return list(getattr(self, "_stage_audio_clips", []))

    # -- reactive values (signals) -----------------------------------------------------

    def effect(self, fn: Any) -> Any:
        """Run ``fn`` now and whenever a Signal/computed it reads changes (an updater)."""
        from .signals import effect

        return effect(fn, scene=self)

    def bind(self, mobject: Any, *, align: Any = None, update: Any = None, **props: Any) -> Any:
        """Keep ``mobject``'s properties equal to signal expressions (see signals.bind)."""
        from .signals import bind

        return bind(mobject, align=align, update=update, scene=self, **props)

    def tear_down(self) -> None:  # Manim hook, called after construct()
        from .signals import dispose_all

        dispose_all(self)  # effects and bindings end with the scene
        for name in self.stage_orphan_cues():
            log.warning(
                "cue %r in %s is in the sidecar but no longer reached (orphan)",
                name,
                type(self).__name__,
            )
        super().tear_down()  # type: ignore[misc]


class StageScene(StageMixin, Scene):
    """A Manim ``Scene`` with manim-stage authoring APIs (``cue``)."""
