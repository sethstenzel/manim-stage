"""Runner child process (ADR-0004): same timeline as in-process, errors with file/line."""

import pytest
from conftest import SCENES, capture_scene

from manim_stage.runner import RunnerError, run_capture


def test_child_process_matches_in_process_capture():
    result = run_capture(SCENES / "timing.py", "Lesson", fps=15)
    assert result.timeline.to_dict() == capture_scene("Lesson", 15).to_dict()
    assert result.manim_version


def test_child_process_reports_scene_error_with_line():
    with pytest.raises(RunnerError) as err:
        run_capture(SCENES / "timing.py", "Broken", fps=15)
    assert "boom" in str(err.value)
    assert err.value.line == 58
    assert err.value.file.endswith("timing.py")


def test_missing_scene_class():
    with pytest.raises(RunnerError, match="no scene class"):
        run_capture(SCENES / "timing.py", "Nope", fps=15)


def test_frames_cached_for_every_frame_and_reused(tmp_path):
    first = run_capture(SCENES / "timing.py", "MixedRunTimes", fps=15, cache_dir=tmp_path)
    n = first.timeline.duration_frames
    assert sorted(first.frames) == list(range(n))
    assert first.frames_drawn == n
    assert all(p.exists() for p in first.frames.values())
    assert {"import", "timeline", "frames", "total"} <= set(first.timings)

    second = run_capture(SCENES / "timing.py", "MixedRunTimes", fps=15, cache_dir=tmp_path)
    assert second.revision == first.revision
    assert second.frames_drawn == 0  # cache hit
    assert sorted(second.frames) == list(range(n))


def test_different_settings_are_a_different_revision(tmp_path):
    a = run_capture(SCENES / "timing.py", "MixedRunTimes", fps=15, cache_dir=tmp_path)
    b = run_capture(SCENES / "timing.py", "MixedRunTimes", fps=10, cache_dir=tmp_path)
    assert a.revision != b.revision
    assert b.frames_drawn == b.timeline.duration_frames
