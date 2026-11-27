"""Read and edit a project's ``manim.cfg`` (backlog MF.6).

Manim reads ``manim.cfg`` from the folder it runs in; its ``[CLI]`` section sets
defaults for every ``manim render`` there (Manim's own mechanism, so plain Manim, the
Studio preview and Studio exports all agree). The Studio's **Config** tab edits the
common keys of that section; other sections and keys are kept as they are.

Preview resolution and frame rate still come from the Studio's quality choice; the
keys here that change preview pixels are ``background_color`` and
``background_opacity``.
"""

from __future__ import annotations

import configparser
import io
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILE = "manim.cfg"
SECTION = "CLI"


@dataclass(frozen=True)
class Key:
    name: str
    type: str  # color | integer | number | boolean | enum | string
    label: str
    options: tuple[str, ...] = ()
    preview: bool = False  # changes preview pixels


KEYS: tuple[Key, ...] = (
    Key("background_color", "color", "Background colour", preview=True),
    Key("background_opacity", "number", "Background opacity (0–1)", preview=True),
    Key("frame_rate", "number", "Frame rate (export)"),
    Key("pixel_width", "integer", "Width in pixels (export)"),
    Key("pixel_height", "integer", "Height in pixels (export)"),
    Key("format", "enum", "Output format", ("mp4", "mov", "webm", "gif", "png")),
    Key("transparent", "boolean", "Transparent background"),
    Key("save_sections", "boolean", "Save each section as its own video"),
    Key("renderer", "enum", "Renderer (export)", ("cairo", "opengl")),
    Key("media_dir", "string", "Media folder"),
)
BY_NAME = {k.name: k for k in KEYS}


class ConfigError(ValueError):
    pass


def path_for(scene_file: str | os.PathLike[str]) -> Path:
    """The ``manim.cfg`` Manim uses for a scene: in the folder ``manim`` runs from
    (the scene's folder, which is where the Studio runs it)."""
    return Path(scene_file).resolve().parent / FILE


def _parser() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # keep key case, like Manim
    return cp


def read(path: str | os.PathLike[str]) -> dict[str, str]:
    """The ``[CLI]`` section as strings (``{}`` when there is no file or section)."""
    p = Path(path)
    if not p.is_file():
        return {}
    cp = _parser()
    cp.read(p, encoding="utf-8")
    return dict(cp[SECTION]) if cp.has_section(SECTION) else {}


def validate(name: str, value: str) -> str:
    key = BY_NAME.get(name)
    if key is None:
        return value
    v = value.strip()
    if key.type == "color" and not re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?|[A-Za-z_]+", v):
        raise ConfigError(f"{name}: expected a colour like #1E1E1E or a Manim name (got {value!r})")
    if key.type == "integer":
        if not v.isdigit() or int(v) <= 0:
            raise ConfigError(f"{name}: expected a positive whole number (got {value!r})")
    if key.type == "number":
        try:
            f = float(v)
        except ValueError:
            raise ConfigError(f"{name}: expected a number (got {value!r})") from None
        if f < 0 or (name == "background_opacity" and f > 1):
            raise ConfigError(f"{name}: out of range (got {value!r})")
    if key.type == "boolean" and v.lower() not in ("true", "false"):
        raise ConfigError(f"{name}: expected True or False (got {value!r})")
    if key.type == "enum" and v not in key.options:
        raise ConfigError(f"{name}: must be one of {list(key.options)} (got {value!r})")
    return v


def render(path: str | os.PathLike[str], values: dict[str, str | None]) -> str:
    """The file text after setting ``values`` in ``[CLI]`` (``None`` or ``""`` removes
    a key). Other sections, keys and their order are kept."""
    p = Path(path)
    cp = _parser()
    if p.is_file():
        cp.read(p, encoding="utf-8")
    if not cp.has_section(SECTION):
        cp.add_section(SECTION)
    for name, value in values.items():
        if value is None or str(value).strip() == "":
            cp.remove_option(SECTION, name)
        else:
            cp.set(SECTION, name, validate(name, str(value)))
    buf = io.StringIO()
    cp.write(buf)
    return buf.getvalue()


def write(path: str | os.PathLike[str], values: dict[str, str | None]) -> Path:
    """Apply ``values`` and save atomically (keeping a ``.bak`` of the old file)."""
    p = Path(path)
    text = render(p, values)
    if p.is_file():
        p.with_name(p.name + ".bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)
    return p


def effective(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Manim's defaults for the keys we edit, overlaid with the file's values."""
    from manim import config

    out: dict[str, Any] = {}
    for k in KEYS:
        try:
            v = config[k.name]
        except (KeyError, AttributeError):
            v = None
        if k.name == "background_color" and v is not None:
            v = v.to_hex() if hasattr(v, "to_hex") else str(v)
        if k.name == "renderer" and v is not None:
            v = getattr(v, "value", str(v))
        out[k.name] = v
    out.update(read(path))
    return out


@dataclass
class CfgEdit:
    """An undoable edit of ``manim.cfg`` (whole-file before/after text)."""

    before: str | None
    after: str
    label: str = "Edit manim.cfg"

    def do(self, path: Path) -> None:
        _put(path, self.after)

    def undo(self, path: Path) -> None:
        if self.before is None:
            path.unlink(missing_ok=True)
        else:
            _put(path, self.before)


def _put(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def edit_for(path: str | os.PathLike[str], values: dict[str, str | None]) -> CfgEdit:
    p = Path(path)
    before = p.read_text(encoding="utf-8") if p.is_file() else None
    return CfgEdit(before, render(p, values))
