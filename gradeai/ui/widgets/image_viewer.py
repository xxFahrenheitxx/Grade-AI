"""Single-image viewer widget with zoom support."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from gradeai.ui.widgets.zoomable_scroll_area import ZoomableScrollArea

logger = logging.getLogger(__name__)

# Supported image file extensions (kept in sync with constants.IMAGE_EXTENSIONS)
SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp",
}


class ImageViewer(ZoomableScrollArea):
    """Displays a single image inside a ``QGraphicsScene`` with zoom.

    Supports the common raster formats: JPEG, PNG, BMP, GIF, TIFF, and WebP.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._file_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Load and display the image at *path*."""
        self._scene.clear()
        self._pixmap_item = None
        self._file_path = None

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            logger.error("Failed to load image: %s", path)
            return

        self._file_path = path
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

        # Fit the image in the view initially
        self.fitInView(self._pixmap_item, aspectRatioMode=1)  # Qt.KeepAspectRatio

    @property
    def file_path(self) -> Optional[Path]:
        """Return the path of the currently loaded image, or ``None``."""
        return self._file_path

    def get_annotation_page_dimensions(self) -> list[tuple[float, float, float]]:
        """Return synthetic single-page dimensions for annotation overlays."""
        rect = self._scene.sceneRect()
        return [(rect.width(), rect.height(), 0.0)]
