"""The feature lessons in examples/lessons render, with their cues and chapters."""

import json
import shutil
from pathlib import Path

import pytest

from manim_stage import compose, web
from manim_stage.runner import run_capture

ROOT = Path(__file__).resolve().parent.parent / "examples" / "lessons"
HAS_LATEX = bool(shutil.which("latex") and shutil.which("dvisvgm"))

# file, scene, cue labels, chapter titles (None: don't check)
CASES = [
    ("01_signals.py", "RadiusSignal", [], None),
    ("01_signals.py", "ArgMin", [], None),
    ("02_flow.py", "FlowHelpers", [], None),
    ("02_flow.py", "Tweening", [], None),
    ("03_code.py", "CodeTour", [], None),
    ("04_cues.py", "TimeEvents", ["explain_idea", "explain_sketch", "wrap_up"], None),
    ("05_sound.py", "Narrated", ["intro.add_four", "intro.show_sum"], None),
    ("05_sound.py", "SoundEffects", [], None),
    ("06_theme.py", "ThemePalette", [], None),
    ("07_inspector.py", "Orbit", [], None),
    ("08_transitions.py", "FirstScene", [], None),
    ("08_transitions.py", "SecondScene", [], None),
    ("09_camera.py", "CenterOn", ["zoom_square", "go_circle"], None),
    ("09_camera.py", "FollowDot", [], None),
    ("10_slides.py", "Slides", [], ["First slide", "Second slide", "Outtakes", "Last slide"]),
    ("11_demo_params.py", "Lissajous", [], None),
    ("12_text.py", "Typography", [], None),
    pytest.param(
        "12_text.py",
        "Formula",
        [],
        None,
        marks=pytest.mark.skipif(not HAS_LATEX, reason="needs LaTeX and dvisvgm"),
    ),
    ("13_binary_search.py", "BinarySearch", [], ["Setup", "Search", "Result"]),
]


@pytest.mark.parametrize(("file", "scene", "cues", "chapters"), CASES)
def test_lesson_renders(tmp_path, file, scene, cues, chapters):
    r = run_capture(ROOT / file, scene, fps=10, width=192, height=108, cache_dir=tmp_path / "c")
    tl = r.timeline
    assert not tl.warnings, tl.warnings
    assert len(r.frames) == tl.duration_frames > 0
    assert [e.label for e in tl.events if e.kind == "cue"] == cues
    if chapters is not None:
        assert [c.title for c in web.chapters(tl.to_dict())] == chapters


def test_every_lesson_scene_is_tested():
    import ast

    tested = {(c.values[0], c.values[1]) if hasattr(c, "values") else c[:2] for c in CASES}
    for path in sorted(ROOT.glob("[0-9][0-9]_*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef):
                assert (path.name, node.name) in tested, f"{path.name}:{node.name} untested"


def test_lessons_are_themed_by_the_shared_project(tmp_path):
    from PIL import Image

    r = run_capture(
        ROOT / "06_theme.py", "ThemePalette", fps=10, width=192, height=108, cache_dir=tmp_path
    )
    px = Image.open(r.frames[0]).convert("RGB").getpixel((2, 2))
    assert px == (0x14, 0x18, 0x1F)  # background from examples/lessons/.manim-stage


def test_sequence_file_is_valid():
    spec = ROOT / "lessons.sequence.json"
    parts, options = compose.load_spec(spec)
    assert [p.scene for p in parts] == ["FirstScene", "SecondScene", "ThemePalette", "Slides"]
    assert all(p.file.exists() for p in parts)
    doc = json.loads(spec.read_text(encoding="utf-8"))
    from jsonschema import Draft202012Validator

    schema_path = ROOT.parent.parent / "docs" / "schemas" / "sequence.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(doc)
    assert options["output"].endswith("lessons.mp4")
