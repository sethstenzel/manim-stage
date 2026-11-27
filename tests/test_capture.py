"""Spec F02 acceptance: correct time ranges, no duplicated events, stable IDs."""

import math
import sys

import pytest
from conftest import capture_scene, capture_scene_and_class

from manim_stage.events import SceneTimeline

FPS = 15


def frames(seconds: float, fps: float = FPS) -> int:
    return math.ceil(seconds * fps - 1e-9)


@pytest.fixture(scope="module")
def lesson():
    return capture_scene("Lesson", FPS)


def main_track(tl):
    return [e for e in tl.events if e.track == "main"]


def test_plays_and_waits_are_contiguous_and_frame_quantized(lesson):
    main = main_track(lesson)
    assert [e.kind for e in main] == ["play"] * 6 + ["wait"]
    expected = [0.5, 1.0, 1.5, 1 / 3, 1 / 3, 1 / 3, 0.7]
    assert [e.end_frame - e.start_frame for e in main] == [frames(s) for s in expected]
    for prev, cur in zip(main, main[1:], strict=False):
        assert cur.start_frame == prev.end_frame
    assert main[0].start_frame == 0
    assert main[-1].end_frame == lesson.duration_frames


def test_no_duplicate_events_and_loop_ids_are_occurrence_indexed(lesson):
    ids = [e.id for e in lesson.events]
    assert len(ids) == len(set(ids))
    loop = [e for e in main_track(lesson) if e.source and e.source.line == 34]
    assert [e.id.rsplit("#", 1)[1] for e in loop] == ["0", "1", "2"]
    assert loop[0].id == "Lesson:play:timing.py:34#0"


def test_lagged_start_children_match_manim_sampling(lesson):
    play = next(e for e in lesson.events if e.label.startswith("LaggedStart"))
    kids = [e for e in lesson.events if e.parent_id == play.id]
    rel = [(k.start_frame - play.start_frame, k.end_frame - play.start_frame) for k in kids]
    # 3 x 1 s children with lag 0.5: group times [0,1], [0.5,1.5], [1,2] of 2, played in 1.5 s.
    assert rel == [
        (0, frames(0.75)),
        (frames(0.375), frames(1.125)),
        (frames(0.75), frames(1.5)),
    ]
    assert all(k.track == "main/1" for k in kids)


def test_animation_group_children(lesson):
    play = next(e for e in lesson.events if e.label.startswith("AnimationGroup"))
    kids = [e for e in lesson.events if e.parent_id == play.id]
    assert [k.label.split("(")[0] for k in kids] == ["FadeIn", ".animate"]
    assert all((k.start_frame, k.end_frame) == (play.start_frame, play.end_frame) for k in kids)


def test_sound_and_section_markers(lesson):
    sound = next(e for e in lesson.events if e.kind == "sound")
    first_play = main_track(lesson)[0]
    assert sound.meta["start_seconds"] == pytest.approx(first_play.end_frame / FPS + 0.1)
    assert sound.start_frame == math.floor(sound.meta["start_seconds"] * FPS + 1e-9)
    assert sound.meta["duration_seconds"] == pytest.approx(0.5)
    assert sound.source.line == 29
    section = next(e for e in lesson.events if e.kind == "section")
    loop_start = next(e for e in main_track(lesson) if e.source.line == 34)
    assert (section.label, section.start_frame) == ("loop", loop_start.start_frame)
    starts = [e.start_frame for e in lesson.events]
    assert starts == sorted(starts)


def test_nested_groups_recurse():
    tl = capture_scene("Nested", FPS)
    play = main_track(tl)[0]
    by_parent: dict = {}
    for e in tl.events:
        by_parent.setdefault(e.parent_id, []).append(e)
    lagged, succession = by_parent[play.id]
    assert lagged.label.startswith("LaggedStart")
    assert succession.label.startswith("Succession")
    a, b = by_parent[lagged.id]
    c, d = by_parent[succession.id]
    assert a.track == "main/2"
    # lag_ratio=1 and Succession both run their members back to back.
    assert a.end_frame == b.start_frame and c.end_frame == d.start_frame
    assert a.start_frame == play.start_frame and d.end_frame == play.end_frame


def test_mixed_run_times_in_one_play():
    tl = capture_scene("MixedRunTimes", FPS)
    play = main_track(tl)[0]
    a, b = (e for e in tl.events if e.parent_id == play.id)
    assert (a.end_frame - a.start_frame, b.end_frame - b.start_frame) == (frames(2), frames(1))


def test_capture_is_deterministic_and_round_trips(lesson):
    again = capture_scene("Lesson", FPS)
    assert again.to_dict() == lesson.to_dict()
    assert SceneTimeline.from_dict(lesson.to_dict()) == lesson


def test_other_frame_rate():
    tl = capture_scene("Lesson", 30)
    assert [e.end_frame - e.start_frame for e in main_track(tl)][:2] == [15, 30]


def test_child_spans_match_observed_manim_frames():
    """Cross-check against what Manim really did, not against our own formula."""
    tl, cls = capture_scene_and_class("Probe", FPS)
    log = sys.modules[cls.__module__].PROBE_LOG
    play = main_track(tl)[0]
    per_frame = log[: play.end_frame - play.start_frame]  # Manim adds one entry after finish()
    kids = [e for e in tl.events if e.parent_id == play.id]
    assert len(kids) == 3
    for i, kid in enumerate(kids):
        running = [k for k, row in enumerate(per_frame) if 0.0 < row[i] < 1.0]
        assert kid.end_frame - play.start_frame == running[-1] + 1
        # A child that begins exactly on a frame shows alpha 0 there.
        assert kid.start_frame - play.start_frame in (running[0] - 1, running[0])
