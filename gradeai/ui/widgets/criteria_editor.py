"""Widget to manage criteria for a single exam question.

Each criterion has a description, points_awarded, and feedback.
The editor supports inline editing, adding new criteria, and
deleting existing ones with confirmation.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from gradeai.models import Criterion

logger = logging.getLogger(__name__)


class _CriterionRowDisplay(QWidget):
    """Read-only display for a single criterion row.

    Layout: [description_label | points_spinbox | edit_btn | delete_btn]
    """

    edit_requested = Signal()
    delete_requested = Signal()
    points_changed = Signal(float)

    def __init__(self, criterion: Criterion, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._criterion = criterion
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        # Description label (elided if too long)
        self._desc_label = QLabel(self._criterion.description)
        self._desc_label.setToolTip(self._criterion.description)
        self._desc_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._desc_label.setWordWrap(False)
        layout.addWidget(self._desc_label, stretch=1)

        # Points spin box (always editable for quick changes)
        self._points_spin = QDoubleSpinBox()
        self._points_spin.setRange(-9999.0, 9999.0)
        self._points_spin.setDecimals(2)
        self._points_spin.setSingleStep(0.5)
        self._points_spin.setValue(self._criterion.points_awarded)
        self._points_spin.setFixedWidth(80)
        self._points_spin.setToolTip("Points awarded")
        self._points_spin.valueChanged.connect(self._on_points_changed)
        layout.addWidget(self._points_spin)

        # Edit button
        self._edit_btn = QPushButton()
        self._edit_btn.setObjectName("secondaryButton")
        self._edit_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self._edit_btn.setIconSize(QSize(16, 16))
        self._edit_btn.setFixedWidth(40)
        self._edit_btn.setToolTip("Edit criterion details")
        self._edit_btn.clicked.connect(self.edit_requested.emit)
        layout.addWidget(self._edit_btn)

        # Delete button
        self._delete_btn = QPushButton()
        self._delete_btn.setObjectName("dangerButton")
        self._delete_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self._delete_btn.setIconSize(QSize(16, 16))
        self._delete_btn.setFixedWidth(36)
        self._delete_btn.setToolTip("Delete criterion")
        self._delete_btn.clicked.connect(self.delete_requested.emit)
        layout.addWidget(self._delete_btn)

        self._update_elided_description()

    def _on_points_changed(self, value: float) -> None:
        self._criterion.points_awarded = value
        self.points_changed.emit(value)

    @property
    def criterion(self) -> Criterion:
        return self._criterion

    def update_display(self, criterion: Criterion) -> None:
        """Refresh the row with updated criterion data."""
        self._criterion = criterion
        self._desc_label.setToolTip(criterion.description)
        self._points_spin.blockSignals(True)
        self._points_spin.setValue(criterion.points_awarded)
        self._points_spin.blockSignals(False)
        self._update_elided_description()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided_description()

    def _update_elided_description(self) -> None:
        """Elide long criterion text so row stays within panel width."""
        metrics = QFontMetrics(self._desc_label.font())
        elided = metrics.elidedText(
            self._criterion.description,
            Qt.TextElideMode.ElideRight,
            max(10, self._desc_label.width()),
        )
        self._desc_label.setText(elided)


class _CriterionRowEdit(QWidget):
    """Inline edit mode for a single criterion row.

    Layout: [description_lineedit | points_spinbox | feedback_lineedit | save_btn | cancel_btn]
    """

    save_requested = Signal(str, float, str)  # description, points, feedback
    cancel_requested = Signal()

    def __init__(
        self,
        criterion: Criterion,
        parent: Optional[QWidget] = None,
        show_feedback: bool = True,
    ) -> None:
        super().__init__(parent)
        self._criterion = criterion
        self._show_feedback = show_feedback
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        # Description edit
        self._desc_edit = QLineEdit(self._criterion.description)
        self._desc_edit.setPlaceholderText("Criterion description...")
        self._desc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._desc_edit, stretch=2)

        # Points spin box
        self._points_spin = QDoubleSpinBox()
        self._points_spin.setRange(-9999.0, 9999.0)
        self._points_spin.setDecimals(2)
        self._points_spin.setSingleStep(0.5)
        self._points_spin.setValue(self._criterion.points_awarded)
        self._points_spin.setFixedWidth(80)
        self._points_spin.setToolTip("Points awarded")
        layout.addWidget(self._points_spin)

        # Feedback edit
        self._feedback_edit: Optional[QLineEdit] = None
        if self._show_feedback:
            self._feedback_edit = QLineEdit(self._criterion.feedback)
            self._feedback_edit.setPlaceholderText("Feedback (optional)...")
            self._feedback_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(self._feedback_edit, stretch=1)

        # Save button
        self._save_btn = QPushButton()
        self._save_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self._save_btn.setIconSize(QSize(16, 16))
        self._save_btn.setFixedWidth(36)
        self._save_btn.setToolTip("Save changes")
        self._save_btn.clicked.connect(self._on_save)
        layout.addWidget(self._save_btn)

        # Cancel button
        self._cancel_btn = QPushButton()
        self._cancel_btn.setObjectName("secondaryButton")
        self._cancel_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self._cancel_btn.setIconSize(QSize(16, 16))
        self._cancel_btn.setFixedWidth(36)
        self._cancel_btn.setToolTip("Discard changes")
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self._cancel_btn)

        # Allow Enter to save
        self._desc_edit.returnPressed.connect(self._on_save)
        if self._feedback_edit is not None:
            self._feedback_edit.returnPressed.connect(self._on_save)

    def _on_save(self) -> None:
        desc = self._desc_edit.text().strip()
        if not desc:
            self._desc_edit.setFocus()
            return
        self.save_requested.emit(
            desc,
            self._points_spin.value(),
            self._feedback_edit.text().strip() if self._feedback_edit is not None else "",
        )

    def focus_description(self) -> None:
        """Set focus to the description field for immediate editing."""
        self._desc_edit.setFocus()
        self._desc_edit.selectAll()


class CriteriaEditor(QWidget):
    """Editor widget that manages a list of criteria for one question.

    Signals
    -------
    criteria_changed(list[Criterion])
        Emitted whenever any criterion is added, removed, or modified.
    """

    criteria_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._criteria: list[Criterion] = []
        # Maps criterion id -> (display_widget, edit_widget_or_None)
        self._row_widgets: dict[str, _CriterionRowDisplay] = {}
        self._active_edit_id: Optional[str] = None  # id of criterion being edited
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(2)

        # Container for criterion rows
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        self._main_layout.addLayout(self._rows_layout)

        # "Add Criterion" button
        self._add_btn = QPushButton("+ Add Criterion")
        self._add_btn.setObjectName("secondaryButton")
        self._add_btn.setToolTip("Add a new grading criterion")
        self._add_btn.clicked.connect(self._on_add_criterion)
        self._main_layout.addWidget(self._add_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_criteria(self, criteria: list[Criterion]) -> None:
        """Replace all criteria with the given list."""
        self._clear_rows()
        self._criteria = list(criteria)
        for criterion in self._criteria:
            self._add_display_row(criterion)

    def get_criteria(self) -> list[Criterion]:
        """Return a copy of the current criteria list."""
        return list(self._criteria)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear_rows(self) -> None:
        """Remove all row widgets from the layout."""
        self._active_edit_id = None
        for cid, widget in self._row_widgets.items():
            widget.setParent(None)
            widget.deleteLater()
        self._row_widgets.clear()
        # Also clear any edit widgets lingering in the layout
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _add_display_row(self, criterion: Criterion) -> None:
        """Create and insert a display row for the given criterion."""
        row = _CriterionRowDisplay(criterion, parent=self)
        row.edit_requested.connect(lambda cid=criterion.id: self._start_edit(cid))
        row.delete_requested.connect(lambda cid=criterion.id: self._on_delete(cid))
        row.points_changed.connect(lambda _val, cid=criterion.id: self._on_points_inline_change(cid))
        self._row_widgets[criterion.id] = row
        self._rows_layout.addWidget(row)

    def _start_edit(self, criterion_id: str, show_feedback: bool = True) -> None:
        """Switch a criterion row into edit mode."""
        # Cancel any other active edit first
        if self._active_edit_id is not None and self._active_edit_id != criterion_id:
            self._cancel_edit(self._active_edit_id)

        criterion = self._find_criterion(criterion_id)
        if criterion is None:
            return

        # Hide display row
        display_row = self._row_widgets.get(criterion_id)
        if display_row is not None:
            display_row.setVisible(False)

        # Create and show edit row
        edit_row = _CriterionRowEdit(criterion, parent=self, show_feedback=show_feedback)
        edit_row.save_requested.connect(
            lambda desc, pts, fb, cid=criterion_id: self._finish_edit(cid, desc, pts, fb)
        )
        edit_row.cancel_requested.connect(lambda cid=criterion_id: self._cancel_edit(cid))
        edit_row.setObjectName(f"edit_{criterion_id}")

        # Insert edit row at the same position as the display row
        idx = self._rows_layout.indexOf(display_row)
        if idx >= 0:
            self._rows_layout.insertWidget(idx + 1, edit_row)
        else:
            self._rows_layout.addWidget(edit_row)

        self._active_edit_id = criterion_id
        edit_row.focus_description()

    def _finish_edit(self, criterion_id: str, description: str, points: float, feedback: str) -> None:
        """Save edits and switch back to display mode."""
        criterion = self._find_criterion(criterion_id)
        if criterion is None:
            return

        criterion.description = description
        criterion.points_awarded = points
        criterion.feedback = feedback

        # Remove the edit widget
        self._remove_edit_widget(criterion_id)

        # Update and show the display row
        display_row = self._row_widgets.get(criterion_id)
        if display_row is not None:
            display_row.update_display(criterion)
            display_row.setVisible(True)

        self._active_edit_id = None
        self._emit_changed()

    def _cancel_edit(self, criterion_id: str) -> None:
        """Cancel editing and show the display row again."""
        self._remove_edit_widget(criterion_id)
        display_row = self._row_widgets.get(criterion_id)
        if display_row is not None:
            display_row.setVisible(True)
        if self._active_edit_id == criterion_id:
            self._active_edit_id = None

    def _remove_edit_widget(self, criterion_id: str) -> None:
        """Find and remove the edit widget for the given criterion."""
        obj_name = f"edit_{criterion_id}"
        for i in range(self._rows_layout.count()):
            item = self._rows_layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None and widget.objectName() == obj_name:
                self._rows_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
                break

    def _on_delete(self, criterion_id: str) -> None:
        """Delete a criterion after confirmation."""
        criterion = self._find_criterion(criterion_id)
        if criterion is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete Criterion",
            f'Delete criterion "{criterion.description}"?\n\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Cancel active edit if it was for this criterion
        if self._active_edit_id == criterion_id:
            self._remove_edit_widget(criterion_id)
            self._active_edit_id = None

        # Remove display widget
        display_row = self._row_widgets.pop(criterion_id, None)
        if display_row is not None:
            self._rows_layout.removeWidget(display_row)
            display_row.setParent(None)
            display_row.deleteLater()

        # Remove from data
        self._criteria = [c for c in self._criteria if c.id != criterion_id]
        self._emit_changed()

    def _on_add_criterion(self) -> None:
        """Add a new blank criterion and immediately enter edit mode."""
        new_criterion = Criterion(
            description="New criterion",
            points_awarded=0.0,
            feedback="",
            id=str(uuid.uuid4()),
        )
        self._criteria.append(new_criterion)
        self._add_display_row(new_criterion)
        self._emit_changed()
        # Open edit mode for the new criterion
        self._start_edit(new_criterion.id, show_feedback=False)

    def _on_points_inline_change(self, criterion_id: str) -> None:
        """Handle points changed directly in the display spin box."""
        self._emit_changed()

    def _find_criterion(self, criterion_id: str) -> Optional[Criterion]:
        """Find a criterion by ID."""
        for c in self._criteria:
            if c.id == criterion_id:
                return c
        return None

    def _emit_changed(self) -> None:
        """Emit the criteria_changed signal with the current list."""
        self.criteria_changed.emit(list(self._criteria))
