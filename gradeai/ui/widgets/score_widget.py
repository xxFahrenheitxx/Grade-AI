"""Widget displaying one question's grading with collapsible criteria details.

Shows a header with question number, title, and score, plus a collapsible
CriteriaEditor for detailed criterion management. Provides visual feedback
for scoring status (green/orange/red) and coherence warnings.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gradeai.models import Criterion, QuestionScore
from gradeai.ui.widgets.criteria_editor import CriteriaEditor

logger = logging.getLogger(__name__)

# Status colours (used for the score label)
_COLOR_GREEN = "#89d185"    # fully scored, coherent
_COLOR_ORANGE = "#cca700"   # partial (has criteria but not maxed)
_COLOR_RED = "#f14c4c"      # incoherent (awarded > possible)
_TITLE_MAX_LEN = 20


class ScoreWidget(QFrame):
    """Displays one question's score with collapsible criteria editor.

    Signals
    -------
    question_changed(QuestionScore)
        Emitted when any criterion or the max-points setting changes.
    max_points_changed(str, float)
        Emitted when the teacher manually sets max points (question_id, max_points).
    """

    question_changed = Signal(object)       # QuestionScore
    max_points_changed = Signal(str, float)  # question_id, max_points

    def __init__(self, question: QuestionScore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("scoreFrame")
        self._question = question
        self._expanded = False
        self._setup_ui()
        self._update_display()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(8, 6, 8, 6)
        self._main_layout.setSpacing(4)

        # --- Header row ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        # Question title label (stretch to fill)
        self._title_label = QLabel()
        self._title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._title_label.setWordWrap(False)
        self._title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title_label.installEventFilter(self)
        header_layout.addWidget(self._title_label, stretch=1)

        # Warning icon / label (hidden when coherent)
        self._warning_label = QLabel("! Over max")
        self._warning_label.setObjectName("warningLabel")
        self._warning_label.setToolTip("Points awarded exceed points possible")
        self._warning_label.setVisible(False)
        header_layout.addWidget(self._warning_label)

        # Score label
        self._score_label = QLabel()
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._score_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self._score_label)

        # "Set Max" button (visible only when points_possible is None)
        self._set_max_btn = QPushButton("Set Max")
        self._set_max_btn.setObjectName("secondaryButton")
        self._set_max_btn.setFixedWidth(60)
        self._set_max_btn.setToolTip("Manually set maximum points for this question")
        self._set_max_btn.clicked.connect(self._on_set_max_points)
        self._set_max_btn.setVisible(False)
        header_layout.addWidget(self._set_max_btn)

        self._main_layout.addLayout(header_layout)

        # --- Criteria body (collapsible) ---
        self._body_widget = QWidget()
        body_layout = QVBoxLayout(self._body_widget)
        body_layout.setContentsMargins(20, 4, 0, 0)
        body_layout.setSpacing(2)

        # Feedback summary label (shows per-criterion feedback count)
        self._feedback_label = QLabel()
        self._feedback_label.setObjectName("subtitleLabel")
        self._feedback_label.setWordWrap(True)
        body_layout.addWidget(self._feedback_label)

        # Manual question-level points
        points_row = QHBoxLayout()
        points_row.setSpacing(6)
        points_row.addWidget(QLabel("Question points:"))
        self._question_points_spin = QDoubleSpinBox()
        self._question_points_spin.setRange(-9999.0, 9999.0)
        self._question_points_spin.setDecimals(2)
        self._question_points_spin.setSingleStep(0.5)
        self._question_points_spin.setFixedWidth(90)
        self._question_points_spin.valueChanged.connect(self._on_question_points_changed)
        points_row.addWidget(self._question_points_spin)
        self._reset_points_btn = QPushButton("Auto")
        self._reset_points_btn.setObjectName("secondaryButton")
        self._reset_points_btn.setFixedWidth(54)
        self._reset_points_btn.setToolTip("Use criteria sum instead of manual points")
        self._reset_points_btn.clicked.connect(self._on_reset_question_points)
        points_row.addWidget(self._reset_points_btn)
        points_row.addStretch(1)
        body_layout.addLayout(points_row)

        # Manual justification (shown when expanded)
        body_layout.addWidget(QLabel("Justification:"))
        self._justification_edit = QPlainTextEdit()
        self._justification_edit.setObjectName("questionJustificationEdit")
        self._justification_edit.setPlaceholderText("Explain why points were awarded/removed...")
        self._justification_edit.setMaximumHeight(90)
        self._justification_edit.textChanged.connect(self._on_justification_changed)
        body_layout.addWidget(self._justification_edit)

        # Criteria editor
        self._criteria_editor = CriteriaEditor(parent=self._body_widget)
        self._criteria_editor.criteria_changed.connect(self._on_criteria_changed)
        body_layout.addWidget(self._criteria_editor)

        self._body_widget.setVisible(False)
        self._main_layout.addWidget(self._body_widget)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def question(self) -> QuestionScore:
        """Return the current question data."""
        return self._question

    def set_question(self, question: QuestionScore) -> None:
        """Replace the displayed question data."""
        self._question = question
        self._criteria_editor.set_criteria(question.criteria)
        self._update_display()

    def set_expanded(self, expanded: bool) -> None:
        """Programmatically expand or collapse."""
        self._expanded = expanded
        self._body_widget.setVisible(expanded)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def eventFilter(self, obj, event):  # noqa: N802
        """Toggle details when user clicks on the question title."""
        if obj is self._title_label and event.type() == QEvent.Type.MouseButtonRelease:
            self._toggle_expanded()
            return True
        return super().eventFilter(obj, event)

    def _on_criteria_changed(self, criteria: list[Criterion]) -> None:
        """Update question when criteria are modified in the editor."""
        self._question.criteria = criteria
        if not self._question.justification.strip():
            self._question.justification = self._build_default_justification()
        self._update_display()
        self.question_changed.emit(self._question)

    def _on_question_points_changed(self, value: float) -> None:
        """Set a manual question-level points value."""
        self._question.points_awarded_override = value
        self._update_display()
        self.question_changed.emit(self._question)

    def _on_reset_question_points(self) -> None:
        """Reset to automatic criteria sum."""
        self._question.points_awarded_override = None
        self._update_display()
        self.question_changed.emit(self._question)

    def _on_justification_changed(self) -> None:
        """Store manual justification edits."""
        self._question.justification = self._justification_edit.toPlainText().strip()
        self.question_changed.emit(self._question)

    def _on_set_max_points(self) -> None:
        """Open a small dialog for the teacher to set max points."""
        current = self._question.points_possible if self._question.points_possible is not None else 0.0
        value, ok = QInputDialog.getDouble(
            self,
            "Set Maximum Points",
            f"Maximum points for Question {self._question.question_number}:",
            current,
            0.0,        # min
            99999.0,    # max
            2,          # decimals
        )
        if ok:
            self._question.points_possible = value
            self._question.manually_set_max = True
            self._update_display()
            self.max_points_changed.emit(self._question.question_id, value)
            self.question_changed.emit(self._question)

    # ------------------------------------------------------------------
    # Display update
    # ------------------------------------------------------------------

    def _update_display(self) -> None:
        """Refresh all visual elements from the current question state."""
        q = self._question
        awarded = q.points_awarded
        possible = q.points_possible

        # Title
        truncated_question = self._truncate_title(q.question_title)
        full_title = f"Q{q.question_number}: {q.question_title}"
        self._title_label.setText(f"Q{q.question_number}: {truncated_question}")
        self._title_label.setToolTip(full_title)

        # Score text
        if possible is not None:
            score_text = f"{awarded:.2f} / {possible:.2f} pts"
        else:
            score_text = f"{awarded:.2f} / ? pts"
        self._score_label.setText(score_text)

        # Color coding
        color = self._compute_color(awarded, possible)
        self._score_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # Warning for incoherent scores
        is_incoherent = possible is not None and awarded > possible + 0.001
        self._warning_label.setVisible(is_incoherent)

        # "Set Max" button visibility
        self._set_max_btn.setVisible(possible is None)

        # Feedback summary
        feedback_count = sum(1 for c in q.criteria if c.feedback)
        criteria_count = len(q.criteria)
        if criteria_count == 0:
            self._feedback_label.setText("No criteria defined")
        else:
            self._feedback_label.setText(
                f"{criteria_count} criteria, {feedback_count} with feedback"
            )

        # Manual points editor state
        auto_points = sum(c.points_awarded for c in q.criteria)
        current_points = q.points_awarded_override if q.points_awarded_override is not None else auto_points
        self._question_points_spin.blockSignals(True)
        self._question_points_spin.setValue(current_points)
        self._question_points_spin.blockSignals(False)
        self._reset_points_btn.setEnabled(q.points_awarded_override is not None)

        # Justification editor state
        justif = q.justification.strip() or self._build_default_justification()
        self._justification_edit.blockSignals(True)
        self._justification_edit.setPlainText(justif)
        self._justification_edit.blockSignals(False)

    @staticmethod
    def _compute_color(awarded: float, possible: Optional[float]) -> str:
        """Determine display colour based on scoring status."""
        if possible is None:
            # No max set yet - use orange to indicate incomplete
            return _COLOR_ORANGE
        if awarded > possible + 0.001:
            return _COLOR_RED
        if awarded >= possible - 0.001:
            return _COLOR_GREEN
        # Partial score
        return _COLOR_ORANGE

    @staticmethod
    def _truncate_title(title: str) -> str:
        """Limit title length for compact panel layout."""
        if len(title) <= _TITLE_MAX_LEN:
            return title
        return f"{title[:_TITLE_MAX_LEN]}..."

    def _build_default_justification(self) -> str:
        """Build a default justification text from criteria."""
        if not self._question.criteria:
            return "No justification yet."
        lines: list[str] = []
        for criterion in self._question.criteria:
            reason = criterion.feedback.strip() or criterion.description.strip()
            if reason:
                lines.append(f"{criterion.points_awarded:+.2f} pts - {reason}")
        if not lines:
            return "No justification yet."
        return "\n".join(lines)
