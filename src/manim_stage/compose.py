"""Scene-to-scene transitions: compose rendered scenes into one video (spec F09).

Motion Canvas plays a project's scenes in order and lets a scene start with a
transition that animates over the previous scene's last frame. In Manim every scene
renders to its own video with ``manim render``. manim-stage keeps that and joins the
videos afterwards, frame-exact:

    manim-stage compose lesson.sequence.json

with ``lesson.sequence.json``::

    {"output": "lesson.mp4", "quality": "high_quality",
     "scenes": [
        {"file": "intro.py", "scene": "Intro"},
        {"file": "sort.py",  "scene": "BubbleSort", "transition": "fade", "duration": 0.5},
        {"file": "outro.py", "scene": "Outro", "transition": "slide_left", "duration": 0.6}
     ]}

Transitions **overlap** the two scenes (like a video editor): a 0.5 s fade at 30 fps
blends the last 15 frames of one scene with the first 15 of the next, so the total is
``sum(frames) - sum(overlaps)`` exactly; nothing is dropped or duplicated. Audio is
placed at the same offsets and cross-faded over the overlap.

Styles: ``cut`` (no overlap), ``fade``, ``slide_left|right|up|down`` (the new scene
pushes the old one out), ``wipe_left|right|up|down`` (a hard edge reveals the new scene).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

STYLES = (
    "cut",
    "fade",
    "slide_left",
    "slide_right",
    "slide_up",
    "slide_down",
    "wipe_left",
    "wipe_right",
    "wipe_up",
    "wipe_down",
)


@dataclass
class Part:
    file: Path
    scene: str
    transition: str = "cut"  # into this scene from the previous one
    duration: float = 0.0
    video: Path | None = None  # set after rendering (or given to skip rendering)


@dataclass
class ComposeResult:
    output: Path
    fps: float
    frames: int
    offsets: list[int]  # first output frame of each part
    overlaps: list[int]  # frames shared with the previous part
    part_frames: list[int] = field(default_factory=list)


def load_spec(path: str | Path) -> tuple[list[Part], dict[str, Any]]:
    path = Path(path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    parts = []
    for i, s in enumerate(spec.get("scenes", [])):
        t = s.get("transition", "cut")
        if t not in STYLES:
            raise ValueError(f"scene {i}: unknown transition {t!r}; use one of {STYLES}")
        if i == 0 and t != "cut":
            raise ValueError("the first scene can't have a transition into it")
        parts.append(
            Part(
                base / s["file"],
                s["scene"],
                t,
                float(s.get("duration", 0.0)),
                base / s["video"] if s.get("video") else None,
            )
        )
    if not parts:
        raise ValueError("the sequence has no scenes")
    options = {k: v for k, v in spec.items() if k != "scenes"}
    options["output"] = str(base / options.get("output", path.stem + ".mp4"))
    return parts, options


def blend(a: np.ndarray, b: np.ndarray, alpha: float, style: str) -> np.ndarray:
    """One transition frame: ``alpha`` goes 0 → 1 over the overlap."""
    h, w = a.shape[:2]
    if style == "fade":
        return (
            (a.astype(np.float32) * (1 - alpha) + b.astype(np.float32) * alpha)
            .round()
            .astype(np.uint8)
        )
    out = a.copy()
    kind, side = style.split("_")
    horizontal = side in ("left", "right")
    n = int(round(alpha * (w if horizontal else h)))
    if n <= 0:
        return out
    if kind == "slide":  # new pushes old out
        if side == "left":
            out[:, : w - n] = a[:, n:]
            out[:, w - n :] = b[:, :n]
        elif side == "right":
            out[:, n:] = a[:, : w - n]
            out[:, :n] = b[:, w - n :]
        elif side == "up":
            out[: h - n] = a[n:]
            out[h - n :] = b[:n]
        else:
            out[n:] = a[: h - n]
            out[:n] = b[h - n :]
    else:  # wipe: hard edge moving across, revealing the new scene in place
        if side == "left":
            out[:, w - n :] = b[:, w - n :]
        elif side == "right":
            out[:, :n] = b[:, :n]
        elif side == "up":
            out[h - n :] = b[h - n :]
        else:
            out[:n] = b[:n]
    return out


def _video_frames(path: Path) -> tuple[list[np.ndarray], float, tuple[int, int]]:
    import av

    with av.open(str(path)) as c:
        v = c.streams.video[0]
        fps = float(v.guessed_rate or v.average_rate)
        frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
    h, w = frames[0].shape[:2]
    return frames, fps, (w, h)


def compose(
    parts: list[Part], output: str | Path, *, progress: Callable[[float, str], None] | None = None
) -> ComposeResult:
    """Join rendered scene videos (``Part.video``) with overlapping transitions."""
    import av

    from . import audio as audio_core

    clips, fps, size = [], None, None
    for p in parts:
        frames, f, s = _video_frames(p.video)
        if fps is None:
            fps, size = f, s
        elif abs(f - fps) > 1e-6 or s != size:
            raise ValueError(
                f"{p.scene}: {s[0]}x{s[1]}@{f:g} differs from {size[0]}x{size[1]}"
                f"@{fps:g}; render all scenes at the same quality"
            )
        clips.append(frames)
    overlaps = [0]
    for i in range(1, len(parts)):
        ov = 0 if parts[i].transition == "cut" else int(round(parts[i].duration * fps))
        ov = min(ov, len(clips[i - 1]), len(clips[i]))
        overlaps.append(ov)
    offsets, pos = [], 0
    for i, c in enumerate(clips):
        pos -= overlaps[i]
        offsets.append(pos)
        pos += len(c)
    total = pos

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    # audio: each part's track at its offset, cross-faded over overlaps
    n_audio = int(math.ceil(total / fps * audio_core.RATE))
    mix = np.zeros((n_audio, 2), dtype=np.float32)
    for i, p in enumerate(parts):
        try:
            a = audio_core.decode(p.video)
        except Exception:
            continue
        if not len(a):
            continue
        a = a.copy()
        fade_in = int(overlaps[i] / fps * audio_core.RATE)
        fade_out = int((overlaps[i + 1] if i + 1 < len(parts) else 0) / fps * audio_core.RATE)
        if fade_in:
            a[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)[:, None]
        if fade_out:
            a[-fade_out:] *= np.linspace(1, 0, fade_out, dtype=np.float32)[:, None]
        start = int(round(offsets[i] / fps * audio_core.RATE))
        k = min(len(a), n_audio - start)
        mix[start : start + k] += a[:k]

    with av.open(str(out), "w") as c:
        vs = c.add_stream("libx264", rate=int(round(fps)) if float(fps).is_integer() else fps)
        vs.width, vs.height = size
        vs.pix_fmt = "yuv420p"
        vs.options = {"crf": "18"}
        has_audio = bool(np.any(mix))
        if has_audio:
            aus = c.add_stream("aac", rate=audio_core.RATE)
            aus.layout = "stereo"
        for idx in range(total):
            frame = _frame_at(idx, clips, offsets, overlaps, parts)
            vf = av.VideoFrame.from_ndarray(frame, format="rgb24")
            for packet in vs.encode(vf):
                c.mux(packet)
            if progress and idx % 30 == 0:
                progress(idx / total, f"frame {idx}/{total}")
        for packet in vs.encode():
            c.mux(packet)
        if has_audio:
            chunk = 1024
            pcm = np.clip(mix, -1, 1)
            for s in range(0, len(pcm), chunk):
                block = np.ascontiguousarray(pcm[s : s + chunk].T)
                af = av.AudioFrame.from_ndarray(block, format="fltp", layout="stereo")
                af.sample_rate = audio_core.RATE
                af.pts = s
                for packet in aus.encode(af):
                    c.mux(packet)
            for packet in aus.encode():
                c.mux(packet)
    return ComposeResult(out, float(fps), total, offsets, overlaps, [len(c) for c in clips])


def _frame_at(
    idx: int,
    clips: list[list[np.ndarray]],
    offsets: list[int],
    overlaps: list[int],
    parts: list[Part],
) -> np.ndarray:
    """Output frame ``idx``: a part's own frame, or a blend inside an overlap."""
    for i in range(len(clips) - 1, -1, -1):
        if idx >= offsets[i]:
            local = idx - offsets[i]
            if i > 0 and local < overlaps[i]:  # inside the transition into part i
                prev = clips[i - 1]
                a = prev[len(prev) - overlaps[i] + local]
                b = clips[i][local]
                alpha = (local + 1) / (overlaps[i] + 1)
                return blend(a, b, alpha, parts[i].transition)
            return clips[i][min(local, len(clips[i]) - 1)]
    return clips[0][0]


def render_parts(
    parts: list[Part],
    *,
    quality: str,
    media_dir: Path,
    progress: Callable[[float, str], None] | None = None,
) -> None:
    """Render each scene with ``manim render`` (the normal Manim pipeline)."""
    from .export import ExportJob, ExportSettings

    for i, p in enumerate(parts):
        if p.video is not None:
            continue
        job = ExportJob(
            p.file,
            p.scene,
            ExportSettings(quality=quality, media_dir=media_dir, output_name=f"{i:02d}-{p.scene}"),
        )
        r = job.start().wait()
        if not r.ok:
            raise RuntimeError(f"{p.scene}: render failed: {r.error}")
        p.video = r.output
        if progress:
            progress((i + 1) / len(parts), f"rendered {p.scene}")
