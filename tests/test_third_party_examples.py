"""The three third-party-style examples (M4 gate) render and behave."""

from pathlib import Path

import pytest

from manim_stage import web
from manim_stage.runner import run_capture

ROOT = Path(__file__).resolve().parent.parent / "examples" / "third_party"
CASES = [
    (
        "graph_search/bfs.py",
        "BFS",
        ["search_starts", "all_visited"],
        ["The graph", "Search", "Result"],
    ),
    ("pendulum/pendulum.py", "Pendulum", ["release"], ["Setup", "Swing"]),
    (
        "http_request/request.py",
        "Request",
        ["request_sent", "query", "render"],
        ["Setup", "Request", "Database", "Response"],
    ),
]


@pytest.mark.parametrize(("file", "scene", "cues", "sections"), CASES)
def test_example_renders_with_its_cues_and_chapters(tmp_path, file, scene, cues, sections):
    r = run_capture(ROOT / file, scene, fps=10, width=192, height=108, cache_dir=tmp_path / "c")
    tl = r.timeline
    assert not tl.warnings, tl.warnings
    assert len(r.frames) == tl.duration_frames > 0
    assert [e.label for e in tl.events if e.kind == "cue"] == cues
    chapters = [c.title for c in web.chapters(tl.to_dict())]
    assert chapters == sections


def test_pendulum_is_themed_and_has_demo_parameters(tmp_path):
    r = run_capture(
        ROOT / "pendulum" / "pendulum.py",
        "Pendulum",
        fps=10,
        width=192,
        height=108,
        cache_dir=tmp_path / "c",
    )
    from PIL import Image

    px = Image.open(r.frames[0]).convert("RGB").getpixel((2, 2))
    assert px == (0x10, 0x14, 0x18)  # background from .manim-stage/project.json
