"""Hands PreviewService events (background threads) to the Qt GUI thread.

Background threads never touch Qt objects: they only append to a lock-free deque.
A GUI-thread timer drains it and emits :attr:`ServiceBridge.message`. This avoids
cross-thread signal emission entirely, so a window can be closed while runner
threads are still reporting without any risk of touching a destroyed QObject.
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, QTimer, Signal

from ..service import PreviewMessage, PreviewService

MAX_PER_DRAIN = 500  # keep the GUI responsive when hundreds of frames arrive at once


class ServiceBridge(QObject):
    """Re-emits every :class:`PreviewMessage` on the GUI thread, in order."""

    message = Signal(object)

    def __init__(self, service: PreviewService, parent: QObject | None = None,
                 interval_ms: int = 5) -> None:  # fmt: skip
        super().__init__(parent)
        self.service = service
        self._queue: deque[PreviewMessage] = deque()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.drain)
        self._timer.start(interval_ms)
        self._unsubscribe = service.subscribe(self._queue.append)

    def drain(self) -> int:
        """Deliver queued messages (GUI thread). Returns how many were delivered."""
        n = 0
        while self._queue and n < MAX_PER_DRAIN:
            self.message.emit(self._queue.popleft())
            n += 1
        return n

    def detach(self) -> None:
        self._unsubscribe()
        self._timer.stop()
        self._queue.clear()
