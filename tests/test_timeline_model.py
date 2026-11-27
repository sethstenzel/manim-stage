"""Timeline layout (backlog 1.4): lanes, overlap rows, ruler ticks, source paths."""

from pathlib import Path

from conftest import capture_scene

from manim_stage.studio.timeline_model import (
    build_layout,
    format_seconds,
    resolve_source,
    ruler_ticks,
)


def test_lanes_for_a_lesson_with_groups_sections_and_sound():
    lay = build_layout(capture_scene("Lesson", 15).to_dict())
    keys = [lane.key for lane in lay.lanes]
    assert keys == ["sections", "main", "level1", "audio"]
    main = next(ln for ln in lay.lanes if ln.key == "main")
    assert len(main.rows) == 1  # play/wait calls never overlap
    level1 = next(ln for ln in lay.lanes if ln.key == "level1")
    # LaggedStart members overlap in time, so they need several rows
    assert len(level1.rows) >= 2
    for row in level1.rows:
        for a, b in zip(row, row[1:], strict=False):
            assert b.start >= a.end  # rows never overlap


def test_no_duplicates_and_everything_placed():
    tl = capture_scene("Nested", 15).to_dict()
    lay = build_layout(tl)
    placed = [b.id for lane in lay.lanes for row in lane.rows for b in row]
    assert sorted(placed) == sorted(e["id"] for e in tl["events"])
    assert len(set(placed)) == len(placed)
    assert {ln.key for ln in lay.lanes} >= {"main", "level1", "level2"}


def test_categories_and_reading_order():
    lay = build_layout(capture_scene("Nested", 15).to_dict())
    play = next(b for b in lay.by_id.values() if b.kind == "play")
    assert play.category == "composition"
    order = lay.ordered()
    assert order[0].id == play.id
    assert [b.start for b in order] == sorted(b.start for b in order)


def test_ruler_ticks_adapt_to_zoom():
    coarse = ruler_ticks(30, 0.5, 0, 900)  # 15 px per second
    labels = [t.label for t in coarse if t.major]
    assert labels[:3] == ["0s", "5s", "10s"]
    fine = ruler_ticks(30, 30, 0, 40)  # a frame is 30 px wide
    assert any(not t.major and t.frame == 1 for t in fine)  # per-frame ticks
    assert [t.label for t in fine if t.major][:2] == ["0s", "0.1s"] or fine[0].label == "0s"


def test_format_seconds():
    assert format_seconds(0.5) == "0.5s"
    assert format_seconds(90) == "1:30"
    assert format_seconds(61.5) == "1:01.5"


def test_resolve_source(tmp_path):
    scene = tmp_path / "lesson.py"
    scene.write_text("")
    (tmp_path / "helper.py").write_text("")
    assert resolve_source("helper.py", scene) == tmp_path / "helper.py"
    assert resolve_source("lesson.py", scene) == scene
    assert resolve_source(str(scene), scene) == scene
    assert resolve_source("missing.py", scene) == scene
    assert isinstance(resolve_source("x", Path(scene)), Path)


def test_cues_get_their_own_lane():
    tl = capture_scene("Narrated", 15, file=Path(__file__).parent / "scenes" / "cues.py")
    lay = build_layout(tl.to_dict())
    cues = next(ln for ln in lay.lanes if ln.key == "cues")
    assert [b.label for row in cues.rows for b in row] == ["intro", "swap", "marker"]
    assert all(b.is_marker and b.category == "cue" for row in cues.rows for b in row)
