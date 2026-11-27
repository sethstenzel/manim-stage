"""Text and LaTeX helpers (backlog MF.10, spec F07).

- :func:`fonts` lists the fonts Pango (and so Manim's ``Text``) can use.
- :func:`tex_templates` names every ``TexTemplateLibrary`` and ``TexFontTemplates``
  template; :func:`tex_template` returns one. A project can choose one in its theme
  (``theme.tex_template``), and ``StageScene`` then makes it the default for
  ``MathTex``/``Tex``.
- :func:`mathtex_snippet` writes the Manim call for a formula with coloured parts
  (``tex_to_color_map``, Manim's own substring colouring).
- :func:`render_tex_png` renders such a formula to a PNG in a child process, for the
  Studio's Text tab preview (needs LaTeX; :func:`latex_status` says whether it's there).
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def fonts() -> list[str]:
    """Font families available to Manim's ``Text`` (Pango), sorted, without duplicates."""
    import manimpango

    return sorted(
        {f for f in manimpango.list_fonts() if f and not f.startswith("@")}, key=str.lower
    )


def latex_status() -> dict[str, Any]:
    """Where ``latex`` and ``dvisvgm`` are (Manim needs both for ``MathTex``/``Tex``)."""
    latex, dvisvgm = shutil.which("latex"), shutil.which("dvisvgm")
    return {"latex": latex, "dvisvgm": dvisvgm, "ok": bool(latex and dvisvgm)}


@functools.cache
def tex_templates() -> dict[str, str]:
    """Template name → Manim expression: ``"default"``, ``"simple"``, ``"ctex"``,
    ``"threeb1b"`` (``TexTemplateLibrary``) and ``"font:<name>"`` (``TexFontTemplates``)."""
    from manim import TexFontTemplates, TexTemplate, TexTemplateLibrary

    out = {}
    for owner, prefix, tag in (
        (TexTemplateLibrary, "TexTemplateLibrary", ""),
        (TexFontTemplates, "TexFontTemplates", "font:"),
    ):
        for name in dir(owner):
            if not name.startswith("_") and isinstance(getattr(owner, name), TexTemplate):
                out[f"{tag}{name}"] = f"{prefix}.{name}"
    return dict(sorted(out.items(), key=lambda kv: (kv[0].startswith("font:"), kv[0])))


def tex_template(name: str) -> Any:
    """The ``TexTemplate`` for a name from :func:`tex_templates`."""
    import manim

    expr = tex_templates().get(name)
    if expr is None:
        raise ValueError(
            f"unknown TeX template {name!r}; see manim_stage.typography.tex_templates()"
        )
    owner, attr = expr.split(".")
    return getattr(getattr(manim, owner), attr)


def parse_color_map(text: str) -> dict[str, str]:
    """``"x: BLUE, y=#FF0000"`` → ``{"x": "BLUE", "y": "#FF0000"}``."""
    out: dict[str, str] = {}
    for part in text.split(","):
        sep = ":" if ":" in part else "=" if "=" in part else None
        if not sep:
            continue
        key, _, color = part.partition(sep)
        if key.strip() and color.strip():
            out[key.strip()] = color.strip()
    return out


def _color_expr(color: str) -> str:
    return f'"{color}"' if color.startswith("#") else color


def _tex_literal(text: str) -> str:
    """A Python literal for LaTeX source: raw string when it has backslashes."""
    if "\\" not in text:
        return json.dumps(text)
    for quote in ('"', "'", '"""', "'''"):
        if quote not in text and not text.endswith("\\"):
            return f"r{quote}{text}{quote}"
    return repr(text)


def missing_substrings(tex: str, color_map: dict[str, str]) -> list[str]:
    """Substrings that don't occur in the formula (Manim would colour nothing)."""
    return [s for s in color_map if s not in tex]


def mathtex_snippet(
    tex: str, color_map: dict[str, str] | None = None, template: str | None = None
) -> str:
    """The ``MathTex(...)`` call for ``tex`` with coloured substrings and a template."""
    args = [_tex_literal(tex)]
    if color_map:
        items = ", ".join(f"{_tex_literal(k)}: {_color_expr(v)}" for k, v in color_map.items())
        args.append(f"tex_to_color_map={{{items}}}")
    if template and template != "default":
        args.append(f"tex_template={tex_templates()[template]}")
    return f"MathTex({', '.join(args)})"


def text_snippet(text: str, font: str | None = None) -> str:
    args = [json.dumps(text)] + ([f"font={json.dumps(font)}"] if font else [])
    return f"Text({', '.join(args)})"


def render_tex_png(
    tex: str,
    color_map: dict[str, str] | None,
    template: str | None,
    out: str | os.PathLike[str],
    *,
    timeout: float = 60,
) -> Path:
    """Render the formula as a transparent PNG in a child process (LaTeX required).

    Raises ``RuntimeError`` with LaTeX's message on failure.
    """
    job = {"tex": tex, "colors": color_map or {}, "template": template, "out": str(out)}
    proc = subprocess.run(
        [sys.executable, "-m", "manim_stage.typography", json.dumps(job)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0 or not Path(out).is_file():
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-6:]
        raise RuntimeError("\n".join(tail) or "LaTeX render failed")
    return Path(out)


def _render_job(job: dict[str, Any]) -> None:
    import manim
    from manim import MathTex, Scene, tempconfig

    kwargs: dict[str, Any] = {}
    if job.get("colors"):
        kwargs["tex_to_color_map"] = {
            k: (v if v.startswith("#") else getattr(manim, v, v)) for k, v in job["colors"].items()
        }
    if job.get("template") and job["template"] != "default":
        kwargs["tex_template"] = tex_template(job["template"])
    out = Path(job["out"])

    class _Preview(Scene):
        def construct(self) -> None:
            m = MathTex(job["tex"], **kwargs)
            m.scale_to_fit_width(min(12.0, m.width * 2))
            self.add(m)
            self.wait(0.1)

    from .capture import capture

    def save(frame: Any) -> None:
        frame.image.save(out)

    with tempconfig(
        {
            "pixel_width": 960,
            "pixel_height": 270,
            "frame_height": 2.5,
            "frame_width": 2.5 * 960 / 270,
            "transparent": True,
            "background_opacity": 0.0,
            "verbosity": "ERROR",
        }
    ):
        capture(_Preview, frame_times=[0.0], on_frame=save)


if __name__ == "__main__":  # child process for render_tex_png
    _render_job(json.loads(sys.argv[1]))
