"""``manim-stage`` CLI (backlog 1.6)."""

import json

import pytest
from conftest import SCENES
from test_schemas import validator

from manim_stage import __version__
from manim_stage.cli import main

FILE = str(SCENES / "timing.py")


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0 and __version__ in capsys.readouterr().out


def test_scenes(capsys):
    assert main(["scenes", FILE]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("Lesson")
    assert main(["scenes", FILE, "--json"]) == 0
    assert [s["name"] for s in json.loads(capsys.readouterr().out)][:2] == ["Lesson", "Nested"]


def test_timeline_text_and_json(capsys):
    assert main(["timeline", FILE, "Nested"]) == 0
    text = capsys.readouterr().out
    assert "Nested: 30 frames at 15 fps" in text and "LaggedStart" in text
    assert main(["timeline", FILE, "Nested", "--json", "--fps", "10"]) == 0
    tl = json.loads(capsys.readouterr().out)
    validator("timeline.schema.json").validate(tl)
    assert tl["frame_rate"] == 10


def test_timeline_error_is_reported(capsys):
    assert main(["timeline", FILE, "Broken"]) == 1
    assert "boom" in capsys.readouterr().err


def test_doctor_json(capsys):
    code = main(["doctor", "--json"])
    checks = {c["name"]: c for c in json.loads(capsys.readouterr().out)}
    assert checks["Manim"]["status"] == "ok"
    assert checks["Cairo renderer"]["status"] == "ok"
    assert "Tex / MathTex" in checks and "Export mp4 (H.264)" in checks
    assert code == (1 if any(c["status"] == "fail" for c in checks.values()) else 0)


def test_cache_info_and_clear(tmp_path, capsys):
    (tmp_path / "abcdef0123456789").mkdir()
    (tmp_path / "abcdef0123456789" / "000000.png").write_bytes(b"x" * 2048)
    assert main(["cache", "--cache-dir", str(tmp_path)]) == 0
    assert "1 revisions" in capsys.readouterr().out
    assert main(["cache", "--clear", "--cache-dir", str(tmp_path)]) == 0
    assert not tmp_path.exists()


def test_studio_subcommand_parses_and_delegates(monkeypatch):
    seen = {}
    import manim_stage.studio.app as app

    monkeypatch.setattr(app, "run", lambda args: seen.setdefault("args", args) and 0)
    assert main(["studio", FILE, "Lesson", "-q", "medium_quality", "--workers", "2",
                 "--no-watch"]) == 0  # fmt: skip
    a = seen["args"]
    assert (a.scene, a.quality, a.workers, a.no_watch) == ("Lesson", "medium_quality", 2, True)


def test_missing_file_is_an_error(capsys):
    with pytest.raises(SystemExit):
        main(["scenes", "does-not-exist.py"])
    assert "is not a file" in capsys.readouterr().err
