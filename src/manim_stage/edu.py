"""Educational helpers (spec F12, backlog 4.2).

Data-structure Mobjects, a call stack, protocol sequence diagrams, labelled graph edges,
a tidy tree layout for Manim's ``Graph`` and data-driven execution traces.

They follow Manim's style: each helper is an ordinary ``VGroup``, and its methods update
the model and *return an animation* that you ``self.play(...)``. So they render with
plain ``manim render`` and show up on the Studio timeline like any other animation::

    arr = Array([5, 2, 4, 1])
    self.play(Create(arr))
    self.play(arr.swap(0, 1))            # values move; boxes stay
    i = arr.pointer(0, "i")
    self.play(FadeIn(i), i.move_to_index(2))

Traces are produced by a trusted Python function *before* animating (no live execution
in the viewer)::

    result, trace = trace_calls(fib, 4)
    stack = CallStack()
    play_trace(self, trace, stack.trace_handlers())
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    DOWN,
    GREY,
    LEFT,
    ORIGIN,
    PI,
    RIGHT,
    UP,
    WHITE,
    YELLOW,
    AnimationGroup,
    Arrow,
    Circle,
    CurvedArrow,
    DashedLine,
    FadeIn,
    FadeOut,
    GrowArrow,
    Line,
    Mobject,
    Rectangle,
    Square,
    Swap,
    Text,
    Transform,
    VGroup,
)

BOX_FILL = "#1C4E80"

__all__ = [
    "Array",
    "ArrayPointer",
    "CallStack",
    "LinkedList",
    "SequenceDiagram",
    "Trace",
    "Tree",
    "label_edges",
    "play_trace",
    "trace_calls",
    "tree_layout",
]


def _text(value: Any, font_size: float, color: Any) -> Text:
    return Text(str(value), font_size=font_size, color=color)


def _fit(mob: Mobject, width: float) -> Mobject:
    if mob.width > width:
        mob.scale_to_fit_width(width)
    return mob


# -- arrays ---------------------------------------------------------------------------


class Array(VGroup):
    """A row of boxed values with optional index labels.

    ``boxes``, ``labels`` and ``indices`` are VGroups; ``values`` is the current list.
    """

    def __init__(
        self,
        values: Iterable[Any],
        *,
        cell_size: float = 0.8,
        font_size: float = 28,
        color: Any = WHITE,
        fill_color: Any = BOX_FILL,
        show_indices: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.values = list(values)
        self.cell_size, self.font_size, self.text_color = cell_size, font_size, color
        self.boxes = VGroup(
            *[
                Square(cell_size, color=color, stroke_width=2).set_fill(fill_color, 0)
                for _ in self.values
            ]
        )
        if self.values:
            self.boxes.arrange(RIGHT, buff=0)
        self.labels = VGroup(
            *[
                _fit(_text(v, font_size, color), cell_size * 0.85).move_to(b)
                for v, b in zip(self.values, self.boxes, strict=True)
            ]
        )
        self.indices = VGroup(
            *(
                [
                    _text(i, font_size * 0.6, GREY).next_to(b, DOWN, buff=0.1)
                    for i, b in enumerate(self.boxes)
                ]
                if show_indices
                else []
            )
        )
        self.add(self.boxes, self.labels, self.indices)

    def swap(self, i: int, j: int, **kwargs: Any) -> Swap:
        """Swap two values (the labels trade places; boxes stay)."""
        a, b = self.labels[i], self.labels[j]
        self.values[i], self.values[j] = self.values[j], self.values[i]
        subs = self.labels.submobjects
        subs[i], subs[j] = subs[j], subs[i]
        return Swap(a, b, **kwargs)

    def set_value(self, i: int, value: Any, **kwargs: Any) -> Transform:
        """Change one value."""
        self.values[i] = value
        new = _fit(_text(value, self.font_size, self.text_color), self.cell_size * 0.85)
        return Transform(self.labels[i], new.move_to(self.boxes[i]), **kwargs)

    def highlight(self, i: int | Iterable[int], color: Any = YELLOW, opacity: float = 0.5) -> Any:
        """Fill one or more boxes (``opacity=0`` clears)."""
        idx = [i] if isinstance(i, int) else list(i)
        return AnimationGroup(*[self.boxes[k].animate.set_fill(color, opacity) for k in idx])

    def pointer(
        self, i: int, label: str = "", *, color: Any = YELLOW, direction: np.ndarray = DOWN
    ) -> ArrayPointer:
        """A labelled arrow pointing at cell ``i`` (add or ``FadeIn`` it yourself)."""
        return ArrayPointer(self, i, label, color=color, direction=direction)


class ArrayPointer(VGroup):
    """An index pointer under (or over) an :class:`Array`; ``move_to_index`` animates it."""

    def __init__(
        self,
        array: Array,
        index: int,
        label: str = "",
        *,
        color: Any = YELLOW,
        direction: np.ndarray = DOWN,
    ) -> None:
        super().__init__()
        self.array, self.index, self.direction = array, index, np.array(direction, dtype=float)
        self.arrow = Arrow(
            self.direction * 0.7,
            ORIGIN,
            buff=0,
            color=color,
            stroke_width=4,
            max_tip_length_to_length_ratio=0.4,
        )
        self.add(self.arrow)
        if label:
            self.label = _text(label, array.font_size * 0.75, color)
            self.add(self.label.next_to(self.arrow, self.direction, buff=0.06))
        self.shift(self._anchor(index) - self.arrow.get_end())

    def _anchor(self, index: int) -> np.ndarray:
        box = self.array.boxes[index]
        below = np.allclose(self.direction, DOWN)
        gap = 0.4 if below and len(self.array.indices) else 0.06
        return box.get_edge_center(self.direction) + self.direction * gap

    def move_to_index(self, index: int) -> Any:
        """Animation moving the pointer to cell ``index``."""
        self.index = index
        return self.animate.shift(self._anchor(index) - self.arrow.get_end())


# -- linked list ----------------------------------------------------------------------


class LinkedList(VGroup):
    """Boxed nodes joined by arrows; ``append`` grows it."""

    def __init__(
        self,
        values: Iterable[Any] = (),
        *,
        node_width: float = 0.9,
        node_height: float = 0.6,
        gap: float = 0.6,
        font_size: float = 26,
        color: Any = WHITE,
        fill_color: Any = BOX_FILL,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.values: list[Any] = []
        self._style = (node_width, node_height, font_size, color, fill_color)
        self.gap = gap
        self.nodes, self.arrows = VGroup(), VGroup()
        self.add(self.arrows, self.nodes)
        for v in values:
            self._attach(v)

    def _node(self, value: Any) -> VGroup:
        w, h, fs, color, fill = self._style
        box = Rectangle(width=w, height=h, color=color, stroke_width=2).set_fill(fill, 0.35)
        return VGroup(box, _fit(_text(value, fs, color), w * 0.85).move_to(box))

    def _attach(self, value: Any) -> tuple[VGroup, Arrow | None]:
        node = self._node(value)
        arrow = None
        if len(self.nodes):
            prev = self.nodes[-1]
            node.next_to(prev, RIGHT, buff=self.gap)
            arrow = Arrow(
                prev.get_right(),
                node.get_left(),
                buff=0.04,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.35,
                color=self._style[3],
            )
            self.arrows.add(arrow)
        else:
            node.move_to(self.get_center() if self.submobjects and self.has_points() else ORIGIN)
        self.nodes.add(node)
        self.values.append(value)
        return node, arrow

    def append(self, value: Any) -> AnimationGroup:
        """Add a node at the end."""
        node, arrow = self._attach(value)
        if arrow is None:
            return AnimationGroup(FadeIn(node))
        return AnimationGroup(GrowArrow(arrow), FadeIn(node, shift=LEFT * 0.3), lag_ratio=1.0)

    def highlight(self, i: int, color: Any = YELLOW, opacity: float = 0.6) -> Any:
        return self.nodes[i][0].animate.set_fill(color, opacity)


# -- trees ----------------------------------------------------------------------------


def tree_layout(
    children: Mapping[Hashable, Sequence[Hashable]],
    root: Hashable,
    *,
    h_gap: float = 1.0,
    v_gap: float = 1.2,
) -> dict[Hashable, np.ndarray]:
    """Tidy positions for a rooted tree: leaves left to right, parents centred over
    their children, root at the top (y=0), centred on x=0.

    Pass the result to Manim's ``Graph(..., layout=tree_layout(children, root))``.
    """
    x: dict[Hashable, float] = {}
    depth: dict[Hashable, int] = {}
    next_leaf = 0
    stack: list[tuple[Hashable, int, bool]] = [(root, 0, False)]
    while stack:
        node, d, done = stack.pop()
        kids = list(children.get(node, ()))
        if done:
            x[node] = (x[kids[0]] + x[kids[-1]]) / 2
            continue
        if node in depth:
            raise ValueError(f"tree_layout: {node!r} is reachable twice (not a tree)")
        depth[node] = d
        if not kids:
            x[node] = next_leaf
            next_leaf += 1
            continue
        stack.append((node, d, True))
        stack.extend((k, d + 1, False) for k in reversed(kids))
    mid = (next_leaf - 1) / 2
    return {n: np.array([(x[n] - mid) * h_gap, -depth[n] * v_gap, 0.0]) for n in depth}


class Tree(VGroup):
    """A rooted tree of circular nodes. ``nodes[key]`` and ``edges[(parent, child)]``."""

    def __init__(
        self,
        children: Mapping[Hashable, Sequence[Hashable]],
        root: Hashable,
        *,
        labels: Mapping[Hashable, Any] | None = None,
        radius: float = 0.32,
        font_size: float = 24,
        h_gap: float = 1.0,
        v_gap: float = 1.2,
        color: Any = WHITE,
        fill_color: Any = BOX_FILL,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        pos = tree_layout(children, root, h_gap=h_gap, v_gap=v_gap)
        self.root = root
        self.nodes: dict[Hashable, VGroup] = {}
        self.edges: dict[tuple[Hashable, Hashable], Line] = {}
        node_group, edge_group = VGroup(), VGroup()
        for key, p in pos.items():
            circle = Circle(radius, color=color, stroke_width=2).set_fill(fill_color, 1).move_to(p)
            text = _text(labels.get(key, key) if labels else key, font_size, color)
            node = VGroup(circle, _fit(text, radius * 1.6).move_to(p))
            self.nodes[key] = node
            node_group.add(node)
        for parent, kids in children.items():
            for kid in kids:
                if parent in pos and kid in pos:
                    edge = Line(pos[parent], pos[kid], buff=radius, color=GREY, stroke_width=3)
                    self.edges[(parent, kid)] = edge
                    edge_group.add(edge)
        self.node_group, self.edge_group = node_group, edge_group
        self.add(edge_group, node_group)

    @classmethod
    def from_heap(cls, values: Sequence[Any], **kwargs: Any) -> Tree:
        """A complete binary tree from an array (heap layout: children of i are 2i+1, 2i+2)."""
        n = len(values)
        children = {i: [c for c in (2 * i + 1, 2 * i + 2) if c < n] for i in range(n)}
        return cls(children, 0, labels=dict(enumerate(values)), **kwargs)

    def highlight(self, key: Hashable, color: Any = YELLOW, opacity: float = 0.55) -> Any:
        """Tint one node (stroke and fill)."""
        return self.nodes[key][0].animate.set_fill(color, opacity).set_stroke(color)


# -- graphs ---------------------------------------------------------------------------


def label_edges(
    graph: Any,
    labels: Mapping[tuple[Hashable, Hashable], Any],
    *,
    font_size: float = 22,
    color: Any = WHITE,
    buff: float = 0.18,
    background: bool = True,
) -> VGroup:
    """Labels (weights, capacities...) that stay beside the edges of a Manim ``Graph``.

    Returns a VGroup to ``add``/``FadeIn``; each label follows its edge with an updater,
    so moving vertices (``graph.animate.change_layout(...)``) keeps them in place.
    """
    group = VGroup()
    for (u, v), lab in labels.items():
        edge = graph.edges.get((u, v)) or graph.edges.get((v, u))
        if edge is None:
            raise KeyError(f"label_edges: no edge {(u, v)!r} in the graph")
        mob = lab if isinstance(lab, Mobject) else _text(lab, font_size, color)
        if background:
            mob.add_background_rectangle(opacity=0.85, buff=0.04)

        def follow(m: Mobject, e: Mobject = edge) -> None:
            s, t = e.get_start(), e.get_end()
            d = t - s
            n = np.array([-d[1], d[0], 0.0])
            norm = np.linalg.norm(n)
            m.move_to((s + t) / 2 + (n / norm * buff if norm else 0))

        follow(mob)
        mob.add_updater(follow)
        group.add(mob)
    return group


# -- call stack -----------------------------------------------------------------------


class CallStack(VGroup):
    """A stack of frames growing upward from a base line; ``push``/``pop`` animate it."""

    def __init__(
        self,
        *,
        frame_width: float = 3.2,
        frame_height: float = 0.55,
        font_size: float = 22,
        color: Any = WHITE,
        fill_color: Any = BOX_FILL,
        title: str = "call stack",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._style = (frame_width, frame_height, font_size, color, fill_color)
        self.base = Line(LEFT * frame_width / 2, RIGHT * frame_width / 2, color=GREY)
        self.title = _text(title, font_size * 0.8, GREY).next_to(self.base, DOWN, buff=0.15)
        self.frames = VGroup()
        self.add(self.base, self.title, self.frames)

    @property
    def depth(self) -> int:
        return len(self.frames)

    def _frame(self, label: str) -> VGroup:
        w, h, fs, color, fill = self._style
        box = Rectangle(width=w, height=h, color=color, stroke_width=2).set_fill(fill, 0.5)
        return VGroup(box, _fit(_text(label, fs, color), w * 0.9).move_to(box))

    def push(self, label: str, **kwargs: Any) -> FadeIn:
        """Push a frame labelled ``label``."""
        frame = self._frame(label)
        below = self.frames[-1] if len(self.frames) else self.base
        frame.next_to(below, UP, buff=0.04)
        self.frames.add(frame)
        return FadeIn(frame, shift=DOWN * 0.4, **kwargs)

    def pop(self, **kwargs: Any) -> FadeOut:
        """Pop the top frame."""
        if not len(self.frames):
            raise IndexError("pop from an empty CallStack")
        frame = self.frames[-1]
        self.frames.remove(frame)
        return FadeOut(frame, shift=UP * 0.4, **kwargs)

    def trace_handlers(self, *, show_args: bool = True) -> dict[str, Callable[[dict], Any]]:
        """Handlers for :func:`play_trace` mapping ``call``/``return`` events to push/pop."""

        def call(e: dict) -> Any:
            args = ", ".join(f"{v}" for v in e.get("args", {}).values()) if show_args else ""
            return self.push(f"{e['function']}({args})")

        return {"call": call, "return": lambda e: self.pop() if len(self.frames) else None}


# -- sequence diagrams ----------------------------------------------------------------


class SequenceDiagram(VGroup):
    """Participants with lifelines; ``message`` adds the next arrow down the page."""

    def __init__(
        self,
        participants: Sequence[str],
        *,
        spacing: float = 3.0,
        height: float = 5.5,
        step: float = 0.6,
        font_size: float = 24,
        color: Any = WHITE,
        fill_color: Any = BOX_FILL,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if len(set(participants)) != len(participants):
            raise ValueError("SequenceDiagram: participant names must be unique")
        self.step, self.font_size, self.color_ = step, font_size, color
        n = len(participants)
        self.heads: dict[str, VGroup] = {}
        self.lifelines: dict[str, DashedLine] = {}
        heads, lines = VGroup(), VGroup()
        for k, name in enumerate(participants):
            x = (k - (n - 1) / 2) * spacing
            text = _text(name, font_size, color)
            box = Rectangle(
                width=max(text.width + 0.4, 1.4),
                height=text.height + 0.35,
                color=color,
                stroke_width=2,
            ).set_fill(fill_color, 0.6)
            head = VGroup(box, text).move_to([x, height / 2, 0])
            line = DashedLine(
                box.get_bottom(),
                box.get_bottom() + DOWN * (height - box.height),
                color=GREY,
                stroke_width=2,
            )
            self.heads[name], self.lifelines[name] = head, line
            heads.add(head)
            lines.add(line)
        self.messages = VGroup()
        self.add(lines, heads, self.messages)
        self._y = min(h.get_bottom()[1] for h in self.heads.values()) - step * 0.8

    def _x(self, name: str) -> float:
        if name not in self.heads:
            raise KeyError(f"SequenceDiagram: unknown participant {name!r}")
        return float(self.heads[name].get_center()[0])

    def message(
        self,
        src: str,
        dst: str,
        label: str = "",
        *,
        reply: bool = False,
        color: Any = None,
        **kwargs: Any,
    ) -> AnimationGroup:
        """Draw the next message from ``src`` to ``dst`` (``reply=True`` draws it faded,
        like a dashed return arrow)."""
        y = self._y
        color = color or self.color_
        xs, xd = self._x(src), self._x(dst)
        if src == dst:
            arrow: Mobject = CurvedArrow(
                [xs, y, 0],
                [xs, y - self.step * 0.5, 0],
                angle=-PI,
                color=color,
                stroke_width=3,
                tip_length=0.14,
            )
            self._y -= self.step * 0.5
        else:
            arrow = Arrow(
                [xs, y, 0],
                [xd, y, 0],
                buff=0.03,
                color=color,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.06,
            )
        if reply:
            arrow.set_stroke(opacity=0.55)
        parts = [arrow]
        if label:
            text = _text(label, self.font_size * 0.75, color)
            text.next_to(arrow, UP if src != dst else RIGHT, buff=0.06)
            parts.append(text)
        msg = VGroup(*parts)
        self.messages.add(msg)
        self._y -= self.step
        anims = [GrowArrow(arrow) if src != dst else FadeIn(arrow)]
        if label:
            anims.append(FadeIn(parts[1]))
        return AnimationGroup(*anims, lag_ratio=0.3, **kwargs)


# -- traces ---------------------------------------------------------------------------


def _short(value: Any, limit: int = 40) -> str:
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class Trace:
    """A list of events (plain dicts with a ``kind``), saved and loaded as JSON.

    Record algorithm state yourself with :meth:`step`, or calls/returns with
    :func:`trace_calls`; animate it with :func:`play_trace`.
    """

    events: list[dict[str, Any]] = field(default_factory=list)

    def step(self, kind: str, **data: Any) -> None:
        """Record one algorithm step, e.g. ``trace.step("compare", i=0, j=1)``."""
        self.events.append({"kind": kind, **data})

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.events)

    def __len__(self) -> int:
        return len(self.events)

    def kinds(self) -> list[str]:
        return [e["kind"] for e in self.events]

    def to_json(self) -> str:
        return json.dumps(
            {"schema": "manim_stage.trace", "version": 1, "events": self.events},
            indent=1,
            default=_short,
        )

    def save(self, path: str | os.PathLike[str]) -> Path:
        p = Path(path)
        p.write_text(self.to_json() + "\n", encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Trace:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != "manim_stage.trace":
            raise ValueError(f"{path}: not a manim_stage.trace file")
        return cls(list(data["events"]))


def trace_calls(
    func: Callable[..., Any],
    *args: Any,
    files: Iterable[str] = (),
    max_events: int = 10_000,
    **kwargs: Any,
) -> tuple[Any, Trace]:
    """Run a trusted ``func(*args, **kwargs)`` and record its Python calls and returns.

    Only functions defined in ``func``'s file (plus ``files``) are recorded; comprehension
    and lambda frames are skipped. Events: ``{"kind": "call", "function", "args", "depth"}``
    and ``{"kind": "return", "function", "value", "depth"}`` (values are short reprs).
    Returns ``(result, trace)``.
    """
    wanted = {func.__code__.co_filename, *map(os.fspath, files)}
    trace = Trace()
    depth = 0

    def profile(frame: Any, event: str, arg: Any) -> None:
        nonlocal depth
        code = frame.f_code
        if event not in ("call", "return") or code.co_filename not in wanted:
            return
        if code.co_name.startswith("<") or len(trace.events) >= max_events:
            return
        if event == "call":
            names = code.co_varnames[: code.co_argcount + code.co_kwonlyargcount]
            args_ = {n: _short(frame.f_locals.get(n)) for n in names}
            trace.events.append(
                {"kind": "call", "function": code.co_name, "args": args_, "depth": depth}
            )
            depth += 1
        else:
            depth = max(0, depth - 1)
            trace.events.append(
                {"kind": "return", "function": code.co_name, "value": _short(arg), "depth": depth}
            )

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        result = func(*args, **kwargs)
    finally:
        sys.setprofile(previous)
    return result, trace


def play_trace(
    scene: Any,
    trace: Iterable[dict[str, Any]],
    handlers: Mapping[str, Callable[[dict[str, Any]], Any]],
    *,
    run_time: float = 0.5,
    wait: float = 0.0,
) -> int:
    """Animate a trace: ``handlers[kind](event)`` returns an animation, a list of them or
    ``None`` (skip). Each non-empty step is one ``scene.play``. Returns the number played.
    """
    played = 0
    for event in trace:
        handler = handlers.get(event.get("kind", ""))
        out = handler(event) if handler else None
        anims = [a for a in (out if isinstance(out, (list, tuple)) else [out]) if a is not None]
        if not anims:
            continue
        scene.play(*anims, run_time=run_time)
        played += 1
        if wait:
            scene.wait(wait)
    return played
