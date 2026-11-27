"""Preview audio playback (spec F04): plays the scene's mixdown in sync with the playhead.

Uses ``sounddevice`` (PortAudio) when available. If it isn't installed, PortAudio is
missing (some Linux systems) or there is no output device, the player reports
``available = False`` with a reason, and the preview stays silent; nothing else
changes. ``MANIM_STAGE_NO_AUDIO=1`` disables it (tests, CI). No Qt.

The mix is the scene's sounds exactly as Manim will mix them
(:func:`manim_stage.audio.mix` of the timeline's sound events).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

import numpy as np

from ..audio import CHANNELS, RATE


class AudioPlayer:
    def __init__(self, stream_factory: Callable[..., Any] | None = None) -> None:
        self._lock = threading.Lock()
        self._mix = np.zeros((0, CHANNELS), dtype=np.float32)
        self._pos = 0  # next sample to play
        self._playing = False
        self._stream: Any = None
        self.reason = ""
        self.muted = False
        if stream_factory is None and os.environ.get("MANIM_STAGE_NO_AUDIO"):
            self.reason = "disabled by MANIM_STAGE_NO_AUDIO"
        elif stream_factory is None:
            try:
                import sounddevice as sd

                sd.query_devices(kind="output")
                stream_factory = sd.OutputStream
            except Exception as e:  # ImportError, OSError (no PortAudio), no device
                self.reason = f"no audio output ({type(e).__name__}: {e})"
        self._factory = stream_factory

    @property
    def available(self) -> bool:
        return self._factory is not None

    @property
    def playing(self) -> bool:
        return self._playing

    def set_mix(self, samples: np.ndarray) -> None:
        with self._lock:
            self._mix = np.ascontiguousarray(np.clip(samples, -1.0, 1.0), dtype=np.float32)

    @property
    def duration(self) -> float:
        return len(self._mix) / RATE

    def position(self) -> float:
        return self._pos / RATE

    def _callback(self, outdata: np.ndarray, frames: int, _time: Any, _status: Any) -> None:
        with self._lock:
            a = self._pos
            chunk = self._mix[a : a + frames]
            n = len(chunk)
            if n and not self.muted:
                outdata[:n] = chunk
            else:
                outdata[:n] = 0
            outdata[n:] = 0
            self._pos = a + frames

    def play(self, seconds: float) -> None:
        """Start (or restart) playback at ``seconds`` into the scene."""
        if not self.available:
            return
        with self._lock:
            self._pos = max(0, int(round(seconds * RATE)))
        if self._stream is None:
            try:
                self._stream = self._factory(
                    samplerate=RATE, channels=CHANNELS, dtype="float32", callback=self._callback
                )
                self._stream.start()
            except Exception as e:
                self._factory, self.reason = None, f"audio output failed: {e}"
                self._stream = None
                return
        self._playing = True

    def seek(self, seconds: float) -> None:
        with self._lock:
            self._pos = max(0, int(round(seconds * RATE)))

    def stop(self) -> None:
        self._playing = False
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def drift(self, seconds: float) -> float:
        """How far audio is ahead (+) or behind (−) the given playhead time."""
        return self.position() - seconds
