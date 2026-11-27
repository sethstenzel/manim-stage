# AnimatedCode

- **Status:** Partial: layout, tokens, ranges, highlighting and selection boxes are Available. Animated edits between code versions (`animate_to`, insert/remove/replace) are Planned (backlog 2.6).
- **Renderer:** Cairo (OpenGL untested)
- **Since:** PR #23
- **Spec:** F05 · **Backlog:** 2.5 · **ADRs:** ADR-0008, ADR-0013 · **Source:** `src/manim_stage/code.py`
- **Motion Canvas origin:** the `Code` node, with `lines()`, `word()`, `findFirstRange()`/`findAllRanges()` and selections that dim everything else. **Built on:** Manim `VGroup`/`MarkupText` (Pango), Pygments, and a bundled JetBrains Mono font.

![AnimatedCode: bubble sort with lines 5–6 highlighted and a selection box around the swap](../img/animated-code.png)

## What it is

`AnimatedCode` shows source code as Manim mobjects, built for teaching:
- every **token** (keyword, name, operator…) is its own `VGroup` of glyphs, so any Manim animation works on a line, a word or a single token;
- you can address code the way you talk about it: "line 5", "the word `swap`", "every `range`".

`manim.Code` is unchanged and still available. Use `AnimatedCode` when the code itself is animated.

## Quick start

```python
from manim import *
from manim_stage import AnimatedCode

SRC = '''def bubble_sort(a):
    n = len(a)
    for i in range(n):
        for j in range(n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]  # swap
    return a
'''

class Walkthrough(Scene):
    def construct(self):
        code = AnimatedCode(SRC, language="python", style="monokai", font_size=24)
        self.play(FadeIn(code))
        self.play(code.highlight_lines(5, 6))                     # dim everything else
        box = code.surround(code.find("a[j + 1], a[j]"), color=YELLOW)
        self.play(Create(box))
        self.play(Indicate(code.get(code.find("swap"))))          # any Manim animation
        self.play(code.reset_highlight(), FadeOut(box))

with tempconfig({"frame_rate": 10, "dry_run": True}):
    Walkthrough().render()
```

## How it works

**Tokens:**
- Pygments lexes the source in any language it knows: Python, JavaScript/TypeScript, Rust, C/C++, Go, Bash, SQL and hundreds more.
- Each token keeps its line, column, text, Pygments type, and the style's colour, bold and italic (`style=` is any Pygments style).
- Whitespace is layout, not a token. Tabs are expanded (`tab_width=4`).

**Glyphs:**
- Each line is one Pango call (`MarkupText` with coloured spans), so it's fast.
- Every glyph is placed on an explicit **character grid** (line, column). A full-block marker glyph gives each line the exact position of column 0 and its baseline; the marker is then removed.
- The default font is **JetBrains Mono** (OFL, bundled), so code lays out the same on Windows, Linux and macOS. Use `font=` to pick another monospace font.

**Grid anchors:**
- Two invisible points in the group track the grid's origin and one cell step, so `code.grid_point(line, col)` stays correct after you `shift`, `scale` or `rotate` the code.
- This is what lets an edited version lay out on the same grid, so unchanged code doesn't jump (2.6).

**Coordinates are 1-based**, as editors show them (Ln 3, Col 5).

## API

| Call | Returns | Motion Canvas analogue |
|---|---|---|
| `AnimatedCode(source, language="python", *, style="monokai", font=…, font_size=24, line_spacing=1.5, tab_width=4)` | the mobject | `<Code code={…}/>` |
| `code.lines(first, last=None)` | `CodeRange` of whole lines | `lines(from, to)` |
| `code.word(line, col, length)` | `CodeRange` | `word(line, col, length)` |
| `code.find(text, nth=0)` / `code.find_all(text)` | `CodeRange` / list | `findFirstRange` / `findAllRanges` |
| `code.get(range_or_ranges)` | `VGroup` of the glyphs (use with any animation) | — |
| `code.get_line(n)` | `VGroup` | — |
| `code.highlight(ranges, dim_opacity=0.25)` / `code.highlight_lines(*n)` | animation dimming everything else | `selection(...)` |
| `code.reset_highlight()` | animation | `selection(DEFAULT)` |
| `code.surround(range, buff=0.06, **kw)` | `SurroundingRectangle` | selection box |
| `code.tokens`, `code.token_mobjects` | parallel lists | — |
| `code.grid_point(line, col)` | scene point of a cell's top-left | — |

## Limitations and unsupported cases

- **Animated edits** (`animate_to(new_source)`, insert/remove/replace with stable token identities) are backlog 2.6.
- **Fonts:** a non-monospace `font=` breaks the grid; use a monospace font.
- **Unicode:** characters that Pango renders as several glyphs (rare combining sequences) can upset the token-to-glyph split. Common accented letters and Greek work.
- **No background panel or line numbers yet.** Add a `SurroundingRectangle` behind the code if you need one.

## Related

- [Timeline](timeline.md), [Named cues](cues.md), [Motion Canvas equivalents](../reference/motion-canvas-equivalents.md).
