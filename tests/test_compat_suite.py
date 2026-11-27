"""Compatibility suite (backlog 4.4, M4 gate): unmodified Manim scenes across feature
families must preview exactly as ``manim render`` draws them, capture a clean timeline,
and render identically when opted into ``StageScene``.

The corpus is ``tests/compat/scenes.py`` (plain Manim, no LaTeX). Add a scene there
when a Manim feature family is missing.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from manim_stage.runner import run_capture

CORPUS = Path(__file__).parent / "compat" / "scenes.py"
FPS, W, H = 10, 256, 144
_spec = importlib.util.spec_from_file_location("compat_scenes", CORPUS)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SCENES = _mod.SCENES


def cli_frames(file: Path, scene: str, media: Path) -> dict[int, Path]:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            "-r",
            f"{W},{H}",
            "--fps",
            str(FPS),
            "--format",
            "png-sequence",
            "--disable_caching",
            "--progress_bar",
            "none",
            "--media_dir",
            str(media),
            str(file),
            scene,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=file.parent,
    )
    return {int(p.stem[-4:]): p for p in media.rglob(f"images/**/{scene}/*.png")}


def pixels(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


@pytest.mark.parametrize("scene", SCENES)
def test_preview_matches_manim_render(tmp_path, scene):
    result = run_capture(CORPUS, scene, fps=FPS, width=W, height=H, cache_dir=tmp_path / "c")
    tl = result.timeline
    assert not tl.warnings, tl.warnings
    plays = [e for e in tl.events if e.kind in ("play", "wait")]
    assert plays and all(e.end_frame > e.start_frame or e.kind == "wait" for e in plays)
    assert len(result.frames) == tl.duration_frames
    cli = cli_frames(CORPUS, scene, tmp_path / "media")
    assert sorted(cli) == sorted(result.frames), "frame indices differ from the Manim CLI"
    for i in sorted(cli)[:: max(1, len(cli) // 6)] + [max(cli)]:
        assert np.array_equal(pixels(result.frames[i]), pixels(cli[i])), f"frame {i} differs"


@pytest.mark.parametrize("scene", ["Geometry", "Updaters", "CameraMove"])
def test_opting_into_stagescene_changes_no_pixels(tmp_path, scene):
    """Spec §2.1: manim-stage features are opt-in; StageMixin alone draws the same."""
    staged = tmp_path / "staged.py"
    staged.write_text(
        CORPUS.read_text(encoding="utf-8")
        + "\n\nfrom manim_stage import StageMixin\n\n\n"
        + f"class Staged{scene}(StageMixin, {scene}):\n    pass\n",
        encoding="utf-8",
    )
    plain = run_capture(CORPUS, scene, fps=FPS, width=W, height=H, cache_dir=tmp_path / "a")
    stage = run_capture(
        staged, f"Staged{scene}", fps=FPS, width=W, height=H, cache_dir=tmp_path / "b"
    )
    assert sorted(stage.frames) == sorted(plain.frames)
    for i in plain.frames:
        assert np.array_equal(pixels(plain.frames[i]), pixels(stage.frames[i])), f"frame {i}"
