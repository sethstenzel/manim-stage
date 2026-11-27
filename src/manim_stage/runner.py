"""Scene runner: a child process that imports a scene file and reports over stdout.

Protocol (ADR-0004): one JSON object per line on stdout, each with ``"v"`` (protocol
version) and ``"type"``. Everything else the scene or Manim prints goes to stderr.

    {"v": 1, "type": "hello", "manim_version": "...", "pid": 123}
    {"v": 1, "type": "scenes", "scenes": [{"name": "...", "line": 3, "bases": [...]}]}  # --list
    {"v": 1, "type": "timeline", "revision": "...", "timeline": {...},
     "dependencies": ["/abs/helper.py", "/abs/logo.png"]}
    {"v": 1, "type": "frame", "frame": 12, "path": "..."}    # only with --cache-dir
    {"v": 1, "type": "done", "elapsed_s": 0.42, "timings": {...}, "frames_drawn": 0}

The revision hashes the scene file, settings, Manim build and the content of every
local file the scene imported or opened (``dependencies``, see :mod:`manim_stage.deps`).
The timeline is sent before any frame is drawn, so an editor can show the scene's
structure while frames are still being cached. Frames already in the cache for this
revision are not drawn again.
    {"v": 1, "type": "error", "message": "...", "traceback": "...",
     "file": "...", "line": 12}

Trust boundary: this executes the given Python file. Only run trusted local
projects (spec §2.8). The parent process never forwards remote input as code.

Parent side: :func:`run_capture`.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from .events import SceneTimeline

PROTOCOL_VERSION = 1


class RunnerError(RuntimeError):
    def __init__(
        self, message: str, *, file: str | None = None, line: int | None = None, tb: str = ""
    ) -> None:
        super().__init__(message)
        self.file, self.line, self.traceback = file, line, tb


def load_scene_class(path: Path, scene: str) -> type:
    """Import ``path`` as a fresh module and return class ``scene`` from it."""
    path = path.resolve()
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))  # local imports next to the scene, as manim does
    name = f"manim_stage_scene_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RunnerError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    try:
        return getattr(module, scene)
    except AttributeError:
        raise RunnerError(f"{path.name} has no scene class {scene!r}") from None


def list_scenes(path: Path) -> list[dict[str, Any]]:
    """Scene classes defined in ``path`` (not imported into it), in source order."""
    import inspect

    from manim import Scene

    path = path.resolve()
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    name = f"manim_stage_scene_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RunnerError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    found = []
    for attr, obj in vars(module).items():
        if not (isinstance(obj, type) and issubclass(obj, Scene) and obj.__module__ == name):
            continue
        try:
            line = inspect.getsourcelines(obj)[1]
        except (OSError, TypeError):
            line = 0
        bases = [c.__name__ for c in obj.__mro__[1:] if c.__module__.startswith("manim.")]
        stage = any(c.__module__ == "manim_stage.scene" for c in obj.__mro__)
        found.append({"name": attr, "line": line, "bases": bases[:3], "stage": stage})
    return sorted(found, key=lambda s: s["line"])


def _used_variables() -> list[dict[str, Any]]:
    """Project variables the scene read (``manim_stage.project.var``), for the Studio."""
    from .project import USED

    return [{"name": n, **var.to_dict()} for n, var in sorted(USED.items())]


def _user_frame(exc: BaseException, scene_file: Path) -> tuple[str | None, int | None]:
    """Where to point the user: a syntax error's own location, else the innermost
    traceback frame in the scene file, else the innermost frame overall."""
    if isinstance(exc, SyntaxError) and exc.filename and exc.lineno:
        return exc.filename, exc.lineno
    frames = traceback.extract_tb(exc.__traceback__)
    for fr in reversed(frames):
        if Path(fr.filename).resolve() == scene_file.resolve():
            return fr.filename, fr.lineno
    return (frames[-1].filename, frames[-1].lineno) if frames else (None, None)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m manim_stage.runner")
    parser.add_argument("file", type=Path)
    parser.add_argument("scene", nargs="?")
    parser.add_argument("--list", action="store_true", help="list scene classes and exit")
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--width", type=int, default=854)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--cache-dir", type=Path, help="cache every frame here (FrameCache)")
    parser.add_argument("--budget-mb", type=int, default=2048, help="frame cache budget")
    parser.add_argument(
        "--media-dir",
        type=Path,
        help="Manim media dir (text/SVG caches); must not be shared by concurrent runners",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="random seed (Manim's --seed); keeps replays identical"
    )
    parser.add_argument(
        "--snapshot-at", type=float, help="render the frame showing this time (s) to --out"
    )
    parser.add_argument("--out", type=Path, help="PNG path for --snapshot-at")
    parser.add_argument("--inspect-at", type=float, help="report the Mobject tree at this time (s)")
    parser.add_argument("--shard", default="0/1", help="i/n: draw only frames with index %% n == i")
    args = parser.parse_args(argv)
    if not args.list and not args.scene:
        parser.error("scene is required unless --list is given")
    shard, shards = (int(x) for x in args.shard.split("/"))
    if not 0 <= shard < shards:
        parser.error("--shard must be i/n with 0 <= i < n")

    out: IO[str] = sys.stdout
    sys.stdout = sys.stderr  # keep the protocol channel clean

    def send(msg: dict[str, Any]) -> None:
        out.write(json.dumps({"v": PROTOCOL_VERSION, **msg}) + "\n")
        out.flush()

    started = time.perf_counter()
    timings: dict[str, float] = {}

    def lap(name: str) -> None:
        timings[name] = round(time.perf_counter() - started, 3)

    try:
        import manim
        from manim import tempconfig

        from . import _compat
        from .framecache import FrameCache, revision_key

        lap("import")
        send({"type": "hello", "manim_version": manim.__version__, "pid": os.getpid()})
        if args.list:
            send({"type": "scenes", "scenes": list_scenes(args.file)})
            lap("total")
            send(
                {
                    "type": "done",
                    "elapsed_s": timings["total"],
                    "timings": timings,
                    "frames_drawn": 0,
                }
            )
            return 0
        settings = {
            "frame_rate": args.fps,
            "pixel_width": args.width,
            "pixel_height": args.height,
            "progress_bar": "none",
            "disable_caching": True,
            "verbosity": "WARNING",
            "seed": args.seed,
        }
        if args.media_dir:  # does not affect pixels, so not part of the revision
            settings["media_dir"] = str(args.media_dir)
        drawn = 0
        with tempconfig(settings):
            from manim import config

            from .capture import capture
            from .deps import DependencyRecorder, content_hashes
            from .determinism import scan_file

            exclude = [config.media_dir] + ([args.cache_dir] if args.cache_dir else [])
            with DependencyRecorder(exclude=exclude) as rec:
                # Import under the final config: ConvertToOpenGL binds bases at class creation.
                scene_cls = load_scene_class(args.file, args.scene)
                timeline = capture(scene_cls)
            for ev in timeline.events:
                if ev.kind == "sound" and ev.meta.get("file"):
                    rec.add(ev.meta["file"])  # opened by FFmpeg, invisible to the hook
            scene_file = args.file.resolve()
            deps = [f for f in rec.files() if f != scene_file]
            # sidecars redirected by environment (editor previews, tests) always count,
            # even when they live in excluded folders such as the frame cache
            for var in (
                "MANIM_STAGE_PROPERTIES",
                "MANIM_STAGE_CUES",
                "MANIM_STAGE_AUDIO",
                "MANIM_STAGE_PROJECT",
            ):
                p = os.environ.get(var)
                if p and Path(p).is_file() and Path(p).resolve() not in deps:
                    deps.append(Path(p).resolve())
            pixel_settings = {k: v for k, v in settings.items() if k != "media_dir"}
            revision = revision_key(
                args.file,
                args.scene,
                pixel_settings,
                manim_version=_compat.manim_build_id(),
                extra=content_hashes(deps, scene_file.parent),
            )
            if scan := scan_file(args.file):
                timeline = dataclasses.replace(timeline, warnings=(*timeline.warnings, *scan))
            lap("timeline")
            send(
                {
                    "type": "timeline",
                    "revision": revision,
                    "timeline": timeline.to_dict(),
                    "dependencies": [str(f) for f in deps],
                    "variables": _used_variables(),
                }
            )

            if args.snapshot_at is not None:
                if args.out is None:
                    raise RunnerError("--snapshot-at needs --out")
                last = max(timeline.duration_frames - 1, 0)
                index = min(math.floor(args.snapshot_at * args.fps + 1e-9), last)
                args.out.parent.mkdir(parents=True, exist_ok=True)

                def save(frame: Any) -> None:
                    frame.image.save(args.out, format="PNG")

                capture(scene_cls, frame_times=[index / args.fps], on_frame=save)
                send({"type": "snapshot", "frame": index, "path": str(args.out.resolve())})

            if args.inspect_at is not None:
                from .inspector import snapshot

                last = max(timeline.duration_frames - 1, 0)
                index = min(math.floor(args.inspect_at * args.fps + 1e-9), last)

                def inspect_frame(frame: Any, scene: Any) -> None:
                    send(
                        {
                            "type": "inspect",
                            "frame": index,
                            "frame_width": float(config.frame_width),
                            "frame_height": float(config.frame_height),
                            "tree": snapshot(scene, getattr(scene, "_stage_exposed", {})),
                        }
                    )

                capture(
                    scene_cls,
                    frame_times=[index / args.fps],
                    on_frame=inspect_frame,
                    with_scene=True,
                )

            if args.cache_dir:
                cache = FrameCache(args.cache_dir, budget_bytes=args.budget_mb * 1024**2)
                have = set(cache.frames(revision))
                for i in sorted(have):
                    send({"type": "frame", "frame": i, "path": str(cache.path(revision, i))})
                missing = [
                    i
                    for i in range(timeline.duration_frames)
                    if i not in have and i % shards == shard
                ]
                if missing:

                    def on_frame(frame: Any) -> None:
                        nonlocal drawn
                        path = cache.put(revision, frame.frame_index, frame.image)
                        drawn += 1
                        send({"type": "frame", "frame": frame.frame_index, "path": str(path)})

                    # A fresh scene instance: Manim evaluates each scene only once.
                    capture(
                        scene_cls,
                        frame_times=[i / args.fps for i in missing],
                        on_frame=on_frame,
                    )
                cache.trim(keep=revision)
                lap("frames")
        lap("total")
        send(
            {
                "type": "done",
                "elapsed_s": timings["total"],
                "timings": timings,
                "frames_drawn": drawn,
            }
        )
        return 0
    except BaseException as exc:  # report everything, including SystemExit from scenes
        file, line = _user_frame(exc, args.file)
        send(
            {
                "type": "error",
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": "".join(traceback.format_exception(exc)),
                "file": file,
                "line": line,
            }
        )
        return 1


@dataclass
class RunResult:
    timeline: SceneTimeline
    revision: str = ""
    frames: dict[int, Path] = field(default_factory=dict)
    frames_drawn: int = 0
    elapsed_s: float = 0.0
    timings: dict[str, float] = field(default_factory=dict)
    """Seconds since child start at: import, timeline, frames, total."""
    manim_version: str = ""
    stderr: str = ""


def _parse(stdout: str, stderr: str, returncode: int) -> RunResult:
    frames: dict[int, Path] = {}
    hello: dict[str, Any] = {}
    done: dict[str, Any] = {}
    revision = ""
    timeline = None
    for raw in stdout.splitlines():
        with contextlib.suppress(json.JSONDecodeError):
            msg = json.loads(raw)
            if msg.get("v") != PROTOCOL_VERSION:
                raise RunnerError(f"runner protocol {msg.get('v')} != {PROTOCOL_VERSION}")
            t = msg.get("type")
            if t == "hello":
                hello = msg
            elif t == "frame":
                frames[msg["frame"]] = Path(msg["path"])
            elif t == "timeline":
                timeline = SceneTimeline.from_dict(msg["timeline"])
                revision = msg.get("revision", "")
            elif t == "done":
                done = msg
            elif t == "error":
                raise RunnerError(
                    msg["message"],
                    file=msg.get("file"),
                    line=msg.get("line"),
                    tb=msg.get("traceback", ""),
                )
    if timeline is None:
        raise RunnerError(f"runner exited with code {returncode} without a timeline", tb=stderr)
    return RunResult(
        timeline=timeline,
        revision=revision,
        frames=frames,
        frames_drawn=done.get("frames_drawn", 0),
        elapsed_s=done.get("elapsed_s", 0.0),
        timings=done.get("timings", {}),
        manim_version=hello.get("manim_version", ""),
        stderr=stderr,
    )


def runner_command(
    file: str | os.PathLike[str],
    scene: str | None,
    *,
    fps: float = 15.0,
    width: int = 854,
    height: int = 480,
    seed: int = 0,
    cache_dir: str | os.PathLike[str] | None = None,
    budget_mb: int = 2048,
    media_dir: str | os.PathLike[str] | None = None,
    shard: tuple[int, int] = (0, 1),
    list_scenes: bool = False,
    python: str = sys.executable,
) -> list[str]:
    """Argument vector for one runner child (see the module docstring)."""
    cmd = [python, "-m", "manim_stage.runner", str(file)]
    if list_scenes:
        return [*cmd, "--list"]
    assert scene
    cmd += [
        scene,
        "--fps",
        str(fps),
        "--width",
        str(width),
        "--height",
        str(height),
        "--seed",
        str(seed),
        "--shard",
        f"{shard[0]}/{shard[1]}",
    ]
    if cache_dir is not None:
        cmd += ["--cache-dir", str(cache_dir), "--budget-mb", str(budget_mb)]
    if media_dir is not None:
        cmd += ["--media-dir", str(media_dir)]
    return cmd


def child_env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


class RunnerProcess:
    """One runner child whose messages are streamed to callbacks as they arrive.

    Callbacks run on reader threads. ``on_exit(returncode)`` runs once, after stdout
    and stderr are fully read. :meth:`kill` ends the child and anything it spawned
    (LaTeX, FFmpeg).
    """

    def __init__(
        self,
        cmd: list[str],
        *,
        on_message: Any,
        on_stderr: Any = None,
        on_exit: Any = None,
        cwd: str | os.PathLike[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        import threading

        self._on_message, self._on_stderr, self._on_exit = on_message, on_stderr, on_exit
        kw: dict[str, Any] = {}
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**child_env(), **(env or {})},
            cwd=cwd,
            **kw,
        )
        self.killed = False
        self._threads = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
        ]
        for t in self._threads:
            t.start()
        threading.Thread(target=self._wait, daemon=True).start()

    @property
    def pid(self) -> int:
        return self.proc.pid

    def _read_stdout(self) -> None:
        assert self.proc.stdout
        for raw in self.proc.stdout:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict):
                self._on_message(msg)

    def _read_stderr(self) -> None:
        assert self.proc.stderr
        for line in self.proc.stderr:
            if self._on_stderr:
                self._on_stderr(line.rstrip("\r\n"))

    def _wait(self) -> None:
        code = self.proc.wait()
        for t in self._threads:
            t.join()
        if self._on_exit:
            self._on_exit(code)

    def kill(self) -> None:
        if self.proc.poll() is not None:
            return
        self.killed = True
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            import signal

            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.proc.pid, signal.SIGKILL)
        with contextlib.suppress(Exception):
            self.proc.kill()

    def wait(self, timeout: float | None = None) -> int:
        return self.proc.wait(timeout)


def run_capture(
    file: str | os.PathLike[str],
    scene: str,
    *,
    fps: float = 15.0,
    width: int = 854,
    height: int = 480,
    cache_dir: str | os.PathLike[str] | None = None,
    budget_mb: int = 2048,
    workers: int = 1,
    seed: int = 0,
    timeout: float | None = 300,
    python: str = sys.executable,
    cwd: str | os.PathLike[str] | None = None,
) -> RunResult:
    """Run the scene in fresh child processes and collect its timeline (and frames).

    Children run in ``cwd`` (default: the scene file's folder), so relative asset
    paths resolve as they do when you run ``manim`` from that folder.

    With ``cache_dir`` and ``workers > 1``, frame drawing is split across that many
    children; each replays the scene from the start (cheap without drawing) and draws
    every ``workers``-th frame.
    """
    from concurrent.futures import ThreadPoolExecutor

    if cache_dir is None:
        workers = 1
    file = Path(file).resolve()
    if cache_dir is not None:
        cache_dir = Path(cache_dir).resolve()
    workdir = Path(cwd).resolve() if cwd else file.parent

    def one(shard: int) -> RunResult:
        # Manim writes Text/SVG caches into media_dir without locking; concurrent
        # runners sharing it can read each other's half-written files.
        media = Path(cache_dir) / ".media" / f"shard-{shard}" if workers > 1 else None
        cmd = runner_command(
            file,
            scene,
            fps=fps,
            width=width,
            height=height,
            seed=seed,
            cache_dir=cache_dir,
            budget_mb=budget_mb,
            media_dir=media,
            shard=(shard, workers),
            python=python,
        )
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=child_env(),
            cwd=workdir,
        )
        return _parse(proc.stdout, proc.stderr, proc.returncode)

    if workers == 1:
        return one(0)
    with ThreadPoolExecutor(workers) as pool:
        parts = list(pool.map(one, range(workers)))
    first = parts[0]
    if any(p.revision != first.revision for p in parts):
        raise RunnerError("runner shards disagree on the scene revision")
    frames: dict[int, Path] = {}
    for p in parts:
        frames.update(p.frames)
    keys = {k for p in parts for k in p.timings}
    return RunResult(
        timeline=first.timeline,
        revision=first.revision,
        frames=frames,
        frames_drawn=sum(p.frames_drawn for p in parts),
        elapsed_s=max(p.elapsed_s for p in parts),
        timings={k: max(p.timings.get(k, 0.0) for p in parts) for k in keys},
        manim_version=first.manim_version,
        stderr="".join(p.stderr for p in parts),
    )


if __name__ == "__main__":
    sys.exit(_main())
