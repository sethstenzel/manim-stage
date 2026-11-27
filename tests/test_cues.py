"""Named cues: store, resolver, StageScene, sidecar overrides, validate/bake (backlog 2.1)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import SCENES, capture_scene
from test_schemas import validator

from manim_stage import cues as cs
from manim_stage.cli import main
from manim_stage.cues import CueError, CueFile, CueResolver
from manim_stage.runner import RunnerError, run_capture

FILE = SCENES / "cues.py"
LINES = FILE.read_text(encoding="utf-8").splitlines()


def line_of(tag: str) -> int:
    return next(i for i, ln in enumerate(LINES, 1) if tag in ln)


# -- store ---------------------------------------------------------------------------


def test_sidecar_roundtrip_schema_and_atomic_backup(tmp_path):
    path = tmp_path / ".manim-stage" / "cues.json"
    f = CueFile(frame_rate=30)
    f.set_target("Lesson", "intro", 2.5, description="hello")
    cs.save(path, f)
    doc = json.loads(path.read_text(encoding="utf-8"))
    validator("cues.schema.json").validate(doc)
    assert doc["scenes"]["Lesson"]["cues"]["intro"]["target_frame"] == 75
    f.set_target("Lesson", "intro", 3.0)
    cs.save(path, f)
    assert (path.parent / "cues.json.bak").exists()
    assert cs.load(path).target_seconds("Lesson", "intro") == 3.0
    assert not list(path.parent.glob(".cues-*"))  # no temp files left behind


def test_corrupt_sidecar_falls_back_to_backup_or_fails_loudly(tmp_path):
    path = tmp_path / "cues.json"
    f = CueFile()
    f.set_target("S", "a", 1.0)
    cs.save(path, f)
    cs.save(path, f)  # creates .bak
    path.write_text("{ not json", encoding="utf-8")
    assert cs.load(path).target_seconds("S", "a") == 1.0
    path.with_suffix(".json.bak").unlink()
    with pytest.raises(CueError, match="corrupt"):
        cs.load(path)


def test_project_root_finds_marker_folder(tmp_path):
    (tmp_path / ".manim-stage").mkdir()
    deep = tmp_path / "lessons" / "week1"
    deep.mkdir(parents=True)
    scene = deep / "lesson.py"
    scene.write_text("")
    assert cs.sidecar_path(scene) == tmp_path / ".manim-stage" / "cues.json"


# -- resolver ------------------------------------------------------------------------


def test_defaults_at_after_and_marker():
    r = CueResolver("S", 15)
    assert r.resolve("a", 15, at=2.0).target_frame == 30
    assert r.resolve("b", 30, after=0.5).target_frame == 38  # ceil like wait(0.5)
    assert r.resolve("c", 38).target_frame == 38


def test_override_rescales_between_frame_rates():
    f = CueFile(frame_rate=30)
    f.set_target("S", "a", 2.0)  # frame 60 @30
    r = CueResolver("S", 15, f)
    rec = r.resolve("a", 0, at=1.0)
    assert rec.overridden and rec.target_frame == 30 and rec.default_frame == 15


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"name": "bad name!"}, "invalid cue name"),
        ({"name": "x", "at": 1, "after": 1}, "not both"),
        ({"name": "x", "at": -1}, ">= 0"),
        ({"name": "x", "at": 0.5}, "negative wait"),
    ],
)
def test_invalid_cues(kwargs, match):
    r = CueResolver("S", 10)
    name = kwargs.pop("name")
    with pytest.raises(CueError, match=match):
        r.resolve(name, 10, **kwargs)


def test_duplicates_and_orphans():
    f = CueFile(frame_rate=10)
    f.set_target("S", "gone", 1.0)
    r = CueResolver("S", 10, f)
    r.resolve("a", 0)
    with pytest.raises(CueError, match="twice"):
        r.resolve("a", 0)
    assert r.orphans() == ["gone"]


def test_negative_override_is_an_error_with_location():
    f = CueFile(frame_rate=10)
    f.set_target("S", "late", 0.5)
    r = CueResolver("S", 10, f)
    with pytest.raises(CueError) as e:
        r.resolve("late", 20, source={"path": "x.py", "line": 7})
    assert (e.value.file, e.value.line) == ("x.py", 7)
    assert "sidecar override" in str(e.value)


def test_monotonic_check():
    recs = [cs.CueRecord("a", 0, 10, 10, False), cs.CueRecord("b", 10, 5, 5, True)]
    assert cs.check_monotonic(recs)


# -- StageScene in Manim -------------------------------------------------------------


def test_stage_scene_cues_drive_timing_and_events():
    tl = capture_scene("Narrated", 15, file=FILE)
    cues = {e.label: e for e in tl.events if e.kind == "cue"}
    assert list(cues) == ["intro", "swap", "marker"]
    assert cues["intro"].start_frame == 30  # at=2.0
    assert cues["swap"].start_frame == 38 + 15  # after=1.0 from 2.5 s
    assert cues["marker"].meta["wait_frames"] == 0
    assert cues["intro"].source.line == line_of("CUE_INTRO")
    assert cues["intro"].meta["description"] == "after 'here is a square'"
    assert cues["intro"].id == "Narrated:cue:intro#0"
    waits = [e for e in tl.events if e.kind == "wait"]
    assert [w.meta["cue"] for w in waits] == ["intro", "swap"]
    assert waits[0].source.line == line_of("CUE_INTRO")  # not manim-stage's own line
    assert waits[0].id == "Narrated:wait:cue:intro#0"
    validator("timeline.schema.json").validate(tl.to_dict())


def test_sidecar_override_moves_downstream_animations(tmp_path, monkeypatch):
    side = tmp_path / "cues.json"
    f = CueFile(frame_rate=30)
    f.set_target("Narrated", "intro", 3.0)
    cs.save(side, f)
    base = capture_scene("Narrated", 15, file=FILE)  # before the override applies
    monkeypatch.setenv("MANIM_STAGE_CUES", str(side))
    moved = run_capture(FILE, "Narrated", fps=15, width=64, height=36).timeline
    plays = lambda tl: [e.start_frame for e in tl.events if e.kind == "play"]  # noqa: E731
    assert plays(moved)[1] - plays(base)[1] == 15  # FadeIn(Circle) starts 1 s later
    assert moved.duration_frames - base.duration_frames == 15
    assert next(e for e in moved.events if e.kind == "cue").meta["overridden"] is True


def test_negative_override_fails_the_render_at_the_cue_line(tmp_path, monkeypatch):
    side = tmp_path / "cues.json"
    f = CueFile(frame_rate=30)
    f.set_target("Narrated", "swap", 1.0)  # reached at 2.5 s
    cs.save(side, f)
    monkeypatch.setenv("MANIM_STAGE_CUES", str(side))
    with pytest.raises(RunnerError) as e:
        run_capture(FILE, "Narrated", fps=15, width=64, height=36)
    assert "negative wait" in str(e.value)
    assert Path(e.value.file).name == "cues.py" and e.value.line == line_of("CUE_SWAP")


def test_orphan_is_a_warning_not_an_error(tmp_path, monkeypatch):
    side = tmp_path / "cues.json"
    f = CueFile(frame_rate=30)
    f.set_target("Narrated", "renamed_away", 1.0)
    cs.save(side, f)
    monkeypatch.setenv("MANIM_STAGE_CUES", str(side))
    tl = run_capture(FILE, "Narrated", fps=15, width=64, height=36).timeline
    assert any("renamed_away" in w and "orphan" in w for w in tl.warnings)


def test_plain_manim_render_honours_the_sidecar(tmp_path):
    """Headless CLI reproduction: `manim render` of a StageScene reads cues.json."""
    import av

    proj = tmp_path / "p"
    (proj / ".manim-stage").mkdir(parents=True)
    (proj / "lesson.py").write_text(FILE.read_text(encoding="utf-8"), encoding="utf-8")
    f = CueFile(frame_rate=15)
    f.set_target("Narrated", "intro", 4.0)  # default 2.0 → +2 s
    cs.save(proj / ".manim-stage" / "cues.json", f)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            "lesson.py",
            "Narrated",
            "-ql",
            "--media_dir",
            str(tmp_path / "m"),
        ],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = next((tmp_path / "m").rglob("Narrated.mp4"))
    with av.open(str(out)) as c:
        seconds = c.duration / 1e6
    base = capture_scene("Narrated", 15, file=FILE).duration_frames / 15
    assert abs(seconds - (base + 2.0)) < 0.1


# -- validate / bake -----------------------------------------------------------------


def test_validate_reports_errors_and_exit_code(capsys):
    assert main(["validate", str(FILE)]) == 1
    out = capsys.readouterr().out
    assert "intro" in out and "ERROR" in out and f"cues.py:{line_of('DUPLICATE')}" in out
    assert main(["validate", str(FILE), "Narrated", "Looping"]) == 0


def test_bake_writes_resolved_targets_and_tombstones(tmp_path):
    proj = tmp_path / "p"
    (proj / ".manim-stage").mkdir(parents=True)
    scene = proj / "lesson.py"
    scene.write_text(FILE.read_text(encoding="utf-8"), encoding="utf-8")
    f = CueFile(frame_rate=30)
    f.set_target("Narrated", "old", 9.0)
    cs.save(proj / ".manim-stage" / "cues.json", f)
    assert main(["bake", str(scene), "Narrated"]) == 0
    baked = cs.load(proj / ".manim-stage" / "cues.json")
    c = baked.scenes["Narrated"]
    assert c["intro"].target_frame == 60 and c["swap"].target_frame == 105
    assert c["intro"].description == "after 'here is a square'"
    assert c["old"].tombstone
    assert main(["bake", str(scene), "Duplicate"]) == 1  # errors: nothing written
