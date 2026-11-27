"""Scene runner: a child process that imports a scene file and reports over stdout.

Protocol (ADR-0004): one JSON object per line on stdout, each with ``"v"`` (protocol
version) and ``"type"``. Everything else the scene or Manim prints goes to stderr.

    {"v": 1, "type": "hello", "manim_version": "...", "pid": 123}
    {"v": 1, "type": "timeline", "revision": "...", "timeline": {...}}
    {"v": 1, "type": "frame", "frame": 12, "path": "..."}    # only with --cache-dir
    {"v": 1, "type": "done", "elapsed_s": 0.42, "timings": {...}, "frames_drawn": 0}

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
import importlib.util
import json
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


def _user_frame(tb: Any, scene_file: Path) -> tuple[str | None, int | None]:
    """Innermost traceback frame in the scene file, else the innermost overall."""
    frames = traceback.extract_tb(tb)
    for fr in reversed(frames):
        if Path(fr.filename).resolve() == scene_file.resolve():
            return fr.filename, fr.lineno
    return (frames[-1].filename, frames[-1].lineno) if frames else (None, None)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m manim_stage.runner")
    parser.add_argument("file", type=Path)
    parser.add_argument("scene")
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
    parser.add_argument("--shard", default="0/1", help="i/n: draw only frames with index %% n == i")
    args = parser.parse_args(argv)
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
        settings = {
            "frame_rate": args.fps,
            "pixel_width": args.width,
            "pixel_height": args.height,
            "progress_bar": "none",
            "disable_caching": True,
            "verbosity": "WARNING",
        }
        revision = revision_key(
            args.file, args.scene, settings, manim_version=_compat.manim_build_id()
        )
        if args.media_dir:  # does not affect pixels, so not part of the revision
            settings["media_dir"] = str(args.media_dir)
        drawn = 0
        with tempconfig(settings):
            # Import under the final config: ConvertToOpenGL binds bases at class creation.
            scene_cls = load_scene_class(args.file, args.scene)
            from .capture import capture

            timeline = capture(scene_cls)
            lap("timeline")
            send({"type": "timeline", "revision": revision, "timeline": timeline.to_dict()})

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
        file, line = _user_frame(exc.__traceback__, args.file)
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
    timeout: float | None = 300,
    python: str = sys.executable,
) -> RunResult:
    """Run the scene in fresh child processes and collect its timeline (and frames).

    With ``cache_dir`` and ``workers > 1``, frame drawing is split across that many
    children; each replays the scene from the start (cheap without drawing) and draws
    every ``workers``-th frame.
    """
    from concurrent.futures import ThreadPoolExecutor

    base = [python, "-m", "manim_stage.runner", str(file), scene, "--fps", str(fps),
            "--width", str(width), "--height", str(height)]  # fmt: skip
    if cache_dir is None:
        workers = 1
    else:
        base += ["--cache-dir", str(cache_dir), "--budget-mb", str(budget_mb)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def one(shard: int) -> RunResult:
        cmd = [*base, "--shard", f"{shard}/{workers}"]
        if workers > 1:
            # Manim writes Text/SVG caches into media_dir without locking; concurrent
            # runners sharing it can read each other's half-written files.
            cmd += ["--media-dir", str(Path(cache_dir) / ".media" / f"shard-{shard}")]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env
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
