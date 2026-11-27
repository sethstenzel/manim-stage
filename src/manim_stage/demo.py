"""Interactive demo parameters (spec F12, backlog 4.3).

A *demo parameter* is a knob for exploring a scene in the Studio: array size, speed,
which algorithm, a colour. The Studio shows a control for each one (Demo tab) and
re-renders the preview as you move it. These values are **editor-time only**: an
export is a linear video rendered with the defaults, unless you explicitly tick
*Bake demo values* in the Export dialog. Use project variables
(:func:`manim_stage.project.var`) for settings that should be saved and always apply.

::

    from manim_stage import demo

    class Sort(Scene):
        def construct(self):
            n = demo.param("n", 6, min=2, max=12)
            algo = demo.param("algorithm", "bubble", options=["bubble", "insertion"])

``param`` returns the default unless the Studio (or a test) points ``MANIM_STAGE_DEMO``
at a JSON object of overrides. Values are validated like project variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .project import VAR_TYPES, ProjectError, Variable, _infer, _validate

ENV = "MANIM_STAGE_DEMO"
USED: dict[str, dict[str, Any]] = {}  # params read in this process (reported to the Studio)

_cache: tuple[str, float, dict[str, Any]] | None = None


def overrides() -> dict[str, Any]:
    """The current override values (``{}`` when no override file is set)."""
    global _cache
    path = os.environ.get(ENV)
    if not path:
        return {}
    p = Path(path)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return {}
    if _cache and _cache[0] == path and _cache[1] == mtime:
        return _cache[2]
    data = json.loads(p.read_text(encoding="utf-8") or "{}")
    if not isinstance(data, dict):
        raise ProjectError(f"{path}: demo overrides must be a JSON object")
    _cache = (path, mtime, data)
    return data


def param(
    name: str,
    default: Any,
    *,
    type: str | None = None,
    min: float | None = None,
    max: float | None = None,
    step: float | None = None,
    options: list[Any] | None = None,
    description: str | None = None,
) -> Any:
    """A demo parameter: the Studio's live value, else ``default`` (always in exports)."""
    kind = type or _infer(default, options)
    if kind not in VAR_TYPES:
        raise ProjectError(f"demo parameter {name!r}: unknown type {kind!r}")
    default = _validate(name, kind, default, min, max, options)
    live = overrides()
    value = _validate(name, kind, live[name], min, max, options) if name in live else default
    info = Variable(name, kind, value, default, min, max, options, description).to_dict()
    if step is not None:
        info["step"] = step
    USED[name] = {"name": name, **info, "overridden": name in live}
    return value


def used() -> list[dict[str, Any]]:
    """Parameters read so far, sorted by name (sent to the Studio with the timeline)."""
    return [USED[n] for n in sorted(USED)]


def write_overrides(path: str | os.PathLike[str], values: dict[str, Any]) -> Path:
    """Write an override file for ``MANIM_STAGE_DEMO``."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(values, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return p
