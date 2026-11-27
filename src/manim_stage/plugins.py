"""Studio plugin SDK, API version 1 (spec F11, backlog 4.1; ADR-0009).

A plugin is any Python object registered under the ``manim_stage.plugins`` entry-point
group (or listed in ``MANIM_STAGE_PLUGINS="pkg.module:obj,..."`` for development).
It declares the API it was written for and implements any of the hooks below; every
hook is optional::

    class BeatsPlugin:
        name = "beats"
        api_version = 1

        def timeline_events(self, timeline, api):      # extra events on your own lane
            return [{"label": "beat", "start_frame": f, "end_frame": f}
                    for f in range(0, timeline["duration_frames"], int(timeline["frame_rate"]))]

        def panels(self, api):                         # (title, factory) dock panels
            return [("Beats", lambda: QLabel("hello"))]

        def inspector_rows(self, node, api):          # extra rows for a selected Mobject
            return [("children", str(len(node.get("children", []))))]

        def commands(self, api):                       # (label, shortcut, callback)
            return [("Jump to middle", "Ctrl+M", lambda: api.seek(api.total_frames() // 2))]

        def exporters(self, api):                      # (label, fn(result) -> str message)
            return [("Copy path", lambda result: str(result.output))]

    plugin = BeatsPlugin()

Rules:
- ``api_version`` must equal :data:`API_VERSION`; otherwise the plugin is listed as
  disabled with the reason and never called (compatibility handshake).
- A hook that raises is caught, logged and the plugin disabled; Studio keeps running.
- Plugins talk to the editor only through :class:`StudioAPI`: read the timeline and
  playhead, seek, show a status message, write to the log. They get no file-system
  or network access from the Studio (they're local Python, trusted like the scene).
- Timeline events from a plugin go on the lane ``plugin:<name>``; their IDs are
  ``<scene>:plugin:<name>:<n>#0``.

Manim's own plugins (``manim.plugins`` entry points) are listed alongside, read-only.
"""

from __future__ import annotations

import importlib
import os
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any

API_VERSION = 1
GROUP = "manim_stage.plugins"
HOOKS = ("timeline_events", "panels", "inspector_rows", "commands", "exporters")


class StudioAPI:
    """What a plugin may do in the editor. The Studio passes an implementation."""

    def scene(self) -> str | None:
        raise NotImplementedError

    def timeline(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def frame(self) -> int:
        raise NotImplementedError

    def total_frames(self) -> int:
        raise NotImplementedError

    def fps(self) -> float:
        raise NotImplementedError

    def seek(self, frame: int) -> None:
        raise NotImplementedError

    def status(self, text: str) -> None:
        raise NotImplementedError

    def log(self, text: str) -> None:
        raise NotImplementedError


@dataclass
class LoadedPlugin:
    name: str
    source: str  # "entry point pkg:obj" or "env pkg:obj"
    obj: Any = None
    enabled: bool = True
    reason: str = ""
    hooks: tuple[str, ...] = ()
    errors: list[str] = field(default_factory=list)

    def call(self, hook: str, *args: Any, log: Callable[[str], None] | None = None) -> Any:
        """Call a hook safely; a failure disables the plugin and returns None."""
        if not self.enabled or hook not in self.hooks:
            return None
        try:
            return getattr(self.obj, hook)(*args)
        except Exception:
            msg = f"plugin {self.name!r} failed in {hook}: {traceback.format_exc(limit=3)}"
            self.errors.append(msg)
            self.enabled, self.reason = False, f"disabled after an error in {hook}"
            if log:
                log(msg)
            return None


def _load_target(spec: str) -> Any:
    module, _, attr = spec.partition(":")
    obj = importlib.import_module(module)
    for part in attr.split(".") if attr else []:
        obj = getattr(obj, part)
    return obj() if isinstance(obj, type) else obj


def _check(lp: LoadedPlugin) -> LoadedPlugin:
    obj = lp.obj
    version = getattr(obj, "api_version", None)
    lp.name = str(getattr(obj, "name", lp.name))
    if version != API_VERSION:
        lp.enabled = False
        lp.reason = (
            f"written for plugin API {version!r}; this Studio provides {API_VERSION}"
            if version is not None
            else "no api_version declared"
        )
    lp.hooks = tuple(h for h in HOOKS if callable(getattr(obj, h, None)))
    if lp.enabled and not lp.hooks:
        lp.enabled, lp.reason = False, "implements no hooks"
    return lp


def discover() -> list[LoadedPlugin]:
    """All registered plugins, with their compatibility status (never raises)."""
    found: list[LoadedPlugin] = []
    specs = [(ep.name, f"entry point {ep.value}", ep.load) for ep in entry_points(group=GROUP)]
    for spec in filter(None, (os.environ.get("MANIM_STAGE_PLUGINS") or "").split(",")):
        spec = spec.strip()
        specs.append((spec, f"env {spec}", lambda s=spec: _load_target(s)))
    for name, source, load in specs:
        lp = LoadedPlugin(name, source)
        try:
            obj = load()
            lp.obj = obj() if isinstance(obj, type) else obj
        except Exception as e:
            lp.enabled, lp.reason = False, f"failed to load: {type(e).__name__}: {e}"
            found.append(lp)
            continue
        found.append(_check(lp))
    return found


def manim_plugins() -> list[str]:
    """Manim's own plugins (``manim.plugins`` entry points), for display."""
    return sorted({f"{ep.name} ({ep.value})" for ep in entry_points(group="manim.plugins")})


def plugin_events(
    plugins: list[LoadedPlugin],
    timeline: dict[str, Any],
    api: StudioAPI,
    log: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Collect plugin timeline events as full SceneEvent dicts on ``plugin:<name>`` lanes."""
    out = []
    scene = timeline.get("scene", "")
    for lp in plugins:
        events = lp.call("timeline_events", timeline, api, log=log) or []
        for n, e in enumerate(events):
            try:
                start = int(e["start_frame"])
                end = int(e.get("end_frame", start))
            except (KeyError, TypeError, ValueError):
                continue
            out.append(
                {
                    "id": f"{scene}:plugin:{lp.name}:{n}#0",
                    "kind": "plugin",
                    "scene": scene,
                    "start_frame": max(0, start),
                    "end_frame": max(start, end),
                    "track": f"plugin:{lp.name}",
                    "label": str(e.get("label", lp.name)),
                    "source": None,
                    "parent_id": None,
                    "meta": {"plugin": lp.name, **dict(e.get("meta", {}))},
                }
            )
    return out
