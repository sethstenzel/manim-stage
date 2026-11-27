"""manim-stage: optional authoring layer and local Studio editor for ManimCE.

Scene APIs (import Manim lazily, so ``import manim_stage`` stays cheap)::

    from manim_stage import StageScene, StageMixin   # self.cue(...), self.narration(...)
    from manim_stage import AnimatedCode, CodeRange  # code animation
"""

from __future__ import annotations

from typing import Any

__version__ = "0.0.1.dev0"

_LAZY = {
    "StageScene": ("manim_stage.scene", "StageScene"),
    "StageMixin": ("manim_stage.scene", "StageMixin"),
    "CueError": ("manim_stage.cues", "CueError"),
    "AnimatedCode": ("manim_stage.code", "AnimatedCode"),
    "CodeRange": ("manim_stage.code", "CodeRange"),
}

__all__ = ["AnimatedCode", "CodeRange", "CueError", "StageMixin", "StageScene", "__version__"]


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(f"module 'manim_stage' has no attribute {name!r}")
