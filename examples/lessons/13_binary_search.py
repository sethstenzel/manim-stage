"""Lesson 13: Teaching an algorithm with the educational helpers.

Ideas from the classic algorithm-visualisation lessons that the Manim community makes
(arrays with index pointers) and from Motion Canvas's "do the work first, then
animate" approach. The search runs first as ordinary Python and records its steps in a
``Trace``. ``play_trace`` then turns each step into one ``self.play``, using an
``Array`` with three pointers.

    manim-stage studio 13_binary_search.py BinarySearch

Try in the Studio:
- Demo tab: change ``target`` (it can be a value that isn't in the array);
- each trace step is its own block on the timeline; sections become web chapters.
"""

from manim import DOWN, UP, Create, FadeIn, Text, Transform

from manim_stage import StageScene, demo, project
from manim_stage.edu import Array, Trace, play_trace

VALUES = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]


def binary_search(values, target):
    """Plain binary search that records what it does."""
    trace, lo, hi = Trace(), 0, len(values) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        trace.step("look", lo=lo, mid=mid, hi=hi, value=values[mid])
        if values[mid] == target:
            trace.step("found", mid=mid)
            return mid, trace
        if values[mid] < target:
            trace.step("go_right", lo=mid + 1, hi=hi, drop=list(range(lo, mid + 1)))
            lo = mid + 1
        else:
            trace.step("go_left", lo=lo, hi=mid - 1, drop=list(range(mid, hi + 1)))
            hi = mid - 1
    trace.step("missing")
    return -1, trace


class BinarySearch(StageScene):
    def construct(self):
        theme = project.theme()
        target = demo.param("target", 23, min=0, max=99, description="value to find")
        _, trace = binary_search(VALUES, target)

        title = Text(f"Binary search for {target}", font_size=40, color=theme.text)
        arr = Array(VALUES, cell_size=0.9, font_size=28).shift(UP * 0.3)
        lo = arr.pointer(0, "lo", color=theme.primary)
        hi = arr.pointer(len(VALUES) - 1, "hi", color=theme.primary)
        mid = arr.pointer(trace.events[0]["mid"], "mid", color=theme.accent, direction=UP)
        status = Text(" ", font_size=28).to_edge(DOWN)

        def say(text, color=theme.muted):
            return Transform(status, Text(text, font_size=28, color=color).to_edge(DOWN))

        self.next_section("Setup")
        self.play(FadeIn(title.to_edge(UP)), Create(arr))
        self.play(FadeIn(lo), FadeIn(hi), FadeIn(mid))

        self.next_section("Search")
        self.add(status)
        play_trace(
            self,
            trace,
            {
                "look": lambda e: [
                    mid.move_to_index(e["mid"]),
                    lo.move_to_index(e["lo"]),
                    hi.move_to_index(e["hi"]),
                    say(f"middle value is {e['value']}"),
                ],
                "go_right": lambda e: [
                    arr.highlight(e["drop"], theme.muted, 0.35),
                    say(f"{target} is bigger: drop the left half"),
                ],
                "go_left": lambda e: [
                    arr.highlight(e["drop"], theme.muted, 0.35),
                    say(f"{target} is smaller: drop the right half"),
                ],
                "found": lambda e: [
                    arr.highlight(e["mid"], theme.success, 0.7),
                    say(f"found {target} at index {e['mid']}", theme.success),
                ],
                "missing": lambda e: say(f"{target} is not in the array", theme.error),
            },
            run_time=0.7,
        )

        self.next_section("Result")
        steps = sum(1 for e in trace if e["kind"] == "look")
        note = Text(f"{steps} looks for {len(VALUES)} values: O(log n)", font_size=26)
        self.play(FadeIn(note.set_color(theme.accent).to_edge(DOWN, buff=1.1)))
        self.wait(0.5)
