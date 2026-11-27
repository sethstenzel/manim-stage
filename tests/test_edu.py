"""Educational helpers (backlog 4.2, spec F12)."""

import numpy as np
import pytest
from manim import Create, FadeIn, Graph, Scene, tempconfig

from manim_stage.capture import capture
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

LOW = {"frame_rate": 15, "pixel_width": 320, "pixel_height": 180}


def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


def test_array_swap_moves_labels_and_model():
    arr = Array([5, 2, 4])
    first = arr.labels[0]
    anim = arr.swap(0, 2)
    assert arr.values == [4, 2, 5] and arr.labels[2] is first
    with tempconfig(LOW):
        anim.begin()
        anim.interpolate(1)
        anim.finish()
    assert np.allclose(first.get_center(), arr.boxes[2].get_center(), atol=1e-6)


def test_array_pointer_moves_between_cells():
    arr = Array([1, 2, 3, 4])
    p = arr.pointer(0, "i")
    x0 = p.arrow.get_end()[0]
    assert np.isclose(x0, arr.boxes[0].get_center()[0])
    p.move_to_index(3)  # builds an animation; apply it directly
    p.shift(p._anchor(3) - p.arrow.get_end())
    assert np.isclose(p.arrow.get_end()[0], arr.boxes[3].get_center()[0])
    assert p.arrow.get_end()[1] < arr.indices[3].get_bottom()[1]  # clear of index labels


def test_tree_layout_is_tidy_and_rejects_cycles():
    pos = tree_layout({"r": ["a", "b"], "a": ["c", "d"]}, "r")
    assert pos["r"][1] == 0 and pos["c"][1] == pytest.approx(-2.4)
    assert pos["a"][0] == pytest.approx((pos["c"][0] + pos["d"][0]) / 2)
    assert pos["c"][0] < pos["d"][0] < pos["b"][0]
    assert sum(p[0] for k, p in pos.items() if k in "cdb") == pytest.approx(0)  # centred
    with pytest.raises(ValueError, match="twice"):
        tree_layout({"r": ["a", "b"], "a": ["b"]}, "r")


def test_tree_from_heap_and_manim_graph_layout():
    t = Tree.from_heap([9, 7, 5, 3])
    assert set(t.nodes) == {0, 1, 2, 3} and set(t.edges) == {(0, 1), (0, 2), (1, 3)}
    g = Graph([1, 2, 3], [(1, 2), (1, 3)], layout=tree_layout({1: [2, 3]}, 1))
    labels = label_edges(g, {(1, 2): 4, (3, 1): "7"})  # either edge direction
    assert len(labels) == 2
    mid = (g.edges[(1, 2)].get_start() + g.edges[(1, 2)].get_end()) / 2
    assert np.linalg.norm(labels[0].get_center() - mid) < 0.3
    with pytest.raises(KeyError):
        label_edges(g, {(2, 3): 1})


def test_trace_calls_records_recursion_and_round_trips(tmp_path):
    result, trace = trace_calls(fib, 3)
    assert result == 2
    calls = [e for e in trace if e["kind"] == "call"]
    assert [c["args"]["n"] for c in calls] == ["3", "2", "1", "0", "1"]
    assert max(c["depth"] for c in calls) == 2
    assert trace.kinds().count("call") == trace.kinds().count("return")
    loaded = Trace.load(trace.save(tmp_path / "t.json"))
    assert loaded.events == trace.events


def test_scene_with_all_helpers_renders_and_appears_on_the_timeline():
    _, trace = trace_calls(fib, 2)

    class Lesson(Scene):
        def construct(self):
            arr = Array([3, 1, 2]).to_edge(1 * np.array([0, 1, 0]))
            self.play(Create(arr))
            self.play(arr.swap(0, 1), arr.highlight([0, 1]))
            lst = LinkedList([1, 2]).shift(np.array([-3, -1, 0]))
            self.add(lst)
            self.play(lst.append(3))
            stack = CallStack().shift(np.array([4, -3, 0]))
            self.add(stack)
            n = play_trace(self, trace, stack.trace_handlers(), run_time=0.2)
            assert n == len(trace) and stack.depth == 0
            sd = SequenceDiagram(["client", "server"]).scale(0.5)
            self.play(FadeIn(sd))
            self.play(sd.message("client", "server", "GET /"))
            self.play(sd.message("server", "server", "work"))
            self.play(sd.message("server", "client", "200", reply=True))

    with tempconfig(LOW):
        tl = capture(Lesson)
    labels = [e.label for e in tl.events if e.kind in ("play", "animation")]
    assert any("Swap" in lab for lab in labels)
    assert sum("FadeIn" in lab for lab in labels) >= 3  # stack pushes
    assert sum("FadeOut" in lab for lab in labels) == 3  # stack pops: fib(2) makes 3 calls


def test_errors():
    with pytest.raises(ValueError):
        SequenceDiagram(["a", "a"])
    with pytest.raises(KeyError):
        SequenceDiagram(["a", "b"]).message("a", "c")
    with pytest.raises(IndexError):
        CallStack().pop()


@pytest.mark.parametrize("scene", ["Recursion", "BubblePass", "Structures", "Protocol"])
def test_gallery_example_scenes_capture(scene):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "examples" / "algorithms" / "gallery.py"
    spec = importlib.util.spec_from_file_location("edu_gallery", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempconfig(LOW):
        tl = capture(getattr(mod, scene))
    assert tl.duration_frames > 0 and any(e.kind == "play" for e in tl.events)


def test_sequence_diagram_rows_follow_a_moved_and_scaled_diagram():
    sd = SequenceDiagram(["a", "b"])
    sd.scale(0.5).shift(np.array([-3, -1, 0]))
    sd.message("a", "b", "hi")
    arrow = sd.messages[0][0]
    head_bottom = sd.heads["a"].get_bottom()[1]
    assert arrow.get_center()[1] < head_bottom  # below the heads, not on them
    assert abs((head_bottom - arrow.get_center()[1]) - 0.8 * sd.step * 0.5) < 0.05
    assert sd.messages[0][1].height < 0.5 * 0.4  # label scaled with the diagram
