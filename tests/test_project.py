"""Project theme and variables (backlog 3.2, spec F07)."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from conftest import SCENES
from PIL import Image
from test_schemas import validator

from manim_stage import project as pj
from manim_stage.runner import run_capture


@pytest.fixture(autouse=True)
def fresh():
    pj.reset_cache()
    yield
    pj.reset_cache()


def test_defaults_roundtrip_and_schema(tmp_path):
    path = tmp_path / ".manim-stage" / "project.json"
    p = pj.load(path)
    assert p.theme.accent == pj.DEFAULT_COLORS["accent"] and p.variables == {}
    p.theme.colors["accent"] = "#FF0080"
    p.theme.code_style = "dracula"
    p.variables["speed"] = pj.Variable("speed", "number", 2.0, 1.0, 0.25, 4.0)
    pj.save(p)
    validator("project.schema.json").validate(json.loads(path.read_text(encoding="utf-8")))
    back = pj.load(path)
    assert back.theme.accent == "#FF0080" and back.theme.code_style == "dracula"
    assert back.variables["speed"].value == 2.0
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(pj.ProjectError, match="not valid JSON"):
        pj.load(path)


def test_var_values_types_and_validation(tmp_path, monkeypatch):
    path = tmp_path / ".manim-stage" / "project.json"
    p = pj.load(path)
    p.variables["speed"] = pj.Variable("speed", "number", 3.0)
    p.variables["mode"] = pj.Variable("mode", "enum", "fast")
    p.variables["bad"] = pj.Variable("bad", "number", 99)
    pj.save(p)
    monkeypatch.setenv("MANIM_STAGE_PROJECT", str(path))
    assert pj.var("speed", 1.0) == 3.0
    assert pj.var("unset", 7) == 7 and pj.USED["unset"].type == "integer"
    assert pj.var("mode", "slow", options=["slow", "fast"]) == "fast"
    assert pj.var("flag", True) is True
    assert pj.var("tint", "#123456") == "#123456" and pj.USED["tint"].type == "color"
    with pytest.raises(pj.ProjectError, match="between 0 and 10"):
        pj.var("bad", 1.0, min=0, max=10)
    with pytest.raises(pj.ProjectError, match="one of"):
        pj.var("mode", "slow", options=["slow", "medium"])


def theme_project(tmp_path, accent, background="#000000"):
    proj = tmp_path / "proj"
    if not proj.exists():
        shutil.copytree(SCENES / "themed", proj)
        (proj / ".manim-stage").mkdir()
    p = pj.load(proj / ".manim-stage" / "project.json")
    p.theme.colors.update(accent=accent, background=background)
    pj.save(p)
    return proj


def centre_and_corner(path):
    a = np.asarray(Image.open(path).convert("RGB"))
    h, w, _ = a.shape
    return tuple(a[h // 2, w // 2]), tuple(a[2, 2])


def render_both(proj, tmp_path, tag):
    out = {}
    for file, scene in (("scene_a.py", "SceneA"), ("scene_b.py", "SceneB")):
        r = run_capture(
            proj / file, scene, fps=10, width=160, height=90, cache_dir=tmp_path / f"cache-{tag}"
        )
        out[scene] = (r, centre_and_corner(r.frames[0]))
    return out


def test_changing_the_theme_updates_every_scene_without_source_edits(tmp_path):
    proj = theme_project(tmp_path, "#FF0000", background="#102030")
    sources = {f: (proj / f).read_bytes() for f in ("scene_a.py", "scene_b.py")}
    first = render_both(proj, tmp_path, "1")
    for _, (centre, corner) in first.values():
        assert centre == (255, 0, 0) and corner == (0x10, 0x20, 0x30)
    theme_project(tmp_path, "#00FF00", background="#102030")  # change only the accent
    second = render_both(proj, tmp_path, "2")
    for scene in ("SceneA", "SceneB"):
        assert second[scene][1][0] == (0, 255, 0)
        assert second[scene][0].revision != first[scene][0].revision  # re-rendered
    assert {f: (proj / f).read_bytes() for f in sources} == sources
    # the scene reports the project variables it read (for the Studio's Project panel)
    msg_vars = second["SceneA"][0]
    assert msg_vars.timeline.scene == "SceneA"


def test_runner_reports_used_variables(tmp_path):
    import subprocess
    import sys

    proj = theme_project(tmp_path, "#FF0000")
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim_stage.runner",
            str(proj / "scene_a.py"),
            "SceneA",
            "--fps",
            "10",
            "--width",
            "64",
            "--height",
            "36",
        ],
        capture_output=True,
        text=True,
        cwd=proj,
    )
    tl = next(json.loads(x) for x in out.stdout.splitlines() if '"timeline"' in x)
    assert tl["variables"] == [
        {
            "name": "size",
            "type": "number",
            "value": 4.0,
            "default": 4.0,
            "min": 1,
            "max": 6,
            "description": "square side",
        }
    ]
    validator("runner-message.schema.json").validate(tl)


def test_animated_code_follows_the_theme_code_style(tmp_path, monkeypatch):
    path = tmp_path / "project.json"
    p = pj.load(path)
    p.theme.code_style = "dracula"
    pj.save(p)
    monkeypatch.setenv("MANIM_STAGE_PROJECT", str(path))
    from manim_stage.code import AnimatedCode

    assert AnimatedCode("x = 1\n").style == "dracula"
    assert AnimatedCode("x = 1\n", style="monokai").style == "monokai"
    assert Path(path).exists()
