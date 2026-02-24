"""Plain-text / Markdown editor with line numbers and zoom support."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QWidget

logger = logging.getLogger(__name__)

# Font settings
_FONT_FAMILY = "Consolas"
_FONT_FALLBACK = "Courier New"
_DEFAULT_FONT_SIZE = 13  # pixels
_MIN_FONT_SIZE = 6
_MAX_FONT_SIZE = 48


class _LineNumberArea(QWidget):
    """Gutter widget that paints line numbers for ``TextEditor``."""

    def __init__(self, editor: TextEditor) -> None:  # noqa: F821
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self._editor.paint_line_numbers(event)


class TextEditor(QPlainTextEdit):
    """A plain-text editor with VSCode-style line numbers and CTRL+scroll zoom.

    Signals
    -------
    content_changed()
        Emitted whenever the document text is modified by the user.
    """

    content_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._file_path: Optional[Path] = None
        self._font_size: int = _DEFAULT_FONT_SIZE

        # Monospace font
        font = QFont(_FONT_FAMILY)
        if not font.exactMatch():
            font = QFont(_FONT_FALLBACK)
        font.setPixelSize(self._font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # Tab width (4 spaces)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * 4
        )

        # Line-number gutter
        self._line_number_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width(0)

        # Track modifications
        self.document().setModified(False)
        self.textChanged.connect(self._on_text_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Load the contents of *path* into the editor."""
        self._file_path = path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Failed to read file: %s", path)
            text = ""
        self.setPlainText(text)
        self.document().setModified(False)

    def save_file(self) -> None:
        """Write the current contents back to the loaded file."""
        if self._file_path is None:
            logger.warning("save_file called but no file is loaded.")
            return
        try:
            self._file_path.write_text(
                self.toPlainText(), encoding="utf-8"
            )
            self.document().setModified(False)
        except OSError:
            logger.exception("Failed to save file: %s", self._file_path)

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    @property
    def is_modified(self) -> bool:
        """Return ``True`` if the document has unsaved changes."""
        return self.document().isModified()

    # ------------------------------------------------------------------
    # Line-number gutter
    # ------------------------------------------------------------------

    def line_number_area_width(self) -> int:
        """Calculate the pixel width needed for the line-number gutter."""
        digits = max(1, len(str(self.blockCount())))
        padding = 16  # left + right padding
        return self.fontMetrics().horizontalAdvance("9") * digits + padding

    def paint_line_numbers(self, event) -> None:
        """Paint the line numbers inside the gutter widget."""
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#2B2B2B"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block)
            .translated(self.contentOffset())
            .top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        line_color = QColor("#858585")
        current_line_color = QColor("#C6C6C6")
        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == current_block:
                    painter.setPen(current_line_color)
                else:
                    painter.setPen(line_color)
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

        painter.end()

    # ------------------------------------------------------------------
    # Resize / update hooks
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def _update_line_number_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    # ------------------------------------------------------------------
    # CTRL+scroll zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle_delta = event.angleDelta().y()
            if angle_delta > 0:
                self._font_size = min(_MAX_FONT_SIZE, self._font_size + 1)
            elif angle_delta < 0:
                self._font_size = max(_MIN_FONT_SIZE, self._font_size - 1)
            else:
                return
            font = self.font()
            font.setPixelSize(self._font_size)
            self.setFont(font)
            self.setTabStopDistance(
                self.fontMetrics().horizontalAdvance(" ") * 4
            )
            self._update_line_number_area_width(0)
            event.accept()
        else:
            super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        self.content_changed.emit()
