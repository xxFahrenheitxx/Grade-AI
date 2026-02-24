"""Compact combo-box selector for associating an exam with a specific file."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget


class AssociationSelector(QWidget):
    """Dropdown selector for associating an exam with a specific file.

    Signals
    -------
    selection_changed(str)
        Emitted when the user picks a different file.
        Payload is the relative path (posix) or empty string for "(None)".
    """

    selection_changed = Signal(str)

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setObjectName("subtitleLabel")
        layout.addWidget(self._label)

        self._combo = QComboBox()
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._combo.setMinimumContentsLength(12)
        self._combo.addItem("(None)", "")
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self._combo, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_items(self, items: list[str]) -> None:
        """Set the available file paths (relative posix paths)."""
        self._combo.blockSignals(True)
        current = self.selected()
        self._combo.clear()
        self._combo.addItem("(None)", "")
        for item in sorted(items):
            display_name = PurePosixPath(item).name
            self._combo.addItem(display_name, item)
            self._combo.setItemData(
                self._combo.count() - 1, item, Qt.ItemDataRole.ToolTipRole
            )
        # Restore previous selection if still available
        self.set_selected(current)
        self._combo.blockSignals(False)

    def selected(self) -> str:
        """Return the currently selected relative path, or empty string."""
        return self._combo.currentData() or ""

    def set_selected(self, path: str) -> None:
        """Set the selection by relative path."""
        self._combo.blockSignals(True)
        if not path:
            self._combo.setCurrentIndex(0)
            self._combo.blockSignals(False)
            return

        idx = self._combo.findData(path)
        if idx < 0:
            display_name = PurePosixPath(path).name
            self._combo.addItem(display_name, path)
            idx = self._combo.count() - 1
            self._combo.setItemData(idx, path, Qt.ItemDataRole.ToolTipRole)

        self._combo.setCurrentIndex(idx)
        self._combo.blockSignals(False)

    def clear(self) -> None:
        """Reset the selector to its initial empty state."""
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("(None)", "")
        self._combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_index_changed(self, index: int) -> None:
        self.selection_changed.emit(self.selected())
