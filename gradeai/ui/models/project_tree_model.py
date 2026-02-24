"""Qt tree model for the project file browser."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QFileSystemModel

from gradeai.constants import EXAMS_DIR, GRADING_REPORTS_DIR, RULES_DIR, SOLUTIONS_DIR


class ProjectFileSystemModel(QFileSystemModel):
    """File system model restricted to project directories."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self._project_dir: Optional[Path] = None

    def set_project_dir(self, project_dir: Path) -> QModelIndex:
        """Set the root project directory and return its model index."""
        self._project_dir = project_dir
        root_path = str(project_dir)
        self.setRootPath(root_path)
        return self.index(root_path)

    @property
    def project_dir(self) -> Optional[Path]:
        return self._project_dir


class ProjectTreeFilterModel(QSortFilterProxyModel):
    """Filter proxy that only shows project folders (Exams, Solutions, Rules, Grading Reports)."""

    VISIBLE_FOLDERS = {EXAMS_DIR, SOLUTIONS_DIR, RULES_DIR, GRADING_REPORTS_DIR}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._project_dir: Optional[Path] = None

    def set_project_dir(self, project_dir: Path) -> None:
        self._project_dir = project_dir
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Only show the 4 project folders at root level; show everything inside them."""
        source_model = self.sourceModel()
        if not isinstance(source_model, ProjectFileSystemModel):
            return True

        index = source_model.index(source_row, 0, source_parent)
        file_path = Path(source_model.filePath(index))

        if self._project_dir is None:
            return True

        # At root level (direct children of project dir), only show project folders
        parent_path = file_path.parent
        if parent_path == self._project_dir:
            return file_path.name in self.VISIBLE_FOLDERS

        # Inside project folders, show everything
        return True
