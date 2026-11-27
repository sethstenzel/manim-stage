"""Sample manim-stage Studio plugin (spec F11 accept): a "Beats" timeline track and an
inspector panel, added without modifying Studio core.

Install it (``pip install -e examples/plugins/stage_beats``) and restart the Studio; or,
for development, ``MANIM_STAGE_PLUGINS=stage_beats:plugin``.
"""

from __future__ import annotations

from typing import Any


class BeatsPlugin:
    name = "beats"
    api_version = 1

    def __init__(self, bpm: float = 60.0) -> None:
        self.bpm = bpm
        self.label = None

    def timeline_events(self, timeline: dict[str, Any], api: Any) -> list[dict[str, Any]]:
        """A marker on every beat, on this plugin's own lane."""
        step = timeline["frame_rate"] * 60.0 / self.bpm
        n = int(timeline["duration_frames"] / step) + 1
        return [
            {"label": f"beat {i + 1}", "start_frame": round(i * step), "meta": {"bpm": self.bpm}}
            for i in range(n)
        ]

    def panels(self, api: Any) -> list[tuple[str, Any]]:
        def make() -> Any:
            from PySide6.QtWidgets import QLabel

            self.label = QLabel(f"{self.bpm:g} BPM: one marker per beat on the Beats lane.")
            self.label.setAccessibleName("Beats plugin panel")
            self.label.setWordWrap(True)
            return self.label

        return [("Beats", make)]

    def inspector_rows(self, node: dict[str, Any], api: Any) -> list[tuple[str, str]]:
        kids = len(node.get("children", []))
        return [("children", str(kids)), ("at frame", str(api.frame()))]

    def commands(self, api: Any) -> list[tuple[str, str, Any]]:
        def next_beat() -> None:
            step = api.fps() * 60.0 / self.bpm
            api.seek(min(int((api.frame() // step + 1) * step), api.total_frames() - 1))

        return [("Next beat", "Ctrl+B", next_beat)]

    def exporters(self, api: Any) -> list[tuple[str, Any]]:
        return [
            (
                "Beat count",
                lambda result: f"{api.total_frames() / api.fps() * self.bpm / 60:.0f} beats",
            )
        ]


plugin = BeatsPlugin()


class OldPlugin:
    """Written for a future plugin API: the Studio must disable it (handshake)."""

    name = "old"
    api_version = 99

    def panels(self, api: Any) -> list:
        raise AssertionError("never called")


old_plugin = OldPlugin()
