"""Scene runner: a child process that imports a scene file and reports over stdout.

Protocol (ADR-0004): one JSON object per line on stdout, each with ``"v"`` (protocol
version) and ``"type"``. Everything else the scene or Manim prints goes to stderr.

    {"v": 1, "type": "hello", "manim_version": "...", "pid": 123}
    {"v": 1, "type": "timeline", "timeline": {...}}         # SceneTimeline.to_dict()
    {"v": 1, "type": "frame", "frame": 12, "path": "..."}    # only with --frames-dir
    {"v": 1, "type": "done", "elapsed_s": 0.42}
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
    parser.add_argument("--frames-dir", type=Path, help="write every frame as PNG here")
    args = parser.parse_args(argv)

    out: IO[str] = sys.stdout
    sys.stdout = sys.stderr  # keep the protocol channel clean

    def send(msg: dict[str, Any]) -> None:
        out.write(json.dumps({"v": PROTOCOL_VERSION, **msg}) + "\n")
        out.flush()

    started = time.perf_counter()
    try:
        import manim
        from manim import tempconfig

        send({"type": "hello", "manim_version": manim.__version__, "pid": os.getpid()})
        settings = {
            "frame_rate": args.fps,
            "pixel_width": args.width,
            "pixel_height": args.height,
            "progress_bar": "none",
            "disable_caching": True,
            "verbosity": "WARNING",
        }
        with tempconfig(settings):
            # Import under the final config: ConvertToOpenGL binds bases at class creation.
            scene_cls = load_scene_class(args.file, args.scene)
            from .capture import capture

            frame_times = on_frame = None
            if args.frames_dir:
                args.frames_dir.mkdir(parents=True, exist_ok=True)
                # Probe the length with a timeline-only pass, then draw every frame.
                probe = capture(scene_cls)
                frame_times = [i / args.fps for i in range(probe.duration_frames)]

                def on_frame(frame: Any) -> None:
                    path = args.frames_dir / f"{frame.frame_index:06d}.png"
                    frame.image.save(path)
                    send({"type": "frame", "frame": frame.frame_index, "path": str(path)})

            timeline = capture(scene_cls, frame_times=frame_times, on_frame=on_frame)
        send({"type": "timeline", "timeline": timeline.to_dict()})
        send({"type": "done", "elapsed_s": round(time.perf_counter() - started, 3)})
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
    frames: dict[int, Path] = field(default_factory=dict)
    elapsed_s: float = 0.0
    manim_version: str = ""
    stderr: str = ""


def run_capture(
    file: str | os.PathLike[str],
    scene: str,
    *,
    fps: float = 15.0,
    width: int = 854,
    height: int = 480,
    frames_dir: str | os.PathLike[str] | None = None,
    timeout: float | None = 300,
    python: str = sys.executable,
) -> RunResult:
    """Run the scene in a fresh child process and collect its timeline (and frames)."""
    cmd = [
        python,
        "-m",
        "manim_stage.runner",
        str(file),
        scene,
        "--fps",
        str(fps),
        "--width",
        str(width),
        "--height",
        str(height),
    ]
    if frames_dir is not None:
        cmd += ["--frames-dir", str(frames_dir)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env
    )
    result: RunResult | None = None
    frames: dict[int, Path] = {}
    hello: dict[str, Any] = {}
    elapsed = 0.0
    timeline = None
    for raw in proc.stdout.splitlines():
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
            elif t == "done":
                elapsed = msg["elapsed_s"]
            elif t == "error":
                raise RunnerError(
                    msg["message"],
                    file=msg.get("file"),
                    line=msg.get("line"),
                    tb=msg.get("traceback", ""),
                )
    if timeline is None:
        raise RunnerError(
            f"runner exited with code {proc.returncode} without a timeline", tb=proc.stderr
        )
    result = RunResult(timeline, frames, elapsed, hello.get("manim_version", ""), proc.stderr)
    return result


if __name__ == "__main__":
    sys.exit(_main())
