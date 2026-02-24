"""Base class for zoomable content viewers using QGraphicsView."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from gradeai.constants import ZOOM_DEFAULT, ZOOM_MAX, ZOOM_MIN, ZOOM_STEP

logger = logging.getLogger(__name__)


class ZoomableScrollArea(QGraphicsView):
    """A QGraphicsView with built-in CTRL+scroll zoom behaviour.

    Zoom range is clamped between ``ZOOM_MIN`` and ``ZOOM_MAX``.  Each wheel
    notch adjusts the zoom level by ``ZOOM_STEP``.

    Signals
    -------
    zoom_changed(float)
        Emitted whenever the zoom level changes.  The float value is the
        current zoom factor (1.0 = 100%).
    """

    zoom_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._zoom_level: float = 1.0

        # Scene setup
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Rendering hints
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.set_zoom(ZOOM_DEFAULT)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def zoom_level(self) -> float:
        """Return the current zoom factor."""
        return self._zoom_level

    def set_zoom(self, level: float) -> None:
        """Set the zoom level, clamped to [ZOOM_MIN, ZOOM_MAX]."""
        level = max(ZOOM_MIN, min(ZOOM_MAX, level))
        if level == self._zoom_level:
            return

        # Calculate the relative scale factor needed
        factor = level / self._zoom_level
        self._zoom_level = level
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom_level)

    def reset_zoom(self) -> None:
        """Reset zoom to the default zoom level."""
        self.set_zoom(ZOOM_DEFAULT)

    # ------------------------------------------------------------------
    # Event overrides
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:  # noqa: N802
        """Zoom on CTRL+scroll, otherwise scroll normally."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle_delta = event.angleDelta().y()
            if angle_delta > 0:
                new_zoom = self._zoom_level + ZOOM_STEP
            elif angle_delta < 0:
                new_zoom = self._zoom_level - ZOOM_STEP
            else:
                return
            self.set_zoom(new_zoom)
            event.accept()
        else:
            super().wheelEvent(event)
