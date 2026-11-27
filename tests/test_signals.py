"""Signals on ValueTracker: computed, effects, bindings (backlog 3.1, spec F06)."""

import numpy as np
import pytest
from manim import (
    BLUE,
    DOWN,
    RED,
    DecimalNumber,
    Rectangle,
    Scene,
    Text,
    Triangle,
    ValueTracker,
    VGroup,
    tempconfig,
)
from manim.utils.color import ManimColor

from manim_stage import StageScene
from manim_stage.signals import Computed, CycleError, Signal, bind, computed, untracked

CFG = {
    "frame_rate": 10,
    "dry_run": True,
    "disable_caching": True,
    "progress_bar": "none",
    "verbosity": "WARNING",
}


def test_signal_is_a_value_tracker_for_many_kinds():
    n = Signal(2)
    assert isinstance(n, ValueTracker) and n() == 2.0 and n.get_value() == 2.0
    n.set_value(3.5)
    assert n.value == 3.5
    v = Signal([5, 2, 4, 1])
    assert v() == [5.0, 2.0, 4.0, 1.0]
    p = Signal(np.array([1.0, 2.0, 0.0]))
    assert isinstance(p(), np.ndarray) and p()[1] == 2.0
    c = Signal(RED)
    assert isinstance(c(), ManimColor) and c().to_hex().lower() == ManimColor(RED).to_hex().lower()
    with pytest.raises(ValueError):
        v.set_value([1, 2])


def test_computed_is_lazy_cached_and_tracks_dependencies():
    a, b = Signal(1), Signal(10)
    calls = []

    def total():
        calls.append(1)
        return a() + b()

    t = computed(total)
    assert t() == 11 and t() == 11 and len(calls) == 1  # cached
    a.set_value(2)
    assert t() == 12 and len(calls) == 2
    assert set(t.dependencies) == {a, b}
    double = computed(lambda: t() * 2)
    assert double() == 24
    b.set_value(20)
    assert double() == 44  # chain re-evaluates through t
    assert untracked(lambda: a()) == 2


def test_cycles_are_detected():
    holder = {}
    x = Computed(lambda: holder["y"]() + 1, "x")
    y = Computed(lambda: x() + 1, "y")
    holder["y"] = y
    with pytest.raises(CycleError, match="x -> y -> x"):
        x()


def test_purity_check():
    import random

    s = Signal(1)
    assert computed(lambda: s() * 2).check_purity()
    assert not computed(lambda: s() + random.random()).check_purity()


def test_bindings_update_only_when_inputs_change():
    s = Signal(1.0)
    r = Rectangle(width=1, height=1)
    b = bind(r, height=lambda: s() * 2, align=DOWN)
    bottom = r.get_bottom().copy()
    assert r.height == pytest.approx(2.0) and np.allclose(r.get_bottom(), bottom)
    n = b.updates
    r.update()  # no change → no work
    assert b.updates == n
    s.set_value(3.0)
    r.update()
    assert r.height == pytest.approx(6.0) and np.allclose(r.get_bottom(), bottom)
    with pytest.raises(ValueError, match="unknown properties"):
        bind(r, colour=lambda: RED)


class ArraySignalScene(StageScene):
    """F06 accept: an array signal drives value labels, bar heights and a comparison
    indicator, with no hand-written updaters; everything is disposed at scene end."""

    def construct(self):
        self.values = values = Signal([5, 2, 4, 1], name="values")
        bars = VGroup(*[Rectangle(width=0.6, height=1, fill_opacity=0.8) for _ in range(4)])
        bars.arrange(buff=0.3, aligned_edge=DOWN)
        labels = VGroup(*[DecimalNumber(0, num_decimal_places=1, mob_class=Text) for _ in range(4)])
        biggest = computed(lambda: int(np.argmax(values())), name="biggest")
        pointer = Triangle(fill_opacity=1).scale(0.2)
        for i, (bar, label) in enumerate(zip(bars, labels, strict=True)):
            self.bind(
                bar,
                height=lambda i=i: values()[i] * 0.5,
                align=DOWN,
                color=lambda i=i: RED if biggest() == i else BLUE,
            )
            self.bind(
                label, value=lambda i=i: values()[i], update=lambda m, i=i: m.next_to(bars[i], DOWN)
            )
        self.bind(pointer, update=lambda m: m.next_to(bars[biggest()], DOWN * 3))
        self.log = []
        self.effect_runs = self.effect(lambda: self.log.append(biggest()))
        self.add(bars, labels, pointer)
        self.bars, self.labels, self.pointer = bars, labels, pointer
        self.play(values.animate.set_value([2, 5, 4, 1]), run_time=1)
        self.mid = (bars[0].height, bars[1].height)
        self.play(values.animate.set_value([1, 2, 4, 5]), run_time=1)


def test_array_signal_drives_bars_labels_and_indicator():
    with tempconfig(CFG):
        s = ArraySignalScene()
        s.render()
    assert [b.height for b in s.bars] == pytest.approx([0.5, 1.0, 2.0, 2.5])
    assert [lab.get_value() for lab in s.labels] == pytest.approx([1, 2, 4, 5])
    assert s.bars[3].get_color().to_hex().lower() == ManimColor(RED).to_hex().lower()
    assert abs(s.pointer.get_x() - s.bars[3].get_x()) < 1e-6
    assert s.log[0] == 0 and s.log[-1] == 3  # the effect saw the max move
    # labels sit under their bars at every step (consistent, same frame)
    for bar, label in zip(s.bars, s.labels, strict=True):
        assert abs(label.get_x() - bar.get_x()) < 1e-6
    # clean disposal: no updaters left on any mobject or the scene
    assert not s.updaters if hasattr(s, "updaters") else True
    assert all(not m.updaters for m in [*s.bars, *s.labels, s.pointer])


def test_plain_manim_scene_can_bind_too():
    class Plain(Scene):
        def construct(self):
            self.s = Signal(1.0)
            self.r = Rectangle()
            bind(self.r, width=lambda: self.s() * 4)
            self.add(self.r)
            self.play(self.s.animate.set_value(2.0), run_time=0.5)

    with tempconfig(CFG):
        sc = Plain()
        sc.render()
    assert sc.r.width == pytest.approx(8.0)
