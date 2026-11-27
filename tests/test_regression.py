"""Regression baseline (spec §2.1, §2.10, §10.1).

1. Installing and importing manim-stage changes nothing Manim renders.
2. Golden frames of representative unmodified scenes, rendered by the plain Manim
   CLI, still match. These catch rendering changes from Manim upgrades
   (docs/upstream-sync.md step 6).

Regenerate golden frames after an intentional, reviewed Manim upgrade:
    MANIM_STAGE_UPDATE_GOLDEN=1 uv run pytest tests/test_regression.py
"""

import os
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import numpy as np
import pytest
from conftest import SCENES
from PIL import Image

GOLDEN = Path(__file__).parent / "golden"
SCENE_FILE = SCENES / "golden.py"
FPS, W, H = 10, 320, 180
# Cairo/pixman builds differ per OS (antialiasing), so a pixel only counts as changed
# if a channel moves by more than PIXEL_TOLERANCE, and at most MAX_CHANGED of pixels may.
PIXEL_TOLERANCE = 24
MAX_CHANGED = 0.001  # a moving dot between golden picks changes ~0.5%
UPDATE = os.environ.get("MANIM_STAGE_UPDATE_GOLDEN") == "1"

CLI_ARGS = [
    "render", "-r", f"{W},{H}", "--fps", str(FPS), "--format", "png-sequence",
    "--disable_caching", "--progress_bar", "none", "--seed", "0",
]  # fmt: skip


def render(scene: str, out: Path, *, import_manim_stage: bool = False) -> dict[int, Path]:
    args = [*CLI_ARGS, "--media_dir", str(out), str(SCENE_FILE), scene]
    if import_manim_stage:
        code = (
            "import sys, manim_stage, manim_stage.capture, manim_stage.runner, "
            "manim_stage.framecache\n"
            "from manim.__main__ import main\n"
            f"sys.argv = ['manim', *{args!r}]\n"
            "main()"
        )
        cmd = [sys.executable, "-c", code]
    else:
        cmd = [sys.executable, "-m", "manim", *args]
    subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
    return {int(p.stem): p for p in out.rglob(f"images/**/{scene}/*.png")}


def test_manim_stage_registers_no_manim_plugin():
    """manim imports every `manim.plugins` entry point; we must not be one (ADR-0009)."""
    eps = metadata.entry_points(group="manim.plugins")
    assert not [ep for ep in eps if ep.value.split(".")[0] == "manim_stage"]


@pytest.mark.parametrize("scene", ["Shapes", "Updaters"])
def test_importing_manim_stage_does_not_change_cli_output(tmp_path, scene):
    plain = render(scene, tmp_path / "plain")
    with_stage = render(scene, tmp_path / "stage", import_manim_stage=True)
    assert sorted(plain) == sorted(with_stage) and plain
    for i in plain:
        assert plain[i].read_bytes() == with_stage[i].read_bytes(), f"frame {i} differs"


def picks(frames: dict[int, Path]) -> list[int]:
    n = max(frames) + 1
    return sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})


@pytest.mark.parametrize("scene", ["Shapes", "Choreography", "Updaters"])
def test_golden_frames(tmp_path, scene):
    frames = render(scene, tmp_path / "media")
    gdir = GOLDEN / scene
    if UPDATE:
        shutil.rmtree(gdir, ignore_errors=True)
        gdir.mkdir(parents=True)
        for i in picks(frames):
            shutil.copy(frames[i], gdir / f"{i:04d}.png")
        (gdir / "count.txt").write_text(str(len(frames)))
        pytest.skip("golden frames regenerated")

    assert gdir.is_dir(), f"no golden frames for {scene}; run with MANIM_STAGE_UPDATE_GOLDEN=1"
    assert len(frames) == int((gdir / "count.txt").read_text()), "frame count changed"
    for g in sorted(gdir.glob("*.png")):
        i = int(g.stem)
        a = np.asarray(Image.open(frames[i]).convert("RGBA"), dtype=np.int16)
        b = np.asarray(Image.open(g).convert("RGBA"), dtype=np.int16)
        assert a.shape == b.shape, f"{scene} frame {i}: size changed"
        diff = np.abs(a - b).max(axis=-1)
        changed = float((diff > PIXEL_TOLERANCE).mean())
        assert changed <= MAX_CHANGED, (
            f"{scene} frame {i}: {changed:.3%} of pixels changed by >{PIXEL_TOLERANCE} "
            f"(max diff {diff.max()}, any diff {(diff > 0).mean():.3%})"
        )
