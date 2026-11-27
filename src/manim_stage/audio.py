"""Audio workspace core (spec F04, backlog 2.3). No Qt.

Manim's audio model stays authoritative: every sound in a scene is an
``add_sound(file, time_offset, gain)`` call, and Manim mixes them into the movie.
manim-stage adds, non-destructively:

- **Audio clips** in ``.manim-stage/audio.json``: per scene, a list of clips with
  start time, trim in/out, gain (dB), fade in/out, mute and solo. A
  :class:`~manim_stage.scene.StageScene` turns each active clip into one
  ``add_sound`` of a *processed copy* (trim/fade/gain applied) cached under
  ``.manim-stage/cache/audio/``; the source recording is never modified.
- **Preview mixdown**: the editor mixes exactly the sounds the timeline reports
  (code ``add_sound`` calls and clips alike) at their start times and gains, so the
  preview hears what Manim will render.
- **Waveform peaks** for the timeline.

Everything is decoded with PyAV (Manim's own dependency) to 48 kHz float32 stereo.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import tempfile
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .cues import SIDECAR_DIR, project_root

RATE = 48_000
CHANNELS = 2
SCHEMA = "manim_stage.audio"
VERSION = 1
SIDECAR_NAME = "audio.json"


# -- decode / encode -------------------------------------------------------------------


def decode(path: str | os.PathLike[str]) -> np.ndarray:
    """Decode any PyAV-readable file to float32 ``[samples, 2]`` at 48 kHz."""
    import av

    chunks = []
    with av.open(str(path)) as c:
        stream = c.streams.audio[0]
        res = av.AudioResampler(format="flt", layout="stereo", rate=RATE)
        for frame in c.decode(stream):
            for out in res.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1, CHANNELS))
        for out in res.resample(None):
            chunks.append(out.to_ndarray().reshape(-1, CHANNELS))
    if not chunks:
        return np.zeros((0, CHANNELS), dtype=np.float32)
    return np.ascontiguousarray(np.concatenate(chunks).astype(np.float32))


def write_wav(path: str | os.PathLike[str], samples: np.ndarray) -> Path:
    """16-bit PCM stereo WAV, written atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).round().astype("<i2")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".wav-", suffix=".tmp")
    os.close(fd)
    try:
        with wave.open(tmp, "wb") as w:
            w.setnchannels(CHANNELS)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm.tobytes())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def db_to_amp(db: float) -> float:
    return float(10 ** (db / 20))


# -- clips -----------------------------------------------------------------------------


@dataclass
class AudioClip:
    """One clip on a scene's audio track (seconds; trim relative to the source file)."""

    id: str
    file: str  # project-relative (preferred) or absolute
    start: float = 0.0
    trim_in: float = 0.0
    trim_out: float | None = None  # None: to the end of the file
    gain_db: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    mute: bool = False
    solo: bool = False
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, False) or k in ("id", "file")}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AudioClip:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def params_key(self) -> str:
        return json.dumps(
            [self.trim_in, self.trim_out, self.gain_db, self.fade_in, self.fade_out], sort_keys=True
        )


@dataclass
class AudioFile:
    scenes: dict[str, list[AudioClip]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "scenes": {
                s: {"clips": [c.to_dict() for c in clips]}
                for s, clips in sorted(self.scenes.items())
                if clips
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AudioFile:
        if d.get("schema") != SCHEMA or d.get("version") != VERSION:
            raise ValueError(f"not a manim-stage audio file v{VERSION}")
        return cls(
            {
                s: [AudioClip.from_dict(c) for c in body.get("clips", [])]
                for s, body in d.get("scenes", {}).items()
            }
        )

    def active(self, scene: str) -> list[AudioClip]:
        """Clips that sound: not muted; if any clip is soloed, only soloed ones."""
        clips = self.scenes.get(scene, [])
        solo = [c for c in clips if c.solo and not c.mute]
        return solo if solo else [c for c in clips if not c.mute]


def sidecar_path(scene_file: str | os.PathLike[str]) -> Path:
    override = os.environ.get("MANIM_STAGE_AUDIO")
    if override:
        return Path(override)
    return project_root(scene_file) / SIDECAR_DIR / SIDECAR_NAME


def load(path: str | os.PathLike[str]) -> AudioFile:
    path = Path(path)
    if not path.exists():
        return AudioFile()
    return AudioFile.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save(path: str | os.PathLike[str], data: AudioFile) -> Path:
    """Atomic write with a ``.bak`` of the previous version (as for cues.json)."""
    import shutil

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".audio-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data.to_dict(), indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


def resolve_file(clip_file: str, root: Path) -> Path:
    p = Path(clip_file)
    return p if p.is_absolute() else (root / p)


def process(samples: np.ndarray, clip: AudioClip) -> np.ndarray:
    """Apply trim, gain and linear fades (in that order) to decoded samples."""
    a = int(round(max(clip.trim_in, 0.0) * RATE))
    b = len(samples) if clip.trim_out is None else int(round(clip.trim_out * RATE))
    out = samples[a : max(a, min(b, len(samples)))].copy()
    if clip.gain_db:
        out *= db_to_amp(clip.gain_db)
    n = len(out)
    for seconds, rising in ((clip.fade_in, True), (clip.fade_out, False)):
        k = min(n, int(round(seconds * RATE)))
        if k > 0:
            ramp = np.linspace(0.0, 1.0, k, endpoint=False, dtype=np.float32)
            if rising:
                out[:k] *= ramp[:, None]
            else:
                out[n - k :] *= ramp[::-1, None]
    return out


def processed_path(clip: AudioClip, source: Path, cache_dir: Path) -> Path:
    """Content-addressed name: source bytes + processing parameters."""
    h = hashlib.sha256()
    h.update(hashlib.sha256(source.read_bytes()).digest())
    h.update(clip.params_key().encode())
    return cache_dir / f"{h.hexdigest()[:24]}.wav"


def render_clip(clip: AudioClip, root: Path) -> Path:
    """Processed WAV for a clip (cached), ready for ``Scene.add_sound``."""
    source = resolve_file(clip.file, root)
    cache_dir = root / SIDECAR_DIR / "cache" / "audio"
    out = processed_path(clip, source, cache_dir)
    if not out.exists():
        write_wav(out, process(decode(source), clip))
    return out


# -- preview mixdown ---------------------------------------------------------------------


@dataclass(frozen=True)
class SoundPlacement:
    """A sound as Manim will mix it: file, absolute start (s) and gain (dB)."""

    file: Path
    start: float
    gain_db: float = 0.0


def sounds_from_timeline(timeline: dict[str, Any], scene_dir: Path) -> list[SoundPlacement]:
    out = []
    for e in timeline.get("events", []):
        if e["kind"] != "sound":
            continue
        m = e.get("meta", {})
        f = Path(str(m.get("file", "")))
        f = f if f.is_absolute() else scene_dir / f
        out.append(
            SoundPlacement(f, float(m.get("start_seconds", 0.0)), float(m.get("gain") or 0.0))
        )
    return out


def mix(
    sounds: list[SoundPlacement], duration: float, decoded: dict[Path, np.ndarray] | None = None
) -> np.ndarray:
    """Sum the sounds into one float32 stereo buffer of ``duration`` seconds.

    Parts before 0 or after the end are cut, as Manim does. Clipping is left to the
    output stage (soft-limited to [-1, 1] only when written or played).
    """
    n = int(math.ceil(duration * RATE))
    buf = np.zeros((n, CHANNELS), dtype=np.float32)
    cache = decoded if decoded is not None else {}
    for s in sounds:
        if s.file not in cache:
            with contextlib.suppress(Exception):
                cache[s.file] = decode(s.file)
        data = cache.get(s.file)
        if data is None or not len(data):
            continue
        a = int(round(s.start * RATE))
        src0 = max(0, -a)
        dst0 = max(0, a)
        k = min(len(data) - src0, n - dst0)
        if k > 0:
            gain = db_to_amp(s.gain_db) if s.gain_db else 1.0
            buf[dst0 : dst0 + k] += data[src0 : src0 + k] * gain
    return buf


def peaks(samples: np.ndarray, per_second: int = 100) -> np.ndarray:
    """Max |amplitude| per bucket (mono), for drawing a waveform."""
    if not len(samples):
        return np.zeros(0, dtype=np.float32)
    mono = np.abs(samples).max(axis=1)
    size = max(1, RATE // per_second)
    pad = (-len(mono)) % size
    if pad:
        mono = np.concatenate([mono, np.zeros(pad, dtype=mono.dtype)])
    return mono.reshape(-1, size).max(axis=1).astype(np.float32)


def file_peaks(path: Path, cache_dir: Path, per_second: int = 100) -> np.ndarray:
    """Peaks of a file, cached by content hash."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:24]
    cached = cache_dir / f"{digest}-{per_second}.npy"
    if cached.exists():
        with contextlib.suppress(Exception):
            return np.load(cached)
    pk = peaks(decode(path), per_second)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        np.save(cached, pk)
    return pk


def duration_of(path: Path) -> float:
    return len(decode(path)) / RATE
