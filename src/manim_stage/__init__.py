"""manim-stage: optional authoring layer and local Studio editor for ManimCE.

Scene APIs (import Manim lazily, so ``import manim_stage`` stays cheap)::

    from manim_stage import StageScene, StageMixin   # self.cue(...), self.narration(...)
    from manim_stage import AnimatedCode, CodeRange  # code animation
    from manim_stage import Signal, computed, bind     # reactive values (ValueTracker-based)
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"

_LAZY = {
    "StageScene": ("manim_stage.scene", "StageScene"),
    "StageMixin": ("manim_stage.scene", "StageMixin"),
    "CueError": ("manim_stage.cues", "CueError"),
    "AnimatedCode": ("manim_stage.code", "AnimatedCode"),
    "Signal": ("manim_stage.signals", "Signal"),
    "computed": ("manim_stage.signals", "computed"),
    "bind": ("manim_stage.signals", "bind"),
    "effect": ("manim_stage.signals", "effect"),
    "all_of": ("manim_stage.flow", "all_of"),
    "chain": ("manim_stage.flow", "chain"),
    "delay": ("manim_stage.flow", "delay"),
    "sequence": ("manim_stage.flow", "sequence"),
    "loop": ("manim_stage.flow", "loop"),
    "tween": ("manim_stage.flow", "tween"),
    "enter": ("manim_stage.flow", "enter"),
    "exit": ("manim_stage.flow", "exit"),
    "CodeRange": ("manim_stage.code", "CodeRange"),
}

__all__ = [
    "AnimatedCode",
    "CodeRange",
    "CueError",
    "Signal",
    "StageMixin",
    "StageScene",
    "__version__",
    "bind",
    "computed",
    "effect",
]


def __getattr__(name: str) -> Any:
    if name == "project":
        import importlib

        return importlib.import_module("manim_stage.project")
    if name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(f"module 'manim_stage' has no attribute {name!r}")
