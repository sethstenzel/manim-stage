"""Export through Manim's own CLI (spec F01/F10, backlog 1.5).

The Studio never encodes video itself: an export *is* a ``manim render`` command,
built from the editor's settings and shown to the user, so the same command
reproduces it headlessly. The preview's seed is passed so random scenes match.

- **Range export** uses Manim's ``-n FIRST,LAST`` (inclusive animation numbers; play
  and wait calls are both counted). A frame range is widened to whole play/wait calls,
  because Manim renders whole animations; the dialog shows the snapped range.
- **Progress** is parsed from Manim's progress bar (``Animation N: …| i/n``).
- **Cancel** kills the Manim process tree. **Result** is located in the media folder
  and inspected with PyAV (size, fps, duration, codecs, audio) for spec F10.
"""

from __future__ import annotations

import contextlib
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FORMATS = ("mp4", "webm", "mov", "gif", "png-sequence", "png")
ALPHA_FORMATS = ("mov", "webm", "png-sequence", "png")  # Manim's -t works with these

_PROGRESS = re.compile(r"Animation (\d+):.*?(\d+)/(\d+)")


@dataclass(frozen=True)
class ExportSettings:
    """What to render. ``quality`` is a key of ``manim.constants.QUALITIES``."""

    quality: str = "high_quality"
    format: str = "mp4"
    transparent: bool = False
    save_sections: bool = False
    play_range: tuple[int, int] | None = None  # inclusive Manim animation numbers
    media_dir: Path | None = None  # default: Manim's (./media next to the scene)
    output_name: str | None = None
    seed: int = 0
    resolution: tuple[int, int] | None = None  # custom size: -r W,H (overrides quality's)
    fps: float | None = None  # custom frame rate: --fps

    def __post_init__(self) -> None:
        if self.format not in FORMATS:
            raise ValueError(f"format must be one of {FORMATS}")
        if self.transparent and self.format not in ALPHA_FORMATS:
            raise ValueError(f"transparent output needs one of {ALPHA_FORMATS}")


@dataclass(frozen=True)
class RenderPreset:
    """A named export setting (spec F10 render presets)."""

    label: str
    quality: str
    resolution: tuple[int, int] | None = None
    fps: float | None = None
    format: str = "mp4"
    transparent: bool = False

    def apply(self, base: ExportSettings) -> ExportSettings:
        from dataclasses import replace

        return replace(
            base,
            quality=self.quality,
            resolution=self.resolution,
            fps=self.fps,
            format=self.format,
            transparent=self.transparent,
        )


PRESETS: dict[str, RenderPreset] = {
    "draft": RenderPreset("Draft 480p15 (-ql)", "low_quality"),
    "720p30": RenderPreset("720p30 (-qm)", "medium_quality"),
    "1080p30": RenderPreset("1080p30", "high_quality", (1920, 1080), 30),
    "1080p60": RenderPreset("1080p60 (-qh)", "high_quality"),
    "1440p60": RenderPreset("1440p60 (-qp)", "production_quality"),
    "4k30": RenderPreset("4K 2160p30", "fourk_quality", (3840, 2160), 30),
    "4k60": RenderPreset("4K 2160p60 (-qk)", "fourk_quality"),
    "alpha1080p30": RenderPreset(
        "Transparent MOV 1080p30 (ProRes 4444)", "high_quality", (1920, 1080), 30, "mov", True
    ),
    "gif480": RenderPreset("GIF 480p15", "low_quality", None, None, "gif"),
}


def quality_flag(quality: str) -> str:
    from manim.constants import QUALITIES

    flag = QUALITIES[quality]["flag"]
    if not flag:
        raise ValueError(f"{quality} has no CLI flag")
    return flag


def play_range_for_frames(timeline: dict[str, Any], start: int, end: int) -> tuple[int, int] | None:
    """Animation numbers of the play/wait calls overlapping frames ``[start, end)``."""
    hits = [
        e["meta"]["play_index"]
        for e in timeline.get("events", [])
        if e["kind"] in ("play", "wait")
        and "play_index" in e.get("meta", {})
        and e["start_frame"] < end
        and max(e["end_frame"], e["start_frame"] + 1) > start
    ]
    return (min(hits), max(hits)) if hits else None


def frames_for_play_range(timeline: dict[str, Any], rng: tuple[int, int]) -> tuple[int, int]:
    """Preview frames ``[start, end)`` covered by animation numbers ``rng`` (inclusive)."""
    spans = [
        (e["start_frame"], e["end_frame"])
        for e in timeline.get("events", [])
        if e["kind"] in ("play", "wait") and rng[0] <= e["meta"].get("play_index", -1) <= rng[1]
    ]
    return (min(s for s, _ in spans), max(e for _, e in spans)) if spans else (0, 0)


def manim_command(
    file: str | Path, scene: str, s: ExportSettings, *, python: str = sys.executable
) -> list[str]:
    """The ``manim render`` command for these settings (also shown to the user)."""
    cmd = [
        python,
        "-m",
        "manim",
        "render",
        str(file),
        scene,
        "-q",
        quality_flag(s.quality),
        *(["-r", f"{s.resolution[0]},{s.resolution[1]}"] if s.resolution else []),
        *(["--fps", f"{s.fps:g}"] if s.fps else []),
        "--format",
        s.format,
        "--seed",
        str(s.seed),
        "--progress_bar",
        "display",
    ]
    if s.transparent:
        cmd.append("-t")
    if s.save_sections:
        cmd.append("--save_sections")
    if s.play_range is not None:
        cmd += ["-n", f"{s.play_range[0]},{s.play_range[1]}"]
    if s.media_dir is not None:
        cmd += ["--media_dir", str(s.media_dir)]
    if s.output_name:
        cmd += ["-o", s.output_name]
    return cmd


def display_command(cmd: list[str]) -> str:
    """Copy-pasteable form, with ``manim`` instead of ``python -m manim``."""
    parts = ["manim", *cmd[3:]] if cmd[1:3] == ["-m", "manim"] else list(cmd)
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def snapshot(
    file: str | Path,
    scene: str,
    seconds: float,
    out: str | Path,
    *,
    quality: str = "high_quality",
    seed: int = 0,
    timeout: float = 600,
    python: str = sys.executable,
) -> tuple[Path, int]:
    """Render the single frame showing ``seconds`` at a Manim quality preset to ``out``.

    Drawn by Manim in a runner child (same seed as the preview). Returns the PNG path
    and the frame index at that quality's frame rate.
    """
    import json

    from manim.constants import QUALITIES

    from .runner import RunnerError, child_env, runner_command

    q = QUALITIES[quality]
    out = Path(out).resolve()
    cmd = runner_command(
        file,
        scene,
        fps=q["frame_rate"],
        width=q["pixel_width"],
        height=q["pixel_height"],
        seed=seed,
        python=python,
    )
    cmd += ["--snapshot-at", repr(float(seconds)), "--out", str(out)]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=child_env(),
        cwd=Path(file).resolve().parent,
    )
    for raw in proc.stdout.splitlines():
        with contextlib.suppress(json.JSONDecodeError):
            m = json.loads(raw)
            if m.get("type") == "snapshot":
                return Path(m["path"]), int(m["frame"])
            if m.get("type") == "error":
                raise RunnerError(
                    m["message"], file=m.get("file"), line=m.get("line"), tb=m.get("traceback", "")
                )
    raise RunnerError(f"snapshot failed (exit {proc.returncode})", tb=proc.stderr)


def find_output(media_dir: Path, name: str, fmt: str, since: float) -> Path | None:
    """The file (or folder, for png-sequence) Manim just wrote."""
    ext = {"png-sequence": ".png"}.get(fmt, "." + fmt)
    found = [
        p
        for p in media_dir.rglob(f"*{ext}")
        if p.stat().st_mtime >= since - 1
        and "partial_movie_files" not in p.parts
        and "sections" not in p.parts
        and (p.stem == name or (fmt.startswith("png") and p.stem.startswith(name)))
    ]
    if not found:
        return None
    newest = max(found, key=lambda p: p.stat().st_mtime)
    return newest.parent if fmt == "png-sequence" else newest


def probe_media(path: Path) -> dict[str, Any]:
    """Size, frame rate, duration, codecs and audio of a rendered file (via PyAV)."""
    import av

    info: dict[str, Any] = {"path": str(path), "bytes": path.stat().st_size}
    with av.open(str(path)) as c:
        if c.streams.video:
            v = c.streams.video[0]
            info.update(
                video_codec=v.codec_context.name,
                width=v.codec_context.width,
                height=v.codec_context.height,
                fps=float(v.guessed_rate or v.base_rate or v.average_rate or 0) or None,
                avg_fps=round(float(v.average_rate), 4) if v.average_rate else None,
                frames=v.frames or None,
                pixel_format=v.codec_context.pix_fmt,
            )
        if info.get("fps") and info.get("avg_fps"):
            # Manim writes constant-frame-rate video; flag anything else explicitly (F10).
            info["variable_frame_rate"] = abs(info["avg_fps"] - info["fps"]) / info["fps"] > 0.005
        if c.duration is not None:
            info["duration_s"] = round(c.duration / 1_000_000, 4)
        info["audio"] = [
            {"codec": a.codec_context.name, "sample_rate": a.codec_context.sample_rate}
            for a in c.streams.audio
        ]
    return info


@dataclass
class ExportResult:
    returncode: int | None = None
    cancelled: bool = False
    output: Path | None = None
    probe: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.cancelled and self.output is not None


class ExportJob:
    """Runs one ``manim render`` child. Callbacks run on a background thread."""

    def __init__(
        self,
        file: str | Path,
        scene: str,
        settings: ExportSettings,
        *,
        total_plays: int | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_done: Callable[[ExportResult], None] | None = None,
        python: str = sys.executable,
    ) -> None:
        self.file = Path(file).resolve()
        self.scene, self.settings = scene, settings
        media = Path(settings.media_dir) if settings.media_dir else Path("media")
        # Relative folders are relative to the scene, like Manim run from the scene folder.
        self.media_dir = (media if media.is_absolute() else self.file.parent / media).resolve()
        self.settings = ExportSettings(**{**settings.__dict__, "media_dir": self.media_dir})
        self.cmd = manim_command(self.file, scene, self.settings, python=python)
        first, last = settings.play_range or (0, (total_plays or 1) - 1)
        self._first, self._count = first, max(1, last - first + 1)
        self._on_progress, self._on_log, self._on_done = on_progress, on_log, on_done
        self.result = ExportResult()
        self.progress = 0.0
        self._proc: subprocess.Popen[str] | None = None
        self._done = threading.Event()
        self._cancel = False
        self._tail: list[str] = []

    def start(self) -> ExportJob:
        from .runner import child_env

        kw: dict[str, Any] = {}
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        env = {**child_env(), "COLUMNS": "200", "TERM": "dumb"}
        self._started = time.time()
        self._proc = subprocess.Popen(
            self.cmd,
            cwd=self.file.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **kw,
        )
        threading.Thread(target=self._read, daemon=True).start()
        return self

    def _read(self) -> None:
        assert self._proc and self._proc.stdout
        buf = ""
        while True:
            ch = self._proc.stdout.read(1)
            if not ch:
                break
            if ch in "\r\n":
                if buf.strip():
                    self._line(buf)
                buf = ""
            else:
                buf += ch
        if buf.strip():
            self._line(buf)
        code = self._proc.wait()
        self._finish(code)

    def _line(self, line: str) -> None:
        m = _PROGRESS.search(line)
        if m:
            n, i, total = (int(x) for x in m.groups())
            frac = (n - self._first + (i / total if total else 1)) / self._count
            self.progress = max(self.progress, min(frac, 0.99))
            if self._on_progress:
                self._on_progress(self.progress, f"Animation {n}: {i}/{total} frames")
            return
        self._tail = (self._tail + [line])[-200:]
        if self._on_log:
            self._on_log(line)

    def _finish(self, code: int) -> None:
        r = self.result
        r.returncode, r.cancelled = code, self._cancel
        if code == 0 and not self._cancel:
            name = self.settings.output_name or self.scene
            r.output = find_output(self.media_dir, name, self.settings.format, self._started)
            if r.output is None:
                r.error = "Manim finished but the output file was not found."
            elif r.output.is_file() and self.settings.format != "png":
                with contextlib.suppress(Exception):
                    r.probe = probe_media(r.output)
            self.progress = 1.0
            if self._on_progress:
                self._on_progress(1.0, "Done")
        elif not self._cancel:
            r.error = "\n".join(self._tail[-15:]) or f"manim exited with code {code}"
        self._done.set()
        if self._on_done:
            self._on_done(r)

    def cancel(self) -> None:
        self._cancel = True
        p = self._proc
        if p is None or p.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False
            )
        else:
            import signal

            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(p.pid, signal.SIGKILL)

    def wait(self, timeout: float | None = None) -> ExportResult:
        self._done.wait(timeout)
        return self.result
