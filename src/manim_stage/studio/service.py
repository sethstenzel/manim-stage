"""PreviewService: the Studio's engine room (ADR-0010). No Qt, no sockets.

It turns "show me scene X of file F" into runner child processes (ADR-0004) and a
stream of typed :class:`PreviewMessage` events (spec §8) for the editor:

- **Revisions.** Each :meth:`PreviewService.render` call gets the next integer ``seq``.
  Starting a new one kills the previous runner; any message still arriving from an
  old ``seq`` is dropped, so a stale frame never replaces a current one (spec §9).
- **Frames** are cached on disk (:class:`~manim_stage.framecache.FrameCache`) and
  referenced by path. Re-rendering an unchanged scene reuses them.
- **Dependencies.** The runner reports every local file the scene imported or opened;
  they are part of the cache revision and are exposed for file watching.
- **Workers.** ``workers > 1`` splits frame drawing over several children.

Listeners are called on background threads; GUI code must marshal to its own thread.

Trust boundary: rendering executes the scene's Python. Only open trusted local
projects. The service never accepts code or commands from the network.
"""

from __future__ import annotations

import contextlib
import dataclasses
import itertools
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..events import SceneTimeline
from ..runner import PROTOCOL_VERSION, RunnerProcess, child_env, runner_command

if TYPE_CHECKING:
    from .watcher import FileWatcher

Listener = Callable[["PreviewMessage"], None]

MESSAGE_TYPES = (
    "scenes",
    "changed",
    "status",
    "timeline",
    "frame",
    "log",
    "error",
    "done",
)
STATES = ("idle", "running", "done", "error", "cancelled")


@dataclass(frozen=True)
class RenderSettings:
    """Preview render settings. All of them (except ``workers``) affect pixels."""

    fps: float = 15.0
    width: int = 854
    height: int = 480
    seed: int = 0
    workers: int = 1


@dataclass(frozen=True)
class PreviewMessage:
    """One event from the service. ``seq`` is the revision number (0 = no revision)."""

    type: str
    seq: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"v": PROTOCOL_VERSION, "type": self.type, "seq": self.seq, **self.data}


@dataclass
class Revision:
    """What the service knows about one render request."""

    seq: int
    scene: str
    settings: RenderSettings
    state: str = "running"
    revision: str = ""
    timeline: SceneTimeline | None = None
    dependencies: list[Path] = field(default_factory=list)
    frames: dict[int, Path] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    timings: dict[str, float] = field(default_factory=dict)
    frames_drawn: int = 0


class PreviewService:
    def __init__(
        self,
        file: str | Path,
        *,
        cache_dir: str | Path,
        settings: RenderSettings | None = None,
        budget_mb: int = 2048,
        cwd: str | Path | None = None,
        python: str = sys.executable,
    ) -> None:
        self.file = Path(file).resolve()
        self.cache_dir = Path(cache_dir).resolve()
        self.settings = settings or RenderSettings()
        self.budget_mb = budget_mb
        self.cwd = Path(cwd).resolve() if cwd else self.file.parent
        self.python = python
        self._lock = threading.RLock()
        self._listeners: list[Listener] = []
        self._seq = itertools.count(1)
        self._current: Revision | None = None
        self._procs: list[RunnerProcess] = []
        self._idle = threading.Event()
        self._idle.set()
        self._closed = False
        self._known_deps: list[Path] = []
        self._last_scene: str | None = None
        self._watcher: FileWatcher | None = None

    # -- subscription ---------------------------------------------------------------

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock, contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return unsubscribe

    def _emit(self, msg: PreviewMessage) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            fn(msg)

    # -- state ----------------------------------------------------------------------

    @property
    def current(self) -> Revision | None:
        return self._current

    @property
    def dependencies(self) -> list[Path]:
        """The scene file plus every local file the scene depends on.

        Kept from the last revision that got as far as a timeline, so a scene that
        currently fails to import is still watched through its helpers.
        """
        return [self.file, *self._known_deps]

    def wait_idle(self, timeout: float | None = None) -> bool:
        """Block until no render is running (for headless use and tests)."""
        return self._idle.wait(timeout)

    # -- commands -------------------------------------------------------------------

    def discover_scenes(self, timeout: float = 120) -> list[dict[str, Any]]:
        """Scene classes in the file, by importing it in a child process."""
        cmd = runner_command(self.file, None, list_scenes=True, python=self.python)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=child_env(),
            cwd=self.cwd,
        )
        scenes: list[dict[str, Any]] = []
        error: dict[str, Any] | None = None
        import json

        for raw in proc.stdout.splitlines():
            with contextlib.suppress(json.JSONDecodeError):
                m = json.loads(raw)
                if m.get("type") == "scenes":
                    scenes = m["scenes"]
                elif m.get("type") == "error":
                    error = m
        if error is not None:
            data = {k: error.get(k) for k in ("message", "traceback", "file", "line")}
            self._emit(PreviewMessage("error", 0, data))
            return []
        self._emit(PreviewMessage("scenes", 0, {"file": str(self.file), "scenes": scenes}))
        return scenes

    def render(self, scene: str, settings: RenderSettings | None = None) -> int:
        """Start a new revision of ``scene``; cancels the running one. Returns its seq."""
        with self._lock:
            if self._closed:
                raise RuntimeError("PreviewService is closed")
            self._cancel_locked("superseded")
            seq = next(self._seq)
            self._last_scene = scene
            rev = Revision(seq, scene, settings or self.settings)
            self._current = rev
            self._idle.clear()
            self._start_locked(rev)
        return seq

    def cancel(self) -> None:
        with self._lock:
            self._cancel_locked("cancelled")

    def watch(self, *, debounce: float = 0.3, interval: float = 0.1) -> None:
        """Re-render the last scene when the scene file or a dependency changes.

        Emits ``changed`` (the files) and then starts a new revision, which cancels
        the running one. Debounced: a burst of saves gives one re-render.
        """
        from .watcher import FileWatcher

        with self._lock:
            if self._watcher is not None:
                self._watcher.stop()
            self._watcher = FileWatcher(
                lambda: self.dependencies, self._on_files_changed,
                interval=interval, debounce=debounce,
            ).start()  # fmt: skip

    def unwatch(self) -> None:
        with self._lock:
            if self._watcher is not None:
                self._watcher.stop()
                self._watcher = None

    def _on_files_changed(self, files: list[Path]) -> None:
        with self._lock:
            if self._closed:
                return
            scene = self._last_scene
            self._emit(PreviewMessage("changed", 0, {"files": [str(f) for f in files]}))
            if scene is not None:
                self.render(scene)

    def close(self) -> None:
        self.unwatch()
        with self._lock:
            self._closed = True
            self._cancel_locked("cancelled")
            self._listeners.clear()

    def __enter__(self) -> PreviewService:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ------------------------------------------------------------------

    def _cancel_locked(self, reason: str) -> None:
        rev = self._current
        procs, self._procs = self._procs, []
        for p in procs:
            p.kill()
        if rev is not None and rev.state == "running":
            rev.state = "cancelled"
            self._emit(
                PreviewMessage(
                    "status", rev.seq, {"state": "cancelled", "reason": reason, "scene": rev.scene}
                )
            )
        self._idle.set()

    def _start_locked(self, rev: Revision) -> None:
        s = rev.settings
        workers = max(1, int(s.workers))
        self._emit(
            PreviewMessage(
                "status",
                rev.seq,
                {"state": "running", "scene": rev.scene, "settings": dataclasses.asdict(s)},
            )
        )
        remaining = {"n": workers}
        for shard in range(workers):
            cmd = runner_command(
                self.file,
                rev.scene,
                fps=s.fps,
                width=s.width,
                height=s.height,
                seed=s.seed,
                cache_dir=self.cache_dir,
                budget_mb=self.budget_mb,
                # Never share Manim's media_dir between concurrent children, and keep it
                # out of the user's project.
                media_dir=self.cache_dir / ".media" / f"shard-{shard}",
                shard=(shard, workers),
                python=self.python,
            )
            proc = RunnerProcess(
                cmd,
                on_message=lambda m, seq=rev.seq: self._on_message(seq, m),
                on_stderr=lambda line, seq=rev.seq: self._on_stderr(seq, line),
                on_exit=lambda code, seq=rev.seq: self._on_exit(seq, code, remaining),
                cwd=self.cwd,
            )
            self._procs.append(proc)

    def _live(self, seq: int) -> Revision | None:
        rev = self._current
        if rev is None or rev.seq != seq or rev.state != "running":
            return None
        return rev

    def _on_message(self, seq: int, m: dict[str, Any]) -> None:
        with self._lock:
            rev = self._live(seq)
            if rev is None:
                return  # stale revision: drop
            t = m.get("type")
            if t == "timeline":
                if rev.timeline is not None:
                    return  # every shard sends one; the first wins
                rev.revision = m["revision"]
                rev.timeline = SceneTimeline.from_dict(m["timeline"])
                rev.dependencies = [Path(p) for p in m.get("dependencies", [])]
                self._known_deps = list(rev.dependencies)
                self._emit(
                    PreviewMessage(
                        "timeline",
                        seq,
                        {
                            "scene": rev.scene,
                            "revision": rev.revision,
                            "timeline": m["timeline"],
                            "dependencies": m.get("dependencies", []),
                        },
                    )
                )
            elif t == "frame":
                i = int(m["frame"])
                if i in rev.frames:
                    return
                rev.frames[i] = Path(m["path"])
                total = rev.timeline.duration_frames if rev.timeline else 0
                self._emit(
                    PreviewMessage(
                        "frame",
                        seq,
                        {
                            "revision": rev.revision,
                            "frame": i,
                            "path": m["path"],
                            "cached": len(rev.frames),
                            "total": total,
                        },
                    )
                )
            elif t == "done":
                rev.frames_drawn += int(m.get("frames_drawn", 0))
                for k, v in m.get("timings", {}).items():
                    rev.timings[k] = max(rev.timings.get(k, 0.0), float(v))
            elif t == "error":
                rev.error = {k: m.get(k) for k in ("message", "traceback", "file", "line")}
                rev.state = "error"
                self._emit(PreviewMessage("error", seq, dict(rev.error)))
                self._emit(PreviewMessage("status", seq, {"state": "error", "scene": rev.scene}))
                procs, self._procs = self._procs, []
                for p in procs:
                    p.kill()
                self._idle.set()

    def _on_stderr(self, seq: int, line: str) -> None:
        with self._lock:
            if self._live(seq) is None:
                return
            self._emit(PreviewMessage("log", seq, {"line": line}))

    def _on_exit(self, seq: int, code: int, remaining: dict[str, int]) -> None:
        with self._lock:
            remaining["n"] -= 1
            rev = self._live(seq)
            if rev is None:
                return
            if code != 0 and rev.error is None:
                rev.error = {
                    "message": f"runner exited with code {code}",
                    "traceback": "",
                    "file": None,
                    "line": None,
                }
                rev.state = "error"
                self._emit(PreviewMessage("error", seq, dict(rev.error)))
                self._emit(PreviewMessage("status", seq, {"state": "error", "scene": rev.scene}))
                for p in self._procs:
                    p.kill()
                self._procs = []
                self._idle.set()
                return
            if remaining["n"] > 0:
                return
            rev.state = "done"
            self._procs = []
            self._emit(
                PreviewMessage(
                    "done",
                    seq,
                    {
                        "scene": rev.scene,
                        "revision": rev.revision,
                        "frames": len(rev.frames),
                        "frames_drawn": rev.frames_drawn,
                        "timings": rev.timings,
                    },
                )
            )
            self._emit(PreviewMessage("status", seq, {"state": "done", "scene": rev.scene}))
            self._idle.set()
