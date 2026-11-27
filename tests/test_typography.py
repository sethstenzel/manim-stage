"""Text and LaTeX helpers (MF.10)."""

import pytest

from manim_stage import project as pj
from manim_stage import typography as ty

SCENE = """from manim import Dot, Scene


class S(Scene):
    def construct(self):
        self.add(Dot())
        self.wait(0.2)
"""


def test_fonts_and_templates():
    fonts = ty.fonts()
    assert fonts == sorted(set(fonts), key=str.lower) and len(fonts) > 3
    names = list(ty.tex_templates())
    assert names[:4] == ["ctex", "default", "simple", "threeb1b"]
    assert any(n.startswith("font:") for n in names)
    from manim import TexFontTemplates

    assert ty.tex_template("font:french_cursive") is TexFontTemplates.french_cursive
    with pytest.raises(ValueError):
        ty.tex_template("nope")


def test_snippets_are_valid_python_with_raw_latex():
    colors = ty.parse_color_map(r"e: BLUE, \pi = #FF0000, junk")
    assert colors == {"e": "BLUE", r"\pi": "#FF0000"}
    code = ty.mathtex_snippet(r"e^{i\pi} + 1 = 0", colors, "font:french_cursive")
    assert code == (
        r'MathTex(r"e^{i\pi} + 1 = 0", tex_to_color_map={"e": BLUE, r"\pi": "#FF0000"}, '
        "tex_template=TexFontTemplates.french_cursive)"
    )
    compile(code, "<snippet>", "eval")
    assert ty.mathtex_snippet("x", None, "default") == 'MathTex("x")'
    assert ty.missing_substrings("a+b", {"a": "RED", "c": "BLUE"}) == ["c"]
    assert ty.text_snippet('say "hi"', "Fira Code") == 'Text("say \\"hi\\"", font="Fira Code")'


def test_theme_tex_template_round_trips_and_applies(tmp_path):
    from manim import MathTex, Scene, Tex, TexFontTemplates

    path = tmp_path / ".manim-stage" / "project.json"
    doc = {
        "schema": pj.SCHEMA,
        "version": pj.VERSION,
        "theme": {"tex_template": "font:french_cursive"},
    }
    pj.write_dict(path, doc)
    th = pj.load(path).theme
    assert th.tex_template == "font:french_cursive"
    assert th.to_dict()["tex_template"] == "font:french_cursive"
    restore = pj.apply_theme(Scene(), th)
    try:
        for cls in (MathTex, Tex):
            init = cls.__dict__["__init__"]  # Manim's set_default: a partialmethod
            assert init.keywords["tex_template"] is TexFontTemplates.french_cursive
    finally:
        restore()
    for cls in (MathTex, Tex):
        assert not hasattr(cls.__dict__["__init__"], "keywords")


@pytest.mark.skipif(not ty.latex_status()["ok"], reason="needs LaTeX")
def test_render_tex_png(tmp_path):
    out = ty.render_tex_png(r"a^2 + b^2", {"a": "BLUE"}, "default", tmp_path / "f.png")
    assert out.stat().st_size > 0


def test_text_tab(qtbot, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from test_studio_ui import dispose, wait_done

    from manim_stage.studio.app import create_window

    root = tmp_path / "proj"
    root.mkdir()
    scene = root / "s.py"
    scene.write_text(SCENE, encoding="utf-8")
    win, _ = create_window(scene, "S", workers=1, cache_dir=tmp_path / "c", watch=False)
    win.show()
    wait_done(qtbot, win, "S")
    tp = win.text_panel
    tp.load()
    assert tp.font_list.count() == len(ty.fonts())
    tp.font_list.setCurrentRow(0)
    family = tp.current_font()
    assert family == tp.font_list.item(0).data(Qt.ItemDataRole.UserRole)
    tp.copy_font()
    assert f'font="{family}"' in QGuiApplication.clipboard().text()
    tp.font_use.click()
    assert pj.load(win.project_path()).theme.font == family
    win.undo_stack.undo()
    assert pj.load(win.project_path()).theme.font is None
    tp.font_search.setText("zzzz-no-such-font")
    assert all(tp.font_list.item(i).isHidden() for i in range(tp.font_list.count()))
    tp.template.setCurrentIndex(tp.template.findData("font:french_cursive"))
    assert "TexFontTemplates.french_cursive" in tp.snippet.toPlainText()
    tp.colors.setText("zzz: RED")
    assert "zzz" in tp.warn.text()
    tp.tex_use.click()
    assert pj.load(win.project_path()).theme.tex_template == "font:french_cursive"
    assert tp.preview_btn.isEnabled() == ty.latex_status()["ok"]
    dispose(win)
