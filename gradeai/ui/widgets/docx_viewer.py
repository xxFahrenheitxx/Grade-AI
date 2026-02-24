"""Word document (.docx) viewer using python-docx."""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextBrowser

logger = logging.getLogger(__name__)

# python-docx is an optional-but-expected dependency
try:
    from docx import Document as DocxDocument
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph as DocxParagraph

    _HAS_DOCX = True
except ImportError:  # pragma: no cover
    _HAS_DOCX = False
    logger.warning("python-docx is not installed; .docx viewing is disabled.")

_DEFAULT_FONT_SIZE = 11
_MIN_FONT_SIZE = 6
_MAX_FONT_SIZE = 48


class DocxViewer(QTextBrowser):
    """Read-only viewer for Word ``.docx`` files.

    Converts paragraphs, tables, and basic character formatting (bold, italic,
    underline) to HTML for display in a ``QTextBrowser``.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._file_path: Optional[Path] = None
        self._font_size: int = _DEFAULT_FONT_SIZE

        self.setReadOnly(True)
        self.setOpenExternalLinks(True)

        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Open a ``.docx`` file and display its content as HTML."""
        self._file_path = path

        if not _HAS_DOCX:
            self.setHtml(
                "<p><i>python-docx is required to view .docx files.</i></p>"
            )
            return

        try:
            doc = DocxDocument(str(path))
        except Exception:
            logger.exception("Failed to open docx: %s", path)
            self.setHtml("<p><i>Error: could not open document.</i></p>")
            return

        html_parts: list[str] = []
        html_parts.append(
            "<html><head><style>"
            "body { font-family: Calibri, Arial, sans-serif; margin: 10px; }"
            "table { border-collapse: collapse; margin: 8px 0; width: 100%; }"
            "td, th { border: 1px solid #888; padding: 4px 8px; }"
            "th { background-color: #333; }"
            "</style></head><body>"
        )

        for element in doc.element.body:
            tag = element.tag.split("}")[-1]  # strip namespace
            if tag == "p":
                para = DocxParagraph(element, doc)
                html_parts.append(self._paragraph_to_html(para))
            elif tag == "tbl":
                table = DocxTable(element, doc)
                html_parts.append(self._table_to_html(table))

        html_parts.append("</body></html>")
        self.setHtml("\n".join(html_parts))

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _paragraph_to_html(para: DocxParagraph) -> str:
        """Convert a python-docx Paragraph to an HTML string."""
        style_name = (para.style.name or "").lower() if para.style else ""

        # Determine tag based on heading level
        tag = "p"
        if style_name.startswith("heading"):
            try:
                level = int(style_name.replace("heading", "").strip())
                level = max(1, min(6, level))
                tag = f"h{level}"
            except ValueError:
                pass
        elif style_name.startswith("list"):
            tag = "li"

        runs_html: list[str] = []
        for run in para.runs:
            text = html.escape(run.text)
            if not text:
                continue
            if run.bold:
                text = f"<b>{text}</b>"
            if run.italic:
                text = f"<i>{text}</i>"
            if run.underline:
                text = f"<u>{text}</u>"
            runs_html.append(text)

        content = "".join(runs_html) or "&nbsp;"

        # Alignment
        alignment = ""
        if para.alignment is not None:
            align_map = {0: "left", 1: "center", 2: "right", 3: "justify"}
            align_val = align_map.get(para.alignment, "")  # type: ignore[arg-type]
            if align_val:
                alignment = f' style="text-align:{align_val}"'

        return f"<{tag}{alignment}>{content}</{tag}>"

    @staticmethod
    def _table_to_html(table: DocxTable) -> str:
        """Convert a python-docx Table to an HTML string."""
        rows_html: list[str] = []
        for row in table.rows:
            cells_html: list[str] = []
            for cell in row.cells:
                cell_text = html.escape(cell.text)
                cells_html.append(f"<td>{cell_text}</td>")
            rows_html.append("<tr>" + "".join(cells_html) + "</tr>")
        return "<table>" + "".join(rows_html) + "</table>"

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
            font.setPointSize(self._font_size)
            self.setFont(font)
            event.accept()
        else:
            super().wheelEvent(event)
