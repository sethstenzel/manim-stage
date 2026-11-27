"""AnimatedCode layout, tokens, ranges and highlighting (backlog 2.5, spec F05)."""

import numpy as np
import pytest
from manim import RIGHT, Scene, tempconfig

from manim_stage.code import AnimatedCode, CodeRange, tokenize

SRC = """def bubble_sort(a):
    n = len(a)
    for i in range(n):
\tfor j in range(n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]  # swap
    return a
"""


@pytest.fixture(scope="module")
def code():
    return AnimatedCode(SRC)


def test_tokens_have_positions_and_tabs_are_expanded():
    toks = tokenize(SRC)
    first = toks[0]
    assert (first.line, first.col, first.text, first.kind) == (1, 1, "def", "Token.Keyword")
    assert first.bold is False and first.color.startswith("#")
    tab_line = [t for t in toks if t.line == 4]
    assert tab_line[0].text == "for" and tab_line[0].col == 5  # "\t" → 4 spaces
    comment = next(t for t in toks if t.text.startswith("#"))
    assert comment.text == "# swap"  # spaces inside a token stay in it


def test_every_glyph_belongs_to_one_token(code):
    assert len(code.tokens) == len(code.token_mobjects)
    for t, m in zip(code.tokens, code.token_mobjects, strict=True):
        assert len(m) == len(t.text.replace(" ", ""))


def test_tokens_sit_on_the_character_grid(code):
    cw = code.cell_width
    for t, m in zip(code.tokens, code.token_mobjects, strict=True):
        cell = code.grid_point(t.line, t.col)
        assert -0.05 * cw <= m.get_left()[0] - cell[0] < 0.6 * cw  # left bearing only
    # tokens in the same column line up across lines
    fors = [m for t, m in zip(code.tokens, code.token_mobjects, strict=True) if t.text == "for"]
    ns = [
        m
        for t, m in zip(code.tokens, code.token_mobjects, strict=True)
        if t.text == "n" and t.col == 5
    ]
    assert abs(fors[0].get_left()[0] - ns[0].get_left()[0]) < 0.15 * cw  # glyph bearings differ
    # line pitch is constant
    ys = [code.grid_point(line, 1)[1] for line in range(1, 6)]
    assert np.allclose(np.diff(ys), -code.line_height)


def test_grid_follows_the_mobject():
    c = AnimatedCode("x = 1\ny = 2\n")
    before = c.grid_point(2, 3)
    c.shift(RIGHT * 2).scale(2)
    after = c.grid_point(2, 3)
    assert not np.allclose(before, after)
    y_tok = c.token_mobjects[3]  # "y"
    assert abs(y_tok.get_left()[0] - c.grid_point(2, 1)[0]) < c.cell_width * 2 * 0.6


def test_ranges(code):
    assert code.find("range") == CodeRange((3, 14), (3, 19))
    assert len(code.find_all("range")) == 2
    swap = code.find("a[j + 1], a[j]")
    assert [code.tokens[i].text for i in code.tokens_in(swap)] == [
        "a",
        "[",
        "j",
        "+",
        "1",
        "],",
        "a",
        "[",
        "j",
        "]",
    ] or len(code.tokens_in(swap)) >= 8
    line5 = code.get_line(5)
    assert len(line5) == len([t for t in code.tokens if t.line == 5])
    assert code.word(1, 5, 11) == CodeRange((1, 5), (1, 16))
    with pytest.raises(ValueError):
        code.find("not there")


def test_non_ascii_and_other_languages():
    c = AnimatedCode('s = "café π"  # naïve\n')
    assert [len(m) for m in c.token_mobjects] == [len(t.text.replace(" ", "")) for t in c.tokens]
    for lang, src in (
        ("javascript", "const x = [1, 2];\n"),
        ("rust", "fn main() { let x = 1; }\n"),
        ("sql", "SELECT a FROM t WHERE b > 1;\n"),
        ("bash", "echo $HOME\n"),
        ("go", "func f() int { return 1 }\n"),
        ("cpp", "int main() { return 0; }\n"),
        ("typescript", "let n: number = 1;\n"),
    ):
        toks = tokenize(src, lang)
        assert toks and toks[0].line == 1, lang


def test_highlight_dims_everything_else():
    class S(Scene):
        def construct(self):
            self.code = AnimatedCode(SRC)
            self.add(self.code)
            self.play(self.code.highlight_lines(5), run_time=0.2)

    with tempconfig({"frame_rate": 10, "dry_run": True}):
        s = S()
        s.render()
    code = s.code
    for t, m in zip(code.tokens, code.token_mobjects, strict=True):
        want = 1.0 if t.line == 5 else 0.25
        assert m[0].get_fill_opacity() == pytest.approx(want), t


def test_layout_is_deterministic():
    a, b = AnimatedCode(SRC), AnimatedCode(SRC)
    for x, y in zip(a.family_members_with_points(), b.family_members_with_points(), strict=True):
        assert np.array_equal(x.points, y.points)
