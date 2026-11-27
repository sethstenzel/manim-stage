"""Breadth-first search on a small graph (third-party-style example, M4 gate).

Written as a user would: plain Manim (``Graph``) plus public manim-stage APIs only.

- ``Trace``: BFS runs first (a trusted, ordinary Python function) and records its steps;
  ``play_trace`` replays them. Nothing runs live in the viewer.
- ``tree_layout`` lays out the BFS tree; ``label_edges`` shows edge weights that follow
  vertices as they move.
- ``Array`` shows the queue; ``StageScene.cue`` names the moments a narrator would hit.
- Sections become chapters in the web player (``manim-stage web bfs.py BFS``).

    manim-stage studio bfs.py BFS
"""

from collections import deque

from manim import DOWN, LEFT, RIGHT, UP, Create, FadeIn, Graph, Text, Write

from manim_stage import StageScene
from manim_stage.edu import Array, Trace, label_edges, play_trace, tree_layout

EDGES = [("A", "B"), ("A", "C"), ("B", "D"), ("B", "E"), ("C", "F"), ("E", "F")]
WEIGHTS = {("A", "B"): 2, ("A", "C"): 5, ("B", "D"): 1, ("B", "E"): 3, ("C", "F"): 2, ("E", "F"): 4}
VISITED, FRONTIER = "#83C167", "#FFC857"


def bfs(edges, start):
    """Plain BFS that records what it does."""
    adj = {}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    trace, seen, queue, parent = Trace(), {start}, deque([start]), {}
    trace.step("enqueue", node=start, queue=list(queue))
    while queue:
        node = queue.popleft()
        trace.step("visit", node=node, queue=list(queue))
        for nxt in sorted(adj[node]):
            if nxt not in seen:
                seen.add(nxt)
                parent[nxt] = node
                queue.append(nxt)
                trace.step("enqueue", node=nxt, parent=node, queue=list(queue))
    return parent, trace


class BFS(StageScene):
    def construct(self):
        parent, trace = bfs(EDGES, "A")
        children = {}
        for child, par in parent.items():
            children.setdefault(par, []).append(child)
        layout = tree_layout(children, "A", h_gap=1.6, v_gap=1.3)

        title = Text("Breadth-first search", font_size=40).to_edge(UP)
        graph = Graph(
            list(layout), EDGES, layout=layout, labels=False, vertex_config={"radius": 0.28}
        ).shift(LEFT * 2.2 + UP * 0.3)
        names = {v: Text(v, font_size=24, color="#0F1720").move_to(graph[v]) for v in layout}
        for v, label in names.items():
            label.add_updater(lambda m, v=v: m.move_to(graph[v]))
        weights = label_edges(graph, WEIGHTS, font_size=20)

        self.next_section("The graph")
        self.play(Write(title))
        self.play(Create(graph), *[FadeIn(n) for n in names.values()])
        self.play(FadeIn(weights))

        self.next_section("Search")
        self.cue("search_starts")
        queue_title = Text("queue", font_size=24).to_corner(RIGHT + UP).shift(DOWN * 1.2 + LEFT)
        queue = Array([" "] * 6, cell_size=0.55, font_size=24, show_indices=False)
        queue.next_to(queue_title, DOWN).to_edge(RIGHT)
        self.play(FadeIn(queue_title), Create(queue))

        def show_queue(e):
            values = list(e["queue"]) + [" "] * (6 - len(e["queue"]))
            return [queue.set_value(i, v) for i, v in enumerate(values[:6])]

        play_trace(
            self,
            trace,
            {
                "enqueue": lambda e: [graph[e["node"]].animate.set_color(FRONTIER), *show_queue(e)],
                "visit": lambda e: [graph[e["node"]].animate.set_color(VISITED), *show_queue(e)],
            },
            run_time=0.45,
        )

        self.next_section("Result")
        self.cue("all_visited")
        order = [e["node"] for e in trace if e["kind"] == "visit"]
        result = Text("visit order: " + " → ".join(order), font_size=28).to_edge(DOWN)
        self.play(Write(result))
        self.play(graph["F"].animate.shift(RIGHT * 0.6))  # weights follow the edges
        self.wait(0.5)
