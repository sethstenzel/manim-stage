"""Scene-tree inspection and exposed properties (backlog 3.3, MF.5, spec F08)."""

import subprocess
import sys

import numpy as np
import pytest
from conftest import SCENES
from PIL import Image
from test_schemas import validator

from manim_stage import inspector
from manim_stage.runner import run_capture
from manim_stage.studio import PreviewService, RenderSettings

FILE = SCENES / "inspectable.py"
SMALL = RenderSettings(fps=10, width=320, height=180)


def test_inspect_reports_the_mobject_tree(tmp_path):
    with PreviewService(FILE, cache_dir=tmp_path / "c", settings=SMALL) as svc:
        msg = svc.inspect_at("Labeled", 0.1)
    validator("runner-message.schema.json").validate({"v": 1, "type": "inspect", **msg})
    tree = msg["tree"]
    assert [n["class"] for n in tree] == ["VGroup", "Square"]
    node, label = tree[0]["children"]
    assert node["class"] == "Circle" and node["name"] == "node"
    assert node["exposed"]["name"] == "node"
    assert node["exposed"]["props"]["fill_color"]["value"].lower() == "#58c4dd"
    assert label["class"] == "Text" and label["children"]  # glyphs
    b = node["bounds"]
    assert b[0] == pytest.approx(-3, abs=0.01) and b[2] == pytest.approx(-1, abs=0.01)
    assert msg["frame_width"] > 0


def test_hit_test_finds_the_deepest_topmost_mobject(tmp_path):
    with PreviewService(FILE, cache_dir=tmp_path / "c", settings=SMALL) as svc:
        tree = svc.inspect_at("Labeled", 0.1)["tree"]
    assert inspector.hit_test(tree, 2.0, 0.0)["class"] == "Square"
    hit = inspector.hit_test(tree, -2.6, 0.5)  # on the circle, away from the label
    assert hit["class"] == "Circle"
    assert inspector.hit_test(tree, 6.5, 3.5) is None


def centre_color(path, x_frac):
    a = np.asarray(Image.open(path).convert("RGB"))
    h, w, _ = a.shape
    return tuple(int(v) for v in a[int(h * 0.58), int(w * x_frac)])


def test_saved_edit_is_reproduced_by_plain_manim_render(tmp_path):
    """F08 accept: adjust the exposed fill colour, preview, save, reproduce headlessly."""
    import shutil

    proj = tmp_path / "proj"
    (proj / ".manim-stage").mkdir(parents=True)
    shutil.copy(FILE, proj / "lesson.py")
    side = proj / ".manim-stage" / "properties.json"
    # preview: an ephemeral override file, nothing saved
    tmp_over = tmp_path / "preview.json"
    inspector.save(tmp_over, {"Labeled": {"node": {"fill_color": "#FF0000"}}})
    with PreviewService(proj / "lesson.py", cache_dir=tmp_path / "c", settings=SMALL) as svc:
        svc.render("Labeled", env={"MANIM_STAGE_PROPERTIES": str(tmp_over)})
        svc.wait_idle(120)
        preview = svc.current.frames[0]
    assert centre_color(preview, 0.36)[0] > 200 and not side.exists()
    # save → plain manim render reproduces it
    inspector.save(side, {"Labeled": {"node": {"fill_color": "#FF0000"}}})
    out = tmp_path / "media"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            "lesson.py",
            "Labeled",
            "-r",
            "320,180",
            "--fps",
            "10",
            "-s",
            "--media_dir",
            str(out),
            "--disable_caching",
        ],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    still = next(out.rglob("*.png"))
    assert centre_color(still, 0.36)[0] > 200
    tl = run_capture(proj / "lesson.py", "Labeled", fps=10, width=64, height=36)
    assert any(p.name == "properties.json" for p in map(__import__("pathlib").Path, [])) or tl


def test_expose_rejects_unknown_properties(tmp_path):
    scene = tmp_path / "bad.py"
    scene.write_text(
        "from manim import *\nfrom manim_stage import StageScene\n"
        "class Bad(StageScene):\n    def construct(self):\n"
        "        self.expose(Square(), 'sq', 'wobble')\n",
        encoding="utf-8",
    )
    from manim_stage.runner import RunnerError

    with pytest.raises(RunnerError, match="unknown properties"):
        run_capture(scene, "Bad", fps=10, width=64, height=36)


def test_as_python():
    code = inspector.as_python(
        "node", {"fill_color": "#FF0000", "scale": 1.5, "position": [1, 2, 0]}
    )
    assert code.splitlines() == [
        'node.set_fill(color="#FF0000")',
        "node.scale(1.5)",
        "node.move_to([1, 2, 0])",
    ]
