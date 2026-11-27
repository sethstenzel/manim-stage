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

import os
import threading
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QImage, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ... import cues as cue_store
from ...export import snapshot
from ..audio_player import AudioPlayer
from ..cue_edit import CueEdit, edit_for_plan, edit_reset, plan_move
from ..playback import Playback
from ..service import PreviewMessage, PreviewService, RenderSettings
from ..timeline_model import resolve_source
from .bridge import ServiceBridge
from .event_panel import EventPanel
from .export_dialog import ExportDialog
from .log_panel import LogPanel, open_in_editor
from .quality import manim_qualities, quality_label
from .theme import apply_theme, is_dark
from .timeline import TimelineView
from .transport import TransportBar
from .viewport import Viewport


def studio_settings() -> QSettings:
    """User preferences (theme, …) in an INI file; tests redirect it with QSettings.setPath."""
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "manim-stage", "studio")


class _CueCommand(QUndoCommand):
    """One cue edit on the undo stack; redo/undo write the sidecar and re-render."""

    def __init__(self, window: MainWindow, edit: CueEdit) -> None:
        super().__init__(edit.label)
        self.window, self.edit = window, edit

    def redo(self) -> None:
        self.edit.do(self.window.cue_sidecar())
        self.window._cue_written(self.edit.label)

    def undo(self) -> None:
        self.edit.undo(self.window.cue_sidecar())
        self.window._cue_written(f"Undo: {self.edit.label}")


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: PreviewService,
        *,
        scene: str | None = None,
        quality: str = "low_quality",
        workers: int = 1,
    ) -> None:
        super().__init__()
        # Destroy the C++ window on close, in the GUI thread. Otherwise Python's cyclic GC
        # may finalise it later on a runner thread, which aborts Qt.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.service = service
        self.workers = max(1, workers)
        self.settings_store = studio_settings()
        self.setWindowTitle(f"manim-stage Studio — {service.file.name}")
        self.resize(1200, 800)

        self.playback = Playback(time.monotonic)
        self.scenes: list[dict] = []
        self.requested_scene = scene
        self.notice = ""
        self.shown_state: tuple[int, str, str] | None = None  # last status the GUI handled
        self._snapshot_results: deque[tuple[str, str]] = deque()  # from snapshot threads
        self.last_snapshot_message = ""
        self.export_dialog: ExportDialog | None = None

        # widgets
        self.viewport = Viewport()
        self.transport = TransportBar()
        self.timeline = TimelineView()
        top = QWidget()
        lay = QVBoxLayout(top)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.viewport, 1)
        lay.addWidget(self.transport)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(top)
        self.splitter.addWidget(self.timeline)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([480, 260])
        self.setCentralWidget(self.splitter)

        self.event_panel = EventPanel()
        self.event_dock = QDockWidget("Event", self)
        self.event_dock.setObjectName("event_dock")
        self.event_dock.setWidget(self.event_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.event_dock)

        self.log = LogPanel()
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("log_dock")
        self.log_dock.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_dock)
        self.tabifyDockWidget(self.event_dock, self.log_dock)
        self.event_dock.raise_()
        self.resizeDocks([self.event_dock], [340], Qt.Orientation.Horizontal)

        self._build_toolbar(quality)
        self._build_actions()
        self.status_label = QLabel("")
        self.status_label.setAccessibleName("Render status")
        self.statusBar().addWidget(self.status_label, 1)

        # wiring
        self.audio = AudioPlayer()
        self._audio_results: deque = deque()  # (seq, mix, waveforms) from worker threads
        self.audio_seq = 0  # revision whose mix is loaded
        self.transport.set_audio_state(self.audio.available, self.audio.reason)
        self.transport.audioToggled.connect(self._set_audio_enabled)
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
        tc = self.timeline.canvas
        tc.seekRequested.connect(self.seek)
        tc.eventSelected.connect(lambda box: self.event_panel.show_event(box, tc.fps))
        tc.sourceRequested.connect(self.open_event_source)
        self.event_panel.seekRequested.connect(self.seek)
        self.event_panel.sourceRequested.connect(self.open_event_source)
        tc.cueMoved.connect(self.apply_cue_plan)
        self.event_panel.cueResetRequested.connect(self.reset_cue)
        self.event_panel.cueTimeRequested.connect(self.set_cue_time)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(10)

        self.refresh_scenes()
        if self.requested_scene:  # don't wait for discovery when the scene is known
            self.render()

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
        self.undo_stack = QUndoStack(self)
        self.act_undo = self.undo_stack.createUndoAction(self, "Undo")
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_redo = self.undo_stack.createRedoAction(self, "Redo")
        self.act_redo.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        self.act_export = QAction("Export…", self)
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.setToolTip("Render with Manim's CLI: video, GIF or PNGs (Ctrl+E)")
        self.act_export.triggered.connect(self.open_export)
        tb.addAction(self.act_export)
        self.act_snapshot = QAction("Save frame…", self)
        self.act_snapshot.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_snapshot.setToolTip(
            "Render the frame at the playhead in full quality (Ctrl+Shift+S)"
        )
        self.act_snapshot.triggered.connect(self.save_snapshot)
        tb.addAction(self.act_snapshot)
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
            "copy_frame": act("Copy frame", "Ctrl+Shift+C", self.copy_frame),
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
        return RenderSettings(
            fps=float(q.get("frame_rate", 15)),
            width=int(q.get("pixel_width", 854)),
            height=int(q.get("pixel_height", 480)),
            workers=self.workers,
        )

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
        self.shown_state = (msg.seq, msg.data["scene"], state)
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
            self.status_label.setText(
                f"Ready — {len(cur.frames) if cur else 0} frames "
                f"(rendered {cur.frames_drawn if cur else 0}) in {t:.1f} s"
                + (f" · {self.notice}" if self.notice else "")
            )
            self.viewport.set_overlay("")

    def _on_timeline(self, msg: PreviewMessage) -> None:
        tl = msg.data["timeline"]
        self._prepare_audio(msg.seq, tl)
        self.timeline.set_timeline(tl)
        sel = self.timeline.canvas.selected
        if sel:  # stable event IDs: keep the selection across re-renders
            self.timeline.canvas.select(sel)
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
        self.log_dock.raise_()

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
        self.transport.show_state(
            playing=pb.playing,
            buffering=pb.buffering,
            frame=pb.frame,
            total=pb.total,
            timecode=pb.timecode(),
        )
        rng = (pb.range.start, pb.range.end) if pb.range else None
        self.transport.scrub.set_state(pb.total, pb.frame, frames, len(frames), rng)
        self.timeline.set_state(pb.frame, frames, rng)

    def _tick(self) -> None:
        if self._snapshot_results:
            self._drain_snapshots()
        if self._audio_results:
            self._drain_audio()
        if not self.playback.playing:
            if self.audio.playing:
                self.audio.stop()
            return
        before = self.playback.frame
        after = self.playback.tick(self._frames())
        if after != before or self.playback.buffering:
            self._show_frame()
        self._sync_audio(jumped=after < before)
        if not self.playback.playing:
            self._sync_transport()

    # -- audio ------------------------------------------------------------------------

    def _audio_wanted(self) -> bool:
        return (
            self.audio.available
            and self.transport.audio_on()
            and self.playback.playing
            and not self.playback.buffering
            and self.playback.speed == 1.0
        )

    def _sync_audio(self, *, jumped: bool = False) -> None:
        """Keep audio within one frame of the playhead; silent while buffering or not 1×."""
        t = self.playback.frame / max(self.playback.fps, 1e-9)
        if not self._audio_wanted():
            if self.audio.playing:
                self.audio.stop()
            return
        if not self.audio.playing:
            self.audio.play(t)
        elif jumped or abs(self.audio.drift(t)) > 1.5 / max(self.playback.fps, 1e-9):
            self.audio.seek(t)

    def _set_audio_enabled(self, on: bool) -> None:
        self._sync_audio()

    def _prepare_audio(self, seq: int, timeline: dict) -> None:
        """Mix the scene's sounds and compute waveforms off the GUI thread."""
        from ... import audio as audio_core

        scene_dir = self.service.file.parent
        peaks_dir = self.service.cache_dir / ".audio-peaks"

        def work() -> None:
            try:
                sounds = audio_core.sounds_from_timeline(timeline, scene_dir)
                waves = {}
                for e in timeline.get("events", []):
                    if e["kind"] != "sound":
                        continue
                    f = Path(str(e["meta"].get("file", "")))
                    f = f if f.is_absolute() else scene_dir / f
                    try:
                        waves[e["id"]] = audio_core.file_peaks(f, peaks_dir)
                    except Exception:
                        continue
                duration = timeline["duration_frames"] / float(timeline["frame_rate"])
                buf = audio_core.mix(sounds, duration) if sounds else None
                self._audio_results.append((seq, buf, waves))
            except Exception as exc:  # reported in the log
                self._audio_results.append((seq, None, {"error": str(exc)}))

        threading.Thread(target=work, daemon=True).start()

    def _drain_audio(self) -> None:
        while self._audio_results:
            seq, buf, waves = self._audio_results.popleft()
            cur = self.service.current
            if cur is None or seq != cur.seq:
                continue  # stale revision
            if "error" in waves:
                self.log.append(f"audio: {waves['error']}")
                continue
            self.audio_seq = seq
            self.audio.set_mix(buf if buf is not None else self.audio._mix[:0])
            self.timeline.canvas.waveforms = waves
            self.timeline.canvas.update()

    def open_event_source(self, box) -> None:
        if box is None or not box.source:
            return
        path = resolve_source(str(box.source.get("path", "")), self.service.file)
        open_in_editor(str(path), int(box.source.get("line") or 1))

    def toggle_play(self) -> None:
        self.playback.toggle()
        self._sync_audio(jumped=True)
        self._sync_transport()

    def step(self, frames: int) -> None:
        self.playback.step(frames)
        self._show_frame()

    def step_seconds(self, seconds: float) -> None:
        self.step(round(seconds * self.playback.fps))

    def seek(self, frame: int) -> None:
        self.playback.seek(frame)
        self._show_frame()
        if self.playback.playing:
            self._sync_audio(jumped=True)

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

    # -- export & snapshots -----------------------------------------------------------

    def open_export(self) -> ExportDialog | None:
        scene = self.current_scene()
        if not scene:
            return None
        cur = self.service.current
        tl = cur.timeline.to_dict() if cur and cur.timeline and cur.scene == scene else None
        pb = self.playback
        rng = (pb.range.start, pb.range.end) if pb.range else None
        dlg = ExportDialog(self.service.file, scene, tl, rng, pb.fps, self)
        dlg.show()
        self.export_dialog = dlg
        return dlg

    def copy_frame(self) -> None:
        path = self._frames().get(self.playback.frame)
        if path is None:
            self.status_label.setText("This frame isn't rendered yet.")
            return
        QGuiApplication.clipboard().setImage(QImage(str(path)))
        self.status_label.setText(f"Copied frame {self.playback.frame} (preview quality).")

    def save_snapshot(self, path: str | None = None, quality: str = "high_quality") -> None:
        scene = self.current_scene()
        if not scene:
            return
        seconds = self.playback.frame / max(self.playback.fps, 1e-9)
        if path is None:
            default = self.service.file.parent / f"{scene}_{self.playback.frame:05d}.png"
            path, _ = QFileDialog.getSaveFileName(self, "Save frame", str(default), "PNG (*.png)")
            if not path:
                return
        self.status_label.setText(f"Rendering frame at {seconds:.2f} s…")
        file, out = self.service.file, Path(path)

        def work() -> None:
            try:
                saved, index = snapshot(file, scene, seconds, out, quality=quality)
                self._snapshot_results.append(("ok", f"Saved frame {index} to {saved}"))
            except Exception as exc:  # reported in the status bar
                self._snapshot_results.append(("error", f"Snapshot failed: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _drain_snapshots(self) -> None:
        while self._snapshot_results:
            kind, text = self._snapshot_results.popleft()
            self.status_label.setText(("⚠ " if kind == "error" else "") + text)
            self.last_snapshot_message = text

    # -- cue editing (undoable) --------------------------------------------------------

    def cue_sidecar(self) -> Path:
        override = os.environ.get("MANIM_STAGE_CUES")
        return Path(override) if override else cue_store.sidecar_path(self.service.file)

    def _push_cue_edit(self, edit: CueEdit) -> None:
        try:
            self.undo_stack.push(_CueCommand(self, edit))
        except (cue_store.CueError, OSError) as e:
            self.status_label.setText(f"⚠ Could not save cues: {e}")

    def _cue_written(self, label: str) -> None:
        """After a sidecar write: suppress the watcher's echo and re-render now."""
        self.service.acknowledge([self.cue_sidecar()])
        self.status_label.setText(f"{label} — saved to {self.cue_sidecar().name}; re-rendering…")
        self.render()

    def apply_cue_plan(self, plan) -> None:
        scene = self.current_scene()
        if not scene:
            return
        if plan.clamped:
            self.status_label.setText(f"Cue {plan.name!r}: {plan.clamped}")
        self._push_cue_edit(edit_for_plan(self.cue_sidecar(), scene, plan, self.playback.fps))

    def reset_cue(self, name: str) -> None:
        scene = self.current_scene()
        if scene:
            self._push_cue_edit(edit_reset(self.cue_sidecar(), scene, name))

    def set_cue_time(self, name: str, seconds: float) -> None:
        scene = self.current_scene()
        if not scene:
            return
        frame = round(seconds * self.playback.fps)
        plan = plan_move(self.timeline.canvas.cue_infos(), name, frame, ripple=False)
        if plan.delta or plan.clamped:
            self.apply_cue_plan(plan)

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
        self.audio.stop()
        self.bridge.detach()
        self.service.close()
        super().closeEvent(event)
