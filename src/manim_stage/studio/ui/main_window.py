"""Studio main window: scene picker, viewport, transport, log (spec F01).

Layout (our own; no Motion Canvas UI code or assets):

    ┌ toolbar: Scene ▾ · Quality ▾ · Render · Cancel · renderer badge · theme ┐
    │ viewport                                                    │ (docks) │
    ├ transport: ⏮ ◀| ▶ |▶ ⏭  ───scrub bar───  00:01.04  [12] /89  1× ⟲    ┤
    └ log / errors (dock)                                                    ┘

Terminology follows Manim (ADR-0013): Scene, quality (``-ql``…``-qk``), frame rate,
renderer, sections.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..playback import Playback
from ..service import PreviewMessage, PreviewService, RenderSettings
from .bridge import ServiceBridge
from .log_panel import LogPanel, open_in_editor
from .theme import apply_theme, is_dark
from .transport import TransportBar
from .viewport import Viewport

PREVIEW_QUALITIES = ("low_quality", "medium_quality", "high_quality",
                     "production_quality", "fourk_quality")  # fmt: skip


def manim_qualities() -> dict[str, dict]:
    """Manim's own quality presets (``manim.constants.QUALITIES``), never hardcoded."""
    from manim.constants import QUALITIES

    return {k: dict(QUALITIES[k]) for k in PREVIEW_QUALITIES if k in QUALITIES}


def quality_label(key: str, q: dict) -> str:
    name = key.replace("_quality", "").replace("fourk", "4K").capitalize()
    flag = f"  (-q{q['flag']})" if q.get("flag") else ""
    return f"{name} {q['pixel_height']}p{q['frame_rate']}{flag}"


def studio_settings() -> QSettings:
    """User preferences (theme, …) in an INI file; tests redirect it with QSettings.setPath."""
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "manim-stage", "studio")


class MainWindow(QMainWindow):
    def __init__(self, service: PreviewService, *, scene: str | None = None,
                 quality: str = "low_quality", workers: int = 1) -> None:  # fmt: skip
        super().__init__()
        self.service = service
        self.workers = max(1, workers)
        self.settings_store = studio_settings()
        self.setWindowTitle(f"manim-stage Studio — {service.file.name}")
        self.resize(1200, 800)

        self.playback = Playback(time.monotonic)
        self.scenes: list[dict] = []
        self.requested_scene = scene
        self.notice = ""

        # widgets
        self.viewport = Viewport()
        self.transport = TransportBar()
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.viewport, 1)
        lay.addWidget(self.transport)
        self.setCentralWidget(central)

        self.log = LogPanel()
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("log_dock")
        self.log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.resizeDocks([self.log_dock], [150], Qt.Orientation.Vertical)

        self._build_toolbar(quality)
        self._build_actions()
        self.status_label = QLabel("")
        self.status_label.setAccessibleName("Render status")
        self.statusBar().addWidget(self.status_label, 1)

        # wiring
        self.bridge = ServiceBridge(service, self)
        self.bridge.message.connect(self.on_message)
        self.transport.playToggled.connect(self.toggle_play)
        self.transport.stepRequested.connect(self.step)
        self.transport.jumpRequested.connect(self.jump)
        self.transport.speedChanged.connect(self.playback.set_speed)
        self.transport.loopToggled.connect(self._set_loop)
        self.transport.frameEntered.connect(self.seek)
        self.transport.scrub.seek.connect(self.seek)
        self.log.openSource.connect(open_in_editor)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(10)

        self.refresh_scenes()

    # -- toolbar & actions ------------------------------------------------------------

    def _build_toolbar(self, quality: str) -> None:
        tb = QToolBar("Main", self)
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addWidget(QLabel(" Scene "))
        self.scene_box = QComboBox()
        self.scene_box.setAccessibleName("Scene")
        self.scene_box.setToolTip("Scene class to preview")
        self.scene_box.setMinimumWidth(200)
        self.scene_box.activated.connect(self._scene_chosen)
        tb.addWidget(self.scene_box)
        tb.addWidget(QLabel("  Quality "))
        self.quality_box = QComboBox()
        self.quality_box.setAccessibleName("Preview quality")
        self.quality_box.setToolTip("Preview resolution and frame rate (Manim quality presets)")
        self.qualities = manim_qualities()
        for key, q in self.qualities.items():
            self.quality_box.addItem(quality_label(key, q), key)
        idx = self.quality_box.findData(quality)
        self.quality_box.setCurrentIndex(max(idx, 0))
        self.quality_box.activated.connect(lambda _i: self.render())
        tb.addWidget(self.quality_box)
        tb.addSeparator()
        self.act_render = QAction("Render", self)
        self.act_render.setShortcut(QKeySequence("Ctrl+R"))
        self.act_render.setToolTip("Re-render the scene (Ctrl+R)")
        self.act_render.triggered.connect(self.render)
        tb.addAction(self.act_render)
        self.act_cancel = QAction("Cancel", self)
        self.act_cancel.setShortcut(QKeySequence("Esc"))
        self.act_cancel.setToolTip("Cancel rendering (Esc)")
        self.act_cancel.triggered.connect(self.service.cancel)
        tb.addAction(self.act_cancel)
        tb.addSeparator()
        self.renderer_badge = QLabel(" Renderer: Cairo · preview from cached frames ")
        self.renderer_badge.setAccessibleName("Renderer capabilities")
        self.renderer_badge.setToolTip(
            "Frames are rendered by Manim's Cairo renderer and cached for scrubbing.\n"
            "OpenGL scenes are not supported in the Studio preview yet."
        )
        tb.addWidget(self.renderer_badge)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.act_theme = QAction("Light theme", self)
        self.act_theme.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.act_theme.setToolTip("Switch dark/light theme (Ctrl+Shift+T)")
        self.act_theme.triggered.connect(self.toggle_theme)
        tb.addAction(self.act_theme)

    def _build_actions(self) -> None:
        def act(text: str, keys: str | list[str], fn) -> QAction:
            a = QAction(text, self)
            seqs = [QKeySequence(k) for k in ([keys] if isinstance(keys, str) else keys)]
            a.setShortcuts(seqs)
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            a.triggered.connect(fn)
            self.addAction(a)
            return a

        self.shortcuts = {
            "play": act("Play/pause", "Space", self.toggle_play),
            "prev": act("Previous frame", "Left", lambda: self.step(-1)),
            "next": act("Next frame", "Right", lambda: self.step(1)),
            "back_1s": act("Back 1 second", "Shift+Left", lambda: self.step_seconds(-1)),
            "fwd_1s": act("Forward 1 second", "Shift+Right", lambda: self.step_seconds(1)),
            "start": act("Go to start", "Home", lambda: self.jump("start")),
            "end": act("Go to end", "End", lambda: self.jump("end")),
            "loop": act("Toggle loop", "L", self.transport.btn_loop.toggle),
            "range_in": act("Set range start", "I", self.set_range_start),
            "range_out": act("Set range end", "O", self.set_range_end),
            "range_clear": act("Clear range", "Alt+X", self.clear_range),
            "fit": act("Zoom to fit", "Ctrl+0", self.viewport.fit),
            "zoom_100": act("Zoom 100%", "Ctrl+1", lambda: self.viewport.set_zoom(1.0)),
            "zoom_in": act("Zoom in", ["Ctrl++", "Ctrl+="], self.viewport.zoom_in),
            "zoom_out": act("Zoom out", "Ctrl+-", self.viewport.zoom_out),
        }

    # -- scenes & rendering -----------------------------------------------------------

    def refresh_scenes(self) -> None:
        """Re-discover scene classes without blocking the GUI."""
        self.status_label.setText("Looking for scenes…")
        threading.Thread(target=self.service.discover_scenes, daemon=True).start()

    def current_scene(self) -> str | None:
        data = self.scene_box.currentData()
        return data or self.requested_scene

    def _scene_chosen(self, _index: int) -> None:
        self.playback.seek(0)
        self.render()

    def render_settings(self) -> RenderSettings:
        q = self.qualities.get(self.quality_box.currentData() or "low_quality", {})
        return RenderSettings(fps=float(q.get("frame_rate", 15)),
                              width=int(q.get("pixel_width", 854)),
                              height=int(q.get("pixel_height", 480)),
                              workers=self.workers)  # fmt: skip

    def render(self) -> None:
        scene = self.current_scene()
        if not scene:
            return
        self.log.clear_error()
        self.service.render(scene, self.render_settings())

    # -- service events ---------------------------------------------------------------

    def on_message(self, msg: PreviewMessage) -> None:
        cur = self.service.current
        if msg.seq and (cur is None or msg.seq != cur.seq):
            return  # stale (the service already filters; belt and braces)
        handler = getattr(self, f"_on_{msg.type}", None)
        if handler:
            handler(msg)

    def _on_scenes(self, msg: PreviewMessage) -> None:
        self.scenes = msg.data["scenes"]
        keep = self.current_scene()
        self.scene_box.clear()
        for s in self.scenes:
            base = s["bases"][0] if s["bases"] else "Scene"
            self.scene_box.addItem(f"{s['name']}  ({base})", s["name"])
        names = [s["name"] for s in self.scenes]
        if not names:
            self.status_label.setText("No Scene classes found in this file.")
            self.viewport.placeholder = "No Scene subclasses found."
            self.viewport.update()
            return
        pick = keep if keep in names else names[0]
        self.scene_box.setCurrentIndex(names.index(pick))
        if self.service.current is None or self.service.current.scene != pick:
            self.render()

    def _on_changed(self, msg: PreviewMessage) -> None:
        names = ", ".join(Path(f).name for f in msg.data["files"])
        self.log.append(f"— changed: {names}")
        if any(Path(f) == self.service.file for f in msg.data["files"]):
            self.refresh_scenes()  # classes may have been added/renamed

    def _on_status(self, msg: PreviewMessage) -> None:
        state = msg.data["state"]
        if state == "running":
            self.viewport.placeholder = "Rendering the first frames…"
            self.status_label.setText(f"Rendering {msg.data['scene']}…")
            self.viewport.set_overlay("Rendering…")
        elif state == "cancelled":
            self.status_label.setText("Cancelled")
            self.viewport.set_overlay("")
        elif state == "done":
            cur = self.service.current
            t = cur.timings.get("total", 0.0) if cur else 0.0
            self.status_label.setText(f"Ready — {len(cur.frames) if cur else 0} frames "
                                      f"(rendered {cur.frames_drawn if cur else 0}) in {t:.1f} s"
                                      + (f" · {self.notice}" if self.notice else ""))  # fmt: skip
            self.viewport.set_overlay("")

    def _on_timeline(self, msg: PreviewMessage) -> None:
        tl = msg.data["timeline"]
        kept = self.playback.set_scene(float(tl["frame_rate"]), int(tl["duration_frames"]))
        self.notice = "" if kept else "playhead reset: the scene is shorter now"
        for w in tl.get("warnings", []):
            self.log.append(f"warning: {w}")
        self._show_frame()

    def _on_frame(self, msg: PreviewMessage) -> None:
        d = msg.data
        if d["frame"] == self.playback.frame or not self.viewport.has_frame:
            self._show_frame()
        if self.service.current and self.service.current.state == "running":
            self.viewport.set_overlay(f"Rendering… {d['cached']}/{d['total']} frames")
        self._sync_transport()

    def _on_log(self, msg: PreviewMessage) -> None:
        self.log.append(msg.data["line"])

    def _on_error(self, msg: PreviewMessage) -> None:
        d = msg.data
        self.log.show_error(d["message"], d.get("file"), d.get("line"), d.get("traceback", ""))
        where = f" ({Path(d['file']).name}:{d['line']})" if d.get("file") and d.get("line") else ""
        self.viewport.set_overlay(d["message"] + where, error=True)
        if not self.viewport.has_frame:
            self.viewport.placeholder = "No frames: the scene raised an error (see the log)."
        self.status_label.setText("Error — see the log")
        self.log_dock.show()

    def _on_done(self, msg: PreviewMessage) -> None:
        pass  # status 'done' follows

    # -- playback ---------------------------------------------------------------------

    def _frames(self) -> dict[int, Path]:
        cur = self.service.current
        return cur.frames if cur else {}

    def _show_frame(self) -> None:
        frames = self._frames()
        path = frames.get(self.playback.frame)
        if path is None and frames:  # not rendered yet: show the nearest earlier frame
            earlier = [i for i in frames if i <= self.playback.frame]
            path = frames[max(earlier)] if earlier else None
        self.viewport.show_frame(path)
        self._sync_transport()

    def _sync_transport(self) -> None:
        pb = self.playback
        frames = self._frames()
        self.transport.show_state(playing=pb.playing, buffering=pb.buffering, frame=pb.frame,
                                  total=pb.total, timecode=pb.timecode())  # fmt: skip
        rng = (pb.range.start, pb.range.end) if pb.range else None
        self.transport.scrub.set_state(pb.total, pb.frame, frames, len(frames), rng)

    def _tick(self) -> None:
        if not self.playback.playing:
            return
        before = self.playback.frame
        after = self.playback.tick(self._frames())
        if after != before or self.playback.buffering:
            self._show_frame()
        if not self.playback.playing:
            self._sync_transport()

    def toggle_play(self) -> None:
        self.playback.toggle()
        self._sync_transport()

    def step(self, frames: int) -> None:
        self.playback.step(frames)
        self._show_frame()

    def step_seconds(self, seconds: float) -> None:
        self.step(round(seconds * self.playback.fps))

    def seek(self, frame: int) -> None:
        self.playback.seek(frame)
        self._show_frame()

    def jump(self, where: str) -> None:
        b = self.playback.bounds
        self.seek(b.start if where == "start" else b.end - 1)

    def _set_loop(self, on: bool) -> None:
        self.playback.loop = on

    def set_range_start(self) -> None:
        pb = self.playback
        end = pb.range.end if pb.range else pb.total
        pb.set_range(pb.frame, end)
        self._sync_transport()

    def set_range_end(self) -> None:
        pb = self.playback
        start = pb.range.start if pb.range else 0
        pb.set_range(start, pb.frame + 1)
        self._sync_transport()

    def clear_range(self) -> None:
        self.playback.set_range(None, None)
        self._sync_transport()

    # -- theme & lifecycle ------------------------------------------------------------

    def toggle_theme(self) -> None:
        app = QApplication.instance()
        dark = not is_dark(app)
        apply_theme(app, dark)
        self.settings_store.setValue("dark", dark)
        self.act_theme.setText("Light theme" if dark else "Dark theme")
        self.transport.refresh_icons()
        self.update()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        self.bridge.detach()
        self.service.close()
        super().closeEvent(event)
