"""Read-only Markdown preview viewer using QTextBrowser."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import markdown
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextBrowser

from gradeai.constants import ZOOM_MAX, ZOOM_MIN

logger = logging.getLogger(__name__)

# Default font size (points) and zoom limits for the text browser
_DEFAULT_FONT_SIZE = 11
_MIN_FONT_SIZE = 6
_MAX_FONT_SIZE = 48


class MarkdownViewer(QTextBrowser):
    """A read-only Markdown preview widget.

    Converts ``.md`` files to HTML via the ``markdown`` library and renders
    them inside a ``QTextBrowser``.  Images referenced in the Markdown source
    are resolved relative to the file's parent directory.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._file_path: Optional[Path] = None
        self._font_size: int = _DEFAULT_FONT_SIZE

        # Make the browser read-only and open external links
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)

        # Set initial font size
        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Load a Markdown file, convert to HTML, and display it."""
        self._file_path = path
        try:
            md_text = path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Failed to read markdown file: %s", path)
            self.setHtml("<p><i>Error: could not read file.</i></p>")
            return

        html = markdown.markdown(
            md_text,
            extensions=["tables", "fenced_code", "codehilite", "toc"],
        )

        # Set search paths so that relative image references resolve
        self.setSearchPaths([str(path.parent)])
        self.setHtml(html)

    @property
    def file_path(self) -> Optional[Path]:
        """Return the path of the currently loaded file."""
        return self._file_path

    # ------------------------------------------------------------------
    # CTRL+scroll zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:  # noqa: N802
        """Zoom (adjust font size) on CTRL+scroll; scroll normally otherwise."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle_delta = event.angleDelta().y()
            if angle_delta > 0:
                self._font_size = min(_MAX_FONT_SIZE, self._font_size + 1)
            elif angle_delta < 0:
                self._font_size = max(_MIN_FONT_SIZE, self._font_size - 1)
            else:
                return
            font = self.font()
            font.setPointSize(self._font_size)
            self.setFont(font)
            event.accept()
        else:
            super().wheelEvent(event)
