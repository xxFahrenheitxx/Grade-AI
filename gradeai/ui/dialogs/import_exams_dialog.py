"""Import exams dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)


class ImportExamsDialog(QDialog):
    """Dialog for importing exam files into a project."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Exams")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)

        self._files: list[Path] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Select exam files or folders to import:"))

        self._file_list = QListWidget()
        layout.addWidget(self._file_list)

        btn_layout = QHBoxLayout()
        add_files_btn = QPushButton("Add Files...")
        add_files_btn.setObjectName("secondaryButton")
        add_files_btn.clicked.connect(self._add_files)

        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.setObjectName("secondaryButton")
        add_folder_btn.clicked.connect(self._add_folder)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("secondaryButton")
        remove_btn.clicked.connect(self._remove_selected)

        btn_layout.addWidget(add_files_btn)
        btn_layout.addWidget(add_folder_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        note = QLabel("Folders will be imported with their complete structure.")
        note.setObjectName("subtitleLabel")
        layout.addWidget(note)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select Exam Files", "")
        for f in files:
            p = Path(f)
            if p not in self._files:
                self._files.append(p)
                self._file_list.addItem(str(p))

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Exam Folder")
        if folder:
            p = Path(folder)
            if p not in self._files:
                self._files.append(p)
                self._file_list.addItem(f"[Folder] {p}")

    def _remove_selected(self) -> None:
        for item in self._file_list.selectedItems():
            row = self._file_list.row(item)
            self._file_list.takeItem(row)
            if row < len(self._files):
                self._files.pop(row)

    @property
    def selected_files(self) -> list[Path]:
        return self._files
