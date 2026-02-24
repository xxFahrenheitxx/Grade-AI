"""Semi-transparent loading overlay with delayed display."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadingOverlay(QWidget):
    """A semi-transparent overlay with a centered loading message.

    The overlay only becomes visible after a configurable delay (default
    500 ms).  If ``hide_loading()`` is called before the delay elapses
    the overlay is never shown, avoiding flicker on fast operations.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "color: white; font-size: 14px; font-weight: bold;"
            " background: rgba(0, 0, 0, 0.70); border-radius: 8px;"
            " padding: 16px 24px;"
        )
        layout.addWidget(self._label)

        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._do_show)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_after_delay(self, message: str = "Loading...", delay_ms: int = 500) -> None:
        """Start a timer; show the overlay only if not hidden before *delay_ms*."""
        self._label.setText(message)
        self._delay_timer.start(delay_ms)

    def hide_loading(self) -> None:
        """Cancel the pending timer and hide immediately."""
        self._delay_timer.stop()
        self.setVisible(False)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()
        super().paintEvent(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_show(self) -> None:
        if self.parentWidget():
            self.resize(self.parentWidget().size())
        self.setVisible(True)
        self.raise_()
