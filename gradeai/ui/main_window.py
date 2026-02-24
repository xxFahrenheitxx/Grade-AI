"""Main application window - central orchestrator."""

from __future__ import annotations

import logging
import re
import socket
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from gradeai.constants import (
    APP_NAME,
    APP_VERSION,
    EXAM_PAPERS_DIR,
    EXAMS_DIR,
    GRADING_REPORTS_DIR,
    PROJECT_EXTENSION,
    PROJECT_FILTER,
    RULES_DIR,
    SOLUTIONS_DIR,
)
from gradeai.models import ExamPaperTemplate
from gradeai.models.grading_report import GradingReport
from gradeai.models.project import GradeProject
from gradeai.models.settings import AppSettings
from gradeai.services.grading_service import GradingService
from gradeai.services.project_service import ProjectService
from gradeai.services.report_generator import ReportGenerator
from gradeai.ui.dialogs.exam_report_dialog import ExamReportDialog
from gradeai.ui.dialogs.import_exams_dialog import ImportExamsDialog
from gradeai.ui.dialogs.new_project_dialog import NewProjectDialog
from gradeai.ui.dialogs.settings_dialog import SettingsDialog
from gradeai.ui.panels.center_panel import CenterPanel
from gradeai.ui.panels.left_panel import LeftPanel
from gradeai.ui.panels.right_panel import RightPanel
from gradeai.ui.theme_manager import ThemeManager
from gradeai.ui.widgets.start_screen import StartScreen
from gradeai.utils.file_utils import (
    get_grading_report_path,
    is_exam_file,
    is_exam_paper_file,
)

logger = logging.getLogger(__name__)


class GradingWorker(QObject):
    """Worker that runs AI grading in a background thread."""

    finished = Signal(object)  # GradingReport
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        grading_service: GradingService,
        exam_path: Path,
        solution_paths: list[Path],
        rule_paths: list[Path],
        prompts_dir: Path,
        point_maximums: dict[str, float],
        exam_paper_path: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self._grading_service = grading_service
        self._exam_path = exam_path
        self._solution_paths = solution_paths
        self._rule_paths = rule_paths
        self._prompts_dir = prompts_dir
        self._point_maximums = point_maximums
        self._exam_paper_path = exam_paper_path

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Extracting exam content...")
            self.progress.emit("Calling Claude AI for grading...")
            report = self._grading_service.grade_exam(
                exam_path=self._exam_path,
                solution_paths=self._solution_paths,
                rule_paths=self._rule_paths,
                prompts_dir=self._prompts_dir,
                point_maximums=self._point_maximums,
                exam_paper_path=self._exam_paper_path,
            )
            self.finished.emit(report)
        except Exception as e:
            logger.exception("AI grading failed")
            self.error.emit(str(e))


class QuestionDetectionWorker(QObject):
    """Worker that runs question detection in a background thread."""

    finished = Signal(list)   # list[QuestionScore]
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        grading_service: GradingService,
        exam_path: Path,
        prompts_dir: Path,
    ) -> None:
        super().__init__()
        self._grading_service = grading_service
        self._exam_path = exam_path
        self._prompts_dir = prompts_dir

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Detecting questions...")
            questions = self._grading_service.detect_questions(
                exam_path=self._exam_path,
                prompts_dir=self._prompts_dir,
            )
            self.finished.emit(questions)
        except Exception as e:
            logger.exception("Question detection failed")
            self.error.emit(str(e))


class GradeCalculationWorker(QObject):
    """Worker that runs grade calculation in a background thread."""

    finished = Signal(str)   # grade value
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        grading_service: GradingService,
        report: GradingReport,
        rule_paths: list[Path],
        prompts_dir: Path,
    ) -> None:
        super().__init__()
        self._grading_service = grading_service
        self._report = report
        self._rule_paths = rule_paths
        self._prompts_dir = prompts_dir

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Calculating grade...")
            grade = self._grading_service.calculate_grade(
                report=self._report,
                rule_paths=self._rule_paths,
                prompts_dir=self._prompts_dir,
            )
            self.finished.emit(grade)
        except Exception as e:
            logger.exception("Grade calculation failed")
            self.error.emit(str(e))


class ExamPaperAnalysisWorker(QObject):
    """Worker that analyzes an exam paper to extract a template."""

    finished = Signal(object)  # ExamPaperTemplate
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        grading_service: GradingService,
        exam_paper_path: Path,
        prompts_dir: Path,
    ) -> None:
        super().__init__()
        self._grading_service = grading_service
        self._exam_paper_path = exam_paper_path
        self._prompts_dir = prompts_dir

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Analyzing exam paper...")
            template = self._grading_service.analyze_exam_paper(
                exam_paper_path=self._exam_paper_path,
                prompts_dir=self._prompts_dir,
            )
            self.finished.emit(template)
        except Exception as e:
            logger.exception("Exam paper analysis failed")
            self.error.emit(str(e))


class ExamMatchingWorker(QObject):
    """Worker that matches a student exam to a known exam paper template."""

    finished = Signal(object)  # Optional[str] - matched paper path or None
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        grading_service: GradingService,
        exam_path: Path,
        templates: list[ExamPaperTemplate],
        prompts_dir: Path,
    ) -> None:
        super().__init__()
        self._grading_service = grading_service
        self._exam_path = exam_path
        self._templates = templates
        self._prompts_dir = prompts_dir

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Matching exam to paper...")
            matched_path = self._grading_service.match_exam_to_paper(
                exam_path=self._exam_path,
                available_templates=self._templates,
                prompts_dir=self._prompts_dir,
            )
            self.finished.emit(matched_path)
        except Exception as e:
            logger.exception("Exam matching failed")
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """The main application window."""

    def __init__(self, app_settings: AppSettings, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._app_settings = app_settings
        self._theme_manager = theme_manager
        self._project_service = ProjectService()
        self._current_exam_path: Optional[Path] = None
        self._current_report: Optional[GradingReport] = None
        self._grading_thread: Optional[QThread] = None
        self._detection_thread: Optional[QThread] = None
        self._grade_calc_thread: Optional[QThread] = None
        self._analysis_thread: Optional[QThread] = None
        self._matching_thread: Optional[QThread] = None
        self._run_grading_action: Optional[QAction] = None
        self._has_internet_connection: bool = True
        self._offline_notice_shown: bool = False
        self._is_grading_in_progress: bool = False
        self._is_exam_context_active: bool = False
        self._grade_calc_pending: bool = False
        self._last_points_signature: tuple = ()
        self._available_exam_papers: list[str] = []
        self._available_solutions: list[str] = []
        self._grade_calc_timer = QTimer(self)
        self._grade_calc_timer.setSingleShot(True)
        self._grade_calc_timer.setInterval(650)
        self._grade_calc_timer.timeout.connect(self._on_grade_calc_timer_timeout)
        self._connectivity_timer = QTimer(self)
        self._connectivity_timer.setInterval(15000)
        self._connectivity_timer.timeout.connect(self._on_connectivity_timer_timeout)

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 700)

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._connect_signals()
        self._restore_state()
        self._refresh_connectivity_state(notify_if_offline=False)
        self._connectivity_timer.start()

    def _setup_ui(self) -> None:
        """Build the three-panel layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._start_screen = StartScreen(self)
        layout.addWidget(self._start_screen)

        # Main splitter: left | center | right
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._left_panel = LeftPanel()
        self._center_panel = CenterPanel()
        self._right_panel = RightPanel()

        self._splitter.addWidget(self._left_panel)
        self._splitter.addWidget(self._center_panel)
        self._splitter.addWidget(self._right_panel)

        # Default sizes: left=250, center=stretch, right=350
        self._splitter.setSizes([250, 600, 350])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)

        layout.addWidget(self._splitter)
        self._set_start_screen_visible(True)

    def _setup_menu_bar(self) -> None:
        """Create the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Project...", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        # Recent projects submenu
        self._recent_menu = QMenu("Open &Recent", self)
        self._update_recent_menu()
        file_menu.addMenu(self._recent_menu)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        import_action = QAction("&Import Exams...", self)
        import_action.triggered.connect(self._on_import_exams)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        settings_action = QAction("Se&ttings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._on_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")

        # View menu
        view_menu = menu_bar.addMenu("&View")

        toggle_theme_action = QAction("Toggle &Dark/Light Theme", self)
        toggle_theme_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        toggle_theme_action.triggered.connect(self._on_toggle_theme)
        view_menu.addAction(toggle_theme_action)

        view_menu.addSeparator()

        split_h_action = QAction("Split Editor &Right", self)
        split_h_action.triggered.connect(lambda: self._center_panel.split_view(Qt.Orientation.Horizontal))
        view_menu.addAction(split_h_action)

        split_v_action = QAction("Split Editor &Down", self)
        split_v_action.triggered.connect(lambda: self._center_panel.split_view(Qt.Orientation.Vertical))
        view_menu.addAction(split_v_action)

        # Grading menu
        grading_menu = menu_bar.addMenu("&Grading")

        self._run_grading_action = QAction("&Run AI Grading", self)
        self._run_grading_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        self._run_grading_action.triggered.connect(self._on_run_ai_grading)
        grading_menu.addAction(self._run_grading_action)

        grading_menu.addSeparator()

        report_action = QAction("Generate Exam &Report...", self)
        report_action.triggered.connect(self._on_generate_report)
        grading_menu.addAction(report_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self) -> None:
        """Create the toolbar with the app title on the left."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        title_label = QLabel(f"  {APP_NAME}  ")
        title_label.setObjectName("headerLabel")
        title_label.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 4px 12px;"
            " color: white; font-family: 'Lato', sans-serif;"
        )
        toolbar.addWidget(title_label)

    def _setup_status_bar(self) -> None:
        """Create the status bar."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)

    def _connect_signals(self) -> None:
        """Connect panel signals to handlers."""
        # Left panel
        self._left_panel.file_selected.connect(self._on_file_selected)
        self._left_panel.title_changed.connect(self._on_title_changed)
        self._left_panel.import_requested.connect(self._on_import_to_folder)
        self._left_panel.items_about_to_delete.connect(self._on_items_about_to_delete)
        self._left_panel.items_deleted.connect(self._on_items_deleted)

        # Center panel
        self._center_panel.document_opened.connect(self._on_document_opened)
        self._center_panel.document_closed.connect(self._on_document_closed)

        # Right panel
        self._right_panel.grading_requested.connect(self._on_run_ai_grading)
        self._right_panel.report_changed.connect(self._on_report_changed)
        self._right_panel.exam_paper_changed.connect(self._on_exam_paper_association_changed)
        self._right_panel.solution_changed.connect(self._on_solution_association_changed)

        # Start screen
        self._start_screen.new_project_requested.connect(self._on_new_project)
        self._start_screen.open_project_requested.connect(self._on_open_project)
        self._start_screen.recent_project_requested.connect(
            lambda p: self._open_project_file(Path(p))
        )
        self._start_screen.project_dropped.connect(
            lambda p: self._open_project_file(Path(p))
        )

    # ------------------------------------------------------------------
    # Project operations
    # ------------------------------------------------------------------

    def _on_new_project(self) -> None:
        dialog = NewProjectDialog(self)
        if dialog.exec() != NewProjectDialog.DialogCode.Accepted:
            return

        # Create temporary working directory
        working_dir = Path(tempfile.mkdtemp(prefix="gradeai_"))

        try:
            exam_paper_sources = getattr(dialog, "exam_paper_files", None)
            project = self._project_service.create_project(
                title=dialog.project_title,
                working_dir=working_dir,
                exam_sources=dialog.exam_files or None,
                solution_sources=dialog.solution_files or None,
                rule_sources=dialog.rule_files or None,
                exam_paper_sources=exam_paper_sources or None,
            )

            # Save as .grd
            if dialog.save_path:
                self._project_service.save_grd(project, dialog.save_path)

            self._load_project_ui(project)
            self._status_label.setText(f"Project created: {project.title}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create project:\n{e}")
            logger.exception("Project creation failed")

    def _on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", PROJECT_FILTER
        )
        if not path:
            return
        self._open_project_file(Path(path))

    def _open_project_file(self, path: Path) -> None:
        try:
            project = self._project_service.open_grd(path)
            self._load_project_ui(project)
            self._app_settings.add_recent_project(str(path))
            self._app_settings.save()
            self._update_recent_menu()
            self._status_label.setText(f"Project opened: {project.title}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")
            logger.exception("Project open failed")

    def _on_save_project(self) -> None:
        # Save the active file in center panel first
        if self._center_panel.save_active_document():
            active = self._center_panel.active_document_path()
            if active:
                self._status_label.setText(f"Saved: {Path(active).name}")

        project = self._project_service.project
        if not project:
            return

        # Save UI state before saving project
        self._save_project_ui_state()

        try:
            if project.grd_file_path:
                self._project_service.save_grd(project)
                self._status_label.setText("Project saved")
            else:
                self._on_save_project_as()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def _on_save_project_as(self) -> None:
        project = self._project_service.project
        if not project:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", project.title + PROJECT_EXTENSION, PROJECT_FILTER
        )
        if not path:
            return
        try:
            save_path = Path(path)
            if not save_path.suffix:
                save_path = save_path.with_suffix(PROJECT_EXTENSION)
            self._project_service.save_grd(project, save_path)
            self._app_settings.add_recent_project(str(save_path))
            self._app_settings.save()
            self._update_recent_menu()
            self._status_label.setText(f"Project saved as: {save_path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def _load_project_ui(self, project: GradeProject) -> None:
        """Update all panels for a loaded project."""
        self._set_start_screen_visible(False)
        self._left_panel.set_project(project.working_dir, project.title)
        self._center_panel.set_project_root(project.working_dir)

        self._center_panel.clear_all()
        self._right_panel.clear()
        self._current_exam_path = None
        self._current_report = None
        self._is_exam_context_active = False
        self.setWindowTitle(f"{project.title} - {APP_NAME}")
        self._update_grading_controls()

        # Populate association dropdowns
        self._refresh_association_dropdowns(project)

        # Restore UI state if available
        project_key = str(project.grd_file_path) if project.grd_file_path else str(project.working_dir)
        if project_key in self._app_settings.project_ui_states:
            ui_state = self._app_settings.project_ui_states[project_key]
            # Restore open files and active file
            if "center_panel" in ui_state:
                self._center_panel.restore_ui_state(ui_state["center_panel"], project.working_dir)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _on_file_selected(self, file_path: str) -> None:
        """Handle file selection from left panel."""
        path = Path(file_path)
        project = self._project_service.project
        if not project:
            return

        # Determine if file is read-only (Exams and Grading Reports are read-only)
        read_only = is_exam_file(path, project.working_dir)
        if read_only:
            self._status_label.setText(f"Opening {path.name}...")
            # Show feedback immediately before heavy document loading starts.
            self._center_panel.show_loading("Opening exam...", delay_ms=0)
            QApplication.processEvents()

        self._center_panel.open_document(path, read_only=read_only)

    def _on_document_opened(self, file_path: str) -> None:
        """Handle document opened in center panel."""
        self._center_panel.hide_loading()
        path = Path(file_path)
        project = self._project_service.project
        if not project:
            return

        # Case 1: Exam Paper opened -> analyze for template if needed
        if is_exam_paper_file(path, project.working_dir):
            self._is_exam_context_active = False
            self._update_grading_controls()
            if self._app_settings.api_key and self._has_internet_connection:
                existing = self._project_service.get_template(project, path)
                if existing is None:
                    self._start_exam_paper_analysis(path, project)
                else:
                    self._status_label.setText(
                        f"Template already exists ({len(existing.questions)} questions)"
                    )
            return

        # Case 2 & 3: Exam file opened
        if is_exam_file(path, project.working_dir):
            self._is_exam_context_active = True
            self._current_exam_path = path
            report = self._project_service.get_or_create_grading_report(project, path)
            original_exam_paper = report.associated_exam_paper
            original_solution = report.associated_solution
            original_student = report.student_name
            report.associated_exam_paper = self._normalize_association_relative_path(
                project, report.associated_exam_paper, project.exam_papers_dir
            )
            report.associated_solution = self._normalize_association_relative_path(
                project, report.associated_solution, project.solutions_dir
            )
            self._apply_open_defaults(report, path)
            if (
                report.associated_exam_paper != original_exam_paper
                or report.associated_solution != original_solution
                or report.student_name != original_student
            ):
                self._project_service.save_grading_report(project, report)
            self._current_report = report

            self._right_panel.load_report(report)
            self._last_points_signature = self._question_points_signature(report)

            # Apply stored point maximums
            for q in report.questions:
                if q.question_title in project.settings.point_maximums and q.points_possible is None:
                    q.points_possible = project.settings.point_maximums[q.question_title]
                    q.manually_set_max = True

            self._update_grading_controls()
            self._center_panel.load_annotations(report.annotations)

            # Case 2: Report already has questions -> done
            if report.questions:
                return

            # Case 3: No questions yet -> try to match/apply template
            if report.graded_by == "ai":
                return

            if not self._app_settings.api_key or not self._has_internet_connection:
                return

            # If already associated with an exam paper, apply its template
            if report.associated_exam_paper:
                paper_path = self._resolve_association_absolute_path(
                    project, report.associated_exam_paper, project.exam_papers_dir
                )
                template = self._project_service.get_template(project, paper_path) if paper_path else None
                if template:
                    self._apply_template_to_report(report, template, project)
                    return

            # Try to match against available templates
            templates = self._project_service.get_all_templates(project)
            if templates:
                self._start_exam_matching(path, templates, project)
            else:
                # No templates available -> fall back to question detection
                self._start_question_detection(path, project)
        else:
            self._is_exam_context_active = False
            self._update_grading_controls()

    def _on_document_closed(self, file_path: str) -> None:
        """Reset/reload grading panel when an exam tab is closed."""
        closed_path = Path(file_path)
        if self._current_exam_path != closed_path:
            return

        self._current_exam_path = None
        self._current_report = None
        self._is_exam_context_active = False
        self._last_points_signature = ()
        # ``document_closed`` is emitted before tab removal in CenterPanel.
        # Defer the active-tab inspection so we don't reload the tab being closed.
        QTimer.singleShot(0, self._sync_grading_panel_after_tab_close)

    def _sync_grading_panel_after_tab_close(self) -> None:
        """Sync right panel with the new active tab after a close operation."""
        active_path = self._center_panel.active_document_path()
        project = self._project_service.project
        if active_path and project:
            active = Path(active_path)
            if is_exam_file(active, project.working_dir):
                self._on_document_opened(active_path)
                return

        self._right_panel.clear()
        self._update_grading_controls()

    def _on_title_changed(self, title: str) -> None:
        project = self._project_service.project
        if project:
            project.title = title
            project.mark_modified()
            self.setWindowTitle(f"{title} - {APP_NAME}")

    def _on_import_to_folder(self, folder_name: str) -> None:
        """Handle import request from left panel context menu."""
        project = self._project_service.project
        if not project:
            return

        if folder_name == EXAMS_DIR:
            self._on_import_exams()
        else:
            files, _ = QFileDialog.getOpenFileNames(
                self, f"Import to {folder_name}", ""
            )
            if files:
                target_dir = project.working_dir / folder_name
                for f in files:
                    import shutil
                    src = Path(f)
                    shutil.copy2(src, target_dir / src.name)
                project.mark_modified()
                self._refresh_association_dropdowns(project)

    def _on_import_exams(self) -> None:
        project = self._project_service.project
        if not project:
            QMessageBox.information(self, "No Project", "Please create or open a project first.")
            return

        dialog = ImportExamsDialog(self)
        if dialog.exec() == ImportExamsDialog.DialogCode.Accepted and dialog.selected_files:
            self._project_service.import_exams(project, dialog.selected_files)
            self._refresh_association_dropdowns(project)
            self._status_label.setText(f"Imported {len(dialog.selected_files)} exam(s)")

    def _close_open_tabs_for_paths(self, paths: list[str]) -> None:
        """Close open tabs matching files/directories in *paths*."""
        if not paths:
            return
        targets = [Path(p) for p in paths]
        open_paths = [Path(p) for p in self._center_panel.get_open_paths()]
        for open_path in open_paths:
            should_close = any(
                open_path == target or target in open_path.parents
                for target in targets
            )
            if should_close:
                self._center_panel.close_document(open_path)

    def _on_items_about_to_delete(self, paths: list[str]) -> None:
        """Close tabs first so files are not locked at deletion time."""
        self._close_open_tabs_for_paths(paths)

    def _on_items_deleted(self, deleted_paths: list[str]) -> None:
        """Close open tabs for deleted files/directories."""
        self._close_open_tabs_for_paths(deleted_paths)
        project = self._project_service.project
        if project:
            self._refresh_association_dropdowns(project)

    # ------------------------------------------------------------------
    # Grading operations
    # ------------------------------------------------------------------

    def _on_run_ai_grading(self) -> None:
        self._refresh_connectivity_state(notify_if_offline=True)

        project = self._project_service.project
        if not project:
            QMessageBox.information(self, "No Project", "Please create or open a project first.")
            return

        if not self._current_exam_path:
            QMessageBox.information(self, "No Exam", "Please open an exam file first.")
            return

        if not self._app_settings.api_key:
            QMessageBox.warning(
                self, "API Key Required",
                "Please set your Claude API key in Settings (Ctrl+,)."
            )
            self._on_settings()
            return
        if not self._has_internet_connection:
            self._status_label.setText("Internet connection required for AI grading")
            return

        if (
            self._current_report
            and (
                self._current_report.questions
                or self._current_report.annotations
                or bool(self._current_report.ai_grade)
            )
        ):
            reply = QMessageBox.warning(
                self,
                "Replace Existing Corrections?",
                (
                    "This exam already has corrections saved in its Grading Report.\n\n"
                    "If you continue, the current corrections will be permanently replaced "
                    "by the new AI grading run.\n\n"
                    "Do you want to continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._status_label.setText("AI grading canceled")
                return

        # Collect all solution and rule paths
        solution_paths = []
        if project.solutions_dir.exists():
            solution_paths = [f for f in project.solutions_dir.rglob("*") if f.is_file()]

        rule_paths = self._collect_rule_paths(project)

        # Resolve associated exam paper path
        exam_paper_path: Optional[Path] = None
        if self._current_report and self._current_report.associated_exam_paper:
            exam_paper_path = self._resolve_association_absolute_path(
                project,
                self._current_report.associated_exam_paper,
                project.exam_papers_dir,
            )

        # Start grading in background thread
        self._start_grading(
            exam_path=self._current_exam_path,
            solution_paths=solution_paths,
            rule_paths=rule_paths,
            prompts_dir=project.prompts_dir,
            point_maximums=project.settings.point_maximums,
            exam_paper_path=exam_paper_path,
        )

    def _start_grading(
        self,
        exam_path: Path,
        solution_paths: list[Path],
        rule_paths: list[Path],
        prompts_dir: Path,
        point_maximums: dict[str, float],
        exam_paper_path: Optional[Path] = None,
    ) -> None:
        """Run AI grading in a background thread."""
        grading_service = GradingService(
            api_key=self._app_settings.api_key,
            provider=self._app_settings.ai_provider,
            model=self._app_settings.ai_model,
        )

        self._grading_thread = QThread()
        self._grading_worker = GradingWorker(
            grading_service, exam_path, solution_paths, rule_paths, prompts_dir,
            point_maximums, exam_paper_path=exam_paper_path,
        )
        self._grading_worker.moveToThread(self._grading_thread)

        self._grading_thread.started.connect(self._grading_worker.run)
        self._grading_worker.finished.connect(self._on_grading_finished)
        self._grading_worker.error.connect(self._on_grading_error)
        self._grading_worker.progress.connect(self._on_grading_progress)
        self._grading_worker.finished.connect(self._grading_thread.quit)
        self._grading_worker.error.connect(self._grading_thread.quit)

        self._is_grading_in_progress = True
        self._update_grading_controls()
        self._right_panel.show_loading("Running AI grading...")
        self._center_panel.show_loading("Running AI grading...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._status_label.setText("AI grading in progress...")

        self._grading_thread.start()

    def _on_grading_finished(self, report: GradingReport) -> None:
        """Handle completed AI grading."""
        self._right_panel.hide_loading()
        self._center_panel.hide_loading()

        project = self._project_service.project
        if not project or not self._current_exam_path:
            return

        # Set the correct exam file path
        rel_path = self._current_exam_path.relative_to(project.working_dir).as_posix()
        report.exam_file_path = rel_path
        if self._current_report:
            if not report.associated_exam_paper:
                report.associated_exam_paper = self._current_report.associated_exam_paper
            if not report.associated_solution:
                report.associated_solution = self._current_report.associated_solution

        report.associated_exam_paper = self._normalize_association_relative_path(
            project, report.associated_exam_paper, project.exam_papers_dir
        )
        report.associated_solution = self._normalize_association_relative_path(
            project, report.associated_solution, project.solutions_dir
        )

        # Save the report
        self._project_service.save_grading_report(project, report)
        self._current_report = report

        # Update UI
        self._right_panel.load_report(report)
        self._is_grading_in_progress = False
        self._update_grading_controls()
        self._progress_bar.setVisible(False)
        self._status_label.setText("AI grading complete")

        # Store point maximums for future use
        for q in report.questions:
            if q.points_possible is not None:
                project.settings.point_maximums[q.question_title] = q.points_possible

        # Load annotations onto the document
        self._center_panel.load_annotations(report.annotations)
        self._last_points_signature = self._question_points_signature(report)
        self._start_grade_calculation(immediate=True)

    def _on_grading_error(self, error_msg: str) -> None:
        self._right_panel.hide_loading()
        self._center_panel.hide_loading()
        self._is_grading_in_progress = False
        self._update_grading_controls()
        self._progress_bar.setVisible(False)
        self._status_label.setText("AI grading failed")
        QMessageBox.critical(self, "Grading Error", f"AI grading failed:\n\n{error_msg}")

    def _on_grading_progress(self, msg: str) -> None:
        self._status_label.setText(msg)

    # ------------------------------------------------------------------
    # Question detection (auto on exam open)
    # ------------------------------------------------------------------

    def _start_question_detection(self, exam_path: Path, project: GradeProject) -> None:
        """Run question detection in a background thread."""
        if self._detection_thread is not None and self._detection_thread.isRunning():
            return

        grading_service = GradingService(
            api_key=self._app_settings.api_key,
            provider=self._app_settings.ai_provider,
            model=self._app_settings.ai_model,
        )

        self._detection_thread = QThread()
        self._detection_worker = QuestionDetectionWorker(
            grading_service, exam_path, project.prompts_dir,
        )
        self._detection_worker.moveToThread(self._detection_thread)

        self._detection_thread.started.connect(self._detection_worker.run)
        self._detection_worker.finished.connect(self._on_question_detection_finished)
        self._detection_worker.error.connect(self._on_question_detection_error)
        self._detection_worker.progress.connect(self._on_grading_progress)
        self._detection_worker.finished.connect(self._detection_thread.quit)
        self._detection_worker.error.connect(self._detection_thread.quit)

        self._right_panel.show_loading("Detecting questions...")
        self._center_panel.show_loading("Detecting questions...", delay_ms=100)
        self._status_label.setText("Detecting questions...")
        self._detection_thread.start()

    def _on_question_detection_finished(self, questions: list) -> None:
        """Handle completed question detection."""
        self._right_panel.hide_loading()
        self._center_panel.hide_loading()

        project = self._project_service.project
        if not project or not self._current_exam_path or not self._current_report:
            return

        self._current_report.questions = questions

        # Apply stored point maximums
        for q in questions:
            if q.question_title in project.settings.point_maximums:
                q.points_possible = project.settings.point_maximums[q.question_title]
                q.manually_set_max = True

        self._project_service.save_grading_report(project, self._current_report)
        self._right_panel.load_report(self._current_report)
        self._last_points_signature = self._question_points_signature(self._current_report)
        self._status_label.setText(f"Detected {len(questions)} question(s)")

    def _on_question_detection_error(self, error_msg: str) -> None:
        """Handle question detection failure (non-blocking)."""
        self._right_panel.hide_loading()
        self._center_panel.hide_loading()
        self._status_label.setText("Question detection failed")
        logger.warning("Question detection failed: %s", error_msg)

    # ------------------------------------------------------------------
    # Exam paper analysis
    # ------------------------------------------------------------------

    def _start_exam_paper_analysis(self, paper_path: Path, project: GradeProject) -> None:
        """Analyze an exam paper to extract its template."""
        if self._analysis_thread is not None and self._analysis_thread.isRunning():
            return

        grading_service = GradingService(
            api_key=self._app_settings.api_key,
            provider=self._app_settings.ai_provider,
            model=self._app_settings.ai_model,
        )

        self._analysis_thread = QThread()
        self._analysis_worker = ExamPaperAnalysisWorker(
            grading_service, paper_path, project.prompts_dir,
        )
        self._analysis_worker.moveToThread(self._analysis_thread)

        self._analysis_thread.started.connect(self._analysis_worker.run)
        self._analysis_worker.finished.connect(self._on_exam_paper_analysis_finished)
        self._analysis_worker.error.connect(self._on_exam_paper_analysis_error)
        self._analysis_worker.progress.connect(self._on_grading_progress)
        self._analysis_worker.finished.connect(self._analysis_thread.quit)
        self._analysis_worker.error.connect(self._analysis_thread.quit)

        # Store paper path for the finished callback
        self._analysis_paper_path = paper_path

        self._right_panel.show_loading("Analyzing exam paper...")
        self._status_label.setText("Analyzing exam paper...")
        self._analysis_thread.start()

    def _on_exam_paper_analysis_finished(self, template: ExamPaperTemplate) -> None:
        """Handle completed exam paper analysis."""
        self._right_panel.hide_loading()

        project = self._project_service.project
        if not project:
            return

        paper_path = self._analysis_paper_path
        self._project_service.save_template(project, template, paper_path)
        self._status_label.setText(
            f"Template saved: {len(template.questions)} question(s) extracted"
        )

    def _on_exam_paper_analysis_error(self, error_msg: str) -> None:
        """Handle exam paper analysis failure."""
        self._right_panel.hide_loading()
        self._status_label.setText("Exam paper analysis failed")
        logger.warning("Exam paper analysis failed: %s", error_msg)

    # ------------------------------------------------------------------
    # Exam-to-paper matching
    # ------------------------------------------------------------------

    def _start_exam_matching(
        self, exam_path: Path, templates: list[ExamPaperTemplate], project: GradeProject,
    ) -> None:
        """Match a student exam to a known exam paper template."""
        if self._matching_thread is not None and self._matching_thread.isRunning():
            return

        grading_service = GradingService(
            api_key=self._app_settings.api_key,
            provider=self._app_settings.ai_provider,
            model=self._app_settings.ai_model,
        )

        self._matching_thread = QThread()
        self._matching_worker = ExamMatchingWorker(
            grading_service, exam_path, templates, project.prompts_dir,
        )
        self._matching_worker.moveToThread(self._matching_thread)

        self._matching_thread.started.connect(self._matching_worker.run)
        self._matching_worker.finished.connect(self._on_exam_matching_finished)
        self._matching_worker.error.connect(self._on_exam_matching_error)
        self._matching_worker.progress.connect(self._on_grading_progress)
        self._matching_worker.finished.connect(self._matching_thread.quit)
        self._matching_worker.error.connect(self._matching_thread.quit)

        self._right_panel.show_loading("Matching exam to paper...")
        self._center_panel.show_loading("Matching exam to paper...", delay_ms=100)
        self._status_label.setText("Matching exam to paper...")
        self._matching_thread.start()

    def _on_exam_matching_finished(self, matched_path) -> None:
        """Handle completed exam matching."""
        self._right_panel.hide_loading()
        self._center_panel.hide_loading()

        project = self._project_service.project
        if not project or not self._current_exam_path or not self._current_report:
            return

        if matched_path:
            normalized_match = self._normalize_association_relative_path(
                project, str(matched_path), project.exam_papers_dir
            )
            # Save association
            self._current_report.associated_exam_paper = normalized_match
            self._project_service.save_grading_report(project, self._current_report)
            self._right_panel.load_report(self._current_report)

            # Apply template questions
            paper_abs = self._resolve_association_absolute_path(
                project, normalized_match, project.exam_papers_dir
            )
            template = self._project_service.get_template(project, paper_abs) if paper_abs else None
            if template:
                self._apply_template_to_report(self._current_report, template, project)
                self._status_label.setText(f"Matched to: {normalized_match}")
                return

        # No match or no template -> fall back to question detection
        self._status_label.setText("No matching exam paper found")
        self._start_question_detection(self._current_exam_path, project)

    def _on_exam_matching_error(self, error_msg: str) -> None:
        """Handle exam matching failure - fall back to question detection."""
        self._right_panel.hide_loading()
        self._center_panel.hide_loading()
        self._status_label.setText("Exam matching failed")
        logger.warning("Exam matching failed: %s", error_msg)

        project = self._project_service.project
        if project and self._current_exam_path:
            self._start_question_detection(self._current_exam_path, project)

    # ------------------------------------------------------------------
    # Template application
    # ------------------------------------------------------------------

    def _apply_template_to_report(
        self, report: GradingReport, template: ExamPaperTemplate, project: GradeProject,
    ) -> None:
        """Apply a template's questions to a grading report."""
        import uuid

        from gradeai.models import QuestionScore

        questions = []
        for tq in template.questions:
            qs = QuestionScore(
                question_id=tq.question_id or str(uuid.uuid4()),
                question_title=tq.question_title,
                question_number=tq.question_number,
                points_possible=tq.points_possible,
                points_awarded=0.0,
            )
            # Apply stored point maximums (override template if teacher set manually)
            if qs.question_title in project.settings.point_maximums:
                qs.points_possible = project.settings.point_maximums[qs.question_title]
                qs.manually_set_max = True
            questions.append(qs)

        report.questions = questions
        self._project_service.save_grading_report(project, report)
        self._right_panel.load_report(report)
        self._last_points_signature = self._question_points_signature(report)

    # ------------------------------------------------------------------
    # Association change handlers
    # ------------------------------------------------------------------

    def _on_exam_paper_association_changed(self, path: str) -> None:
        """Handle exam paper association change from right panel."""
        project = self._project_service.project
        if not project or not self._current_report:
            return

        # If report has no questions and user selected a paper, apply its template
        if path and not self._current_report.questions:
            paper_abs = self._resolve_association_absolute_path(
                project, path, project.exam_papers_dir
            )
            template = self._project_service.get_template(project, paper_abs) if paper_abs else None
            if template:
                self._apply_template_to_report(self._current_report, template, project)

    def _on_solution_association_changed(self, path: str) -> None:
        """Handle solution association change from right panel.

        The report is already updated via report_changed signal; nothing extra needed.
        """

    def _refresh_association_dropdowns(self, project: GradeProject) -> None:
        """Refresh exam-paper and solution dropdown values."""
        self._available_exam_papers = sorted(
            self._project_service.list_exam_paper_relative_paths(project)
        )
        self._available_solutions = sorted(
            self._project_service.list_solution_relative_paths(project)
        )
        self._right_panel.set_available_exam_papers(self._available_exam_papers)
        self._right_panel.set_available_solutions(self._available_solutions)

    def _apply_open_defaults(self, report: GradingReport, exam_path: Path) -> None:
        """Fill student/exam-paper/solution when missing at exam open."""
        if not report.student_name:
            report.student_name = self._guess_student_name(exam_path)

        if not report.associated_exam_paper and self._available_exam_papers:
            report.associated_exam_paper = self._available_exam_papers[0]

        if not report.associated_solution and self._available_solutions:
            report.associated_solution = self._available_solutions[0]

    def _guess_student_name(self, exam_path: Path) -> str:
        """Derive a readable student name from the exam filename."""
        base = exam_path.stem.strip()
        base = re.sub(r"[_\-]+", " ", base)
        base = re.sub(r"\s+", " ", base).strip()
        return base or exam_path.name

    # ------------------------------------------------------------------
    # Association path helpers
    # ------------------------------------------------------------------

    def _resolve_association_absolute_path(
        self,
        project: GradeProject,
        stored_path: Optional[str],
        preferred_dir: Path,
    ) -> Optional[Path]:
        """Resolve stored association path to an existing absolute path when possible."""
        if not stored_path:
            return None

        candidates = [
            project.working_dir / stored_path,
            preferred_dir / stored_path,
            preferred_dir / Path(stored_path).name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _normalize_association_relative_path(
        self,
        project: GradeProject,
        stored_path: Optional[str],
        preferred_dir: Path,
    ) -> Optional[str]:
        """Normalize association path to project-relative posix if resolvable."""
        if not stored_path:
            return None
        resolved = self._resolve_association_absolute_path(project, stored_path, preferred_dir)
        if resolved is None:
            return stored_path
        return resolved.relative_to(project.working_dir).as_posix()

    def _on_report_changed(self, report: GradingReport) -> None:
        """Handle manual changes to the grading report."""
        project = self._project_service.project
        if not project:
            return
        self._current_report = report
        self._project_service.save_grading_report(project, report)

        # Update stored point maximums
        for q in report.questions:
            if q.manually_set_max and q.points_possible is not None:
                project.settings.point_maximums[q.question_title] = q.points_possible

        current_signature = self._question_points_signature(report)
        if current_signature != self._last_points_signature:
            self._last_points_signature = current_signature
            self._start_grade_calculation(immediate=False)

    def _on_generate_report(self) -> None:
        project = self._project_service.project
        if not project:
            QMessageBox.information(self, "No Project", "Please create or open a project first.")
            return

        reports = self._project_service.get_all_grading_reports(project)
        if not reports:
            QMessageBox.information(self, "No Reports", "No graded exams found.")
            return

        generator = ReportGenerator()
        summary = generator.generate_report(reports)

        dialog = ExamReportDialog(summary, self)
        dialog.exec()

    # ------------------------------------------------------------------
    # UI state persistence
    # ------------------------------------------------------------------

    def _save_project_ui_state(self) -> None:
        """Save the current UI state for the active project."""
        project = self._project_service.project
        if not project:
            return

        project_key = str(project.grd_file_path) if project.grd_file_path else str(project.working_dir)
        ui_state = {
            "center_panel": self._center_panel.get_ui_state(),
        }
        self._app_settings.project_ui_states[project_key] = ui_state
        self._app_settings.save()

    # ------------------------------------------------------------------
    # Grade calculation
    # ------------------------------------------------------------------

    def _on_grade_calc_timer_timeout(self) -> None:
        self._start_grade_calculation(immediate=True)

    def _question_points_signature(self, report: GradingReport) -> tuple:
        """Build signature used to detect question-points changes."""
        entries = []
        for q in report.questions:
            possible = q.points_possible if q.points_possible is not None else -1.0
            entries.append((q.question_id, round(q.points_awarded, 4), round(possible, 4)))
        return tuple(sorted(entries))

    def _collect_rule_paths(self, project: GradeProject) -> list[Path]:
        """Collect all rule files in the project."""
        if not project.rules_dir.exists():
            return []
        return [f for f in project.rules_dir.rglob("*") if f.is_file()]

    def _start_grade_calculation(self, immediate: bool) -> None:
        """Schedule or start dedicated AI grade calculation."""
        project = self._project_service.project
        if (
            not project
            or not self._current_report
            or not self._app_settings.api_key
            or not self._has_internet_connection
        ):
            return

        if not immediate:
            self._grade_calc_timer.start()
            return

        if self._grade_calc_thread is not None and self._grade_calc_thread.isRunning():
            self._grade_calc_pending = True
            return

        report_snapshot = GradingReport.from_dict(self._current_report.to_dict())
        rule_paths = self._collect_rule_paths(project)

        grading_service = GradingService(
            api_key=self._app_settings.api_key,
            provider=self._app_settings.ai_provider,
            model=self._app_settings.ai_model,
        )

        self._grade_calc_thread = QThread()
        self._grade_calc_worker = GradeCalculationWorker(
            grading_service=grading_service,
            report=report_snapshot,
            rule_paths=rule_paths,
            prompts_dir=project.prompts_dir,
        )
        self._grade_calc_worker.moveToThread(self._grade_calc_thread)

        self._grade_calc_thread.started.connect(self._grade_calc_worker.run)
        self._grade_calc_worker.finished.connect(self._on_grade_calculation_finished)
        self._grade_calc_worker.error.connect(self._on_grade_calculation_error)
        self._grade_calc_worker.progress.connect(self._on_grading_progress)
        self._grade_calc_worker.finished.connect(self._grade_calc_thread.quit)
        self._grade_calc_worker.error.connect(self._grade_calc_thread.quit)

        self._right_panel.set_grade_calculating(True)
        self._grade_calc_thread.start()

    def _on_grade_calculation_finished(self, grade: str) -> None:
        """Apply newly calculated grade and persist it."""
        project = self._project_service.project
        if project and self._current_report:
            self._current_report.ai_grade = grade
            self._project_service.save_grading_report(project, self._current_report)
            self._right_panel.refresh_summary()
            self._status_label.setText("Grade calculated")

        self._right_panel.set_grade_calculating(False)

        if self._grade_calc_pending:
            self._grade_calc_pending = False
            self._start_grade_calculation(immediate=True)

    def _on_grade_calculation_error(self, error_msg: str) -> None:
        logger.warning("Grade calculation failed: %s", error_msg)
        self._right_panel.set_grade_calculating(False)
        self._status_label.setText("Grade calculation failed")
        if self._grade_calc_pending:
            self._grade_calc_pending = False
            self._start_grade_calculation(immediate=True)

    # ------------------------------------------------------------------
    # Settings & theme
    # ------------------------------------------------------------------

    def _on_settings(self) -> None:
        old_theme = self._app_settings.theme
        dialog = SettingsDialog(self._app_settings, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            if dialog.settings.theme != old_theme:
                self._theme_manager.apply_theme(dialog.settings.theme)
            self._update_grading_controls()

    def _on_connectivity_timer_timeout(self) -> None:
        self._refresh_connectivity_state(notify_if_offline=True)

    def _check_internet_connection(self) -> bool:
        """Return True when outbound network connectivity is available."""
        probes = [("1.1.1.1", 53), ("8.8.8.8", 53)]
        for host, port in probes:
            try:
                with socket.create_connection((host, port), timeout=1.0):
                    return True
            except OSError:
                continue
        return False

    def _refresh_connectivity_state(self, notify_if_offline: bool) -> None:
        """Update cached connectivity state and refresh grading controls."""
        was_online = self._has_internet_connection
        self._has_internet_connection = self._check_internet_connection()

        if self._has_internet_connection:
            self._offline_notice_shown = False
        elif notify_if_offline and (was_online or not self._offline_notice_shown):
            QMessageBox.warning(
                self,
                "Internet Connection Required",
                (
                    "You must be connected to the internet to enjoy all the benefits "
                    "of the Grade AI application."
                ),
            )
            self._offline_notice_shown = True
            self._status_label.setText("Offline: AI grading is unavailable")

        self._update_grading_controls()

    def _update_grading_controls(self) -> None:
        """Enable grading controls only when project/exam/API/internet are ready."""
        project_loaded = self._project_service.project is not None
        exam_opened = self._is_exam_context_active and self._current_exam_path is not None
        has_api_key = bool(self._app_settings.api_key)

        disabled_reason: Optional[str] = None
        if self._is_grading_in_progress:
            disabled_reason = "AI grading is running"
        elif not has_api_key:
            disabled_reason = "Set your API key in Settings to enable AI grading"
        elif not self._has_internet_connection:
            disabled_reason = "Internet connection required for AI grading"
        elif not exam_opened:
            disabled_reason = "Open an exam file to enable AI grading"
        elif not project_loaded:
            disabled_reason = "Create or open a project to enable AI grading"

        enabled = (
            project_loaded
            and exam_opened
            and has_api_key
            and self._has_internet_connection
            and not self._is_grading_in_progress
        )
        self._right_panel.set_grading_enabled(enabled, disabled_reason=disabled_reason)
        if self._run_grading_action:
            self._run_grading_action.setEnabled(enabled)
            self._run_grading_action.setToolTip(disabled_reason or "Run AI-powered grading")

    def _on_toggle_theme(self) -> None:
        new_theme = self._theme_manager.toggle_theme()
        self._app_settings.theme = new_theme
        self._app_settings.save()

    def _on_about(self) -> None:
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME}</h2>"
            f"<p>Version {APP_VERSION}</p>"
            f"<p>AI-powered exam grading assistant for teachers.</p>"
            f"<p>GitHub: <a href='https://github.com/xxFahrenheitxx/Grade-AI'>"
            f"https://github.com/xxFahrenheitxx/Grade-AI</a></p>"
        )

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        for path_str in self._app_settings.recent_projects:
            path = Path(path_str)
            action = QAction(path.name, self)
            action.setToolTip(str(path))
            action.triggered.connect(lambda checked, p=path: self._open_project_file(p))
            self._recent_menu.addAction(action)
        if not self._app_settings.recent_projects:
            empty_action = QAction("(No recent projects)", self)
            empty_action.setEnabled(False)
            self._recent_menu.addAction(empty_action)
        self._start_screen.set_recent_projects(self._app_settings.recent_projects)

    def _set_start_screen_visible(self, visible: bool) -> None:
        """Toggle startup splash visibility vs. workspace panels."""
        self._start_screen.setVisible(visible)
        self._splitter.setVisible(not visible)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _restore_state(self) -> None:
        if self._app_settings.splitter_sizes:
            self._splitter.setSizes(self._app_settings.splitter_sizes)

    def closeEvent(self, event) -> None:
        """Save state and clean up on close."""
        # Save UI state for current project
        self._save_project_ui_state()

        # Save splitter sizes
        self._app_settings.splitter_sizes = self._splitter.sizes()
        self._app_settings.save()

        # Close project
        project = self._project_service.project
        if project:
            # Ask to save if modified
            reply = QMessageBox.question(
                self,
                "Save Project?",
                "Do you want to save the project before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._on_save_project()

            self._project_service.close_project(project)

        event.accept()
