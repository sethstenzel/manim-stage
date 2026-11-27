"""PreviewService: revisions, cancellation, stale-message discard, dependencies (ADR-0010)."""

import json
import os
import threading
import time
from pathlib import Path

import pytest
from conftest import SCENES
from test_schemas import validator

from manim_stage.studio import PreviewService, RenderSettings

SMALL = RenderSettings(fps=10, width=160, height=90)


class Recorder:
    def __init__(self):
        self.msgs = []
        self.lock = threading.Lock()

    def __call__(self, m):
        with self.lock:
            self.msgs.append(m)

    def of(self, type_, seq=None):
        with self.lock:
            return [m for m in self.msgs if m.type == type_ and (seq is None or m.seq == seq)]


@pytest.fixture
def service(tmp_path):
    svc = PreviewService(SCENES / "timing.py", cache_dir=tmp_path / "cache", settings=SMALL)
    rec = Recorder()
    svc.subscribe(rec)
    yield svc, rec
    svc.close()


def test_discover_scenes_in_source_order(service):
    svc, rec = service
    scenes = svc.discover_scenes()
    names = [s["name"] for s in scenes]
    assert names[:4] == ["Lesson", "Nested", "MixedRunTimes", "Broken"]
    assert scenes[0]["bases"][0] == "Scene"
    lines = (SCENES / "timing.py").read_text(encoding="utf-8").splitlines()
    assert lines[scenes[0]["line"] - 1].startswith("class Lesson(")
    assert rec.of("scenes")[0].data["scenes"] == scenes


def test_render_streams_timeline_then_all_frames(service):
    svc, rec = service
    seq = svc.render("MixedRunTimes")
    assert svc.wait_idle(120)
    types = [m.type for m in rec.msgs if m.type != "log"]
    assert types[0] == "status" and types[1] == "timeline"
    assert types[-2:] == ["done", "status"]
    total = rec.of("timeline")[0].data["timeline"]["duration_frames"]
    frames = rec.of("frame", seq)
    assert sorted(m.data["frame"] for m in frames) == list(range(total))
    assert frames[-1].data["cached"] == total == frames[-1].data["total"]
    assert all(Path(m.data["path"]).is_file() for m in frames)
    assert svc.current.state == "done"
    v = validator("preview-message.schema.json")
    for m in rec.msgs:
        v.validate(json.loads(json.dumps(m.to_dict())))


def test_rerender_reuses_cached_frames(service):
    svc, rec = service
    svc.render("MixedRunTimes")
    svc.wait_idle(120)
    seq = svc.render("MixedRunTimes")
    svc.wait_idle(120)
    done = rec.of("done", seq)[0].data
    assert done["frames_drawn"] == 0 and done["frames"] > 0


def test_new_render_cancels_old_and_drops_its_messages(service):
    svc, rec = service
    first = svc.render("Lesson")
    second = svc.render("MixedRunTimes")
    assert svc.wait_idle(120)
    assert rec.of("status", first)[-1].data["state"] == "cancelled"
    # nothing from the first revision after it was cancelled
    cancel_at = next(i for i, m in enumerate(rec.msgs)
                     if m.seq == first and m.data.get("state") == "cancelled")  # fmt: skip
    assert all(m.seq != first for m in rec.msgs[cancel_at + 1 :])
    assert rec.of("done", second)


def test_cancel_kills_the_runner(service):
    svc, rec = service
    svc.render("Lesson", RenderSettings(fps=30, width=640, height=360))
    deadline = time.time() + 60
    while not rec.of("timeline") and time.time() < deadline:
        time.sleep(0.05)
    procs = list(svc._procs)
    svc.cancel()
    for p in procs:
        assert p.wait(30) is not None
    assert svc.current.state == "cancelled"


def test_scene_error_reports_file_and_line(service):
    svc, rec = service
    seq = svc.render("Broken")
    svc.wait_idle(120)
    err = rec.of("error", seq)[0].data
    assert err["message"] == "ValueError: boom"
    assert Path(err["file"]).name == "timing.py"
    lines = (SCENES / "timing.py").read_text(encoding="utf-8").splitlines()
    assert 'raise ValueError("boom")' in lines[err["line"] - 1]
    assert svc.current.state == "error"


def test_parallel_workers(service):
    svc, rec = service
    seq = svc.render("MixedRunTimes", RenderSettings(fps=10, width=160, height=90, workers=2))
    svc.wait_idle(120)
    total = rec.of("timeline", seq)[0].data["timeline"]["duration_frames"]
    assert len({m.data["frame"] for m in rec.of("frame", seq)}) == total
    assert len(rec.of("timeline", seq)) == 1


PROJECT_SCENE = """\
from pathlib import Path
from manim import Scene, Square, FadeIn
from helper import SIZE

class UsesHelper(Scene):
    def construct(self):
        side = float(Path("data.txt").read_text())
        self.play(FadeIn(Square(side_length=SIZE * side)), run_time=0.3)
"""


def test_dependencies_are_reported_and_part_of_the_revision(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "lesson.py").write_text(PROJECT_SCENE, encoding="utf-8")
    (proj / "helper.py").write_text("SIZE = 1.0\n", encoding="utf-8")
    (proj / "data.txt").write_text("2\n", encoding="utf-8")
    with PreviewService(proj / "lesson.py", cache_dir=tmp_path / "c", settings=SMALL) as svc:
        rec = Recorder()
        svc.subscribe(rec)
        svc.render("UsesHelper")
        assert svc.wait_idle(120), rec.msgs
        assert svc.current.state == "done", rec.of("error")
        deps = {Path(p).name for p in rec.of("timeline")[0].data["dependencies"]}
        assert deps == {"helper.py", "data.txt"}
        assert {p.name for p in svc.dependencies} == {"lesson.py", "helper.py", "data.txt"}
        first = svc.current.revision

        (proj / "helper.py").write_text("SIZE = 1.5\n", encoding="utf-8")
        svc.render("UsesHelper")
        svc.wait_idle(120)
        assert svc.current.revision != first
        assert svc.current.frames_drawn > 0

        (proj / "data.txt").write_text("3\n", encoding="utf-8")
        second = svc.current.revision
        svc.render("UsesHelper")
        svc.wait_idle(120)
        assert svc.current.revision not in (first, second)


def test_media_dir_stays_out_of_the_project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    scene = proj / "t.py"
    scene.write_text(
        "from manim import Scene, Text, FadeIn\n"
        "class T(Scene):\n"
        "    def construct(self):\n"
        "        self.play(FadeIn(Text('hi')), run_time=0.2)\n",
        encoding="utf-8",
    )
    with PreviewService(scene, cache_dir=tmp_path / "c", settings=SMALL) as svc:
        svc.render("T")
        svc.wait_idle(120)
        assert svc.current.state == "done"
        assert svc.current.dependencies == []  # Manim's text cache is not a dependency
    assert "media" not in os.listdir(proj)
