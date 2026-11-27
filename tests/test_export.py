"""Export through Manim's CLI and snapshots (backlog 1.5, spec F01/F10)."""

import json
import time

import numpy as np
import pytest
from conftest import SCENES, capture_scene
from PIL import Image

from manim_stage.export import (
    ExportJob,
    ExportSettings,
    display_command,
    frames_for_play_range,
    manim_command,
    play_range_for_frames,
    snapshot,
)
from manim_stage.runner import run_capture

FILE = SCENES / "timing.py"


def test_command_is_plain_manim_render(tmp_path):
    s = ExportSettings(quality="low_quality", format="webm", transparent=True,
                       save_sections=True, play_range=(1, 3), media_dir=tmp_path,
                       output_name="clip", seed=7)  # fmt: skip
    cmd = manim_command(FILE, "Lesson", s, python="py")
    assert cmd[:6] == ["py", "-m", "manim", "render", str(FILE), "Lesson"]
    joined = " ".join(cmd)
    for part in ("-q l", "--format webm", "--seed 7", "-t", "--save_sections", "-n 1,3",
                 f"--media_dir {tmp_path}", "-o clip"):  # fmt: skip
        assert part in joined
    assert display_command(cmd).startswith("manim render ")


def test_settings_validation():
    with pytest.raises(ValueError):
        ExportSettings(format="avi")
    with pytest.raises(ValueError):
        ExportSettings(format="mp4", transparent=True)


def test_frame_range_snaps_to_whole_plays():
    tl = capture_scene("Lesson", 15).to_dict()
    plays = [e for e in tl["events"] if e["kind"] in ("play", "wait")]
    second = plays[1]
    mid = (second["start_frame"] + second["end_frame"]) // 2
    rng = play_range_for_frames(tl, mid, mid + 1)
    assert rng == (1, 1)
    assert frames_for_play_range(tl, rng) == (second["start_frame"], second["end_frame"])
    assert play_range_for_frames(tl, 0, tl["duration_frames"]) == (0, len(plays) - 1)


def _decode(path, index):
    import av

    with av.open(str(path)) as c:
        for i, frame in enumerate(c.decode(video=0)):
            if i == index:
                return np.asarray(frame.to_image().convert("RGB"), dtype=np.int16)
    raise AssertionError("frame not found")


def test_full_export_matches_preview_and_has_audio(tmp_path):
    progress = []
    job = ExportJob(FILE, "Lesson", ExportSettings(quality="low_quality", media_dir=tmp_path),
                    on_progress=lambda f, _m: progress.append(f)).start()  # fmt: skip
    r = job.wait(300)
    assert r.ok, r.error
    tl = capture_scene("Lesson", 15).to_dict()
    p = r.probe
    assert (p["width"], p["height"], p["fps"]) == (854, 480, 15.0)
    assert p["video_codec"] == "h264" and p["variable_frame_rate"] is False
    assert abs(p["duration_s"] - tl["duration_frames"] / 15) < 0.1
    assert p["audio"] and p["audio"][0]["codec"] == "aac"  # add_sound mixed in
    assert progress and progress[-1] == 1.0 and progress == sorted(progress)
    # a representative frame agrees with the preview within video-codec tolerance
    pre = run_capture(FILE, "Lesson", fps=15, width=854, height=480, cache_dir=tmp_path / "c")
    k = tl["duration_frames"] // 2
    preview = np.asarray(Image.open(pre.frames[k]).convert("RGB"), dtype=np.int16)
    assert np.abs(_decode(r.output, k) - preview).mean() < 4.0


def test_range_export_renders_only_those_plays(tmp_path):
    tl = capture_scene("MixedRunTimes", 15).to_dict()
    job = ExportJob(SCENES / "timing.py", "Lesson",
                    ExportSettings(quality="low_quality", media_dir=tmp_path, play_range=(1, 1),
                                   output_name="part"))  # fmt: skip
    r = job.start().wait(300)
    assert r.ok, r.error
    lesson = capture_scene("Lesson", 15).to_dict()
    start, end = frames_for_play_range(lesson, (1, 1))
    assert r.output.stem == "part"
    assert abs(r.probe["duration_s"] - (end - start) / 15) < 0.1
    assert tl  # (MixedRunTimes only used to warm imports)


def test_cancel_kills_manim(tmp_path):
    job = ExportJob(FILE, "Lesson", ExportSettings(quality="high_quality", media_dir=tmp_path))
    job.start()
    time.sleep(1.0)
    job.cancel()
    r = job.wait(60)
    assert r.cancelled and not r.ok
    assert job._proc.poll() is not None


def test_snapshot_equals_preview_frame(tmp_path):
    out, index = snapshot(FILE, "MixedRunTimes", 1.0, tmp_path / "s.png", quality="low_quality")
    assert index == 15
    pre = run_capture(FILE, "MixedRunTimes", fps=15, width=854, height=480,
                      cache_dir=tmp_path / "c")  # fmt: skip
    a = np.asarray(Image.open(out))
    b = np.asarray(Image.open(pre.frames[index]))
    assert a.shape == (480, 854, a.shape[2]) and np.array_equal(a, b)


def test_snapshot_message_matches_runner_schema(tmp_path):
    from test_schemas import runner_lines, validator

    msgs = runner_lines("MixedRunTimes", "--snapshot-at", "0.5", "--out", str(tmp_path / "x.png"))
    v = validator("runner-message.schema.json")
    for m in msgs:
        v.validate(m)
    assert any(m["type"] == "snapshot" for m in msgs)
    assert json.dumps(msgs)
