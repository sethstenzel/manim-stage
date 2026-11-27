"""The only module allowed to touch Manim internals or version-specific APIs.

Everything else in manim_stage goes through the names defined here, so a Manim
upgrade (see docs/upstream-sync.md) only needs changes in this file and its tests.
Capabilities are detected by feature, not version: Manim's main branch still
reports 0.22.1 while carrying 0.30 APIs (ADR-0003).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import cache


class UnsupportedManimError(RuntimeError):
    """The installed Manim lacks an API manim-stage requires."""


@dataclass(frozen=True)
class ManimCapabilities:
    version: str
    evaluate: bool
    """``Manager.evaluate`` (run a scene without encoding)."""
    timeline_capture: bool
    """``Manager.evaluate(capture_timeline=True)`` and ``manim.Timeline``."""
    frame_callbacks: bool
    """``Manager.evaluate(frame_times=..., on_frame=...)``."""

    def missing(self) -> list[str]:
        return [
            name
            for name in ("evaluate", "timeline_capture", "frame_callbacks")
            if not getattr(self, name)
        ]


@cache
def capabilities() -> ManimCapabilities:
    import manim

    manager = getattr(manim, "Manager", None)
    evaluate = getattr(manager, "evaluate", None)
    params = set(inspect.signature(evaluate).parameters) if evaluate else set()
    return ManimCapabilities(
        version=getattr(manim, "__version__", "unknown"),
        evaluate=evaluate is not None,
        timeline_capture="capture_timeline" in params and hasattr(manim, "Timeline"),
        frame_callbacks={"frame_times", "on_frame"} <= params,
    )


def require_supported() -> ManimCapabilities:
    caps = capabilities()
    if missing := caps.missing():
        raise UnsupportedManimError(
            f"manim {caps.version} lacks {', '.join(missing)}. manim-stage needs the "
            "Manim 0.30 line; see docs/architecture-decisions.md (ADR-0003)."
        )
    return caps
