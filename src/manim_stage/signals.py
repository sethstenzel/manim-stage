"""Signals, computed values, effects and bindings on Manim's ``ValueTracker``
(spec F06, backlog 3.1; ADR-0013).

Motion Canvas's reactive signals, ported into Manim's model instead of beside it:

- :class:`Signal` **is a** ``ValueTracker``. It holds a number, a vector/point, a list
  of numbers or a colour; ``.animate.set_value(...)``, ``get_value()``, updaters and
  everything else that works on a ``ValueTracker`` work on it. Call it to read it:
  ``values()``.
- :func:`computed` derives a read-only value from signals (and other computed values).
  It is lazy and cached: it re-evaluates only when a value it read has changed, so
  frames where nothing changed cost nothing. Dependencies are discovered while it runs.
- :func:`effect` / :func:`bind` are Manim **updaters** that run only when their inputs
  change. ``bind(bar, height=lambda: values()[0])`` keeps a mobject's property in
  sync with no hand-written updater.

Determinism: evaluation is pull-based and ordered (bindings run in the order they were
created, each pulls its inputs), so a frame is computed the same way every time.

Diagnostics: a dependency cycle raises :class:`CycleError` naming the chain; a
computed function that returns different results for the same inputs is reported as
impure (``Computed.check_purity``); see the KB page for the checks.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
from manim import ValueTracker
from manim.utils.color import ManimColor

# -- dependency tracking -----------------------------------------------------------------

_TRACK: list[set[Any]] = []  # stack of dependency sets being collected
_EVALUATING: list[str] = []  # names of computed values being evaluated (cycle detection)


class CycleError(RuntimeError):
    """A computed value depends on itself."""


def _track(source: Any) -> None:
    if _TRACK:
        _TRACK[-1].add(source)


def untracked(fn: Callable[[], Any]) -> Any:
    """Read signals without making them dependencies (like Motion Canvas ``peek``)."""
    _TRACK.append(set())
    try:
        return fn()
    finally:
        _TRACK.pop()


# -- Signal --------------------------------------------------------------------------------


class Signal(ValueTracker):
    """A ``ValueTracker`` holding a number, vector, list of numbers or colour.

    ``s = Signal([5, 2, 4])`` · ``s()`` reads (and tracks) · ``s.set_value([...])`` ·
    ``self.play(s.animate.set_value([...]))`` interpolates every component.
    """

    def __init__(self, value: Any = 0.0, *, name: str | None = None, **kwargs: Any) -> None:
        self._kind, self._shape = _kind_of(value)
        self.signal_name = name
        self._kind_init = self._kind
        self._kind = "number"  # ValueTracker.__init__ stores a plain number first
        super().__init__(0.0, **kwargs)
        self._kind = self._kind_init
        self.set_value(value)

    # storage: the flattened value is spread over points rows (3 floats per row)
    def set_value(self, value: Any) -> Signal:
        flat = _flatten(value, self._kind)
        if self._kind != "number" and len(flat) != int(np.prod(self._shape or (1,))):
            raise ValueError(
                f"Signal {self.signal_name or ''}: expected {self._shape} values, got {len(flat)}"
            )
        rows = max(1, math.ceil(len(flat) / 3))
        pts = np.zeros((rows, 3))
        pts.flat[: len(flat)] = flat
        self.points = pts
        return self

    def get_value(self) -> Any:
        _track(self)
        return self._raw_value()

    def _raw_value(self) -> Any:
        n = int(np.prod(self._shape or (1,)))
        flat = np.asarray(self.points, dtype=float).flat[:n]
        if self._kind == "number":
            return float(flat[0])
        if self._kind == "color":
            return ManimColor.from_rgba(np.clip(np.array(flat), 0, 1))
        arr = np.array(flat).reshape(self._shape)
        return arr.tolist() if self._kind == "list" else arr

    def __call__(self) -> Any:
        return self.get_value()

    @property
    def value(self) -> Any:
        return self.get_value()

    def _snapshot(self) -> bytes:
        return np.asarray(self.points, dtype=float).tobytes()

    def __repr__(self) -> str:
        return f"Signal({self.signal_name or ''}={self._raw_value()!r})"


def _kind_of(value: Any) -> tuple[str, tuple[int, ...]]:
    if isinstance(value, (int, float, np.floating, np.integer)) and not isinstance(value, bool):
        return "number", ()
    if isinstance(value, (ManimColor, str)) or (
        hasattr(value, "to_rgba") and not isinstance(value, np.ndarray)
    ):
        return "color", (4,)
    arr = np.asarray(value, dtype=float)
    return ("array" if isinstance(value, np.ndarray) else "list"), arr.shape


def _flatten(value: Any, kind: str) -> np.ndarray:
    if kind == "number":
        return np.array([float(value)])
    if kind == "color":
        return np.asarray(ManimColor(value).to_rgba(), dtype=float)
    return np.asarray(value, dtype=float).ravel()


# -- computed --------------------------------------------------------------------------------


class Computed:
    """A lazily evaluated, cached value derived from signals (Motion Canvas ``computed``)."""

    def __init__(self, fn: Callable[[], Any], name: str | None = None) -> None:
        self.fn = fn
        self.name = name or getattr(fn, "__name__", "computed")
        self._deps: dict[Any, Any] = {}
        self._value: Any = None
        self._valid = False
        self.version = 0  # bumps when the value actually changes
        self.evaluations = 0

    def _deps_unchanged(self) -> bool:
        for dep, snap in self._deps.items():
            if isinstance(dep, Signal):
                if dep._snapshot() != snap:
                    return False
            elif isinstance(dep, Computed):
                dep._refresh()
                if dep.version != snap:
                    return False
        return True

    def _refresh(self) -> None:
        if self._valid and self._deps_unchanged():
            return
        if self.name in _EVALUATING:
            chain = " -> ".join([*_EVALUATING[_EVALUATING.index(self.name) :], self.name])
            raise CycleError(f"computed values depend on themselves: {chain}")
        _EVALUATING.append(self.name)
        _TRACK.append(set())
        try:
            value = self.fn()
        finally:
            deps = _TRACK.pop()
            _EVALUATING.pop()
        self._deps = {d: (d._snapshot() if isinstance(d, Signal) else d.version) for d in deps}
        self.evaluations += 1
        if not self._valid or not _equal(value, self._value):
            self.version += 1
        self._value, self._valid = value, True

    def __call__(self) -> Any:
        if self.name in _EVALUATING:
            chain = " -> ".join([*_EVALUATING[_EVALUATING.index(self.name) :], self.name])
            raise CycleError(f"computed values depend on themselves: {chain}")
        self._refresh()
        _track(self)
        return self._value

    @property
    def value(self) -> Any:
        return self()

    @property
    def dependencies(self) -> list[Any]:
        return list(self._deps)

    def check_purity(self) -> bool:
        """Evaluate twice without any change in between; ``False`` means impure
        (reads the clock, randomness or outside state), which breaks replay."""
        a = untracked(self.fn)
        b = untracked(self.fn)
        return _equal(a, b)

    def __repr__(self) -> str:
        return f"Computed({self.name})"


def computed(fn: Callable[[], Any] | None = None, *, name: str | None = None) -> Any:
    """``total = computed(lambda: sum(values()))`` · also usable as ``@computed``."""
    if fn is None:
        return lambda f: Computed(f, name)
    return Computed(fn, name)


def _equal(a: Any, b: Any) -> bool:
    try:
        if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
            return np.array_equal(np.asarray(a), np.asarray(b))
        return bool(a == b)
    except Exception:
        return a is b


# -- effects and bindings (updaters) -------------------------------------------------------


class Effect:
    """Runs ``fn`` now and again whenever a value it read changes (a Manim updater)."""

    def __init__(self, fn: Callable[[], Any], name: str | None = None) -> None:
        self._computed = Computed(fn, name or getattr(fn, "__name__", "effect"))
        self.runs = 0
        self.disposed = False
        self._detach: Callable[[], None] | None = None
        self.update()

    def update(self, *_: Any) -> None:
        if self.disposed:
            return
        before = self._computed.evaluations
        self._computed._refresh()
        if self._computed.evaluations != before:
            self.runs += 1

    def dispose(self) -> None:
        self.disposed = True
        if self._detach:
            self._detach()
            self._detach = None


def effect(fn: Callable[[], Any], *, scene: Any) -> Effect:
    """Register an effect as a scene updater; disposed with the scene (StageScene)."""
    eff = Effect(fn)

    def updater(dt: float) -> None:
        eff.update()

    scene.add_updater(updater)
    eff._detach = lambda: scene.remove_updater(updater)
    _register(scene, eff)
    return eff


_SETTERS: dict[str, Callable[[Any, Any], Any]] = {
    "x": lambda m, v: m.set_x(v),
    "y": lambda m, v: m.set_y(v),
    "position": lambda m, v: m.move_to(v),
    "color": lambda m, v: m.set_color(v),
    "fill_color": lambda m, v: m.set_fill(color=v),
    "stroke_color": lambda m, v: m.set_stroke(color=v),
    "opacity": lambda m, v: m.set_opacity(v),
    "fill_opacity": lambda m, v: m.set_fill(opacity=v),
    "stroke_width": lambda m, v: m.set_stroke(width=v),
    "value": lambda m, v: m.set_value(v),
}


class Binding:
    """Keeps mobject properties equal to signal expressions (a mobject updater)."""

    def __init__(
        self,
        mobject: Any,
        props: dict[str, Callable[[], Any]],
        *,
        align: Any = None,
        update: Callable[[Any], Any] | None = None,
    ) -> None:
        unknown = set(props) - set(_SETTERS) - {"height", "width"}
        if unknown:
            raise ValueError(
                f"bind: unknown properties {sorted(unknown)}; "
                f"supported: {sorted([*_SETTERS, 'height', 'width'])}"
            )
        self.mobject, self.align = mobject, align
        self._exprs = {k: Computed(v, f"{type(mobject).__name__}.{k}") for k, v in props.items()}
        self._custom = Computed(lambda: update(mobject), "update") if update else None
        self._seen: dict[str, int] = {}
        self.updates = 0
        self.disposed = False
        self.apply()
        mobject.add_updater(self._updater)

    def _updater(self, m: Any, *args: Any) -> None:
        self.apply()

    def apply(self) -> None:
        if self.disposed:
            return
        changed = False
        for key, comp in self._exprs.items():
            value = comp()
            if self._seen.get(key) == comp.version:
                continue
            self._seen[key] = comp.version
            self._set(key, value)
            changed = True
        if self._custom is not None:
            if changed:  # e.g. a new value changed the mobject's size: re-place it
                self._custom._valid = False
            before = self._custom.evaluations
            self._custom._refresh()
            changed |= self._custom.evaluations != before
        if changed:
            self.updates += 1

    def _set(self, key: str, value: Any) -> None:
        m = self.mobject
        if key in ("height", "width"):
            anchor = m.get_critical_point(self.align) if self.align is not None else None
            value = max(float(value), 1e-6)  # a zero size can't be scaled back up
            if key == "height":
                m.stretch_to_fit_height(value)
            else:
                m.stretch_to_fit_width(value)
            if anchor is not None:
                m.shift(anchor - m.get_critical_point(self.align))
        else:
            _SETTERS[key](m, value)

    def dispose(self) -> None:
        self.disposed = True
        self.mobject.remove_updater(self._updater)


def bind(
    mobject: Any,
    *,
    align: Any = None,
    update: Callable[[Any], Any] | None = None,
    scene: Any = None,
    **props: Callable[[], Any],
) -> Binding:
    """``bind(bar, height=lambda: values()[i] * 0.5, align=DOWN)`` (spec F06).

    Properties: x, y, position, height, width (``align=DOWN`` keeps that edge in place),
    color, fill_color, stroke_color, opacity, fill_opacity, stroke_width, value.
    ``update=lambda m: ...`` runs arbitrary code when its inputs change, and after any of
    the bound properties changed (so it can re-position the mobject).
    """
    b = Binding(mobject, props, align=align, update=update)
    if scene is not None:
        _register(scene, b)
    return b


def _register(scene: Any, item: Any) -> None:
    items = getattr(scene, "_stage_reactive", None)
    if items is None:
        items = []
        try:
            scene._stage_reactive = items
        except AttributeError:
            return
    items.append(item)


def dispose_all(scene: Any) -> int:
    """Dispose a scene's effects and bindings (StageScene does this at scene end)."""
    items = getattr(scene, "_stage_reactive", None) or []
    for it in items:
        it.dispose()
    n = len(items)
    items.clear()
    return n


__all__ = [
    "Binding",
    "Computed",
    "CycleError",
    "Effect",
    "Signal",
    "bind",
    "computed",
    "dispose_all",
    "effect",
    "untracked",
]
