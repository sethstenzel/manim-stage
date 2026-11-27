"""Scene-tree snapshots and exposed (editable) properties (spec F08, backlog 3.3, MF.5).

**Inspect any scene.** :func:`snapshot` walks ``scene.mobjects`` and their families at a
moment of the scene and records, per Mobject: a path ID, class, ``name``, bounds,
centre, size, z-index, fill/stroke colour and opacity, stroke width, number of
updaters and of points. This is read-only and works for every Mobject (custom
subclasses included); nothing is claimed beyond what Manim's public API reports.

**Edit opted-in objects.** ``self.expose(mobject, "title", "fill_color", "scale")``
on a StageScene names a mobject and declares which properties the Studio may edit.
Saved edits live in ``.manim-stage/properties.json`` and are applied when ``expose``
runs, so ``manim render`` reproduces them; the editor previews unsaved edits through a
temporary overrides file (``MANIM_STAGE_PROPERTIES``), never touching your source.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .cues import SIDECAR_DIR, project_root

SCHEMA = "manim_stage.properties"
VERSION = 1
FILE_NAME = "properties.json"

# property -> (type, getter, setter)
EDITABLE: dict[str, tuple[str, Any, Any]] = {
    "fill_color": (
        "color",
        lambda m: m.get_fill_color().to_hex(),
        lambda m, v: m.set_fill(color=v),
    ),
    "stroke_color": (
        "color",
        lambda m: m.get_stroke_color().to_hex(),
        lambda m, v: m.set_stroke(color=v),
    ),
    "color": ("color", lambda m: m.get_color().to_hex(), lambda m, v: m.set_color(v)),
    "fill_opacity": (
        "number",
        lambda m: float(m.get_fill_opacity()),
        lambda m, v: m.set_fill(opacity=v),
    ),
    "stroke_width": (
        "number",
        lambda m: float(m.get_stroke_width()),
        lambda m, v: m.set_stroke(width=v),
    ),
    "opacity": ("number", lambda m: float(m.get_fill_opacity()), lambda m, v: m.set_opacity(v)),
    "position": (
        "point",
        lambda m: [round(float(x), 4) for x in m.get_center()],
        lambda m, v: m.move_to(np.array(v, dtype=float)),
    ),
    "scale": ("number", lambda m: 1.0, lambda m, v: m.scale(float(v))),
    "z_index": ("integer", lambda m: int(m.z_index), lambda m, v: m.set_z_index(int(v))),
}


def _hex(c: Any) -> str | None:
    try:
        return c.to_hex() if c is not None else None
    except Exception:
        return None


@dataclass
class Exposed:
    name: str
    props: tuple[str, ...]
    source: dict[str, Any] | None


def snapshot(
    scene: Any, exposed: dict[int, Exposed] | None = None, max_nodes: int = 5000
) -> list[dict[str, Any]]:
    """The scene's Mobject tree as nested dicts (``children``), top level in draw order."""
    exposed = exposed or {}
    count = 0

    def node(m: Any, path: str) -> dict[str, Any]:
        nonlocal count
        count += 1
        d: dict[str, Any] = {"id": path, "class": type(m).__name__, "module": type(m).__module__}
        name = getattr(m, "name", None)
        if name and name != type(m).__name__:
            d["name"] = str(name)
        try:
            if m.has_points() or m.submobjects:
                lo, hi = m.get_critical_point([-1, -1, 0]), m.get_critical_point([1, 1, 0])
                d["bounds"] = [
                    round(float(lo[0]), 4),
                    round(float(lo[1]), 4),
                    round(float(hi[0]), 4),
                    round(float(hi[1]), 4),
                ]
                d["center"] = [round(float(x), 4) for x in m.get_center()]
        except Exception:
            pass
        d["z_index"] = int(getattr(m, "z_index", 0))
        d["points"] = int(len(getattr(m, "points", [])))
        d["updaters"] = len(getattr(m, "updaters", []) or [])
        for key, fn in (("fill_color", "get_fill_color"), ("stroke_color", "get_stroke_color")):
            getter = getattr(m, fn, None)
            if callable(getter):
                try:
                    d[key] = _hex(getter())
                except Exception:
                    pass
        for key, fn in (("fill_opacity", "get_fill_opacity"), ("stroke_width", "get_stroke_width")):
            getter = getattr(m, fn, None)
            if callable(getter):
                try:
                    d[key] = round(float(getter()), 4)
                except Exception:
                    pass
        ex = exposed.get(id(m))
        if ex is not None:
            d["exposed"] = {
                "name": ex.name,
                "source": ex.source,
                "props": {
                    p: {"type": EDITABLE[p][0], "value": EDITABLE[p][1](m)} for p in ex.props
                },
            }
        if count < max_nodes:
            d["children"] = [node(c, f"{path}/{i}") for i, c in enumerate(m.submobjects)]
        return d

    from manim import Mobject

    def visible(m: Any) -> bool:  # skip Manim's empty placeholders (e.g. from wait())
        return not (type(m) is Mobject and not m.submobjects and not m.has_points())

    return [node(m, str(i)) for i, m in enumerate(scene.mobjects) if visible(m)]


def flatten(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    stack = list(reversed(tree))
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(reversed(n.get("children", [])))
    return out


def hit_test(tree: list[dict[str, Any]], x: float, y: float) -> dict[str, Any] | None:
    """Deepest, topmost node whose bounds contain scene point (x, y)."""
    best, best_key = None, None
    order = 0
    for n in flatten(tree):
        order += 1
        b = n.get("bounds")
        if not b or not (b[0] <= x <= b[2] and b[1] <= y <= b[3]):
            continue
        if not n.get("points") and n.get("children"):
            continue  # a group: prefer its parts
        depth = n["id"].count("/")
        key = (n.get("z_index", 0), depth, order)
        if best_key is None or key > best_key:
            best, best_key = n, key
    return best


# -- the properties sidecar -----------------------------------------------------------------


def sidecar_path(anchor: str | os.PathLike[str] | None) -> Path:
    override = os.environ.get("MANIM_STAGE_PROPERTIES")
    if override:
        return Path(override)
    anchor = Path(anchor) if anchor else Path.cwd() / "__scene__.py"
    return project_root(anchor) / SIDECAR_DIR / FILE_NAME


def load(path: str | os.PathLike[str]) -> dict[str, dict[str, dict[str, Any]]]:
    """``{scene: {exposed name: {property: value}}}``"""
    path = Path(path)
    if not path.exists():
        return {}
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema") != SCHEMA or d.get("version") != VERSION:
        raise ValueError(f"{path}: not a manim-stage properties file v{VERSION}")
    return d.get("scenes", {})


def save(path: str | os.PathLike[str], scenes: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    doc = {
        "schema": SCHEMA,
        "version": VERSION,
        "scenes": {s: v for s, v in sorted(scenes.items()) if v},
    }
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".props-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


def apply(mobject: Any, props: dict[str, Any]) -> None:
    for key, value in props.items():
        if key in EDITABLE:
            EDITABLE[key][2](mobject, value)


def as_python(var: str, props: dict[str, Any]) -> str:
    """The same edits as Python, for 'Copy as Python' (a reviewable code change)."""
    lines = []
    for key, value in props.items():
        if key in ("fill_color", "stroke_color"):
            fn = "set_fill" if key == "fill_color" else "set_stroke"
            lines.append(f'{var}.{fn}(color="{value}")')
        elif key == "color":
            lines.append(f'{var}.set_color("{value}")')
        elif key == "fill_opacity":
            lines.append(f"{var}.set_fill(opacity={value})")
        elif key == "stroke_width":
            lines.append(f"{var}.set_stroke(width={value})")
        elif key == "opacity":
            lines.append(f"{var}.set_opacity({value})")
        elif key == "position":
            lines.append(f"{var}.move_to([{', '.join(str(v) for v in value)}])")
        elif key == "scale":
            lines.append(f"{var}.scale({value})")
        elif key == "z_index":
            lines.append(f"{var}.set_z_index({value})")
    return "\n".join(lines)


@dataclass
class PropertiesEdit:
    """An undoable change to properties.json (whole document before/after)."""

    before: dict[str, Any]
    after: dict[str, Any]
    label: str

    def do(self, path: Path) -> None:
        save(path, self.after)

    def undo(self, path: Path) -> None:
        save(path, self.before)


def merged(saved: dict[str, Any], scene: str, name: str, props: dict[str, Any]) -> dict[str, Any]:
    """``saved`` with ``props`` set for one exposed object (a new dict)."""
    out = json.loads(json.dumps(saved))
    out.setdefault(scene, {}).setdefault(name, {}).update(props)
    return out
