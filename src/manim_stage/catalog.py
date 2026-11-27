"""Manim feature catalog (ADR-0011).

Classifies Manim objects by Manim's own module layout, so the editor can treat every
animation, mobject and rate function intelligently (colour/icon per category, rate
curves, docs) and so new upstream features are picked up automatically.

Animation metadata and rate functions (backlog MF.2), and the full introspected
catalog of everything ``from manim import *`` provides (``build_catalog``, MF.1),
used by the Studio Library tab and ``manim-stage catalog``.
"""

from __future__ import annotations

import inspect
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
    "plugin": "Plugin",
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


# -- the full introspected catalog (backlog MF.1) --------------------------------------

DOCS_URL = "https://docs.manim.community/en/stable/reference/{module}.{name}.html"

# kinds, in the order the Library shows them
KINDS = (
    "mobjects",
    "animations",
    "scenes",
    "cameras",
    "rate_functions",
    "colors",
    "manim_stage",
    "utilities",
    "constants",
    "modules",
)

# manim_stage APIs listed beside Manim's (Library panel, `manim-stage catalog`)
STAGE_APIS = {
    "scene": ["StageScene", "StageMixin"],
    "signals": ["Signal", "computed", "bind", "effect"],
    "flow": ["all_of", "sequence", "chain", "delay", "loop", "tween", "enter", "exit"],
    "code": ["AnimatedCode"],
    "edu": [
        "Array",
        "LinkedList",
        "Tree",
        "tree_layout",
        "label_edges",
        "CallStack",
        "SequenceDiagram",
        "Trace",
        "trace_calls",
        "play_trace",
    ],
    "demo": ["param"],
    "project": ["theme", "var"],
}

_CATALOG: dict[str, Any] | None = None


def _summary(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    for para in doc.split("\n\n"):
        line = " ".join(para.split())
        if line:
            return line if len(line) <= 200 else line[:199] + "…"
    return ""


def _signature(obj: Any) -> str:
    target = obj.__init__ if inspect.isclass(obj) else obj
    try:
        sig = inspect.signature(target)
    except (TypeError, ValueError):
        return "(…)"
    params = [p for p in sig.parameters.values() if p.name != "self"]
    text = str(sig.replace(parameters=params, return_annotation=inspect.Signature.empty))
    return text if len(text) <= 240 else text[:239] + "…"


def _required(obj: Any) -> list[str]:
    target = obj.__init__ if inspect.isclass(obj) else obj
    try:
        sig = inspect.signature(target)
    except (TypeError, ValueError):
        return []
    return [
        p.name
        for p in sig.parameters.values()
        if p.name != "self"
        and p.default is inspect.Parameter.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]


def _group(module: str, root: str) -> str:
    """``manim.mobject.geometry.arc`` under ``manim.mobject`` -> ``geometry``."""
    rest = module[len(root) + 1 :] if module.startswith(root + ".") else module
    return rest.split(".")[0] or "other"


def _snippet(kind: str, name: str, obj: Any) -> str:
    args = ", ".join(_required(obj))
    if kind == "mobjects":
        return f"{name}({args})"
    if kind == "animations":
        return f"self.play({name}({args or 'mobject'}))"
    if kind == "scenes":
        return f"class MyScene({name}):\n    def construct(self):\n        ..."
    if kind == "rate_functions":
        return f"self.play(FadeIn(mobject), rate_func={name})"
    if kind == "colors":
        return name
    if kind == "cameras":
        return f"camera_class={name}"
    return f"{name}({args})" if callable(obj) else name


def _entry(kind: str, name: str, obj: Any, group: str) -> dict[str, Any]:
    module = getattr(obj, "__module__", "") or ""
    e: dict[str, Any] = {"name": name, "kind": kind, "group": group, "module": module}
    if inspect.isclass(obj) or inspect.isfunction(obj):
        e["signature"] = _signature(obj)
        e["summary"] = _summary(obj)
        if module.startswith("manim."):
            e["docs"] = DOCS_URL.format(module=module, name=getattr(obj, "__qualname__", name))
    e["snippet"] = _snippet(kind, name, obj)
    return e


def build_catalog() -> dict[str, Any]:
    """Everything ``from manim import *`` provides, classified, plus manim-stage APIs.

    JSON-safe: ``{"manim_version", "kinds": {kind: [entry, ...]}}``. Each entry has
    ``name``, ``kind``, ``group`` (Manim sub-package, e.g. ``geometry``), ``module``,
    ``signature``/``summary``/``docs`` for classes and functions, and a ``snippet``.
    Rate functions add ``curve``; colours add ``hex``; mobjects add ``needs_latex`` and
    ``three_d``.
    """
    import manim
    from manim import Animation, Camera, Mobject, Scene

    from . import _compat
    from .plugins import manim_plugins

    kinds: dict[str, list[dict[str, Any]]] = {k: [] for k in KINDS}
    latex_base = getattr(manim, "SingleStringMathTex", None)
    three_d_root = "manim.mobject.three_d"
    for name in sorted(n for n in dir(manim) if not n.startswith("_")):
        obj = getattr(manim, name)
        module = getattr(obj, "__module__", "") or ""
        if inspect.ismodule(obj):
            kinds["modules"].append(
                {
                    "name": name,
                    "kind": "modules",
                    "group": "module",
                    "module": obj.__name__,
                    "snippet": f"manim.{name}",
                }
            )
        elif inspect.isclass(obj) and issubclass(obj, Mobject):
            e = _entry("mobjects", name, obj, _group(module, "manim.mobject"))
            e["needs_latex"] = bool(latex_base and issubclass(obj, latex_base))
            e["three_d"] = module.startswith(three_d_root)
            kinds["mobjects"].append(e)
        elif inspect.isclass(obj) and issubclass(obj, Animation):
            e = _entry("animations", name, obj, animation_category(obj))
            kinds["animations"].append(e)
        elif inspect.isclass(obj) and issubclass(obj, Scene):
            kinds["scenes"].append(_entry("scenes", name, obj, _group(module, "manim.scene")))
        elif inspect.isclass(obj) and issubclass(obj, Camera):
            kinds["cameras"].append(_entry("cameras", name, obj, "camera"))
        elif isinstance(obj, manim.ManimColor):
            e = _entry("colors", name, obj, "color")
            e["hex"] = obj.to_hex()
            kinds["colors"].append(e)
        elif callable(obj) and module.startswith("manim.utils.rate_functions"):
            e = _entry("rate_functions", name, obj, "rate_functions")
            curve = sample_rate_func(obj)
            if curve is not None:
                e["curve"] = curve
            kinds["rate_functions"].append(e)
        elif callable(obj):
            kinds["utilities"].append(_entry("utilities", name, obj, _group(module, "manim")))
        else:
            kinds["constants"].append(
                {
                    "name": name,
                    "kind": "constants",
                    "group": type(obj).__name__,
                    "module": "manim",
                    "snippet": name,
                }
            )
    from manim.utils import rate_functions as rf

    exported = {e["name"] for e in kinds["rate_functions"]}
    for name, obj in sorted(vars(rf).items()):  # ease_* etc. live in manim.rate_functions
        if name.startswith("_") or name in exported or not inspect.isfunction(obj):
            continue
        if obj.__module__ != rf.__name__:
            continue
        curve = sample_rate_func(obj)
        if curve is None:
            continue  # helpers such as squish_rate_func take other arguments
        e = _entry("rate_functions", name, obj, "rate_functions")
        e["snippet"] = f"self.play(FadeIn(mobject), rate_func=rate_functions.{name})"
        e["curve"] = curve
        kinds["rate_functions"].append(e)
    kinds["rate_functions"].sort(key=lambda e: e["name"])

    import importlib

    import manim_stage

    for mod_name, names in STAGE_APIS.items():
        mod = importlib.import_module(f"manim_stage.{mod_name}")
        for n in names:
            obj = getattr(mod, n)
            qualified = mod_name in ("demo", "project")
            e = _entry("manim_stage", f"{mod_name}.{n}" if qualified else n, obj, mod_name)
            if qualified:
                e["snippet"] = f"from manim_stage import {mod_name}\n{mod_name}.{n}(...)"
            elif hasattr(manim_stage, n):
                e["snippet"] = f"from manim_stage import {n}"
            else:
                e["snippet"] = f"from manim_stage.{mod_name} import {n}"
            kinds["manim_stage"].append(e)
    return {
        "schema": "manim_stage.catalog",
        "version": 1,
        "manim_version": _compat.manim_build_id(),
        "plugins": manim_plugins(),
        "kinds": kinds,
    }


def catalog() -> dict[str, Any]:
    """The catalog, built once per process."""
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = build_catalog()
    return _CATALOG


def search(query: str, cat: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Entries whose name (best) or summary contains every word of ``query``."""
    words = query.lower().split()
    found = []
    for entries in (cat or catalog())["kinds"].values():
        for e in entries:
            name, text = e["name"].lower(), (e["name"] + " " + e.get("summary", "")).lower()
            if all(w in text for w in words):
                rank = 0 if name == query.lower() else 1 if all(w in name for w in words) else 2
                found.append((rank, e["name"], e))
    return [e for _, _, e in sorted(found, key=lambda t: (t[0], t[1]))]
