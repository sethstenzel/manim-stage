"""Audio clip editing rules and undo (backlog 2.3b)."""

import numpy as np
import pytest

from manim_stage import audio
from manim_stage.studio import audio_edit as ae


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / ".manim-stage").mkdir(parents=True)
    ext = tmp_path / "outside" / "take.wav"
    audio.write_wav(ext, np.zeros((audio.RATE * 2, 2), dtype=np.float32))
    return root, root / ".manim-stage" / "audio.json", ext


def test_import_copies_outside_files_into_the_project(project, tmp_path):
    root, side, ext = project
    edit = ae.add_clip(side, root, "S", ext, start=1.25)
    edit.do(side)
    clip = audio.load(side).scenes["S"][0]
    assert clip.file == "assets/audio/take.wav" and clip.start == 1.25 and clip.id == "take"
    assert (root / "assets" / "audio" / "take.wav").exists()
    # same content again → same file; different content with the same name → suffix
    assert ae.project_relative(root, ext) == "assets/audio/take.wav"
    other = tmp_path / "elsewhere" / "take.wav"
    audio.write_wav(other, np.ones((100, 2), dtype=np.float32) * 0.1)
    assert ae.project_relative(root, other) == "assets/audio/take-1.wav"


def test_unique_ids():
    assert ae.unique_id([{"id": "a"}, {"id": "a_2"}], "a") == "a_3"
    assert ae.unique_id([], "my take (final)!") == "my_take_final"


def test_change_remove_and_undo(project):
    root, side, ext = project
    ae.add_clip(side, root, "S", ext, 0).do(side)
    ch = ae.change_clip(side, "S", "take", "gain", gain_db=-6.0, mute=True)
    ch.do(side)
    c = audio.load(side).scenes["S"][0]
    assert c.gain_db == -6 and c.mute
    ch.undo(side)
    c = audio.load(side).scenes["S"][0]
    assert c.gain_db == 0 and not c.mute
    rm = ae.remove_clip(side, "S", "take")
    rm.do(side)
    assert audio.load(side).scenes.get("S", []) == []
    rm.undo(side)
    assert audio.load(side).scenes["S"][0].id == "take"


@pytest.mark.parametrize(
    "mode, delta, expected",
    [
        ("move", -0.5, {"start": 0.5}),
        ("trim_in", 0.25, {"start": 1.25, "trim_in": 0.75}),
        ("trim_in", -2.0, {"start": 0.5, "trim_in": 0.0}),  # clamped at the file start
        ("trim_out", 0.5, {"trim_out": 2.0}),
        ("trim_out", 5.0, {"trim_out": None}),  # back to "end of file"
        ("trim_out", -5.0, {"trim_out": 0.52}),  # minimum length after trim_in
    ],
)
def test_drag_changes(mode, delta, expected):
    clip = {"start": 1.0, "trim_in": 0.5, "trim_out": 1.5}
    assert ae.drag_changes(clip, mode, delta, source_duration=3.0) == expected


def test_muted_clips_still_produce_timeline_events(project):
    root, side, ext = project
    ae.add_clip(side, root, "S", ext, 0.5).do(side)
    ae.change_clip(side, "S", "take", "m", mute=True, trim_in=0.5).do(side)
    evs = ae.muted_events(side, root, "S", 10, present=set())
    assert len(evs) == 1
    e = evs[0]
    assert e["meta"]["silent"] and e["meta"]["silent_reason"] == "muted"
    assert (e["start_frame"], e["end_frame"]) == (5, 20)  # 1.5 s left after trim_in
    assert ae.muted_events(side, root, "S", 10, present={"take"}) == []


def test_source_duration(project):
    *_, ext = project
    assert ae.source_duration(ext) == pytest.approx(2.0, abs=0.01)
