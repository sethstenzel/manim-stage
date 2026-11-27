"""Cached preview frames must equal what the unmodified Manim CLI renders (spec §2.5, §9).

Compared against ``--format png-sequence``. That format omits the frames of frozen
waits, so these scenes contain only plays (see spikes/README.md).
"""

import subprocess
import sys

import numpy as np
import pytest
from conftest import SCENES
from PIL import Image

from manim_stage.runner import run_capture

FPS = 15
W, H = 427, 240  # small: parity does not depend on resolution, CI time does


def cli_frames(scene: str, out_dir):
    subprocess.run(
        [
            sys.executable, "-m", "manim", "render",
            "-r", f"{W},{H}", "--fps", str(FPS),
            "--format", "png-sequence", "--disable_caching",
            "--progress_bar", "none", "--media_dir", str(out_dir),
            str(SCENES / "timing.py"), scene,
        ],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )  # fmt: skip
    return {int(p.stem): p for p in out_dir.rglob(f"images/**/{scene}/*.png")}


@pytest.mark.parametrize("scene", ["MixedRunTimes", "Nested"])
def test_cached_frames_are_pixel_identical_to_cli_render(tmp_path, scene):
    cli = cli_frames(scene, tmp_path / "media")
    result = run_capture(
        SCENES / "timing.py", scene, fps=FPS, width=W, height=H, cache_dir=tmp_path / "cache"
    )
    assert sorted(cli) == sorted(result.frames), "frame indices differ"
    for i, path in result.frames.items():
        a = np.asarray(Image.open(path).convert("RGBA"))
        b = np.asarray(Image.open(cli[i]).convert("RGBA"))
        assert a.shape == b.shape
        assert np.array_equal(a, b), f"frame {i} differs from CLI render"


def test_parallel_workers_produce_identical_frames(tmp_path):
    one = run_capture(SCENES / "timing.py", "Nested", fps=FPS, width=W, height=H,
                      cache_dir=tmp_path / "a")  # fmt: skip
    three = run_capture(SCENES / "timing.py", "Nested", fps=FPS, width=W, height=H,
                        cache_dir=tmp_path / "b", workers=3)  # fmt: skip
    assert three.revision == one.revision
    assert sorted(three.frames) == sorted(one.frames)
    assert three.frames_drawn == len(one.frames)
    for i, path in one.frames.items():
        a = np.asarray(Image.open(path))
        b = np.asarray(Image.open(three.frames[i]))
        assert np.array_equal(a, b), f"frame {i} differs between 1 and 3 workers"
