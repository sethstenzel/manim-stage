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
    AnimationGroup,
    MarkupText,
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

    ``AnimatedCode(source, language="python", style="monokai", font_size=24)``

    Submobjects: the tokens (``VGroup`` of glyphs each), in reading order, then two
    invisible anchor points (grid origin and one cell step) used to keep layout
    stable across edits.
    """

    def __init__(
        self,
        source: str,
        language: str = "python",
        *,
        style: str = "monokai",
        font: str = DEFAULT_FONT,
        font_size: float = 24,
        line_spacing: float = 1.5,
        tab_width: int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
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
        mobs: list[VGroup] = []
        for line_no in sorted(by_line):
            toks = by_line[line_no]
            markup = [_MARKER]
            last = 1
            for t in toks:
                markup.append(" " * (t.col - last))
                attrs = f'foreground="{t.color}"'
                if t.bold:
                    attrs += ' font_weight="bold"'
                if t.italic:
                    attrs += ' font_style="italic"'
                markup.append(f"<span {attrs}>{html.escape(t.text, quote=False)}</span>")
                last = t.end_col
            text = MarkupText("".join(markup), font=self.font, font_size=self.font_size)
            glyphs = list(text.submobjects)
            marker, glyphs = glyphs[0], glyphs[1:]
            # cell (line, col 1) top-left in grid space = (0, -(line-1) * line_height)
            shift = np.array(
                [
                    -marker.get_left()[0] - self.cell_width,  # the marker is column 0
                    -marker.get_center()[1] - (line_no - 1) * self.line_height,
                    0,
                ]
            )
            for g in glyphs:
                g.shift(shift)
            i = 0
            for t in toks:
                n = len(re.sub(r"\s", "", t.text))
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

    def __repr__(self) -> str:
        first = self.source.splitlines()[0] if self.source else ""
        return f"AnimatedCode({first[:30]!r}…, {len(self.tokens)} tokens)"


@lru_cache(maxsize=32)
def _cell_size(font: str, font_size: float) -> tuple[float, float]:
    """Advance width and height of one monospace cell at this size."""
    if font == DEFAULT_FONT:
        register_bundled_fonts()
    probe = MarkupText(_MARKER * 10, font=font, font_size=font_size)
    width = (probe.get_right()[0] - probe.get_left()[0]) / 10
    return width, probe.height


__all__ = ["AnimatedCode", "CodeRange", "Token", "register_bundled_fonts", "tokenize"]
