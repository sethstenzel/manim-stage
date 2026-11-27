"""Manim feature catalog (ADR-0011).

Classifies Manim objects by Manim's own module layout, so the editor can treat every
animation, mobject and rate function intelligently (colour/icon per category, rate
curves, docs) and so new upstream features are picked up automatically.

This first part covers animations and rate functions (backlog MF.2). The full
introspected catalog (mobjects, colours, scene types, config, plugins) is MF.1.
"""

from __future__ import annotations

from typing import Any

# Manim module (under manim.animation.) -> (category key, display label).
# Keys follow Manim's module names (ADR-0013: Manim terminology).
ANIMATION_CATEGORIES: dict[str, tuple[str, str]] = {
    "creation": ("creation", "Creation"),
    "fading": ("fading", "Fading"),
    "transform": ("transform", "Transform"),
    "transform_matching_parts": ("transform", "Transform"),
    "indication": ("indication", "Indication"),
    "movement": ("movement", "Movement"),
    "rotation": ("rotation", "Rotation"),
    "growing": ("growing", "Growing"),
    "numbers": ("numbers", "Numbers"),
    "changing": ("changing", "Changing"),
    "composition": ("composition", "Composition"),
    "speedmodifier": ("speedmodifier", "Speed modifier"),
    "updaters": ("updaters", "Updaters"),
    "specialized": ("specialized", "Specialized"),
    "animation": ("animation", "Animation"),
}
CATEGORY_LABELS = {key: label for key, label in ANIMATION_CATEGORIES.values()} | {
    "animate": ".animate",
    "wait": "Wait",
    "cue": "Cue",
    "section": "Section",
    "sound": "Sound",
    "caption": "Caption",
    "custom": "Custom",
}

RATE_SAMPLES = 33  # points of the rate-function curve sent to the editor


def animation_category(cls: type) -> str:
    """Category of an Animation class: the first Manim animation module in its MRO.

    ``.animate`` builds are ``"animate"``; ``Wait`` is ``"wait"``; a user subclass of
    ``FadeIn`` is ``"fading"``; a direct ``Animation`` subclass outside Manim is
    ``"custom"``.
    """
    if cls.__name__ == "_MethodAnimation":
        return "animate"
    if cls.__name__ == "Wait" and cls.__module__.startswith("manim."):
        return "wait"
    for klass in cls.__mro__:
        mod = klass.__module__
        if not mod.startswith("manim.animation."):
            continue
        part = mod.split(".")[2]
        key = ANIMATION_CATEGORIES.get(part, ("animation", ""))[0]
        if key == "animation" and klass is not cls:
            return "custom"  # user class deriving directly from Animation
        return key
    return "custom"


def rate_func_name(func: Any) -> str:
    """``smooth``, ``linear``, ``there_and_back`` …; ``<lambda>`` or ``custom`` otherwise."""
    name = getattr(func, "__name__", None)
    if name is None:
        inner = getattr(func, "func", None)  # functools.partial
        name = getattr(inner, "__name__", None)
    return name or "custom"


def is_manim_rate_func(func: Any) -> bool:
    mod = getattr(func, "__module__", "") or ""
    return mod.startswith("manim.utils.rate_functions")


def sample_rate_func(func: Any, n: int = RATE_SAMPLES) -> list[float] | None:
    """``func(t)`` at ``n`` evenly spaced t in [0, 1]; None if it can't be evaluated."""
    try:
        return [round(float(func(i / (n - 1))), 4) for i in range(n)]
    except Exception:
        return None


def animate_methods(animation: Any) -> list[str]:
    """Method chain of an ``.animate`` build, e.g. ``["shift", "scale"]``."""
    return [
        getattr(getattr(m, "method", None), "__name__", "?")
        for m in getattr(animation, "methods", ())
    ]


def animation_info(animation: Any) -> dict[str, Any]:
    """JSON-safe description of one Animation instance for timeline metadata."""
    cls = type(animation)
    category = animation_category(cls)
    mob = getattr(animation, "mobject", None)
    rate = getattr(animation, "rate_func", None)
    info: dict[str, Any] = {
        "class": ".animate" if category == "animate" else cls.__name__,
        "module": cls.__module__,
        "category": category,
        "run_time": float(getattr(animation, "run_time", 0.0)),
    }
    if category == "animate":
        info["methods"] = animate_methods(animation)
    if rate is not None:
        info["rate_func"] = rate_func_name(rate)
        info["rate_func_builtin"] = is_manim_rate_func(rate)
        samples = sample_rate_func(rate)
        if samples is not None:
            info["rate_curve"] = samples
    lag = getattr(animation, "lag_ratio", None)
    if lag is not None:
        info["lag_ratio"] = float(lag)
    if mob is not None and category != "wait":
        info["mobject"] = type(mob).__name__
        name = getattr(mob, "name", None)
        if name and name != type(mob).__name__:
            info["mobject_name"] = str(name)
    for flag in ("introducer", "remover"):
        attr = getattr(animation, f"is_{flag}", None)
        if callable(attr):
            try:
                if attr():
                    info[flag] = True
            except Exception:
                pass
    return info
