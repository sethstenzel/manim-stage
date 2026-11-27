"""Asset inventory and validation (spec F10, backlog 3.5).

Before a render, find every asset a project's scenes refer to and check that it
exists, resolving names the way Manim does: the path as written (relative to the
folder you render from, i.e. the scene's folder), else ``assets_dir`` + name +
Manim's default extensions (``ImageMobject`` tries .jpg/.jpeg/.png/.gif/.ico,
``SVGMobject`` .svg, ``add_sound`` .wav/.mp3).

References come from:

- the scene source: string literals passed to ``ImageMobject``, ``SVGMobject``,
  ``add_sound``, ``self.narration(file=…)``, ``VideoMobject``-like calls and
  ``Text(font=…)`` (fonts are checked against Pango's font list);
- the audio workspace (``.manim-stage/audio.json``) clip files.

Names built at run time (f-strings, variables) can't be checked statically; they are
listed as "dynamic" so you know, and the runner's dependency tracking still records
the files a render actually opened.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KINDS = {
    "image": (".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp", ".tif", ".tiff"),
    "svg": (".svg",),
    "audio": (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"),
    "video": (".mp4", ".mov", ".webm", ".mkv", ".avi"),
    "font": (".ttf", ".otf"),
    "data": (".json", ".csv", ".txt", ".yaml", ".yml", ".toml"),
}
# call name -> (kind, Manim's default extensions)
CALLS = {
    "ImageMobject": ("image", (".jpg", ".jpeg", ".png", ".gif", ".ico")),
    "ImageMobjectFromCamera": ("image", ()),
    "SVGMobject": ("svg", (".svg",)),
    "add_sound": ("audio", (".wav", ".mp3")),
    "narration": ("audio", ()),
}


@dataclass
class AssetRef:
    name: str  # as written in the source (or the clip file)
    kind: str
    source: str  # "lesson.py:12" or ".manim-stage/audio.json"
    resolved: Path | None = None
    dynamic: bool = False

    @property
    def ok(self) -> bool:
        return self.dynamic or self.resolved is not None


@dataclass
class Inventory:
    refs: list[AssetRef] = field(default_factory=list)
    fonts_missing: list[tuple[str, str]] = field(default_factory=list)  # (font, source)

    @property
    def missing(self) -> list[AssetRef]:
        return [r for r in self.refs if not r.ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "assets": [
                {
                    "name": r.name,
                    "kind": r.kind,
                    "source": r.source,
                    "resolved": str(r.resolved) if r.resolved else None,
                    "dynamic": r.dynamic,
                    "ok": r.ok,
                    "bytes": r.resolved.stat().st_size if r.resolved else None,
                }
                for r in self.refs
            ],
            "fonts_missing": [{"font": f, "source": s} for f, s in self.fonts_missing],
        }


def kind_of(path: str | Path) -> str:
    ext = Path(str(path)).suffix.lower()
    return next((k for k, exts in KINDS.items() if ext in exts), "other")


def resolve(name: str, base: Path, assets_dir: Path, extensions: tuple[str, ...]) -> Path | None:
    """Manim's ``seek_full_path_from_defaults``, relative to ``base``."""
    candidates = [Path(name).expanduser()]
    candidates += [assets_dir / f"{name}{ext}" for ext in ("", *extensions)]
    for c in candidates:
        p = c if c.is_absolute() else base / c
        if p.exists():
            return p.resolve()
    return None


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _string(node: ast.AST | None) -> tuple[str | None, bool]:
    """(value, dynamic) of an argument expression."""
    if node is None:
        return None, False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    return None, True


def scan_source(path: Path) -> list[tuple[str, str, int, bool, tuple[str, ...]]]:
    """(name, kind, line, dynamic, default extensions) of asset references in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in CALLS:
            kind, exts = CALLS[name]
            arg = node.args[0] if node.args else None
            if name == "narration":
                arg = next((k.value for k in node.keywords if k.arg == "file"), None)
                if arg is None:
                    continue
            if arg is None:
                arg = next(
                    (
                        k.value
                        for k in node.keywords
                        if k.arg in ("filename_or_array", "file_name", "sound_file")
                    ),
                    None,
                )
            value, dynamic = _string(arg)
            if value is None and not dynamic:
                continue
            out.append((value or "<dynamic>", kind, node.lineno, dynamic, exts))
        font = next((k.value for k in node.keywords if k.arg == "font"), None)
        if name in ("Text", "MarkupText", "Paragraph", "Code", "AnimatedCode") and font is not None:
            value, dynamic = _string(font)
            if value:
                out.append((value, "font", node.lineno, False, ()))
    return out


def inventory(files: list[str | os.PathLike[str]], *, assets_dir: str | None = None) -> Inventory:
    """Check every asset the given scene files (and their project's audio clips) use."""
    from . import audio as audio_core

    inv = Inventory()
    fonts: set[str] | None = None
    seen_clip_files: set[Path] = set()
    for f in files:
        f = Path(f).resolve()
        base = f.parent
        adir = base / (assets_dir or "./")
        for name, kind, line, dynamic, exts in scan_source(f):
            src = f"{f.name}:{line}"
            if kind == "font":
                if fonts is None:
                    fonts = _font_names()
                if name not in fonts and name.lower() not in {x.lower() for x in fonts}:
                    inv.fonts_missing.append((name, src))
                continue
            ref = AssetRef(name, kind, src, dynamic=dynamic)
            if not dynamic:
                ref.resolved = resolve(name, base, adir, exts)
            inv.refs.append(ref)
        side = audio_core.sidecar_path(f)
        if side.exists() and side not in seen_clip_files:
            seen_clip_files.add(side)
            root = side.parent.parent
            for scene, clips in audio_core.load(side).scenes.items():
                for c in clips:
                    p = audio_core.resolve_file(c.file, root)
                    inv.refs.append(
                        AssetRef(
                            c.file,
                            "audio",
                            f".manim-stage/audio.json ({scene})",
                            p.resolve() if p.exists() else None,
                        )
                    )
    return inv


def _font_names() -> set[str]:
    try:
        import manimpango

        from .code import register_bundled_fonts

        register_bundled_fonts()
        return set(manimpango.list_fonts())
    except Exception:
        return set()


def format_report(inv: Inventory) -> str:
    lines = []
    for r in inv.refs:
        mark = "dyn " if r.dynamic else ("ok  " if r.ok else "MISS")
        where = (
            r.resolved.name
            if r.resolved
            else ("(computed at run time)" if r.dynamic else "not found")
        )
        lines.append(f"{mark} {r.kind:6s} {r.name:40s} {r.source:28s} {where}")
    for font, src in inv.fonts_missing:
        lines.append(f"MISS font   {font:40s} {src:28s} not installed (Pango)")
    if not lines:
        lines.append("no assets referenced")
    return "\n".join(lines)
