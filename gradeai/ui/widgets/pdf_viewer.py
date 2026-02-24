"""PDF document viewer using PyMuPDF (fitz) with lazy page rendering."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from gradeai.ui.widgets.zoomable_scroll_area import ZoomableScrollArea

logger = logging.getLogger(__name__)

# Spacing (in scene pixels) between rendered pages
_PAGE_GAP = 20

# Base DPI for rendering; higher = sharper at 1x zoom
_BASE_DPI = 150


class PDFViewer(ZoomableScrollArea):
    """Displays a multi-page PDF with lazy rendering and zoom support.

    Only pages that are currently visible (plus one buffer page above and
    below) are rendered to pixmap items.  When the zoom level changes every
    page is re-rendered at the new resolution.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._doc: Optional[fitz.Document] = None
        self._file_path: Optional[Path] = None
        self._page_items: list[Optional[QGraphicsPixmapItem]] = []
        self._page_rects: list[QRectF] = []  # scene rects for each page
        self._page_count: int = 0

        # Timer used to debounce rendering after scroll / zoom
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(50)
        self._render_timer.timeout.connect(self._render_visible_pages)

        # Re-render pages when zoom changes
        self.zoom_changed.connect(self._on_zoom_changed)

        # Schedule render check when scrollbars move
        self.verticalScrollBar().valueChanged.connect(self._schedule_render)
        self.horizontalScrollBar().valueChanged.connect(self._schedule_render)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Open a PDF file and prepare the scene layout."""
        self._clear()
        try:
            self._doc = fitz.open(str(path))
        except Exception:
            logger.exception("Failed to open PDF: %s", path)
            return

        self._file_path = path
        self._page_count = len(self._doc)
        self._page_items = [None] * self._page_count

        self._layout_pages()
        # Render only the first page immediately for faster perceived open,
        # then render visible/buffer pages on the next event-loop turn.
        self._render_initial_page()
        QTimer.singleShot(0, self._render_visible_pages)

    def get_page_count(self) -> int:
        """Return the total number of pages."""
        return self._page_count

    def get_annotation_page_dimensions(self) -> list[tuple[float, float, float]]:
        """Return page dimensions for annotation overlays."""
        return [(rect.width(), rect.height(), rect.y()) for rect in self._page_rects]

    def release_resources(self) -> None:
        """Release open PDF handles immediately."""
        self._clear()

    @property
    def current_page(self) -> int:
        """Return the 0-based index of the page currently centred in view."""
        if not self._page_rects:
            return 0

        centre_scene = self.mapToScene(self.viewport().rect().center())
        for idx, rect in enumerate(self._page_rects):
            if rect.contains(centre_scene):
                return idx
        # Fallback: closest page
        min_dist = float("inf")
        closest = 0
        for idx, rect in enumerate(self._page_rects):
            dist = abs(rect.center().y() - centre_scene.y())
            if dist < min_dist:
                min_dist = dist
                closest = idx
        return closest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _layout_pages(self) -> None:
        """Pre-compute the scene rectangles for every page (at 1x zoom)."""
        if self._doc is None:
            return

        y_offset = 0.0
        self._page_rects.clear()

        for page_num in range(self._page_count):
            page = self._doc[page_num]
            # Page size in points -> pixels at base DPI
            scale = _BASE_DPI / 72.0
            width = page.rect.width * scale
            height = page.rect.height * scale

            rect = QRectF(0, y_offset, width, height)
            self._page_rects.append(rect)
            y_offset += height + _PAGE_GAP

        # Set the scene rect large enough for all pages
        if self._page_rects:
            last = self._page_rects[-1]
            max_width = max(r.width() for r in self._page_rects)
            self._scene.setSceneRect(0, 0, max_width, last.bottom())

    def _visible_page_range(self) -> tuple[int, int]:
        """Return the (start, end) indices of pages visible in the viewport.

        Includes one buffer page above and below.
        """
        if not self._page_rects:
            return (0, 0)

        viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        first_visible = 0
        last_visible = self._page_count - 1

        for idx, rect in enumerate(self._page_rects):
            if rect.bottom() >= viewport_rect.top():
                first_visible = idx
                break

        for idx in range(self._page_count - 1, -1, -1):
            if self._page_rects[idx].top() <= viewport_rect.bottom():
                last_visible = idx
                break

        # Buffer
        first_visible = max(0, first_visible - 1)
        last_visible = min(self._page_count - 1, last_visible + 1)

        return (first_visible, last_visible)

    def _render_page(self, page_num: int) -> None:
        """Render a single page and place/update its pixmap item."""
        if self._doc is None:
            return

        page = self._doc[page_num]
        scale = _BASE_DPI / 72.0
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        qimage = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
        )
        pixmap = QPixmap.fromImage(qimage)

        rect = self._page_rects[page_num]

        if self._page_items[page_num] is None:
            item = QGraphicsPixmapItem(pixmap)
            item.setPos(rect.topLeft())
            self._scene.addItem(item)
            self._page_items[page_num] = item
        else:
            self._page_items[page_num].setPixmap(pixmap)
            self._page_items[page_num].setPos(rect.topLeft())

    def _render_initial_page(self) -> None:
        """Render only page 0 to provide an immediate visual result."""
        if self._doc is None or self._page_count == 0:
            return
        self._render_page(0)

    def _unload_page(self, page_num: int) -> None:
        """Remove a page pixmap from the scene to free memory."""
        item = self._page_items[page_num]
        if item is not None:
            self._scene.removeItem(item)
            self._page_items[page_num] = None

    def _render_visible_pages(self) -> None:
        """Render only the visible pages (+ buffer) and unload the rest."""
        if self._doc is None or self._page_count == 0:
            return

        first, last = self._visible_page_range()

        for idx in range(self._page_count):
            if first <= idx <= last:
                self._render_page(idx)
            else:
                self._unload_page(idx)

    def _schedule_render(self) -> None:
        """Debounced render trigger after scroll."""
        self._render_timer.start()

    def _on_zoom_changed(self, _level: float) -> None:
        """Re-render all visible pages at the new zoom / scale."""
        self._render_visible_pages()

    def _clear(self) -> None:
        """Close the current document and reset state."""
        self._render_timer.stop()
        if self._doc is not None:
            self._doc.close()
            self._doc = None

        self._scene.clear()
        self._page_items.clear()
        self._page_rects.clear()
        self._page_count = 0
        self._file_path = None

    def closeEvent(self, event) -> None:  # noqa: N802
        """Ensure PDF handles are closed when the widget closes."""
        self._clear()
        super().closeEvent(event)
