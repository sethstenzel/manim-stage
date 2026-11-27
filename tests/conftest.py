import math
import struct
import sys
import wave
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
SCENES = TESTS / "scenes"
sys.path.insert(0, str(TESTS))  # lets test modules import helpers from here


@pytest.fixture(scope="session")
def monkeypatch_session():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session", autouse=True)
def test_sound(tmp_path_factory, monkeypatch_session):
    """A 0.5 s tone; scenes find it through MANIM_STAGE_TEST_SOUND (also in subprocesses)."""
    path = tmp_path_factory.mktemp("audio") / "beep.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(
            b"".join(
                struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 48000)))
                for i in range(24000)
            )
        )
    monkeypatch_session.setenv("MANIM_STAGE_TEST_SOUND", str(path))
    return path


def capture_scene(scene: str, fps: float = 15.0, file: Path = SCENES / "timing.py"):
    """Capture in-process under the same config the runner uses."""
    return capture_scene_and_class(scene, fps, file)[0]


def capture_scene_and_class(scene: str, fps: float = 15.0, file: Path = SCENES / "timing.py"):
    """Like capture_scene, also returning the freshly imported scene class."""
    from manim import tempconfig

    from manim_stage.capture import capture
    from manim_stage.runner import load_scene_class

    cfg = {
        "frame_rate": fps,
        "pixel_width": 854,
        "pixel_height": 480,
        "progress_bar": "none",
        "disable_caching": True,
        "verbosity": "WARNING",
    }
    with tempconfig(cfg):
        cls = load_scene_class(file, scene)
        return capture(cls), cls
