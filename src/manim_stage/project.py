"""Project theme and variables (spec F07, backlog 3.2; ADR-0013).

Motion Canvas has project-wide variables. manim-stage puts them, plus a visual
**theme**, in ``.manim-stage/project.json`` next to ``cues.json``, and gives scenes a
Manim-style API::

    from manim_stage import project

    theme = project.theme()               # semantic colours, fonts, code style
    Square(color=theme.accent)
    speed = project.var("speed", 1.0, min=0.25, max=4, description="animation speed")

Change the accent colour or a variable in the Studio's Project panel (or the file):
every scene that uses them re-renders with the new value, without source edits.
Plain ``manim render`` reads the same file, so CLI, Studio and CI agree.

A :class:`~manim_stage.scene.StageScene` also applies the theme's ``background`` and
default ``font`` (for ``Text``/``MarkupText``) when it starts, and restores Manim's
defaults when it ends.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cues import SIDECAR_DIR, project_root

SCHEMA = "manim_stage.project"
VERSION = 1
FILE_NAME = "project.json"

DEFAULT_COLORS: dict[str, str] = {
    "primary": "#58C4DD",  # Manim BLUE
    "secondary": "#5CD0B3",  # TEAL
    "accent": "#FFFF00",  # YELLOW
    "highlight": "#F0AC5F",  # GOLD
    "success": "#83C167",  # GREEN
    "warning": "#FF862F",  # ORANGE
    "error": "#FC6255",  # RED
    "text": "#FFFFFF",
    "muted": "#888888",
    "background": "#000000",
}
VAR_TYPES = ("number", "integer", "boolean", "string", "color", "enum")


class ProjectError(ValueError):
    pass


@dataclass
class Theme:
    colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COLORS))
    font: str | None = None  # default font for Text / MarkupText
    code_font: str | None = None  # AnimatedCode font (None: bundled JetBrains Mono)
    code_style: str | None = None  # Pygments style for AnimatedCode (None: monokai)
    tex_template: str | None = None  # MathTex/Tex template name (typography.tex_templates)

    def color(self, name: str) -> str:
        try:
            return self.colors[name]
        except KeyError:
            raise ProjectError(
                f"theme has no colour {name!r}; known: {sorted(self.colors)}"
            ) from None

    def __getattr__(self, name: str) -> str:
        colors = self.__dict__.get("colors", {})
        if name in colors:
            return colors[name]
        raise AttributeError(name)

    @property
    def background(self) -> str:
        return self.colors.get("background", DEFAULT_COLORS["background"])

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"colors": dict(self.colors)}
        for k in ("font", "code_font", "code_style", "tex_template"):
            if getattr(self, k):
                d[k] = getattr(self, k)
        return d


@dataclass
class Variable:
    name: str
    type: str
    value: Any = None
    default: Any = None
    min: float | None = None
    max: float | None = None
    options: list[Any] | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if v is not None and k != "name"}
        return d


@dataclass
class Project:
    root: Path
    path: Path
    theme: Theme = field(default_factory=Theme)
    variables: dict[str, Variable] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)  # scenes, assets, … kept as-is

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"schema": SCHEMA, "version": VERSION}
        if self.settings:
            d["settings"] = self.settings
        d["theme"] = self.theme.to_dict()
        if self.variables:
            d["variables"] = {n: v.to_dict() for n, v in sorted(self.variables.items())}
        d.update(self.extra)
        return d


def project_file(anchor: str | os.PathLike[str] | None = None) -> Path:
    override = os.environ.get("MANIM_STAGE_PROJECT")
    if override:
        return Path(override)
    anchor = Path(anchor) if anchor else Path.cwd() / "__scene__.py"
    return project_root(anchor) / SIDECAR_DIR / FILE_NAME


def load(path: str | os.PathLike[str]) -> Project:
    path = Path(path)
    root = path.parent.parent
    if not path.exists():
        return Project(root, path)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProjectError(f"{path} is not valid JSON: {e}") from e
    if d.get("schema") != SCHEMA or d.get("version") != VERSION:
        raise ProjectError(f"{path}: not a manim-stage project file v{VERSION}")
    t = d.get("theme", {})
    theme = Theme(
        {**DEFAULT_COLORS, **t.get("colors", {})},
        t.get("font"),
        t.get("code_font"),
        t.get("code_style"),
        t.get("tex_template"),
    )
    variables = {}
    for name, v in d.get("variables", {}).items():
        if v.get("type") not in VAR_TYPES:
            raise ProjectError(f"variable {name!r}: unknown type {v.get('type')!r}")
        variables[name] = Variable(
            name, **{k: v.get(k) for k in Variable.__dataclass_fields__ if k != "name"}
        )
    extra = {
        k: v
        for k, v in d.items()
        if k not in ("schema", "version", "settings", "theme", "variables")
    }
    return Project(root, path, theme, variables, d.get("settings", {}), extra)


def save(project: Project) -> Path:
    """Atomic write with a ``.bak`` copy of the previous version."""
    path = project.path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".project-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(project.to_dict(), indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


def write_dict(path: str | os.PathLike[str], data: dict[str, Any]) -> Path:
    """Validate (by loading) and atomically write a project dict (used by the Studio)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".project-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    try:
        load(tmp)  # reject anything we couldn't read back
    except ProjectError:
        Path(tmp).unlink(missing_ok=True)
        raise
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    os.replace(tmp, path)
    return path


@dataclass
class ProjectEdit:
    """An undoable change to project.json (whole document before/after)."""

    before: dict[str, Any]
    after: dict[str, Any]
    label: str

    def do(self, path: Path) -> None:
        write_dict(path, self.after)

    def undo(self, path: Path) -> None:
        write_dict(path, self.before)


# -- the scene-facing API ------------------------------------------------------------------

_CACHE: dict[Path, tuple[float, Project]] = {}
USED: dict[str, Variable] = {}  # variables read during this process (reported to the Studio)


def current(anchor: str | os.PathLike[str] | None = None) -> Project:
    """The project of the scene being rendered (nearest ``.manim-stage/project.json``)."""
    path = project_file(anchor).resolve()
    mtime = path.stat().st_mtime if path.exists() else -1.0
    cached = _CACHE.get(path)
    if cached is None or cached[0] != mtime:
        cached = (mtime, load(path))
        _CACHE[path] = cached
    return cached[1]


def theme(anchor: str | os.PathLike[str] | None = None) -> Theme:
    return current(_caller_file(anchor)).theme


def var(
    name: str,
    default: Any,
    *,
    type: str | None = None,
    min: float | None = None,
    max: float | None = None,
    options: list[Any] | None = None,
    description: str | None = None,
    anchor: str | None = None,
) -> Any:
    """A project variable: its value from ``project.json`` if set, else ``default``.

    The type is inferred from ``default`` (number, integer, boolean, string, colour
    ``"#RRGGBB"``) or given (``"enum"`` with ``options``). Values are validated; an
    invalid stored value is an error naming the variable.
    """
    kind = type or _infer(default, options)
    if kind not in VAR_TYPES:
        raise ProjectError(f"variable {name!r}: unknown type {kind!r}")
    proj = current(_caller_file(anchor))
    stored = proj.variables.get(name)
    value = default if stored is None or stored.value is None else stored.value
    value = _validate(name, kind, value, min, max, options)
    USED[name] = Variable(name, kind, value, default, min, max, options, description)
    return value


def _infer(default: Any, options: list[Any] | None) -> str:
    if options is not None:
        return "enum"
    if isinstance(default, bool):
        return "boolean"
    if isinstance(default, int):
        return "integer"
    if isinstance(default, float):
        return "number"
    if isinstance(default, str) and default.startswith("#") and len(default) in (7, 9):
        return "color"
    return "string"


def _validate(
    name: str, kind: str, value: Any, lo: float | None, hi: float | None, options: list[Any] | None
) -> Any:
    def bad(msg: str) -> ProjectError:
        return ProjectError(f"variable {name!r}: {msg} (got {value!r})")

    if kind in ("number", "integer"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise bad(f"expected a {kind}")
        if kind == "integer" and float(value) != int(value):
            raise bad("expected an integer")
        value = int(value) if kind == "integer" else float(value)
        if lo is not None and value < lo or hi is not None and value > hi:
            raise bad(f"must be between {lo} and {hi}")
    elif kind == "boolean" and not isinstance(value, bool):
        raise bad("expected true/false")
    elif kind == "color":
        import re

        if not isinstance(value, str) or not re.fullmatch(
            r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", value
        ):
            raise bad("expected a colour like #58C4DD")
    elif kind == "enum" and value not in (options or []):
        raise bad(f"must be one of {options}")
    elif kind == "string" and not isinstance(value, str):
        raise bad("expected text")
    return value


def _caller_file(anchor: Any) -> Any:
    """Find the scene file that called us (for locating the project)."""
    if anchor:
        return anchor
    import inspect

    here = Path(__file__).resolve().parent
    frame = inspect.currentframe()
    try:
        while frame is not None:
            f = frame.f_code.co_filename
            if not f.startswith("<"):
                p = Path(f).resolve()
                if not p.is_relative_to(here) and "site-packages" not in p.parts:
                    return p
            frame = frame.f_back
    finally:
        del frame
    return None


def reset_cache() -> None:
    _CACHE.clear()
    USED.clear()


def apply_theme(scene: Any, th: Theme) -> Any:
    """Apply the theme's background and Text font to a scene; returns a restore function
    (StageScene calls it at tear_down so other scenes in the process are unaffected)."""
    from manim import MarkupText, MathTex, Tex, Text

    old_bg = None
    with contextlib.suppress(Exception):
        old_bg = scene.camera.background_color
        scene.camera.background_color = th.background
    if th.font:
        Text.set_default(font=th.font)
        MarkupText.set_default(font=th.font)
    if th.tex_template:
        from .typography import tex_template

        template = tex_template(th.tex_template)
        MathTex.set_default(tex_template=template)
        Tex.set_default(tex_template=template)

    def restore() -> None:
        if th.font:
            Text.set_default()
            MarkupText.set_default()
        if th.tex_template:
            MathTex.set_default()
            Tex.set_default()
        if old_bg is not None:
            with contextlib.suppress(Exception):
                scene.camera.background_color = old_bg

    return restore
