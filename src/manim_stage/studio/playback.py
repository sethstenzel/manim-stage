"""Playback state for the viewport: playhead, play/pause, speed, loop range (spec F01).

Pure Python (no Qt) so it is unit-testable. Time is an integer frame index at the
preview frame rate (docs/schemas/README.md time model). While playing, the playhead
is derived from elapsed wall time × speed, not by adding per-tick increments, so it
does not drift; if the next frame has not been rendered yet, playback holds
("buffering") instead of skipping ahead.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Container
from dataclasses import dataclass

SPEEDS = (0.25, 0.5, 1.0, 1.5, 2.0, 4.0)


@dataclass
class PlayRange:
    start: int
    end: int  # exclusive

    def clamp(self, frame: int) -> int:
        return max(self.start, min(frame, self.end - 1))


class Playback:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self.fps = 15.0
        self.total = 0  # frames in the scene
        self.frame = 0
        self.playing = False
        self.buffering = False
        self.speed = 1.0
        self.loop = True
        self.range: PlayRange | None = None  # None = whole scene
        self._anchor_time = 0.0
        self._anchor_frame = 0

    # -- scene / revision changes -----------------------------------------------------

    def set_scene(self, fps: float, total: int) -> bool:
        """New timeline. Keeps the playhead if still valid; returns False if it was reset."""
        self.fps, self.total = fps, total
        valid = 0 <= self.frame < max(total, 1)
        if not valid:
            self.frame = 0
        if self.range and (self.range.end > total or self.range.start >= total):
            self.range = None
        self._reanchor()
        return valid

    # -- transport --------------------------------------------------------------------

    @property
    def bounds(self) -> PlayRange:
        return self.range or PlayRange(0, max(self.total, 1))

    def play(self) -> None:
        if self.total <= 0:
            return
        if self.frame >= self.bounds.end - 1:
            self.frame = self.bounds.start  # play from the start when at the end
        self.playing = True
        self._reanchor()

    def pause(self) -> None:
        self.playing = False
        self.buffering = False

    def toggle(self) -> None:
        self.pause() if self.playing else self.play()

    def seek(self, frame: int) -> None:
        self.frame = max(0, min(int(frame), max(self.total - 1, 0)))
        self._reanchor()

    def step(self, frames: int) -> None:
        self.pause()
        self.seek(self.frame + frames)

    def seek_seconds(self, seconds: float) -> None:
        self.seek(math.floor(seconds * self.fps + 1e-9))

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.speed = speed
        self._reanchor()

    def set_range(self, start: int | None, end: int | None) -> None:
        """Loop/play range in frames, half-open. ``None`` clears it."""
        if start is None or end is None:
            self.range = None
            return
        start, end = sorted((max(0, start), min(end, self.total)))
        self.range = PlayRange(start, end) if end > start else None
        if self.range:
            self.frame = self.range.clamp(self.frame)
            self._reanchor()

    # -- clock ------------------------------------------------------------------------

    def _reanchor(self) -> None:
        self._anchor_time = self._clock()
        self._anchor_frame = self.frame

    def tick(self, available: Container[int]) -> int:
        """Advance while playing; ``available`` holds rendered frame indices."""
        if not self.playing or self.total <= 0:
            return self.frame
        b = self.bounds
        target = self._anchor_frame + int(
            (self._clock() - self._anchor_time) * self.fps * self.speed
        )
        if target >= b.end:
            if self.loop:
                self.frame = b.start
                self._reanchor()
                target = b.start
            else:
                self.frame = b.end - 1
                self.pause()
                return self.frame
        # Advance through rendered frames only; hold at the first missing one.
        f = self.frame
        while f < target and (f + 1) in available:
            f += 1
        self.buffering = f < target
        if self.buffering:
            self.frame = f
            self._reanchor()  # resume smoothly once the frame arrives
        else:
            self.frame = target
        return self.frame

    # -- display ----------------------------------------------------------------------

    def timecode(self, frame: int | None = None) -> str:
        """``mm:ss.ff`` where ``ff`` is the frame within the second."""
        f = self.frame if frame is None else frame
        fps = max(self.fps, 1e-9)
        secs = f / fps
        whole = int(secs + 1e-9)
        within = f - round(whole * fps)
        return f"{whole // 60:02d}:{whole % 60:02d}.{max(within, 0):02d}"
