"""manim-stage educational helpers: one scene per helper.

manim-stage studio gallery.py Recursion
"""

from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, Graph, Scene, Text, Write

from manim_stage import demo
from manim_stage.edu import (
    Array,
    CallStack,
    LinkedList,
    SequenceDiagram,
    Trace,
    Tree,
    label_edges,
    play_trace,
    trace_calls,
    tree_layout,
)


def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


class Recursion(Scene):
    """A call stack driven by a recorded trace of fib(3)."""

    def construct(self):
        result, trace = trace_calls(fib, 3)
        title = Text(f"fib(3) = {result}", font_size=36).to_edge(UP)
        stack = CallStack().to_edge(DOWN, buff=0.8)
        self.play(Write(title), FadeIn(stack))
        play_trace(self, trace, stack.trace_handlers(), run_time=0.35)
        self.wait(0.5)


class BubblePass(Scene):
    """One bubble-sort pass, recorded as algorithm steps and replayed.

    ``size`` is a demo parameter: drag it in the Studio's Demo tab; exports use 5.
    """

    def construct(self):
        size = demo.param("size", 5, min=3, max=9, description="array length")
        values = [(7 * k + 3) % 10 for k in range(size)]
        data = list(values)
        steps = Trace()
        for j in range(len(data) - 1):
            steps.step("compare", i=j, j=j + 1)
            if data[j] > data[j + 1]:
                data[j], data[j + 1] = data[j + 1], data[j]
                steps.step("swap", i=j, j=j + 1)

        arr = Array(values)
        ptr = arr.pointer(0, "j")
        self.next_section("Setup")  # sections become chapters in the web player
        self.play(Create(arr), FadeIn(ptr))

        def compare(e):
            anims = [ptr.move_to_index(e["i"]), arr.highlight([e["i"], e["j"]], opacity=0.4)]
            if e["i"] > 0:  # un-highlight the cell the pair just left
                anims.append(arr.highlight(e["i"] - 1, opacity=0))
            return anims

        self.next_section("Compare and swap")
        play_trace(
            self,
            steps,
            {"compare": compare, "swap": lambda e: arr.swap(e["i"], e["j"])},
            run_time=0.4,
        )
        self.next_section("Largest value in place")
        self.play(arr.highlight(size - 2, opacity=0), arr.highlight(size - 1, "#83C167"))
        self.wait(0.5)


class Structures(Scene):
    """A heap as a tree, a linked list, and a weighted graph using tree_layout."""

    def construct(self):
        heap = Tree.from_heap([9, 7, 8, 3, 5, 6], h_gap=0.8, v_gap=1.0).to_edge(LEFT).shift(UP)
        lst = LinkedList([1, 2]).to_edge(LEFT).shift(DOWN * 2.5)
        g = (
            Graph(
                ["A", "B", "C", "D"],
                [("A", "B"), ("A", "C"), ("C", "D")],
                layout=tree_layout({"A": ["B", "C"], "C": ["D"]}, "A", h_gap=2.2, v_gap=1.5),
            )
            .to_edge(RIGHT, buff=1.5)
            .shift(UP * 0.5)
        )
        weights = label_edges(g, {("A", "B"): 4, ("A", "C"): 1, ("C", "D"): 2})
        self.play(Create(heap), Create(g), FadeIn(lst))
        self.play(FadeIn(weights), heap.highlight(0), lst.append(3))
        self.play(g["D"].animate.shift(LEFT * 1.2))  # labels follow the edge
        self.wait(0.5)


class Protocol(Scene):
    """A protocol sequence diagram."""

    def construct(self):
        sd = SequenceDiagram(["browser", "server", "database"], spacing=3.6)
        self.play(FadeIn(sd))
        self.play(sd.message("browser", "server", "GET /users"))
        self.play(sd.message("server", "database", "SELECT *"))
        self.play(sd.message("database", "server", "rows", reply=True))
        self.play(sd.message("server", "server", "render"))
        self.play(sd.message("server", "browser", "200 OK", reply=True))
        self.wait(0.5)
