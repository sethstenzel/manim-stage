"""Demo parameters and the web player (backlog 4.3, spec F12)."""

import json

import pytest
from conftest import SCENES

from manim_stage import demo, web
from manim_stage.project import ProjectError
from manim_stage.runner import run_capture

SCENE = SCENES / "demo_params.py"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv(demo.ENV, raising=False)
    demo.USED.clear()
    yield
    demo.USED.clear()


def test_param_defaults_overrides_and_validation(tmp_path, monkeypatch):
    assert demo.param("n", 3, min=1, max=8) == 3
    assert demo.USED["n"]["type"] == "integer" and demo.USED["n"]["overridden"] is False
    f = demo.write_overrides(tmp_path / "d.json", {"n": 5, "algo": "nope"})
    monkeypatch.setenv(demo.ENV, str(f))
    assert demo.param("n", 3, min=1, max=8) == 5 and demo.USED["n"]["overridden"]
    with pytest.raises(ProjectError, match="one of"):
        demo.param("algo", "bubble", options=["bubble", "insertion"])
    demo.write_overrides(f, {"n": 99})
    with pytest.raises(ProjectError, match="between"):
        demo.param("n", 3, min=1, max=8)
    assert [p["name"] for p in demo.used()] == ["n"]  # invalid values never register


def test_runner_reports_params_and_overrides_change_the_render(tmp_path, monkeypatch):
    base = run_capture(SCENE, "Demo", cache_dir=tmp_path / "c")
    f = demo.write_overrides(tmp_path / "d.json", {"n": 6, "round": True})
    monkeypatch.setenv(demo.ENV, str(f))
    live = run_capture(SCENE, "Demo", cache_dir=tmp_path / "c")
    assert live.revision != base.revision  # the override file is a dependency


def test_chapters_captions_and_vtt():
    tl = {
        "scene": "S",
        "frame_rate": 10,
        "duration_frames": 50,
        "events": [
            {"kind": "section", "label": "autocreated", "start_frame": 0, "end_frame": 0},
            {"kind": "section", "label": "Swap", "start_frame": 20, "end_frame": 20},
            {
                "kind": "cue",
                "label": "ignored when sections exist",
                "start_frame": 5,
                "end_frame": 5,
            },
            {"kind": "caption", "label": "hello", "start_frame": 0, "end_frame": 15},
        ],
    }
    chs = web.chapters(tl)
    assert [(c.title, c.start) for c in chs] == [("S", 0.0), ("Swap", 2.0)]
    vtt = web.chapters_vtt(chs, 5.0)
    assert "00:00:02.000 --> 00:00:05.000\nSwap" in vtt and vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.500\nhello" in web.captions_vtt(web.captions(tl))
    part = web.slice_timeline(tl, 10, 40)
    assert part["duration_frames"] == 30
    assert [c.start for c in web.chapters(part)] == [0.0, 1.0]
    no_sections = {**tl, "events": [e for e in tl["events"] if e["kind"] != "section"]}
    assert [c.title for c in web.chapters(no_sections)] == ["S", "ignored when sections exist"]


def test_cli_builds_a_player_from_a_render(tmp_path, capsys):
    from manim_stage.cli import main

    out = tmp_path / "site"
    assert main(["web", str(SCENE), "Demo", "-q", "low_quality", "-o", str(out)]) == 0
    assert "2 chapters" in capsys.readouterr().out or (out / "index.html").exists()
    page = (out / "index.html").read_text(encoding="utf-8")
    data = json.loads((out / "player.json").read_text(encoding="utf-8"))
    assert (out / data["video"]).is_file() and data["video"] in page
    assert [c["title"] for c in data["chapters"]] == ["Intro", "Outro"]
    assert [c["text"] for c in data["captions"]] == ["Some shapes", "The end"]
    assert (out / "chapters.vtt").is_file() and (out / "captions.vtt").is_file()
    assert data["poster"] == "poster.jpg" and (out / "poster.jpg").is_file()
    assert "http" not in page.replace("http-equiv", "")  # self-contained: no remote fetches


def test_demo_tab_drives_the_preview_and_export_defaults(qtbot, tmp_path):
    from test_studio_ui import dispose, wait_done

    from manim_stage.studio.app import create_window

    win, _ = create_window(SCENE, "Demo", workers=1, cache_dir=tmp_path / "c", watch=False)
    win.show()
    wait_done(qtbot, win, "Demo")
    panel = win.demo_panel
    assert set(panel.controls) == {"n", "round", "size"}
    first = win.service.current.revision
    slider = panel.controls["n"][0]
    slider.slider.setValue(6)  # like dragging; debounced re-render
    qtbot.waitUntil(lambda: win.service.current.revision not in ("", first), timeout=60_000)
    wait_done(qtbot, win, "Demo")
    assert panel.values == {"n": 6}
    env = win._demo_env()
    assert json.loads(open(env[demo.ENV], encoding="utf-8").read()) == {"n": 6}
    # exports default to the parameter defaults; baking is explicit
    from manim_stage.studio.ui.export_dialog import ExportDialog

    dlg = ExportDialog(SCENE, "Demo", None, None, 15, win, demo_env=env)
    assert not dlg.bake_demo.isHidden() and not dlg.bake_demo.isChecked()
    dlg.close()
    panel.reset()
    assert panel.values == {} and win._demo_env() == {}
    dispose(win)
