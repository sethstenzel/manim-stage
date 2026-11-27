"""File watching and live reload (backlog 1.2, spec F01, §9 debounce)."""

import time
from pathlib import Path

import pytest
from test_schemas import validator
from test_service import SMALL, Recorder

from manim_stage.studio import PreviewService
from manim_stage.studio.watcher import FileWatcher


def wait_for(pred, timeout=120.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_poll_debounces_a_burst_into_one_change(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("1")
    w = FileWatcher(lambda: [f], lambda _: None, debounce=0.2)
    w._snapshot()
    assert w.poll() is None
    for i in range(3):  # a burst of saves
        f.write_text("x" * (i + 2))
        assert w.poll() is None  # still inside the debounce window
        time.sleep(0.05)
    time.sleep(0.25)
    assert w.poll() == [f]
    assert w.poll() is None  # reported once


def test_new_paths_are_a_baseline_and_deletion_is_a_change(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_text("1")
    b.write_text("2")
    watched = [a]
    w = FileWatcher(lambda: watched, lambda _: None, debounce=0.05)
    w._snapshot()
    watched.append(b)  # dependency discovered later
    time.sleep(0.06)
    assert w.poll() is None
    b.unlink()
    w.poll()
    time.sleep(0.06)
    assert w.poll() == [b]


def test_debounce_range_is_enforced():
    with pytest.raises(ValueError):
        FileWatcher(lambda: [], lambda _: None, debounce=10)


SCENE = """\
from manim import Scene, Square, FadeIn
from helper import SIDE

class S(Scene):
    def construct(self):
        self.play(FadeIn(Square(side_length=SIDE)), run_time=0.2)
"""


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "lesson.py").write_text(SCENE, encoding="utf-8")
    (proj / "helper.py").write_text("SIDE = 1.0\n", encoding="utf-8")
    svc = PreviewService(proj / "lesson.py", cache_dir=tmp_path / "c", settings=SMALL)
    rec = Recorder()
    svc.subscribe(rec)
    yield proj, svc, rec
    svc.close()


def done_seqs(rec):
    return [m.seq for m in rec.of("done")]


def test_editing_a_helper_rerenders(project):
    proj, svc, rec = project
    svc.render("S")
    assert svc.wait_idle(120) and svc.current.state == "done", rec.of("error")
    first = svc.current.revision
    svc.watch(debounce=0.2)
    (proj / "helper.py").write_text("SIDE = 2.0  # bigger\n", encoding="utf-8")
    assert wait_for(lambda: len(done_seqs(rec)) == 2)
    changed = rec.of("changed")[0].data["files"]
    assert [Path(f).name for f in changed] == ["helper.py"]
    assert svc.current.revision != first
    v = validator("preview-message.schema.json")
    for m in rec.msgs:
        v.validate(m.to_dict())


def test_syntax_error_points_at_the_line_and_recovers_on_save(project):
    proj, svc, rec = project
    scene = proj / "lesson.py"
    broken = SCENE.replace("run_time=0.2)", "run_time=0.2")  # unclosed paren
    scene.write_text(broken, encoding="utf-8")
    svc.render("S")
    svc.wait_idle(120)
    err = rec.of("error")[0].data
    assert err["message"].startswith("SyntaxError")
    assert Path(err["file"]).name == "lesson.py" and err["line"] in (6, 7)
    svc.watch(debounce=0.2)
    scene.write_text(SCENE, encoding="utf-8")
    assert wait_for(lambda: done_seqs(rec))
    assert svc.current.state == "done"
