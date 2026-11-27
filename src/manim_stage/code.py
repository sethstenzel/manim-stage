"""``AnimatedCode``: syntax-highlighted source as Manim mobjects, made for animation
(spec F05; ADR-0008, ADR-0013).

Motion Canvas's Code node (ranges, selections, token-diff edits) ported onto Manim:

- an ``AnimatedCode`` is a ``VGroup`` of **tokens**; each token is a ``VGroup`` of its
  glyphs, so any Manim animation works on code, a line, a word or a token;
- tokens come from **Pygments** (any language it knows; bold/italic from the style);
- glyphs come from Pango via ``MarkupText``, one call per line, in a **bundled
  monospace font** (JetBrains Mono, OFL) so layout is the same on every machine;
- every glyph sits on an explicit **character grid** (line, column), anchored by two
  invisible points, so after moving/scaling the code, a new version of the source
  lays out on the same grid; unchanged tokens can then stay exactly in place
  (backlog 2.6 ``animate_to``).

Lines and columns are **1-based**, as editors show them (``Ln 3, Col 5``).
``manim.Code`` is untouched and still available.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    Animation,
    AnimationGroup,
    MarkupText,
    Mobject,
    VectorizedPoint,
    VGroup,
    VMobject,
)

FONT_DIR = Path(__file__).resolve().parent / "fonts"
DEFAULT_FONT = "JetBrains Mono"
_MARKER = "█"  # fills its cell in a monospace font: column-0 and baseline reference


@lru_cache(maxsize=1)
def register_bundled_fonts() -> tuple[str, ...]:
    """Make the bundled JetBrains Mono available to Pango (once per process)."""
    import manimpango

    done = []
    for f in sorted(FONT_DIR.glob("*.ttf")):
        if manimpango.register_font(str(f)):
            done.append(f.name)
    return tuple(done)


# -- tokens ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    """One lexical token on one line (whitespace is not a token)."""

    line: int  # 1-based
    col: int  # 1-based, in characters after tab expansion
    text: str
    kind: str  # Pygments token type, e.g. "Token.Keyword"
    color: str
    bold: bool = False
    italic: bool = False

    @property
    def end_col(self) -> int:  # exclusive
        return self.col + len(self.text)


def tokenize(
    source: str, language: str = "python", style: str = "monokai", tab_width: int = 4
) -> list[Token]:
    """Pygments tokens with line/column positions and style colours."""
    from pygments.lexers import get_lexer_by_name
    from pygments.styles import get_style_by_name

    source = source.expandtabs(tab_width)
    lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False)
    sty = get_style_by_name(style)
    default = "#" + (sty.style_for_token(_token_root())["color"] or "f8f8f2")
    out: list[Token] = []
    line, col = 1, 1
    for ttype, value in lexer.get_tokens(source):
        s = sty.style_for_token(ttype)
        color = "#" + s["color"] if s["color"] else default
        for k, part in enumerate(value.split("\n")):
            if k:
                line, col = line + 1, 1
            for m in re.finditer(r"\S+(?: +\S+)*", part):
                out.append(
                    Token(
                        line,
                        col + m.start(),
                        m.group(),
                        str(ttype),
                        color,
                        bool(s["bold"]),
                        bool(s["italic"]),
                    )
                )
            col += len(part)
    return out


def _token_root() -> Any:
    from pygments.token import Token as PT

    return PT.Text


# -- ranges ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeRange:
    """Characters from ``start`` to ``end`` (exclusive), as (line, col), 1-based."""

    start: tuple[int, int]
    end: tuple[int, int]

    def contains(self, tok: Token) -> bool:
        a, b = (tok.line, tok.col), (tok.line, tok.end_col)
        return self.start <= a and b <= self.end

    def overlaps(self, tok: Token) -> bool:
        a, b = (tok.line, tok.col), (tok.line, tok.end_col)
        return a < self.end and self.start < b


# -- the mobject -------------------------------------------------------------------------


class AnimatedCode(VGroup):
    """Syntax-highlighted code whose tokens are individual mobjects.

    ``AnimatedCode(source, language="python", style=None, font_size=24)``: ``style`` and
    ``font`` default to the project theme (``code_style``/``code_font``), else Monokai
    and the bundled JetBrains Mono.

    Submobjects: the tokens (``VGroup`` of glyphs each), in reading order, then two
    invisible anchor points (grid origin and one cell step) used to keep layout
    stable across edits.
    """

    def __init__(
        self,
        source: str,
        language: str = "python",
        *,
        style: str | None = None,
        font: str | None = None,
        font_size: float = 24,
        line_spacing: float = 1.5,
        tab_width: int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if style is None or font is None:  # project theme, else the built-in defaults
            from . import project

            th = project.theme()
            style = style or th.code_style or "monokai"
            font = font or th.code_font or DEFAULT_FONT
        if font == DEFAULT_FONT:
            register_bundled_fonts()
        self.language, self.style, self.font = language, style, font
        self.font_size, self.line_spacing, self.tab_width = font_size, line_spacing, tab_width
        self.source = source.expandtabs(tab_width)
        self.tokens: list[Token] = tokenize(self.source, language, style, tab_width)
        self.cell_width, self.cell_height = _cell_size(font, font_size)
        self.line_height = self.cell_height * line_spacing
        self.token_mobjects: list[VGroup] = self._build()
        self.origin_point = VectorizedPoint(np.array([0.0, 0.0, 0.0]))
        self.step_point = VectorizedPoint(np.array([self.cell_width, -self.line_height, 0.0]))
        self.add(*self.token_mobjects, self.origin_point, self.step_point)
        self.center()

    # -- layout ---------------------------------------------------------------------------

    def _build(self) -> list[VGroup]:
        by_line: dict[int, list[Token]] = {}
        for t in self.tokens:
            by_line.setdefault(t.line, []).append(t)
        line_nos = sorted(by_line)
        markups = []
        for line_no in line_nos:
            markup = [_MARKER]
            last = 1
            for t in by_line[line_no]:
                markup.append(" " * (t.col - last))
                attrs = f'foreground="{t.color}"'
                if t.bold:
                    attrs += ' font_weight="bold"'
                if t.italic:
                    attrs += ' font_style="italic"'
                markup.append(f"<span {attrs}>{html.escape(t.text, quote=False)}</span>")
                last = t.end_col
            counts = tuple(len(re.sub(r"\s", "", t.text)) for t in by_line[line_no])
            markups.append(("".join(markup), counts))
        layouts = _layout_lines(markups, self.font, self.font_size, self.cell_width)
        mobs: list[VGroup] = []
        for line_no, layout in zip(line_nos, layouts, strict=True):
            line_y = (line_no - 1) * self.line_height
            glyphs = [
                _glyph(points, fill, stroke, width, line_y)
                for points, fill, stroke, width in layout
            ]
            i = 0
            for n in (len(re.sub(r"\s", "", t.text)) for t in by_line[line_no]):
                mobs.append(VGroup(*glyphs[i : i + n]))
                i += n
        return mobs

    def grid_point(self, line: float, col: float) -> np.ndarray:
        """Scene point of the top-left of cell (line, col), following moves/scales."""
        o = self.origin_point.get_center()
        step = self.step_point.get_center() - o
        return o + np.array([step[0] * (col - 1), step[1] * (line - 1), 0.0])

    # -- tokens and ranges -----------------------------------------------------------------

    def token_index(self, line: int, col: int) -> int | None:
        for i, t in enumerate(self.tokens):
            if t.line == line and t.col <= col < t.end_col:
                return i
        return None

    def lines(self, first: int, last: int | None = None) -> CodeRange:
        """Lines ``first``..``last`` (inclusive, 1-based)."""
        last = first if last is None else last
        return CodeRange((first, 1), (last, 10**9))

    def word(self, line: int, col: int, length: int) -> CodeRange:
        return CodeRange((line, col), (line, col + length))

    def find_all(self, text: str) -> list[CodeRange]:
        """Every occurrence of ``text`` in the source (may span lines)."""
        out = []
        for m in re.finditer(re.escape(text), self.source):
            out.append(CodeRange(self._pos(m.start()), self._pos(m.end())))
        return out

    def find(self, text: str, nth: int = 0) -> CodeRange:
        found = self.find_all(text)
        if len(found) <= nth:
            raise ValueError(f"{text!r} occurs {len(found)} time(s) in the code")
        return found[nth]

    def _pos(self, offset: int) -> tuple[int, int]:
        before = self.source[:offset]
        line = before.count("\n") + 1
        return line, offset - (before.rfind("\n") + 1) + 1

    def tokens_in(self, rng: CodeRange | Iterable[CodeRange]) -> list[int]:
        ranges = [rng] if isinstance(rng, CodeRange) else list(rng)
        return [i for i, t in enumerate(self.tokens) if any(r.overlaps(t) for r in ranges)]

    def get(self, rng: CodeRange | Iterable[CodeRange]) -> VGroup:
        """The glyphs of a range, as a ``VGroup`` (for any Manim animation)."""
        return VGroup(*(self.token_mobjects[i] for i in self.tokens_in(rng)))

    def get_line(self, line: int) -> VGroup:
        return self.get(self.lines(line))

    # -- highlighting (Motion Canvas "selection") ----------------------------------------

    def highlight(
        self, rng: CodeRange | Sequence[CodeRange], *, dim_opacity: float = 0.25, **anim_kwargs: Any
    ) -> AnimationGroup:
        """Animation that dims every token outside ``rng`` (and restores those inside)."""
        keep = set(self.tokens_in(rng))
        anims = [
            m.animate.set_opacity(1.0 if i in keep else dim_opacity)
            for i, m in enumerate(self.token_mobjects)
        ]
        return AnimationGroup(*anims, **anim_kwargs)

    def highlight_lines(
        self, *line_numbers: int, dim_opacity: float = 0.25, **anim_kwargs: Any
    ) -> AnimationGroup:
        return self.highlight(
            [self.lines(n) for n in line_numbers], dim_opacity=dim_opacity, **anim_kwargs
        )

    def reset_highlight(self, **anim_kwargs: Any) -> AnimationGroup:
        return AnimationGroup(
            *(m.animate.set_opacity(1.0) for m in self.token_mobjects), **anim_kwargs
        )

    def surround(self, rng: CodeRange, buff: float = 0.06, **kwargs: Any) -> VMobject:
        """A ``SurroundingRectangle`` around a range (Motion Canvas selection box)."""
        from manim import SurroundingRectangle

        return SurroundingRectangle(self.get(rng), buff=buff, **kwargs)

    # -- edits (backlog 2.6) ----------------------------------------------------------------

    def _like(self, source: str) -> AnimatedCode:
        """A new AnimatedCode for ``source`` laid out on this code's current grid."""
        new = AnimatedCode(
            source,
            self.language,
            style=self.style,
            font=self.font,
            font_size=self.font_size,
            line_spacing=self.line_spacing,
            tab_width=self.tab_width,
        )
        # map the new grid onto ours: uniform scale from the step points, then translate
        scale = np.linalg.norm(self.step_point.get_center() - self.origin_point.get_center()) / (
            np.linalg.norm(new.step_point.get_center() - new.origin_point.get_center())
        )
        new.scale(scale, about_point=new.origin_point.get_center())
        new.shift(self.origin_point.get_center() - new.origin_point.get_center())
        return new

    def animate_to(
        self,
        source: str,
        *,
        mapping: dict[int, int | None] | None = None,
        lag_ratio: float = 0.0,
        **kwargs: Any,
    ) -> CodeEdit:
        """Animation from this code to ``source``: kept tokens slide, others fade.

        ``mapping`` pins old→new token indices (``None`` = fade out) where repeated
        tokens make the automatic match ambiguous; see :mod:`manim_stage.code_diff`.
        """
        return CodeEdit(self, source, mapping=mapping, lag_ratio=lag_ratio, **kwargs)

    def _offset(self, line: int, col: int) -> int:
        lines = self.source.split("\n")
        if not 1 <= line <= len(lines):
            raise IndexError(f"line {line} is outside the code (1..{len(lines)})")
        return sum(len(x) + 1 for x in lines[: line - 1]) + (col - 1)

    def _token_offsets(self) -> list[int]:
        return [self._offset(t.line, t.col) for t in self.tokens]

    def replace(self, rng: CodeRange, text: str, **kwargs: Any) -> CodeEdit:
        """Replace the characters in ``rng`` with ``text`` (Motion Canvas ``replace``).

        Tokens outside the range are pinned to themselves, so nothing else re-matches.
        """
        a = self._offset(*rng.start)
        end_line = min(rng.end[0], len(self.source.split("\n")))
        end_col = (
            rng.end[1] if rng.end[1] < 10**9 else len(self.source.split("\n")[end_line - 1]) + 1
        )
        b = self._offset(end_line, end_col)
        new_source = self.source[:a] + text.expandtabs(self.tab_width) + self.source[b:]
        delta = len(text.expandtabs(self.tab_width)) - (b - a)
        new_tokens = tokenize(new_source, self.language, self.style, self.tab_width)
        new_lines = new_source.split("\n")
        new_off = {
            sum(len(x) + 1 for x in new_lines[: t.line - 1]) + t.col - 1: k
            for k, t in enumerate(new_tokens)
        }
        mapping: dict[int, int | None] = {}
        for i, (t, off) in enumerate(zip(self.tokens, self._token_offsets(), strict=True)):
            if off + len(t.text) <= a:
                k = new_off.get(off)
            elif off >= b:
                k = new_off.get(off + delta)
            else:
                continue
            if k is not None and new_tokens[k].text == t.text:
                mapping[i] = k
        return CodeEdit(self, new_source, mapping=mapping, **kwargs)

    def insert(self, line: int, col: int, text: str, **kwargs: Any) -> CodeEdit:
        """Insert ``text`` before (line, col)."""
        return self.replace(CodeRange((line, col), (line, col)), text, **kwargs)

    def remove(self, rng: CodeRange, **kwargs: Any) -> CodeEdit:
        return self.replace(rng, "", **kwargs)

    def __repr__(self) -> str:
        first = self.source.splitlines()[0] if self.source else ""
        return f"AnimatedCode({first[:30]!r}…, {len(self.tokens)} tokens)"


# Glyph outlines + colours per laid-out line, in grid space (column 1 at x=0, the line's
# baseline-centre at y=0), as plain arrays. Keyed by (markup, font, size).
_LINE_CACHE: dict[tuple[str, str, float], tuple[tuple[Any, Any, Any, float], ...]] = {}
_NO_LIGATURES = '<span font_features="liga=0, clig=0, dlig=0, calt=0">'


def _layout_lines(
    lines: list[tuple[str, tuple[int, ...]]], font: str, font_size: float, cell_width: float
) -> list[tuple[tuple[Any, Any, Any, float], ...]]:
    """Lay out code lines, reusing cached lines and sending all the others to Pango in
    **one** call (a Pango call has a large fixed cost, about 3 s cold on Windows).

    Each line starts with a full-block marker glyph that pins its column 0 and baseline.
    Ligatures are off, so every non-space character is exactly one glyph.
    """
    keys = [(markup, font, float(font_size)) for markup, _ in lines]
    missing = [k for k in dict.fromkeys(keys) if k not in _LINE_CACHE]
    if missing:
        counts = {k: c for k, (_, c) in zip(keys, lines, strict=True)}
        body = "\n".join(k[0] for k in missing)
        text = MarkupText(
            _NO_LIGATURES + body + "</span>",
            font=font,
            font_size=font_size,
            warn_missing_font=False,
        )
        glyphs = list(text.submobjects)
        expected = sum(1 + sum(counts[k]) for k in missing)
        if len(glyphs) != expected:
            raise RuntimeError(
                f"AnimatedCode: Pango produced {len(glyphs)} glyphs for {expected} characters; "
                "the font may be substituting characters it lacks"
            )
        pos = 0
        for k in missing:
            n = sum(counts[k])
            marker, line = glyphs[pos], glyphs[pos + 1 : pos + 1 + n]
            pos += 1 + n
            shift = np.array([-marker.get_left()[0] - cell_width, -marker.get_center()[1], 0.0])
            _LINE_CACHE[k] = tuple(
                (
                    g.points + shift,
                    g.fill_rgbas.copy(),
                    g.stroke_rgbas.copy(),
                    float(g.stroke_width),
                )
                for g in line
            )
        if len(_LINE_CACHE) > 20000:  # bound memory in very long sessions
            for old in list(_LINE_CACHE)[:5000]:
                _LINE_CACHE.pop(old, None)
    return [_LINE_CACHE[k] for k in keys]


def _glyph(points: Any, fill: Any, stroke: Any, width: float, line_y: float) -> VMobject:
    g = VMobject(stroke_width=width)
    g.points = points - np.array([0.0, line_y, 0.0])
    g.fill_rgbas = fill.copy()
    g.stroke_rgbas = stroke.copy()
    return g


@lru_cache(maxsize=32)
def _cell_size(font: str, font_size: float) -> tuple[float, float]:
    """Advance width and height of one monospace cell at this size."""
    if font == DEFAULT_FONT:
        register_bundled_fonts()
    probe = MarkupText(_MARKER * 10, font=font, font_size=font_size, warn_missing_font=False)
    width = (probe.get_right()[0] - probe.get_left()[0]) / 10
    return width, probe.height


__all__ = ["AnimatedCode", "CodeRange", "Token", "register_bundled_fonts", "tokenize"]


class CodeEdit(Animation):
    """Animate an :class:`AnimatedCode` to a new source (Motion Canvas code edits).

    Matched tokens slide (and recolour) to their new grid place, removed tokens fade
    out, new tokens fade in. When it finishes, the ``AnimatedCode`` *is* the new code:
    its ``source``, ``tokens`` and ``token_mobjects`` describe the new version, so the
    next ``highlight``/``find``/``animate_to`` works on it.

    ``lag_ratio`` staggers tokens in reading order of the new code (0 = all at once).
    ``diff`` (after construction) tells what matched, moved, faded and any ambiguity
    warnings.
    """

    def __init__(
        self,
        code: AnimatedCode,
        source: str,
        *,
        mapping: dict[int, int | None] | None = None,
        lag_ratio: float = 0.0,
        **kwargs: Any,
    ) -> None:
        from .code_diff import diff_tokens

        self.code = code
        self.target = code._like(source)
        self.diff = diff_tokens(code.tokens, self.target.tokens, mapping=mapping)
        self._lag = lag_ratio
        super().__init__(code, **kwargs)

    def create_starting_mobject(self) -> Mobject:
        return Mobject()  # unused: we keep raw arrays, not a deep copy of the whole code

    def begin(self) -> None:
        code, tgt, d = self.code, self.target, self.diff
        n_new = max(len(tgt.tokens), 1)
        n_old = max(len(code.tokens), 1)
        # Per glyph: (glyph, points0, points1, fill0, fill1, stroke0, stroke1), no copies
        self._moves: list[tuple[float, list[tuple]]] = []
        for o, n in d.matches:
            src = code.token_mobjects[o].family_members_with_points()
            dst = tgt.token_mobjects[n].family_members_with_points()
            keep = src[0].fill_rgbas[0, 3] if src else 1.0  # keep the highlight/dim level
            rows = []
            for g0, g1 in zip(src, dst, strict=False):
                f1, s1 = g1.fill_rgbas.copy(), g1.stroke_rgbas.copy()
                f1[:, 3] *= keep
                s1[:, 3] *= keep
                rows.append(
                    (
                        g0,
                        g0.points.copy(),
                        g1.points.copy(),
                        g0.fill_rgbas.copy(),
                        f1,
                        g0.stroke_rgbas.copy(),
                        s1,
                    )
                )
            self._moves.append((n / n_new, rows))
        self._fade_out = [
            (code.tokens[o].line / n_old, _alpha_rows(code.token_mobjects[o])) for o in d.deleted
        ]
        self._fade_in = []
        for n in d.inserted:
            mob = tgt.token_mobjects[n]
            self._fade_in.append((n / n_new, mob, _alpha_rows(mob)))
        # new tokens join the group now (drawn as part of it, never added to the scene
        # separately); faded tokens leave it when the edit finishes
        code.add(*(m for _, m, _ in self._fade_in))
        super().begin()

    def _local(self, alpha: float, key: float) -> float:
        if not self._lag:
            return alpha
        span = 1.0 / (1.0 + self._lag)
        start = key * self._lag * span
        return float(np.clip((alpha - start) / span, 0.0, 1.0))

    def interpolate_mobject(self, alpha: float) -> None:
        for key, rows in self._moves:
            a = self._local(alpha, key)
            for g, p0, p1, f0, f1, s0, s1 in rows:
                if len(p0) == len(p1):
                    g.points = p0 + (p1 - p0) * a
                elif a >= 1:
                    g.points = p1.copy()
                if f0.shape == f1.shape:
                    g.fill_rgbas = f0 + (f1 - f0) * a
                if s0.shape == s1.shape:
                    g.stroke_rgbas = s0 + (s1 - s0) * a
        for key, rows in self._fade_out:
            a = self._local(alpha, key)
            for g, fa, sa in rows:
                g.fill_rgbas[:, 3] = fa * (1.0 - a)
                g.stroke_rgbas[:, 3] = sa * (1.0 - a)
        for key, _mob, rows in self._fade_in:
            a = self._local(alpha, key)
            for g, fa, sa in rows:
                g.fill_rgbas[:, 3] = fa * a
                g.stroke_rgbas[:, 3] = sa * a

    def finish(self) -> None:
        super().finish()
        code, tgt, d = self.code, self.target, self.diff
        old_for_new = {n: code.token_mobjects[o] for o, n in d.matches}
        fade_in = {n: m for n, (_, m, _) in zip(d.inserted, self._fade_in, strict=True)}
        new_mobs = [old_for_new.get(n) or fade_in[n] for n in range(len(tgt.tokens))]
        code.submobjects = [*new_mobs, code.origin_point, code.step_point]
        code.token_mobjects = new_mobs
        code.tokens = tgt.tokens
        code.source = tgt.source


def _alpha_rows(mob: VGroup) -> list[tuple[Any, Any, Any]]:
    """(glyph, fill alphas, stroke alphas) of a token, for fading without copies."""
    return [
        (g, g.fill_rgbas[:, 3].copy(), g.stroke_rgbas[:, 3].copy())
        for g in mob.family_members_with_points()
    ]
