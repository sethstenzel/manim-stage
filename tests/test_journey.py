"""M1 gate user journey (spec F01 accept, §10.9, §11 M1 gate).

"A developer can edit an existing unmodified Manim scene, save, view the updated
preview, scrub an already-rendered range, and export a full-quality MP4; the CLI
version continues to work unmodified."
"""

import shutil
import subprocess
import sys

import numpy as np
import pytest
from conftest import SCENES
from PIL import Image

pytest.importorskip("PySide6")

from manim_stage.export import ExportJob, ExportSettings, manim_command  # noqa: E402
from manim_stage.studio.app import create_window  # noqa: E402

TIMEOUT = 300_000


def _frames(path):
    import av

    with av.open(str(path)) as c:
        return [np.asarray(f.to_image().convert("RGB"), dtype=np.int16) for f in c.decode(video=0)]


def test_edit_preview_scrub_export_unmodified_scene(qtbot, tmp_path):
    from test_studio_ui import dispose

    proj = tmp_path / "lesson"
    proj.mkdir()
    scene = proj / "golden.py"
    shutil.copy(SCENES / "golden.py", scene)  # an unmodified Manim script

    win, svc = create_window(scene, "Shapes", workers=2, cache_dir=tmp_path / "cache", watch=True)
    win.show()

    def done_after(seq):
        def ok():
            st = win.shown_state
            assert st and st[0] > seq and st[2] == "done"

        return ok

    qtbot.waitUntil(done_after(0), timeout=TIMEOUT)
    first = win.service.current
    k = 8  # the blue square is on screen (Create, 0.53 s)
    win.seek(k)
    before = np.asarray(Image.open(first.frames[k]).convert("RGB"))

    # 1. edit and save -> the preview re-renders by itself, playhead kept
    src = scene.read_text(encoding="utf-8")
    assert "Square(color=BLUE" in src
    scene.write_text(src.replace("Square(color=BLUE", "Square(color=GREEN"), encoding="utf-8")
    qtbot.waitUntil(done_after(first.seq), timeout=TIMEOUT)
    second = win.service.current
    assert second.revision != first.revision
    assert win.playback.frame == k  # playhead preserved
    after = np.asarray(Image.open(second.frames[k]).convert("RGB"))
    assert not np.array_equal(before, after)  # the update is visible

    # 2. scrub the rendered range
    last = second.timeline.duration_frames - 1
    for f in (0, last // 3, last // 2, last, k):
        win.seek(f)
        assert win.viewport.has_frame
        assert win.timeline.canvas.playhead == f

    # 3. full-quality MP4 export from the Studio == plain `manim render`
    settings = ExportSettings(quality="high_quality", media_dir=tmp_path / "studio_media")
    studio = ExportJob(scene, "Shapes", settings).start().wait(600)
    assert studio.ok, studio.error
    p = studio.probe
    assert (p["width"], p["height"], p["fps"], p["video_codec"]) == (1920, 1080, 60.0, "h264")
    assert abs(p["duration_s"] - second.timeline.duration_frames / 15) < 0.1
    dispose(win)

    plain_settings = ExportSettings(quality="high_quality", media_dir=tmp_path / "cli_media")
    cli = manim_command(scene, "Shapes", plain_settings)
    proc = subprocess.run(cli, cwd=proj, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    plain = next((tmp_path / "cli_media").rglob("Shapes.mp4"))
    a, b = _frames(studio.output), _frames(plain)
    assert len(a) == len(b)
    assert max(float(np.abs(x - y).max()) for x, y in zip(a, b, strict=True)) <= 2


def test_plain_manim_cli_still_renders_with_manim_stage_installed(tmp_path):
    """The CLI keeps working on the unmodified file (regression suite covers bytes/pixels)."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            str(SCENES / "golden.py"),
            "Shapes",
            "-ql",
            "--media_dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert list(tmp_path.rglob("Shapes.mp4"))
