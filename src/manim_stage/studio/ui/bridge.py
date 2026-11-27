"""Hands PreviewService events (background threads) to the Qt GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..service import PreviewMessage, PreviewService


class ServiceBridge(QObject):
    """Re-emits every :class:`PreviewMessage` as a queued Qt signal."""

    message = Signal(object)

    def __init__(self, service: PreviewService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._unsubscribe = service.subscribe(self._forward)

    def _forward(self, msg: PreviewMessage) -> None:
        self.message.emit(msg)  # queued: the receiver lives in the GUI thread

    def detach(self) -> None:
        self._unsubscribe()
