"""Turn one evaluation of a Manim scene into a :class:`SceneTimeline` (ADR-0005)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

from . import _compat
from .events import SceneEvent, SceneTimeline, SourceRef

_TOL = 1e-9


def _frame_at(seconds: float, frame_rate: float) -> int:
    """Index of the frame showing ``seconds`` (frame i covers [i/r, (i+1)/r))."""
    return math.floor(seconds * frame_rate + _TOL)


def _frame_end(seconds: float, frame_rate: float) -> int:
    """Exclusive end frame for a span ending at ``seconds``."""
    return max(0, math.ceil(seconds * frame_rate - _TOL))


def _source(entry: dict[str, Any]) -> SourceRef | None:
    src = entry.get("source")
    if not src or src.get("line") is None:
        return None
    return SourceRef(path=src.get("path") or "?", line=int(src["line"]))


class _Ids:
    """``scene:kind:path:line#occurrence``; occurrence counts repeats of a call site."""

    def __init__(self, scene: str) -> None:
        self._scene = scene
        self._seen: Counter[tuple[str, str]] = Counter()

    def make(self, kind: str, source: SourceRef | None, fallback: str) -> str:
        site = f"{source.path}:{source.line}" if source else f"?:{fallback}"
        n = self._seen[(kind, site)]
        self._seen[(kind, site)] += 1
        return f"{self._scene}:{kind}:{site}#{n}"


def _child_events(
    span: _compat.AnimationSpan,
    *,
    event_id: str,
    parent_id: str,
    scene: str,
    play_start: int,
    depth: int,
    source: SourceRef | None,
) -> list[SceneEvent]:
    events = [
        SceneEvent(
            id=event_id,
            kind="animation",
            scene=scene,
            start_frame=play_start + span.start,
            end_frame=play_start + span.end,
            track=f"main/{depth}",
            label=span.label,
            source=source,
            parent_id=parent_id,
        )
    ]
    for i, child in enumerate(span.children):
        events += _child_events(
            child,
            event_id=f"{event_id}/{i}",
            parent_id=event_id,
            scene=scene,
            play_start=play_start,
            depth=depth + 1,
            source=source,
        )
    return events


def capture(
    scene_cls: type,
    *,
    frame_times: Sequence[float] | None = None,
    on_frame: Callable[[Any], None] | None = None,
) -> SceneTimeline:
    """Evaluate ``scene_cls`` once and return its events.

    Call inside the ``tempconfig`` that sets frame rate and resolution.
    """
    from manim import config

    frame_rate = float(config.frame_rate)
    scene_name = scene_cls.__name__
    result = _compat.evaluate(scene_cls(), frame_times=frame_times, on_frame=on_frame)
    tl = result.timeline
    ids = _Ids(scene_name)
    warnings: list[str] = []
    events: list[SceneEvent] = []

    play_entries = [e for e in tl["entries"] if e["kind"] in ("play", "wait")]
    if len(play_entries) != len(result.plays):
        warnings.append(
            f"Manim timeline lists {len(play_entries)} play/wait calls but the run loop saw "
            f"{len(result.plays)}; source locations may be misattributed."
        )
    plays_by_entry = iter(result.plays)

    for entry in tl["entries"]:
        kind = entry["kind"]
        source = _source(entry)
        if kind in ("play", "wait"):
            play = next(plays_by_entry, None)
            if play is None:
                continue
            event_id = ids.make(kind, source, f"play{play.index}")
            start, end = play.first_frame, play.first_frame + play.frame_count
            labels = [_compat.animation_label(a) for a in play.animations]
            events.append(
                SceneEvent(
                    id=event_id,
                    kind=kind,
                    scene=scene_name,
                    start_frame=start,
                    end_frame=end,
                    track="main",
                    label="wait" if kind == "wait" else ", ".join(labels),
                    source=source,
                    meta={
                        "play_index": play.index,
                        "run_time": play.run_time,
                        "frozen": play.frozen,
                        "skipped": entry.get("skipped", False),
                    },
                )
            )
            if kind == "play":
                spans = _compat.animation_spans(play, frame_rate)
                if len(spans) == 1:
                    # The play event already stands for its single animation; show that
                    # animation's members (if it is a group) directly under the play.
                    spans = spans[0].children
                if spans:
                    for i, span in enumerate(spans):
                        events += _child_events(
                            span,
                            event_id=f"{event_id}/{i}",
                            parent_id=event_id,
                            scene=scene_name,
                            play_start=start,
                            depth=1,
                            source=source,
                        )
        elif kind == "section":
            frame = _frame_at(entry["start"], frame_rate)
            events.append(
                SceneEvent(
                    id=ids.make(kind, source, entry["name"]),
                    kind="section",
                    scene=scene_name,
                    start_frame=frame,
                    end_frame=frame,
                    track="sections",
                    label=entry["name"],
                    source=source,
                    meta={"type": entry.get("type"), "skip_animations": entry["skip_animations"]},
                )
            )
        elif kind == "sound":
            start_s = float(entry["start"])
            duration = entry.get("duration")
            end_s = start_s + duration if duration is not None else start_s
            events.append(
                SceneEvent(
                    id=ids.make(kind, source, str(entry.get("file"))),
                    kind="sound",
                    scene=scene_name,
                    start_frame=_frame_at(start_s, frame_rate),
                    end_frame=_frame_end(end_s, frame_rate),
                    track="audio",
                    label=str(entry.get("file", "")).replace("\\", "/").rsplit("/", 1)[-1],
                    source=source,
                    meta={
                        "file": entry.get("file"),
                        "start_seconds": start_s,
                        "duration_seconds": duration,
                        "gain": entry.get("gain"),
                    },
                )
            )
        elif kind == "caption":
            events.append(
                SceneEvent(
                    id=ids.make(kind, source, entry.get("content", "")),
                    kind="caption",
                    scene=scene_name,
                    start_frame=_frame_at(entry["start"], frame_rate),
                    end_frame=_frame_end(entry["end"], frame_rate),
                    track="captions",
                    label=entry.get("content", ""),
                    source=source,
                )
            )
        else:
            warnings.append(f"Ignored unknown Manim timeline entry kind {kind!r}.")

    # Manim lists entries in call order; a sound offset can start after later plays.
    events.sort(key=lambda e: e.start_frame)
    duplicate = [k for k, v in Counter(e.id for e in events).items() if v > 1]
    if duplicate:  # _Ids makes this impossible; guard the invariant anyway.
        raise AssertionError(f"duplicate event ids: {duplicate}")

    return SceneTimeline(
        scene=scene_name,
        frame_rate=frame_rate,
        duration_frames=result.end_frame,
        events=tuple(events),
        source_sha256=(tl.get("source") or {}).get("sha256"),
        warnings=tuple(warnings),
    )
