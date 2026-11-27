"""manim.cfg config panel (MF.6) and sections navigator (MF.7)."""

import pytest
from conftest import SCENES
from PIL import Image

from manim_stage import manimcfg
from manim_stage.runner import run_capture
from manim_stage.studio.ui.sections_panel import section_spans

SCENE = """
from manim import Dot, Scene

class Bg(Scene):
    def construct(self):
        self.add(Dot())
        self.wait(0.2)
"""


def test_cfg_edit_keeps_other_sections_and_validates(tmp_path):
    cfg = tmp_path / "manim.cfg"
    cfg.write_text(
        "[CLI]\nverbosity = INFO\nframe_rate = 30\n\n[logger]\nlog_width = 80\n", encoding="utf-8"
    )
    manimcfg.write(cfg, {"background_color": "#102030", "frame_rate": None})
    data = manimcfg.read(cfg)
    assert data == {"verbosity": "INFO", "background_color": "#102030"}
    assert "[logger]" in cfg.read_text(encoding="utf-8")
    assert (tmp_path / "manim.cfg.bak").is_file()
    for bad in (
        {"pixel_width": "wide"},
        {"format": "avi"},
        {"background_opacity": "2"},
        {"transparent": "yes"},
    ):
        with pytest.raises(manimcfg.ConfigError):
            manimcfg.render(cfg, bad)
    edit = manimcfg.edit_for(cfg, {"format": "gif"})
    edit.do(cfg)
    assert manimcfg.read(cfg)["format"] == "gif"
    edit.undo(cfg)
    assert "format" not in manimcfg.read(cfg)
    fresh = tmp_path / "new" / "manim.cfg"
    fresh.parent.mkdir()
    e2 = manimcfg.edit_for(fresh, {"transparent": "True"})
    e2.do(fresh)
    e2.undo(fresh)
    assert not fresh.exists()


def test_cfg_background_reaches_the_preview_and_invalidates_the_cache(tmp_path):
    scene = tmp_path / "bg.py"
    scene.write_text(SCENE, encoding="utf-8")
    plain = run_capture(scene, "Bg", cache_dir=tmp_path / "c", width=64, height=36)
    manimcfg.write(manimcfg.path_for(scene), {"background_color": "#FF0000"})
    red = run_capture(scene, "Bg", cache_dir=tmp_path / "c", width=64, height=36)
    assert red.revision != plain.revision
    px = Image.open(red.frames[0]).convert("RGB").getpixel((1, 1))
    assert px[0] > 200 and px[1] < 40 and px[2] < 40


def test_section_spans():
    tl = {
        "duration_frames": 100,
        "events": [
            {
                "kind": "section",
                "label": "B",
                "start_frame": 40,
                "end_frame": 40,
                "meta": {"type": "default.normal", "skip_animations": True},
            },
            {"kind": "section", "label": "A", "start_frame": 10, "end_frame": 10, "meta": {}},
        ],
    }
    spans = section_spans(tl)
    assert [(s.name, s.start, s.end, s.skip) for s in spans] == [
        ("(start)", 0, 10, False),
        ("A", 10, 40, False),
        ("B", 40, 100, True),
    ]
    assert section_spans({"duration_frames": 5, "events": []})[0].name == "(start)"


def test_sections_tab_and_config_tab(qtbot, tmp_path):
    from test_studio_ui import dispose, wait_done

    from manim_stage.studio.app import create_window

    win, _ = create_window(
        SCENES / "demo_params.py", "Demo", workers=1, cache_dir=tmp_path / "c", watch=False
    )
    win.show()
    wait_done(qtbot, win, "Demo")
    sp = win.sections_panel
    names = [sp.tree.topLevelItem(i).text(0) for i in range(sp.tree.topLevelItemCount())]
    assert names == ["Intro", "Outro"]
    outro = sp.spans[1]
    sp.tree.setCurrentItem(sp.tree.topLevelItem(1))
    sp.loop_btn.click()
    assert (win.playback.range.start, win.playback.range.end) == (outro.start, outro.end)
    assert win.playback.frame == outro.start
    dlg = win.export_section(outro.start, outro.end)
    assert dlg.ranged.isChecked()
    dlg.close()
    dlg = win.export_all_sections()
    assert dlg.whole.isChecked() and dlg.sections.isChecked()
    dlg.close()
    # Config tab: shows Manim's defaults, apply is undoable and writes manim.cfg
    cp = win.config_panel
    assert cp.path == SCENES / "manim.cfg"
    cp.path = tmp_path / "manim.cfg"  # don't write into the test scenes folder
    cp.reload()
    assert cp.editors["background_color"].placeholderText().lower().startswith("#000000")
    cp.editors["background_color"].setText("#223344")
    cp.applyRequested.disconnect()  # the window would write next to the test scenes
    edits = []
    cp.applyRequested.connect(edits.append)
    cp.apply_btn.click()
    assert edits and "#223344" in edits[0].after
    edits[0].do(cp.path)
    cp.reload()
    assert cp.editors["background_color"].text() == "#223344"
    cp.editors["pixel_width"].setText("wide")
    cp.apply_btn.click()
    assert "pixel_width" in cp.error.text() and len(edits) == 1
    assert not (SCENES / "manim.cfg").exists()
    dispose(win)
