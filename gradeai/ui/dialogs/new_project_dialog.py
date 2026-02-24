"""New project creation dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class NewProjectDialog(QDialog):
    """Dialog for creating a new Grade AI project."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        self._exam_files: list[Path] = []
        self._exam_paper_files: list[Path] = []
        self._solution_files: list[Path] = []
        self._rule_files: list[Path] = []
        self._save_path: Optional[Path] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Project title
        title_group = QGroupBox("Project")
        title_layout = QVBoxLayout(title_group)

        # Save location
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("Save As:"))
        self._save_label = QLabel("Not selected")
        self._save_label.setObjectName("subtitleLabel")
        self._save_label.setWordWrap(True)
        save_layout.addWidget(self._save_label, 1)
        save_btn = QPushButton("Browse...")
        save_btn.setObjectName("secondaryButton")
        save_btn.clicked.connect(self._browse_save_location)
        save_layout.addWidget(save_btn)
        title_layout.addLayout(save_layout)
        layout.addWidget(title_group)

        # Exam files
        exam_group = QGroupBox("Exam Files (optional - can import later)")
        exam_layout = QVBoxLayout(exam_group)
        self._exam_list = QListWidget()
        self._exam_list.setMaximumHeight(100)
        exam_layout.addWidget(self._exam_list)
        exam_btn_layout = QHBoxLayout()
        add_exam_btn = QPushButton("Add Files...")
        add_exam_btn.setObjectName("secondaryButton")
        add_exam_btn.clicked.connect(self._add_exam_files)
        add_exam_folder_btn = QPushButton("Add Folder...")
        add_exam_folder_btn.setObjectName("secondaryButton")
        add_exam_folder_btn.clicked.connect(self._add_exam_folder)
        clear_exam_btn = QPushButton("Clear")
        clear_exam_btn.setObjectName("secondaryButton")
        clear_exam_btn.clicked.connect(lambda: self._clear_list(self._exam_list, self._exam_files))
        exam_btn_layout.addWidget(add_exam_btn)
        exam_btn_layout.addWidget(add_exam_folder_btn)
        exam_btn_layout.addWidget(clear_exam_btn)
        exam_btn_layout.addStretch()
        exam_layout.addLayout(exam_btn_layout)
        layout.addWidget(exam_group)

        # Exam paper files
        paper_group = QGroupBox("Exam Paper Files (optional - blank exam versions)")
        paper_layout = QVBoxLayout(paper_group)
        self._exam_paper_list = QListWidget()
        self._exam_paper_list.setMaximumHeight(80)
        paper_layout.addWidget(self._exam_paper_list)
        paper_btn_layout = QHBoxLayout()
        add_paper_btn = QPushButton("Add Files...")
        add_paper_btn.setObjectName("secondaryButton")
        add_paper_btn.clicked.connect(self._add_exam_paper_files)
        clear_paper_btn = QPushButton("Clear")
        clear_paper_btn.setObjectName("secondaryButton")
        clear_paper_btn.clicked.connect(
            lambda: self._clear_list(self._exam_paper_list, self._exam_paper_files)
        )
        paper_btn_layout.addWidget(add_paper_btn)
        paper_btn_layout.addWidget(clear_paper_btn)
        paper_btn_layout.addStretch()
        paper_layout.addLayout(paper_btn_layout)
        layout.addWidget(paper_group)

        # Solution files
        sol_group = QGroupBox("Solution Files (optional)")
        sol_layout = QVBoxLayout(sol_group)
        self._solution_list = QListWidget()
        self._solution_list.setMaximumHeight(80)
        sol_layout.addWidget(self._solution_list)
        sol_btn_layout = QHBoxLayout()
        add_sol_btn = QPushButton("Add Files...")
        add_sol_btn.setObjectName("secondaryButton")
        add_sol_btn.clicked.connect(self._add_solution_files)
        clear_sol_btn = QPushButton("Clear")
        clear_sol_btn.setObjectName("secondaryButton")
        clear_sol_btn.clicked.connect(lambda: self._clear_list(self._solution_list, self._solution_files))
        sol_btn_layout.addWidget(add_sol_btn)
        sol_btn_layout.addWidget(clear_sol_btn)
        sol_btn_layout.addStretch()
        sol_layout.addLayout(sol_btn_layout)
        layout.addWidget(sol_group)

        # Rule files
        rule_group = QGroupBox("Grading Rules (optional)")
        rule_layout = QVBoxLayout(rule_group)
        self._rule_list = QListWidget()
        self._rule_list.setMaximumHeight(80)
        rule_layout.addWidget(self._rule_list)
        rule_btn_layout = QHBoxLayout()
        add_rule_btn = QPushButton("Add Files...")
        add_rule_btn.setObjectName("secondaryButton")
        add_rule_btn.clicked.connect(self._add_rule_files)
        clear_rule_btn = QPushButton("Clear")
        clear_rule_btn.setObjectName("secondaryButton")
        clear_rule_btn.clicked.connect(lambda: self._clear_list(self._rule_list, self._rule_files))
        rule_btn_layout.addWidget(add_rule_btn)
        rule_btn_layout.addWidget(clear_rule_btn)
        rule_btn_layout.addStretch()
        rule_layout.addLayout(rule_btn_layout)
        layout.addWidget(rule_group)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_save_location(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "Grade AI Project (*.grd)"
        )
        if path:
            self._save_path = Path(path)
            if not self._save_path.suffix:
                self._save_path = self._save_path.with_suffix(".grd")
            self._save_label.setText(str(self._save_path))

    def _add_exam_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select Exam Files", "")
        for f in files:
            p = Path(f)
            if p not in self._exam_files:
                self._exam_files.append(p)
                self._exam_list.addItem(p.name)

    def _add_exam_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Exam Folder")
        if folder:
            p = Path(folder)
            if p not in self._exam_files:
                self._exam_files.append(p)
                self._exam_list.addItem(f"[Folder] {p.name}")

    def _add_exam_paper_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select Exam Paper Files", "")
        for f in files:
            p = Path(f)
            if p not in self._exam_paper_files:
                self._exam_paper_files.append(p)
                self._exam_paper_list.addItem(p.name)

    def _add_solution_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select Solution Files", "")
        for f in files:
            p = Path(f)
            if p not in self._solution_files:
                self._solution_files.append(p)
                self._solution_list.addItem(p.name)

    def _add_rule_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Rule Files", "", "Markdown Files (*.md);;All Files (*)"
        )
        for f in files:
            p = Path(f)
            if p not in self._rule_files:
                self._rule_files.append(p)
                self._rule_list.addItem(p.name)

    def _clear_list(self, list_widget: QListWidget, file_list: list[Path]) -> None:
        list_widget.clear()
        file_list.clear()

    def _on_accept(self) -> None:
        if not self._save_path:
            self._browse_save_location()
            if not self._save_path:
                return
        self.accept()

    @property
    def project_title(self) -> str:
        if self._save_path is not None and self._save_path.stem:
            return self._save_path.stem
        return "Untitled"

    @property
    def save_path(self) -> Optional[Path]:
        return self._save_path

    @property
    def exam_files(self) -> list[Path]:
        return self._exam_files

    @property
    def exam_paper_files(self) -> list[Path]:
        return self._exam_paper_files

    @property
    def solution_files(self) -> list[Path]:
        return self._solution_files

    @property
    def rule_files(self) -> list[Path]:
        return self._rule_files
