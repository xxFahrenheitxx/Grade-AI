"""Code viewer with Pygments-based syntax highlighting and line numbers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

logger = logging.getLogger(__name__)

# Pygments is an optional-but-expected dependency
try:
    from pygments import lex
    from pygments.lexers import get_lexer_for_filename, TextLexer
    from pygments.token import (
        Comment,
        Error,
        Keyword,
        Literal,
        Name,
        Number,
        Operator,
        Punctuation,
        String,
        Token,
    )

    _HAS_PYGMENTS = True
except ImportError:  # pragma: no cover
    _HAS_PYGMENTS = False
    logger.warning("Pygments is not installed; syntax highlighting is disabled.")

# Font settings
_FONT_FAMILY = "Consolas"
_FONT_FALLBACK = "Courier New"
_DEFAULT_FONT_SIZE = 13  # pixels
_MIN_FONT_SIZE = 6
_MAX_FONT_SIZE = 48

# ---------------------------------------------------------------------------
# Colour palette (dark-theme defaults, similar to VSCode Dark+)
# ---------------------------------------------------------------------------
_TOKEN_COLORS: dict[object, str] = {}

if _HAS_PYGMENTS:
    _TOKEN_COLORS = {
        Token: "#D4D4D4",
        Comment: "#6A9955",
        Comment.Single: "#6A9955",
        Comment.Multiline: "#6A9955",
        Comment.Preproc: "#C586C0",
        Keyword: "#569CD6",
        Keyword.Constant: "#569CD6",
        Keyword.Declaration: "#569CD6",
        Keyword.Namespace: "#C586C0",
        Keyword.Type: "#4EC9B0",
        Name: "#D4D4D4",
        Name.Builtin: "#DCDCAA",
        Name.Class: "#4EC9B0",
        Name.Decorator: "#DCDCAA",
        Name.Exception: "#4EC9B0",
        Name.Function: "#DCDCAA",
        Name.Tag: "#569CD6",
        Name.Attribute: "#9CDCFE",
        String: "#CE9178",
        String.Doc: "#6A9955",
        String.Escape: "#D7BA7D",
        String.Regex: "#D16969",
        Number: "#B5CEA8",
        Number.Integer: "#B5CEA8",
        Number.Float: "#B5CEA8",
        Operator: "#D4D4D4",
        Operator.Word: "#569CD6",
        Punctuation: "#D4D4D4",
        Literal: "#CE9178",
        Error: "#F44747",
    }


def _format_for_token(token_type) -> QTextCharFormat:
    """Build a ``QTextCharFormat`` for a Pygments token type."""
    fmt = QTextCharFormat()
    # Walk the token-type hierarchy until we find a colour
    tt = token_type
    while tt:
        color = _TOKEN_COLORS.get(tt)
        if color:
            fmt.setForeground(QColor(color))
            return fmt
        tt = tt.parent
    fmt.setForeground(QColor("#D4D4D4"))
    return fmt


# ---------------------------------------------------------------------------
# QSyntaxHighlighter backed by Pygments
# ---------------------------------------------------------------------------

class _PygmentsHighlighter(QSyntaxHighlighter):
    """Applies Pygments tokenisation to a ``QTextDocument``."""

    def __init__(self, document: QTextDocument, lexer=None) -> None:
        super().__init__(document)
        self._lexer = lexer

    def set_lexer(self, lexer) -> None:
        self._lexer = lexer
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        if self._lexer is None or not _HAS_PYGMENTS:
            return
        index = 0
        for token_type, value in lex(text, self._lexer):
            length = len(value)
            if length:
                fmt = _format_for_token(token_type)
                self.setFormat(index, length, fmt)
            index += length


# ---------------------------------------------------------------------------
# Line-number gutter (identical pattern to TextEditor)
# ---------------------------------------------------------------------------

class _LineNumberArea(QWidget):
    def __init__(self, editor: CodeViewer) -> None:  # noqa: F821
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self._editor.paint_line_numbers(event)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class CodeViewer(QPlainTextEdit):
    """Read-only (by default) code viewer with syntax highlighting.

    Supports ``.py``, ``.js``, ``.sql``, ``.html``, ``.css``, ``.java``,
    ``.c``, ``.cpp``, ``.json``, ``.xml``, ``.yaml`` and more via Pygments
    auto-detection from the file extension.
    """

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

        # Tab width
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * 4
        )

        # Read-only by default
        self.setReadOnly(True)

        # Line-number gutter
        self._line_number_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width(0)

        # Syntax highlighter (lexer will be set when a file is loaded)
        self._highlighter: Optional[_PygmentsHighlighter] = None
        if _HAS_PYGMENTS:
            self._highlighter = _PygmentsHighlighter(self.document())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Load a source file and apply syntax highlighting."""
        self._file_path = path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Failed to read code file: %s", path)
            text = ""

        # Determine lexer from file extension
        if _HAS_PYGMENTS:
            try:
                lexer = get_lexer_for_filename(path.name, stripall=True)
            except Exception:
                lexer = TextLexer()
            if self._highlighter is not None:
                self._highlighter.set_lexer(lexer)

        self.setPlainText(text)

    def set_editable(self, editable: bool) -> None:
        """Toggle between read-only and editable mode."""
        self.setReadOnly(not editable)

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    # ------------------------------------------------------------------
    # Line-number gutter
    # ------------------------------------------------------------------

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        padding = 16
        return self.fontMetrics().horizontalAdvance("9") * digits + padding

    def paint_line_numbers(self, event) -> None:
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
