"""manim-stage Studio: the local editor (ADR-0010, ADR-0012).

``studio.service`` is GUI-independent and has no extra dependencies. The editor UI
(PySide6) is in the optional ``studio`` extra.
"""

from .service import PreviewMessage, PreviewService, RenderSettings, Revision

__all__ = ["PreviewMessage", "PreviewService", "RenderSettings", "Revision"]
