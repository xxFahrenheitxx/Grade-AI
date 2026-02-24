"""Multi-select widget for choosing solution files.

Provides a compact, collapsible QListWidget with checkboxes
so the teacher can select which solution files to use for
AI grading. The selection persists via get/set methods.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class SolutionSelector(QWidget):
    """Multi-select list of solution files with checkboxes.

    Signals
    -------
    selection_changed(list[str])
        Emitted whenever the set of checked files changes.
    """

    selection_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._expanded = True
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(4)

        # Header row with title and collapse toggle
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self._toggle_btn = QPushButton("v")
        self._toggle_btn.setObjectName("secondaryButton")
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.setToolTip("Expand / collapse solution list")
        self._toggle_btn.clicked.connect(self._toggle_expanded)
        header_layout.addWidget(self._toggle_btn)

        header_label = QLabel("Solution Files")
        header_label.setObjectName("headerLabel")
        header_layout.addWidget(header_label, stretch=1)

        self._count_label = QLabel("0 selected")
        self._count_label.setObjectName("subtitleLabel")
        header_layout.addWidget(self._count_label)

        self._main_layout.addLayout(header_layout)

        # File list with checkboxes
        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._list_widget.setMaximumHeight(150)
        self._list_widget.itemChanged.connect(self._on_item_changed)
        self._main_layout.addWidget(self._list_widget)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_solutions(self, file_list: list[str]) -> None:
        """Populate the list with solution file paths.

        Existing selections are preserved for files that remain in the list.
        """
        # Remember current selection
        previously_selected = set(self.get_selected())

        self._list_widget.blockSignals(True)
        self._list_widget.clear()

        for file_path in sorted(file_list):
            item = QListWidgetItem(file_path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if file_path in previously_selected:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(file_path)
            self._list_widget.addItem(item)

        self._list_widget.blockSignals(False)
        self._update_count_label()

    def get_selected(self) -> list[str]:
        """Return the list of currently checked file paths."""
        selected: list[str] = []
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def set_selected(self, selected: list[str]) -> None:
        """Restore a previously saved selection.

        Files not present in the current list are silently ignored.
        """
        selected_set = set(selected)
        self._list_widget.blockSignals(True)
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item is not None:
                if item.text() in selected_set:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
        self._list_widget.blockSignals(False)
        self._update_count_label()
        # Emit so consumers can react to the restored selection
        self.selection_changed.emit(self.get_selected())

    def clear(self) -> None:
        """Remove all items from the list."""
        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        self._list_widget.blockSignals(False)
        self._update_count_label()

    def set_expanded(self, expanded: bool) -> None:
        """Programmatically expand or collapse the file list."""
        self._expanded = expanded
        self._list_widget.setVisible(expanded)
        self._toggle_btn.setText("v" if expanded else ">")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """Handle a checkbox state change."""
        self._update_count_label()
        self.selection_changed.emit(self.get_selected())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_count_label(self) -> None:
        count = len(self.get_selected())
        total = self._list_widget.count()
        self._count_label.setText(f"{count}/{total} selected")
