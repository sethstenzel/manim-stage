"""Manim quality presets for the UI (never hardcoded: read from Manim)."""

from __future__ import annotations

PREVIEW_QUALITIES = (
    "low_quality",
    "medium_quality",
    "high_quality",
    "production_quality",
    "fourk_quality",
)


def manim_qualities() -> dict[str, dict]:
    """Manim's own quality presets (``manim.constants.QUALITIES``), never hardcoded."""
    from manim.constants import QUALITIES

    return {k: dict(QUALITIES[k]) for k in PREVIEW_QUALITIES if k in QUALITIES}


def quality_label(key: str, q: dict) -> str:
    name = key.replace("_quality", "").replace("fourk", "4K").capitalize()
    flag = f"  (-q{q['flag']})" if q.get("flag") else ""
    return f"{name} {q['pixel_height']}p{q['frame_rate']}{flag}"
