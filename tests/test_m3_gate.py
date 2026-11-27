"""M3 gate (spec §11): a complete multi-scene lesson with configurable visuals and
deterministic exports."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from manim_stage import inspector
from manim_stage import project as pj
from manim_stage.cli import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "lesson_series"


@pytest.fixture
def lesson(tmp_path):
    proj = tmp_path / "series"
    shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns("media", "*.mp4"))
    (proj / ".manim-stage").mkdir(exist_ok=True)
    pj.reset_cache()
    yield proj
    pj.reset_cache()


def frames(path):
    import av

    with av.open(str(path)) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


def compose(proj, name):
    spec = json.loads((proj / "lesson.sequence.json").read_text())
    spec["output"] = name
    spec["media_dir"] = f"media-{name}"
    (proj / f"{name}.sequence.json").write_text(json.dumps(spec))
    assert main(["compose", str(proj / f"{name}.sequence.json"), "-q", "low_quality"]) == 0
    return proj / name


def accent_pixels(img, accent):
    want = np.array([int(accent[i : i + 2], 16) for i in (1, 3, 5)])
    return int((np.abs(img.astype(int) - want).sum(axis=2) < 40).sum())


def test_lesson_is_deterministic_and_restyles_from_the_project(lesson):
    a = compose(lesson, "a.mp4")
    b = compose(lesson, "b.mp4")
    fa, fb = frames(a), frames(b)
    assert len(fa) == len(fb) > 0
    diffs = [
        (i, int(np.abs(x.astype(int) - y.astype(int)).max()))
        for i, (x, y) in enumerate(zip(fa, fb, strict=True))
        if not np.array_equal(x, y)
    ]
    assert not diffs, f"exports differ at frames (index, max channel diff): {diffs[:10]}"

    # restyle every scene through the project file only
    p = pj.load(lesson / ".manim-stage" / "project.json")
    p.theme.colors["accent"] = "#FF00FF"
    p.variables["speed"] = pj.Variable("speed", "number", value=2.0)
    pj.save(p)
    c = compose(lesson, "c.mp4")
    fc = frames(c)
    assert len(fc) < len(fa)  # speed 2 shortens every scene
    assert max(accent_pixels(f, "#FF00FF") for f in fc) > 50  # new accent visible
    assert max(accent_pixels(f, "#FF00FF") for f in fa) == 0

    # an inspector edit saved to properties.json is reproduced by the export
    inspector.save(
        lesson / ".manim-stage" / "properties.json", {"Intro": {"title": {"color": "#00FFFF"}}}
    )
    d = compose(lesson, "d.mp4")
    assert max(accent_pixels(f, "#00FFFF") for f in frames(d)[:10]) > 50
