"""Right-side grading panel for the Grade AI application.

Displays the complete grading interface for the currently viewed exam:
student name, solution file selector, per-question score widgets,
an AI grading button, and a total/grade summary frame.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gradeai.models import GradingReport, QuestionScore
from gradeai.ui.widgets.association_selector import AssociationSelector
from gradeai.ui.widgets.loading_overlay import LoadingOverlay
from gradeai.ui.widgets.score_widget import ScoreWidget

logger = logging.getLogger(__name__)


class RightPanel(QFrame):
    """Complete grading panel occupying the right side of the main window.

    Signals
    -------
    grading_requested()
        Emitted when the "Run AI Grading" button is clicked.
    report_changed(GradingReport)
        Emitted whenever any score, criterion, or student name is modified.
    solution_selection_changed(list[str])
        Emitted when the solution file selection changes.
    """

    grading_requested = Signal()
    report_changed = Signal(object)             # GradingReport
    exam_paper_changed = Signal(str)            # relative path
    solution_changed = Signal(str)              # relative path

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanelFrame")
        self._report: Optional[GradingReport] = None
        self._score_widgets: list[ScoreWidget] = []
        self._is_grade_calculating: bool = False
        self._grade_loader_step: int = 0
        self._grade_loader_timer = QTimer(self)
        self._grade_loader_timer.setInterval(320)
        self._grade_loader_timer.timeout.connect(self._on_grade_loader_tick)
        self._setup_ui()
        self._show_placeholder()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scroll area wrapping the entire panel content
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("rightPanelScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(self._scroll_area)
        self._scroll_area.viewport().setObjectName("rightPanelViewport")

        # Inner container widget
        self._container = QWidget()
        self._container.setObjectName("rightPanelContainer")
        self._scroll_area.setWidget(self._container)

        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(8)

        # 1. Header
        self._header_label = QLabel("Grading")
        self._header_label.setObjectName("titleLabel")
        self._layout.addWidget(self._header_label)

        # 2. Student name
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        name_label = QLabel("Student:")
        name_label.setObjectName("headerLabel")
        name_layout.addWidget(name_label)

        self._student_name_edit = QLineEdit()
        self._student_name_edit.setPlaceholderText("Auto-detected or enter name...")
        self._student_name_edit.textChanged.connect(self._on_student_name_changed)
        name_layout.addWidget(self._student_name_edit, stretch=1)
        self._layout.addLayout(name_layout)

        # 3. Associations
        associations_header = QLabel("Associations")
        associations_header.setObjectName("subtitleLabel")
        self._layout.addWidget(associations_header)

        self._exam_paper_selector = AssociationSelector("Exam Paper:")
        self._exam_paper_selector.selection_changed.connect(self._on_exam_paper_changed)
        self._layout.addWidget(self._exam_paper_selector)

        self._solution_selector = AssociationSelector("Solution:")
        self._solution_selector.selection_changed.connect(self._on_solution_changed)
        self._layout.addWidget(self._solution_selector)

        # 4. Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(sep1)

        # 5. Questions section header
        self._questions_header = QLabel("Questions")
        self._questions_header.setObjectName("headerLabel")
        self._layout.addWidget(self._questions_header)

        # Container for ScoreWidget instances
        self._questions_layout = QVBoxLayout()
        self._questions_layout.setContentsMargins(0, 0, 0, 0)
        self._questions_layout.setSpacing(6)
        self._layout.addLayout(self._questions_layout)

        # 6. "Run AI Grading" button
        self._grade_btn = QPushButton("Run AI Grading")
        self._grade_btn.setToolTip("Run AI-powered grading on this exam")
        self._grade_btn.setMinimumHeight(36)
        self._grade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grade_btn.clicked.connect(self.grading_requested.emit)
        self._layout.addWidget(self._grade_btn)

        # 7. Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        self._layout.addWidget(sep2)

        # 8. Total / grade frame
        self._total_frame = QFrame()
        self._total_frame.setObjectName("totalFrame")
        total_layout = QVBoxLayout(self._total_frame)
        total_layout.setContentsMargins(10, 8, 10, 8)
        total_layout.setSpacing(4)

        self._total_label = QLabel("Total: 0.00 / 0.00 pts")
        self._total_label.setObjectName("headerLabel")
        self._total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_layout.addWidget(self._total_label)

        self._grade_label = QLabel("Grade: --")
        self._grade_label.setObjectName("headerLabel")
        self._grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_layout.addWidget(self._grade_label)

        self._layout.addWidget(self._total_frame)

        # Spacer to push content to top
        self._layout.addStretch(1)

        # Placeholder message (shown when no exam is loaded)
        self._placeholder_label = QLabel("Open an exam file to start grading")
        self._placeholder_label.setObjectName("subtitleLabel")
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setWordWrap(True)
        self._placeholder_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Loading overlay (shown during long operations)
        self._loading_overlay = LoadingOverlay(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_loading(self, message: str = "Processing...") -> None:
        """Show loading overlay after 500 ms delay."""
        self._loading_overlay.show_after_delay(message, delay_ms=500)

    def hide_loading(self) -> None:
        """Hide the loading overlay."""
        self._loading_overlay.hide_loading()

    def set_available_exam_papers(self, papers: list[str]) -> None:
        """Populate the exam paper dropdown."""
        self._exam_paper_selector.set_items(papers)

    def set_available_solutions(self, solutions: list[str]) -> None:
        """Populate the solution dropdown."""
        self._solution_selector.set_items(solutions)

    def load_report(self, report: GradingReport) -> None:
        """Populate the panel from a grading report."""
        self._report = report
        self._show_content()

        # Student name
        self._student_name_edit.blockSignals(True)
        self._student_name_edit.setText(report.student_name or "")
        self._student_name_edit.blockSignals(False)

        # Associations
        self._exam_paper_selector.set_selected(report.associated_exam_paper or "")
        self._solution_selector.set_selected(report.associated_solution or "")

        # Clear existing question widgets
        self._clear_score_widgets()

        # Create a ScoreWidget for each question
        for question in report.questions:
            self._add_score_widget(question)

        # Update totals
        self._update_totals()

    def get_report(self) -> Optional[GradingReport]:
        """Collect the current panel state into a GradingReport.

        Returns None if no report is loaded.
        """
        if self._report is None:
            return None

        self._report.student_name = self._student_name_edit.text().strip() or None
        self._report.associated_exam_paper = self._exam_paper_selector.selected() or None
        self._report.associated_solution = self._solution_selector.selected() or None

        # Question data is already kept in sync via signals, but ensure
        # the report's question list matches the widget order.
        self._report.questions = [sw.question for sw in self._score_widgets]

        return self._report

    def set_grading_enabled(self, enabled: bool, disabled_reason: Optional[str] = None) -> None:
        """Enable or disable the AI grading button."""
        self._grade_btn.setEnabled(enabled)
        if enabled:
            self._grade_btn.setText("Run AI Grading")
            self._grade_btn.setToolTip("Run AI-powered grading on this exam")
        else:
            self._grade_btn.setText("AI Grading Unavailable")
            self._grade_btn.setToolTip(disabled_reason or "AI grading is currently disabled")

    def refresh_summary(self) -> None:
        """Refresh total and grade labels from current report."""
        self._update_totals()

    def set_grade_calculating(self, calculating: bool) -> None:
        """Show/hide a subtle animated loader in the grade label."""
        if self._is_grade_calculating == calculating:
            return
        self._is_grade_calculating = calculating
        if calculating:
            self._grade_loader_step = 0
            self._grade_loader_timer.start()
            self._on_grade_loader_tick()
        else:
            self._grade_loader_timer.stop()
            self._grade_label.setStyleSheet("")
            self._update_totals()

    def clear(self) -> None:
        """Reset the panel to its initial empty state."""
        self._report = None
        self._is_grade_calculating = False
        self._grade_loader_step = 0
        self._grade_loader_timer.stop()
        self._clear_score_widgets()
        self._student_name_edit.blockSignals(True)
        self._student_name_edit.clear()
        self._student_name_edit.blockSignals(False)
        self._exam_paper_selector.clear()
        self._solution_selector.clear()
        self._update_totals()
        self._show_placeholder()

    # ------------------------------------------------------------------
    # Visibility management
    # ------------------------------------------------------------------

    def _show_placeholder(self) -> None:
        """Show the placeholder message and hide content widgets."""
        self._set_content_visible(False)
        # Add placeholder to outer layout if not already there
        if self._placeholder_label.parent() is None:
            self.layout().addWidget(self._placeholder_label)
        self._placeholder_label.setVisible(True)

    def _show_content(self) -> None:
        """Hide the placeholder and show the content widgets."""
        self._placeholder_label.setVisible(False)
        if self._placeholder_label.parent() == self:
            self.layout().removeWidget(self._placeholder_label)
        self._set_content_visible(True)

    def _set_content_visible(self, visible: bool) -> None:
        """Toggle visibility of the main scrollable content."""
        self._scroll_area.setVisible(visible)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_score_widget(self, question: QuestionScore) -> None:
        """Create and add a ScoreWidget for the given question."""
        sw = ScoreWidget(question, parent=self._container)
        sw.setMinimumWidth(0)
        sw.question_changed.connect(self._on_question_changed)
        sw.max_points_changed.connect(self._on_max_points_changed)
        sw.set_question(question)
        self._score_widgets.append(sw)
        self._questions_layout.addWidget(sw)

    def _clear_score_widgets(self) -> None:
        """Remove and delete all ScoreWidget instances."""
        for sw in self._score_widgets:
            self._questions_layout.removeWidget(sw)
            sw.setParent(None)
            sw.deleteLater()
        self._score_widgets.clear()

    def _update_totals(self) -> None:
        """Recalculate and display total points and grade."""
        if self._report is None:
            self._total_label.setText("Total: -- / -- pts")
            self._grade_label.setText("Grade: --")
            return

        awarded = self._report.total_points_awarded
        possible = self._report.total_points_possible

        if possible is not None:
            self._total_label.setText(f"Total: {awarded:.2f} / {possible:.2f} pts")
        else:
            self._total_label.setText(f"Total: {awarded:.2f} / ? pts")

        if self._is_grade_calculating:
            self._grade_label.setStyleSheet("color: #9aa0a6; font-weight: normal;")
            return

        if self._report.ai_grade:
            self._grade_label.setText(f"Grade: {self._report.ai_grade}")
            self._grade_label.setStyleSheet("font-weight: bold;")
        else:
            percentage = self._report.percentage
            if percentage is not None:
                self._grade_label.setText(f"Grade: {percentage:.1f}%")
                # Compatibility fallback for legacy reports without ai_grade
                if percentage >= 90:
                    self._grade_label.setStyleSheet("color: #89d185; font-weight: bold;")
                elif percentage >= 70:
                    self._grade_label.setStyleSheet("color: #cca700; font-weight: bold;")
                elif percentage >= 50:
                    self._grade_label.setStyleSheet("color: #dcdcaa; font-weight: bold;")
                else:
                    self._grade_label.setStyleSheet("color: #f14c4c; font-weight: bold;")
            else:
                self._grade_label.setText("Grade: --")
                self._grade_label.setStyleSheet("")

    def _on_grade_loader_tick(self) -> None:
        """Animate a subtle 3-step loader in the grade label."""
        if not self._is_grade_calculating:
            return
        frames = [".  ", ".. ", "..."]
        self._grade_label.setText(f"Grade: {frames[self._grade_loader_step]}")
        self._grade_loader_step = (self._grade_loader_step + 1) % len(frames)

    def _emit_report_changed(self) -> None:
        """Build the current report and emit report_changed."""
        report = self.get_report()
        if report is not None:
            self.report_changed.emit(report)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_student_name_changed(self, text: str) -> None:
        """Handle student name edits."""
        if self._report is not None:
            self._report.student_name = text.strip() or None
            self._emit_report_changed()

    def _on_question_changed(self, question: QuestionScore) -> None:
        """Handle changes from a ScoreWidget."""
        # The question object is already updated in-place via the ScoreWidget
        self._update_totals()
        self._emit_report_changed()

    def _on_max_points_changed(self, question_id: str, max_points: float) -> None:
        """Handle manual max-points changes."""
        # Already applied by the ScoreWidget; just update totals and notify
        self._update_totals()
        self._emit_report_changed()

    def _on_exam_paper_changed(self, path: str) -> None:
        """Handle exam paper association change."""
        if self._report is not None:
            self._report.associated_exam_paper = path or None
            self._emit_report_changed()
            self.exam_paper_changed.emit(path)

    def _on_solution_changed(self, path: str) -> None:
        """Handle solution association change."""
        if self._report is not None:
            self._report.associated_solution = path or None
            self._emit_report_changed()
            self.solution_changed.emit(path)
