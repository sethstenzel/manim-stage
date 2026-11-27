"""Turn one evaluation of a Manim scene into a :class:`SceneTimeline` (ADR-0005)."""

from __future__ import annotations

import dataclasses
import math
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

from . import _compat
from .catalog import animation_info
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
            meta={"animation": span.info} if span.info else {},
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


def _clip_events(scene: Any, scene_name: str, events: list[SceneEvent]) -> list[SceneEvent]:
    """Tag the sounds that audio-workspace clips produced (by processed file path)."""
    clips = {c["processed"]: c for c in getattr(scene, "stage_audio_clips", []) or []}
    if not clips:
        return events
    out = []
    for e in events:
        clip = clips.get(str(e.meta.get("file"))) if e.kind == "sound" else None
        if clip is None:
            out.append(e)
            continue
        settings = {k: v for k, v in clip.items() if k not in ("id", "processed", "label")}
        out.append(
            dataclasses.replace(
                e,
                id=f"{scene_name}:sound:clip:{clip['id']}#0",
                label=clip["label"],
                source=None,
                meta={**e.meta, "clip": clip["id"], "clip_settings": settings},
            )
        )
    return out


def _cue_events(
    scene: Any, scene_name: str, events: list[SceneEvent]
) -> tuple[list[SceneEvent], list[str]]:
    """Add one ``cue`` marker per ``self.cue(...)`` of a StageScene (spec F03).

    The ``wait`` a cue issued is attributed to the user's ``cue(...)`` line (Manim
    records the first frame outside Manim, which is manim-stage's wrapper) and tagged
    with the cue name. Cue IDs are name-based (``Scene:cue:name#0``) so they stay
    stable across edits that move the call.
    """
    records = list(getattr(scene, "stage_cues", []) or [])
    if not records:
        return events, []
    by_play = {e.meta.get("play_index"): i for i, e in enumerate(events) if e.kind == "wait"}
    out = list(events)
    for rec in records:
        src = SourceRef(rec.source["path"], int(rec.source["line"])) if rec.source else None
        if rec.play_index is not None and rec.play_index in by_play:
            i = by_play[rec.play_index]
            out[i] = dataclasses.replace(
                out[i],
                id=f"{scene_name}:wait:cue:{rec.name}#0",
                source=src or out[i].source,
                label=f"cue {rec.name}",
                meta={**out[i].meta, "cue": rec.name},
            )
        out.append(
            SceneEvent(
                id=f"{scene_name}:cue:{rec.name}#0",
                kind="cue",
                scene=scene_name,
                start_frame=rec.target_frame,
                end_frame=rec.target_frame,
                track="cues",
                label=rec.name,
                source=src,
                meta={
                    "name": rec.name,
                    "description": rec.description,
                    "call_frame": rec.call_frame,
                    "default_frame": rec.default_frame,
                    "target_frame": rec.target_frame,
                    "overridden": rec.overridden,
                    "wait_frames": rec.wait_frames,
                    "play_index": rec.play_index,
                },
            )
        )
    orphans = scene.stage_orphan_cues() if hasattr(scene, "stage_orphan_cues") else []
    warnings = [
        f"cue {n!r} has a sidecar override but is no longer reached (orphan; renamed or "
        "removed?). It is kept until you dismiss it."
        for n in orphans
    ]
    return out, warnings


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
    scene = scene_cls()
    result = _compat.evaluate(scene, frame_times=frame_times, on_frame=on_frame)
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
                        **(
                            {"animations": [animation_info(a) for a in play.animations]}
                            if kind == "play"
                            else {}
                        ),
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

    events = _clip_events(scene, scene_name, events)
    events, cue_warnings = _cue_events(scene, scene_name, events)
    warnings += cue_warnings

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
