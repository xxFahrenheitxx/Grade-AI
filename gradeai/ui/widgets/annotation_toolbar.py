"""Floating annotation toolbar for exam documents.

Shows at the bottom-centre of the centre panel when an exam file is
the active document.  Provides two tools: red text annotation and
fluorescent-red highlighter (stabilo effect).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QWidget,
)


class AnnotationToolbar(QFrame):
    """Floating toolbar with annotation tools for exam documents.

    Signals
    -------
    text_annotation_toggled(bool)
        Emitted when the text annotation tool is toggled on/off.
    highlight_toggled(bool)
        Emitted when the highlighter tool is toggled on/off.
    """

    text_annotation_toggled = Signal(bool)
    highlight_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("annotationToolbar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(44)
        self.setStyleSheet(
            "QFrame#annotationToolbar {"
            "  background: rgba(30, 30, 30, 0.92);"
            "  border: 1px solid #444;"
            "  border-radius: 8px;"
            "  padding: 4px 12px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Text annotation button (red text)
        self._text_btn = QPushButton("\u270E  Text Annotation")
        self._text_btn.setCheckable(True)
        self._text_btn.setToolTip("Click on document to place a red text annotation")
        self._text_btn.setStyleSheet(
            "QPushButton { color: #F14C4C; font-weight: bold; padding: 4px 12px;"
            "  border: 1px solid transparent; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(241, 76, 76, 0.1); }"
            "QPushButton:checked { background: rgba(241, 76, 76, 0.2);"
            "  border: 1px solid #F14C4C; }"
        )
        self._text_btn.clicked.connect(self._on_text_toggled)
        layout.addWidget(self._text_btn)

        # Highlight button (fluorescent red / stabilo)
        self._highlight_btn = QPushButton("\u2588  Highlight")
        self._highlight_btn.setCheckable(True)
        self._highlight_btn.setToolTip("Click and drag to highlight in fluorescent red")
        self._highlight_btn.setStyleSheet(
            "QPushButton { color: #FF6B6B; font-weight: bold; padding: 4px 12px;"
            "  border: 1px solid transparent; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255, 107, 107, 0.1); }"
            "QPushButton:checked { background: rgba(255, 107, 107, 0.2);"
            "  border: 1px solid #FF6B6B; }"
        )
        self._highlight_btn.clicked.connect(self._on_highlight_toggled)
        layout.addWidget(self._highlight_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def active_tool(self) -> Optional[str]:
        """Return the currently active tool name, or ``None``."""
        if self._text_btn.isChecked():
            return "text_annotation"
        if self._highlight_btn.isChecked():
            return "highlight"
        return None

    def deactivate_all(self) -> None:
        """Uncheck all tool buttons."""
        self._text_btn.setChecked(False)
        self._highlight_btn.setChecked(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_text_toggled(self, checked: bool) -> None:
        if checked:
            self._highlight_btn.setChecked(False)
        self.text_annotation_toggled.emit(checked)

    def _on_highlight_toggled(self, checked: bool) -> None:
        if checked:
            self._text_btn.setChecked(False)
        self.highlight_toggled.emit(checked)
