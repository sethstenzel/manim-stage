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


def test_frames_written_for_every_frame(tmp_path):
    result = run_capture(SCENES / "timing.py", "MixedRunTimes", fps=15, frames_dir=tmp_path)
    assert sorted(result.frames) == list(range(result.timeline.duration_frames))
    assert all(p.exists() for p in result.frames.values())
