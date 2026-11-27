"""Asset inventory/validation and render presets (backlog 3.5, spec F10)."""

import json

import numpy as np
import pytest
from PIL import Image

from manim_stage import audio
from manim_stage.assets import inventory, kind_of, resolve
from manim_stage.cli import main
from manim_stage.export import PRESETS, ExportJob, ExportSettings, manim_command

SCENE = """
from manim import *
from manim_stage import StageScene

class Pics(StageScene):
    def construct(self):
        self.add(ImageMobject("assets/logo"))        # extension found like Manim does
        self.add(SVGMobject("diagram.svg"))
        self.add_sound("missing_click.wav")
        name = "dyn.png"
        self.add(ImageMobject(name))                  # computed: listed as dynamic
        self.add(Text("hi", font="NoSuchFontAnywhere"))
"""


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "p"
    (p / "assets").mkdir(parents=True)
    Image.new("RGB", (8, 8), "red").save(p / "assets" / "logo.png")
    (p / "diagram.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" '
        'height="10"><rect width="10" height="10"/></svg>'
    )
    (p / "lesson.py").write_text(SCENE, encoding="utf-8")
    return p


def test_inventory_resolves_like_manim_and_reports_missing(proj):
    inv = inventory([proj / "lesson.py"])
    by = {r.name: r for r in inv.refs}
    assert by["assets/logo"].resolved == (proj / "assets" / "logo.png").resolve()
    assert by["diagram.svg"].ok and by["diagram.svg"].kind == "svg"
    assert not by["missing_click.wav"].ok and by["missing_click.wav"].source == "lesson.py:9"
    assert by["<dynamic>"].dynamic and by["<dynamic>"].ok
    assert inv.fonts_missing == [("NoSuchFontAnywhere", "lesson.py:12")]
    assert [r.name for r in inv.missing] == ["missing_click.wav"]


def test_audio_workspace_clips_are_checked(proj):
    (proj / ".manim-stage").mkdir()
    audio.save(
        proj / ".manim-stage" / "audio.json",
        audio.AudioFile({"Pics": [audio.AudioClip("v", "voice.wav")]}),
    )
    inv = inventory([proj / "lesson.py"])
    assert any(r.name == "voice.wav" and not r.ok for r in inv.refs)
    audio.write_wav(proj / "voice.wav", np.zeros((10, 2), np.float32))
    assert all(r.ok for r in inventory([proj / "lesson.py"]).refs if r.name == "voice.wav")


def test_cli_assets_exit_code_and_json(proj, capsys):
    assert main(["assets", str(proj / "lesson.py")]) == 1
    assert "MISS" in capsys.readouterr().out
    assert main(["assets", str(proj / "lesson.py"), "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert {a["name"] for a in doc["assets"] if not a["ok"]} == {"missing_click.wav"}


def test_kinds_and_resolution(tmp_path):
    assert kind_of("a.MP3") == "audio" and kind_of("b.svg") == "svg" and kind_of("c.xyz") == "other"
    (tmp_path / "x.wav").write_bytes(b"")
    assert resolve("x", tmp_path, tmp_path, (".wav",)) == (tmp_path / "x.wav").resolve()
    assert resolve("y", tmp_path, tmp_path, (".wav",)) is None


def test_presets_map_to_manim_flags():
    s = PRESETS["4k30"].apply(ExportSettings())
    cmd = " ".join(manim_command("a.py", "S", s, python="py"))
    assert "-q k" in cmd and "-r 3840,2160" in cmd and "--fps 30" in cmd
    a = PRESETS["alpha1080p30"].apply(ExportSettings())
    assert a.transparent and a.format == "mov"
    assert "-r" not in manim_command("a.py", "S", PRESETS["1080p60"].apply(ExportSettings()))


def test_custom_preset_export_metadata(tmp_path):
    from conftest import SCENES

    s = ExportSettings(quality="low_quality", resolution=(320, 180), fps=12, media_dir=tmp_path)
    r = ExportJob(SCENES / "golden.py", "Shapes", s).start().wait(300)
    assert r.ok, r.error
    assert (r.probe["width"], r.probe["height"], r.probe["fps"]) == (320, 180, 12.0)
