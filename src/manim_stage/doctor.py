"""Environment checks (``manim-stage doctor``; backlog 1.6, MF.9).

What a Manim scene can use depends on the machine: LaTeX (for ``Tex``/``MathTex``),
fonts (``Text``), FFmpeg codecs via PyAV (export formats), Qt (the Studio). This
reports each in Manim's terms so missing pieces are explained before a render fails.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str


def _manim() -> list[Check]:
    from . import _compat

    try:
        _compat.require_supported()
    except Exception as e:  # UnsupportedManimError or import failure
        return [Check("Manim", "fail", str(e))]
    return [Check("Manim", "ok", f"{_compat.manim_build_id()} (evaluate, timeline, frames)")]


def _cairo() -> Check:
    try:
        import cairo

        return Check("Cairo renderer", "ok", f"pycairo {cairo.version}")
    except Exception as e:
        return Check("Cairo renderer", "fail", f"pycairo unavailable: {e}")


def _fonts() -> Check:
    try:
        import manimpango

        n = len(manimpango.list_fonts())
        return Check("Text (Pango fonts)", "ok", f"manimpango {manimpango.__version__}, {n} fonts")
    except Exception as e:
        return Check("Text (Pango fonts)", "fail", f"manimpango unavailable: {e}")


def _latex() -> Check:
    latex, dvisvgm = shutil.which("latex"), shutil.which("dvisvgm")
    if latex and dvisvgm:
        return Check("Tex / MathTex", "ok", f"latex: {latex}; dvisvgm: {dvisvgm}")
    missing = [n for n, p in (("latex", latex), ("dvisvgm", dvisvgm)) if not p]
    return Check(
        "Tex / MathTex",
        "warn",
        f"{' and '.join(missing)} not found: Tex/MathTex won't render (Text still works). "
        "Install a TeX distribution (e.g. MiKTeX, TeX Live, MacTeX).",
    )


def _codecs() -> list[Check]:
    try:
        import av
    except Exception as e:
        return [Check("FFmpeg (PyAV)", "fail", f"PyAV unavailable: {e}")]
    libs = getattr(av, "library_versions", {})
    out = [
        Check(
            "FFmpeg (PyAV)",
            "ok",
            f"PyAV {av.__version__}; libavcodec {'.'.join(map(str, libs.get('libavcodec', ())))}",
        )
    ]
    wanted = {
        "mp4 (H.264)": ("libx264", "h264"),
        "webm (VP9)": ("libvpx-vp9", "vp9"),
        "mov (ProRes, alpha)": ("prores_ks", "prores"),
        "gif": ("gif",),
    }
    for label, names in wanted.items():
        found = None
        for n in names:
            try:
                av.codec.Codec(n, "w")
                found = n
                break
            except Exception:
                continue
        out.append(
            Check(
                f"Export {label}",
                "ok" if found else "warn",
                f"encoder {found}" if found else "no encoder in this FFmpeg build",
            )
        )
    return out


def _qt() -> Check:
    try:
        import PySide6
    except ImportError:
        return Check("Studio (PySide6)", "warn", "not installed: pip install 'manim-stage[studio]'")
    v = PySide6.__version__
    if sys.version_info < (3, 12) and v.startswith("6.12.0"):
        return Check(
            "Studio (PySide6)",
            "fail",
            f"PySide6 {v} crashes on Python 3.11 (refcount bug); use PySide6 < 6.12",
        )
    return Check("Studio (PySide6)", "ok", f"PySide6 {v}")


def _plugins() -> Check:
    from importlib.metadata import entry_points

    eps = entry_points(group="manim.plugins")
    names = sorted({ep.name for ep in eps})
    return Check("Manim plugins", "ok", ", ".join(names) if names else "none installed")


def run_checks() -> list[Check]:
    checks = [Check("Python", "ok", sys.version.split()[0])]
    checks += _manim()
    checks += [_cairo(), _fonts(), _latex()]
    checks += _codecs()
    checks += [_qt(), _plugins()]
    return checks
