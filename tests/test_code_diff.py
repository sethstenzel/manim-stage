"""Code diff engine and animated code edits (backlog 2.6, spec F05 accept)."""

import time

import numpy as np
import pytest
from manim import Scene, tempconfig

from manim_stage.code import AnimatedCode, tokenize
from manim_stage.code_diff import diff_tokens, patience


def texts(toks, idxs):
    return [toks[i].text for i in idxs]


def test_patience_prefers_unique_lines():
    a = ["def f():", "    x = 1", "}", "def g():", "    y = 2", "}"]
    b = ["def g():", "    y = 2", "}", "def f():", "    x = 1", "}"]
    pairs = patience(a, b)
    assert all(a[i] == b[j] for i, j in pairs)
    assert len(pairs) >= 3


def test_equal_lines_keep_tokens_and_changed_lines_match_by_token():
    old = tokenize("a = 1\nb = a + 1\n")
    new = tokenize("a = 2\nb = a + 1\n")
    d = diff_tokens(old, new)
    assert texts(old, d.deleted) == ["1"] and texts(new, d.inserted) == ["2"]
    assert len(d.matches) == len(old) - 1


def test_moved_line_is_detected():
    old = tokenize("x = 1\ny = 2\nz = 3\n")
    new = tokenize("y = 2\nz = 3\nx = 1\n")
    d = diff_tokens(old, new)
    assert not d.deleted and not d.inserted
    assert (1, 3) in d.moved_lines or len(d.matches) == len(old)


def test_mapping_overrides_the_automatic_match():
    old = tokenize("f(x, x)\n")
    new = tokenize("f(x)\n")
    xs_old = [i for i, t in enumerate(old) if t.text == "x"]
    x_new = next(i for i, t in enumerate(new) if t.text == "x")
    d = diff_tokens(old, new, mapping={xs_old[1]: x_new, xs_old[0]: None})
    assert (xs_old[1], x_new) in d.matches and xs_old[0] in d.deleted
    with pytest.raises(ValueError):
        diff_tokens(old, new, mapping={xs_old[0]: x_new, xs_old[1]: x_new})


def test_repeated_tokens_are_reported_as_ambiguous():
    d = diff_tokens(tokenize("swap(a, a)\n"), tokenize("swap(b, a, a)\n"))
    assert any("token 'a' repeats" in w and "mapping=" in w for w in d.warnings)
    clean = diff_tokens(tokenize("x = 1\n"), tokenize("x = 2\n"))
    assert clean.warnings == []


def test_multiline_edit_and_non_ascii():
    old = tokenize('s = "café"\nfor c in s:\n    print(c)\n')
    new = tokenize('s = "café π"\nfor i, c in enumerate(s):\n    print(i, c)\n')
    d = diff_tokens(old, new)
    kept = {old[o].text for o, _ in d.matches}
    assert {"s", "=", "for", "c", "in", "print"} <= kept
    assert set(texts(new, d.inserted)) >= {"enumerate", "i"}


def test_500_lines_diff_fast():
    lines = [f"value_{i} = compute({i}, {i * 2})" for i in range(600)]
    old = tokenize("\n".join(lines) + "\n")
    lines[300] = "value_300 = compute(300, 601)"
    lines.insert(100, "# inserted")
    new = tokenize("\n".join(lines) + "\n")
    t0 = time.perf_counter()
    d = diff_tokens(old, new)
    assert time.perf_counter() - t0 < 2.0
    assert texts(old, d.deleted) == ["600"]
    assert texts(new, d.inserted) == ["# inserted", "601"]


# -- animated edits --------------------------------------------------------------------

BUBBLE = """def bubble_sort(a):
    n = len(a)
    for i in range(n):
        for j in range(n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
    return a
"""


def positions(code):
    return {
        (t.line, t.col, t.text): m.get_center().copy()
        for t, m in zip(code.tokens, code.token_mobjects, strict=True)
    }


def run(code, *anims, fps=10):
    class S(Scene):
        def construct(self):
            self.add(code)
            for a in anims:
                self.play(a(code), run_time=0.3)

    with tempconfig({"frame_rate": fps, "dry_run": True, "disable_caching": True}):
        S().render()


def test_animate_to_ends_as_the_new_code_on_the_same_grid():
    code = AnimatedCode(BUBBLE)
    old_pos = positions(code)
    new_src = BUBBLE.replace("    return a\n", "    print(a)\n    return a\n")
    run(code, lambda c: c.animate_to(new_src))
    assert code.source == new_src
    fresh = AnimatedCode(new_src)
    fresh.shift(code.origin_point.get_center() - fresh.origin_point.get_center())
    for t, m, f in zip(code.tokens, code.token_mobjects, fresh.token_mobjects, strict=True):
        assert np.allclose(m.get_center(), f.get_center(), atol=1e-6), t
    # unchanged lines didn't move at all
    for (line, col, text), p in old_pos.items():
        if line <= 6:
            i = next(
                k for k, t in enumerate(code.tokens) if (t.line, t.col, t.text) == (line, col, text)
            )
            assert np.allclose(code.token_mobjects[i].get_center(), p, atol=1e-9)


def test_insert_remove_replace():
    code = AnimatedCode("x = compute(a)\n")
    run(
        code,
        lambda c: c.replace(c.find("compute"), "evaluate"),
        lambda c: c.insert(*c.find(")").start, ", b"),
        lambda c: c.remove(c.find("x = ")),
    )
    assert code.source == "evaluate(a, b)\n"
    assert [t.text for t in code.tokens] == ["evaluate", "(", "a", ",", "b", ")"]
    assert len(code.submobjects) == len(code.tokens) + 2  # tokens + 2 anchors
    for t, m in zip(code.tokens, code.token_mobjects, strict=True):
        cell = code.grid_point(t.line, t.col)
        assert -0.05 <= m.get_left()[0] - cell[0] < 0.6 * code.cell_width


def test_highlight_survives_an_edit():
    code = AnimatedCode("a = 1\nb = 2\n")
    run(code, lambda c: c.highlight_lines(2), lambda c: c.replace(c.find("2"), "3"))
    first = code.get_line(1)
    assert first.family_members_with_points()[0].get_fill_opacity() == pytest.approx(0.25)


TEN_EDITS = [
    ("    n = len(a)\n", "    n = len(a)  # size\n"),
    ("range(n)", "range(n - 1)"),
    ("a[j] > a[j + 1]", "a[j + 1] < a[j]"),
    ("    return a\n", "    print(a)\n    return a\n"),
    ("def bubble_sort(a):", "def bubble_sort(items):"),
    ("    n = len(a)  # size\n", "    n = len(items)\n"),
    (
        "                a[j], a[j + 1] = a[j + 1], a[j]\n",
        "                swapped = True\n                a[j], a[j + 1] = a[j + 1], a[j]\n",
    ),
    ("    print(a)\n", ""),
    ("for i in", "for k in"),
    ("    return a\n", "    return items\n"),
]


def bubble_25():
    return BUBBLE + "".join(f"# note {i}: café π\n" for i in range(18))


@pytest.mark.parametrize("fps", [30, 60])
def test_bubble_sort_through_ten_edits_is_deterministic(fps):
    """Spec F05 accept: 25-line bubble sort, 10 edits, stable unchanged lines, 30/60 fps."""

    def render_once():
        code = AnimatedCode(bubble_25())
        frames = []

        class S(Scene):
            def construct(self):
                self.add(code)
                src = code.source
                for old, new in TEN_EDITS:
                    assert old in src, old
                    src = src.replace(old, new, 1)
                    before = positions(code)
                    edit = code.animate_to(src)
                    self.play(edit, run_time=0.2)
                    after = positions(code)
                    # tokens on lines whose text didn't change stay put
                    for key, p in before.items():
                        if key in after and edit.diff and key[0] > 7:
                            assert np.allclose(after[key], p, atol=1e-9)
                    frames.append(
                        np.concatenate([m.points for m in code.family_members_with_points()])
                    )
                self.play(code.highlight_lines(5, 6), run_time=0.2)

        with tempconfig({"frame_rate": fps, "dry_run": True, "disable_caching": True}):
            S().render()
        return code, frames

    code_a, frames_a = render_once()
    code_b, frames_b = render_once()
    assert len(code_a.source.splitlines()) == 26
    assert all(np.array_equal(x, y) for x, y in zip(frames_a, frames_b, strict=True))
