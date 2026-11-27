"""Narrated bubble sort: the M2 end-to-end demo (spec §11 M2 gate).

Plain Manim plus three manim-stage features:

- ``self.narration(...)`` plays the recorded narration and shows it as subcaptions;
- ``self.cue(...)`` waits for named moments in that narration. The times live in
  ``.manim-stage/cues.json`` and are dragged on the Studio timeline, not typed as
  ``wait()`` calls;
- ``AnimatedCode`` shows the algorithm, highlights the running line, and animates an
  edit (the early-exit optimisation).

Render:   manim render lesson.py BubbleSortLesson -ql
Studio:   manim-stage studio lesson.py BubbleSortLesson
Audio:    record narration.wav yourself, or run make_audio.py for a placeholder.
"""

from manim import (
    BLUE,
    DOWN,
    GREEN,
    LEFT,
    RIGHT,
    UP,
    YELLOW,
    Create,
    FadeIn,
    Indicate,
    Rectangle,
    Text,
    VGroup,
    Write,
)

from manim_stage import AnimatedCode, StageScene

VALUES = [5, 2, 4, 1]
CODE = """def bubble_sort(a):
    n = len(a)
    for i in range(n):
        for j in range(n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
    return a
"""
OPTIMISED = """def bubble_sort(a):
    n = len(a)
    for i in range(n):
        swapped = False
        for j in range(n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        if not swapped:
            break
    return a
"""
SCRIPT = (
    "Bubble sort walks the array again and again. "
    "It compares neighbours, and swaps them when they are out of order. "
    "After the first pass, the largest value has bubbled to the end. "
    "We can stop early when a pass makes no swaps."
)


def bars_for(values):
    bars = VGroup(
        *[
            Rectangle(width=0.6, height=0.5 * v, fill_opacity=0.85, color=BLUE, stroke_width=2)
            for v in values
        ]
    )
    bars.arrange(RIGHT, aligned_edge=DOWN, buff=0.25)
    return bars


class BubbleSortLesson(StageScene):
    def construct(self):
        title = Text("Bubble sort", font_size=40).to_edge(UP)
        code = AnimatedCode(CODE, font_size=20).to_edge(LEFT, buff=0.5).shift(DOWN * 0.3)
        bars = bars_for(VALUES).to_edge(RIGHT, buff=1.0).shift(DOWN * 0.5)
        values = list(VALUES)

        with self.narration("voice", file="narration.wav", text=SCRIPT, wait=False) as voice:
            self.play(Write(title), FadeIn(code), run_time=1.5)

        self.cue("show_array", at=3.0, description="'walks the array'")
        self.play(Create(bars), run_time=1.0)

        self.cue("compare", at=6.0, description="'compares neighbours'")
        self.play(code.highlight_lines(5), run_time=0.5)
        self.play(Indicate(bars[0]), Indicate(bars[1]), run_time=0.8)

        self.cue("swap", at=9.0, description="'swaps them'")
        self.play(code.highlight_lines(6), run_time=0.4)
        for j in range(len(values) - 1):  # first pass
            if values[j] > values[j + 1]:
                values[j], values[j + 1] = values[j + 1], values[j]
                left, right = bars[j], bars[j + 1]
                self.play(
                    left.animate.move_to([right.get_x(), left.get_y(), 0]),
                    right.animate.move_to([left.get_x(), right.get_y(), 0]),
                    run_time=0.6,
                )
                bars.submobjects[j], bars.submobjects[j + 1] = right, left

        self.cue("largest_done", at=15.0, description="'bubbled to the end'")
        self.play(bars[-1].animate.set_color(GREEN), code.reset_highlight(), run_time=0.8)

        self.cue("optimise", at=20.0, description="'stop early'")
        self.play(code.animate_to(OPTIMISED), run_time=1.5)
        self.play(code.highlight_lines(4, 8, 9, 10), run_time=0.6)
        self.play(*(b.animate.set_color(YELLOW) for b in bars[:-1]), run_time=0.6)

        voice.wait_for_end()  # hold the last frame until the narration has finished
