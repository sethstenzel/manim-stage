"""Narration / voiceover adapter (spec F04, backlog 2.4; ADR-0013).

manim-voiceover's ``with self.voiceover(text=...) as tracker`` is the established way
to narrate Manim scenes. On the Manim 0.30 line it doesn't run (it reads a removed
renderer attribute), it can't use pre-recorded files (its issue #100) and its
bookmarks need TTS word timings (#113). manim-stage provides the same *concepts* on
Manim primitives, without TTS, speech recognition or microphone recording in core
(spec F04):

- ``with self.narration("intro", file="intro.wav", text="... <bookmark mark='swap'/> ...")
  as n:`` plays a recorded file (``Scene.add_sound``), adds the text as a subcaption
  (``Scene.add_subcaption``) and, on exit, waits for the narration to finish.
- ``n.wait_until("swap")`` waits for a bookmark. Bookmarks are **named cues**
  (``intro.swap``), so they appear on the timeline and can be dragged (cues.json).
- Bookmark default times come from, in order: an explicit ``bookmarks={"swap": 2.1}``;
  supplied word timings (``words=[(word, start, end), ...]`` or a transcript JSON); a
  linear text-position estimate (as manim-voiceover does without word timings).
- :func:`load_voiceover_cache` reads a manim-voiceover ``cache.json`` so audio and word
  timings it generated (with any TTS service) can be reused as recorded narration.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BOOKMARK_RE = re.compile(r"""<bookmark\s+mark\s*=\s*['"]([^'"]+)['"]\s*/>""")
Word = tuple[str, float, float]  # text, start seconds, end seconds (from the file start)


def strip_bookmarks(text: str) -> tuple[str, dict[str, int]]:
    """Text without ``<bookmark/>`` tags (whitespace collapsed), and each mark's
    character offset in that clean text."""
    parts = BOOKMARK_RE.split(text)  # text, mark, text, mark, ...
    clean, marks = "", {}
    for k, part in enumerate(parts):
        if k % 2:
            marks[part] = len(clean)
            continue
        seg = re.sub(r"\s+", " ", part)
        if not clean or clean.endswith(" "):
            seg = seg.lstrip()
        clean += seg
    return clean.rstrip(), marks


def bookmark_times(
    text: str,
    duration: float,
    *,
    bookmarks: dict[str, float] | None = None,
    words: Sequence[Word] | None = None,
) -> dict[str, float]:
    """Seconds from the narration start for each bookmark in ``text``."""
    clean, marks = strip_bookmarks(text)
    explicit = dict(bookmarks or {})
    out: dict[str, float] = {}
    word_starts: list[tuple[int, float]] = []
    if words:
        # character offset of each word in the clean text, matched in order
        pos = 0
        lowered = clean.lower()
        for w, start, _end in words:
            i = lowered.find(w.lower().strip(".,;:!?\"'"), pos)
            if i >= 0:
                word_starts.append((i, float(start)))
                pos = i + 1
    for name, off in marks.items():
        if name in explicit:
            out[name] = float(explicit[name])
        elif word_starts:
            nxt = next((t for i, t in word_starts if i >= off), None)
            out[name] = nxt if nxt is not None else duration
        else:
            out[name] = duration * (off / max(len(clean), 1))
    for name, t in explicit.items():  # explicit marks not present in the text
        out.setdefault(name, float(t))
    return out


def load_words(path: str | Path) -> list[Word]:
    """Word timings from a transcript JSON.

    Accepts ``[{"word"|"text", "start", "end"}, ...]``, ``{"words": [...]}`` and
    ``{"segments": [{"words": [...]}]}`` (Whisper / stable-ts / WhisperX style).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "segments" in data:
        items = [w for seg in data["segments"] for w in seg.get("words", [])]
    elif isinstance(data, dict):
        items = data.get("words", [])
    else:
        items = data
    out = []
    for w in items:
        text = (w.get("word") or w.get("text") or "").strip()
        if text:
            out.append((text, float(w["start"]), float(w["end"])))
    return out


@dataclass
class CachedVoiceover:
    text: str
    audio: Path
    words: list[Word] = field(default_factory=list)


def load_voiceover_cache(path: str | Path) -> list[CachedVoiceover]:
    """Entries of a manim-voiceover ``cache.json`` (audio files are next to it).

    Word boundaries come from ``word_boundaries`` (``audio_offset`` in 100 ns ticks,
    ``text``), as manim-voiceover stores them.
    """
    path = Path(path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for e in entries:
        audio = path.parent / (e.get("final_audio") or e.get("original_audio"))
        words = []
        bounds = e.get("word_boundaries") or []
        for i, b in enumerate(bounds):
            start = b["audio_offset"] / 10_000_000
            end = (bounds[i + 1]["audio_offset"] / 10_000_000) if i + 1 < len(bounds) else start
            words.append((b.get("text", ""), start, end))
        text = e.get("input_text") or e.get("input_data", {}).get("input_text", "")
        out.append(CachedVoiceover(text, audio, words))
    return out


def find_cached(entries: Sequence[CachedVoiceover], text: str) -> CachedVoiceover | None:
    """The cache entry whose text matches ``text`` (bookmarks and whitespace ignored)."""
    want = strip_bookmarks(text)[0]
    for e in entries:
        if strip_bookmarks(e.text)[0] == want:
            return e
    return None


class Narration:
    """Handle returned by ``StageScene.narration(...)`` (like manim-voiceover's tracker)."""

    def __init__(
        self,
        scene: Any,
        name: str,
        file: Path,
        *,
        text: str | None,
        bookmarks: dict[str, float],
        start_frame: int,
        duration: float,
        fps: float,
        words: list[Word],
    ) -> None:
        self.scene, self.name, self.file = scene, name, file
        self.text, self.bookmarks, self.words = text, bookmarks, words
        self.start_frame, self.duration, self.fps = start_frame, duration, fps

    @property
    def start(self) -> float:
        return self.start_frame / self.fps

    @property
    def end(self) -> float:
        return self.start + self.duration

    def get_remaining_duration(self) -> float:
        from . import _compat

        return max(0.0, self.end - _compat.scene_frame(self.scene, self.fps) / self.fps)

    def time_until_bookmark(self, mark: str) -> float:
        from . import _compat

        now = _compat.scene_frame(self.scene, self.fps) / self.fps
        return max(0.0, self.start + self.bookmarks[mark] - now)

    def wait_until(self, mark: str) -> Any:
        """Wait for a bookmark. It is the cue ``<narration>.<mark>`` (draggable)."""
        if mark not in self.bookmarks:
            raise KeyError(
                f"narration {self.name!r} has no bookmark {mark!r}; known: {sorted(self.bookmarks)}"
            )
        return self.scene.cue(
            f"{self.name}.{mark}",
            at=self.start + self.bookmarks[mark],
            description=f"bookmark in narration {self.name!r}",
        )

    def wait_for_end(self) -> None:
        remaining = self.get_remaining_duration()
        frames = int(round(remaining * self.fps))
        if frames > 0:
            self.scene.wait(frames / self.fps)
