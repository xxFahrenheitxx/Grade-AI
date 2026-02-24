"""Left panel -- VSCode-style file explorer sidebar."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, QEvent, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from gradeai.constants import (
    EXAM_PAPERS_DIR,
    EXAMS_DIR,
    GRADING_REPORTS_DIR,
    RULES_DIR,
    SOLUTIONS_DIR,
)

logger = logging.getLogger(__name__)

# The project folders shown in the file browser.
_PROJECT_FOLDERS = {EXAM_PAPERS_DIR, EXAMS_DIR, SOLUTIONS_DIR, RULES_DIR, GRADING_REPORTS_DIR}


class _ProjectFileSystemModel(QFileSystemModel):
    """A QFileSystemModel subclass that filters top-level entries to only
    show the four canonical project folders.  Below the top level every
    file/directory is shown normally.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._project_root: Optional[Path] = None

    def set_project_root(self, root: Path) -> None:
        self._project_root = root

    # ----- Qt overrides ---------------------------------------------------

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        """Hide entries at the project-root level that are not in _PROJECT_FOLDERS."""
        # If no project root is set, show everything.
        if self._project_root is None:
            return True

        # Get the file path of the parent directory
        parent_path = self.filePath(source_parent) if source_parent.isValid() else ""

        # Only filter direct children of the project root
        if parent_path == str(self._project_root):
            idx = self.index(source_row, 0, source_parent)
            name = self.fileName(idx)
            return name in _PROJECT_FOLDERS

        # For all other levels, show everything
        return True

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:  # noqa: N802
        """Ensure folders that pass the filter still report children."""
        return super().hasChildren(parent)


class _ExplorerTreeView(QTreeView):
    """Tree view that accepts external file/folder drops."""

    external_drop = Signal(list, QModelIndex)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
            if urls:
                dropped_paths = [Path(url.toLocalFile()) for url in urls]
                target_index = self.indexAt(event.position().toPoint())
                self.external_drop.emit(dropped_paths, target_index)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class LeftPanel(QWidget):
    """File explorer panel for the left side of the IDE.

    Signals
    -------
    file_selected(str)
        Emitted when the user double-clicks a file.  The payload is the
        absolute file path as a string.
    title_changed(str)
        Emitted when the user edits the project title.
    import_requested(str)
        Emitted when the user selects *Import Files...* from the context
        menu.  The payload is the target folder name (e.g. ``"Exams"``).
    items_deleted(list[str])
        Emitted after deletion with absolute paths that were successfully deleted.
    items_about_to_delete(list[str])
        Emitted just before deletion with absolute target paths.
    """

    file_selected = Signal(str)
    title_changed = Signal(str)
    import_requested = Signal(str)
    items_about_to_delete = Signal(list)
    items_deleted = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("leftPanel")

        self._working_dir: Optional[Path] = None

        # ----- Layout ---------------------------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Header area (explorer label) --------------------------------------
        header = QWidget()
        header.setObjectName("panelFrame")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 4)

        self._explorer_label = QLabel("EXPLORER")
        self._explorer_label.setObjectName("subtitleLabel")
        header_layout.addWidget(self._explorer_label)
        header_layout.addStretch()
        layout.addWidget(header)

        # -- Project title (display + edit) ------------------------------------
        title_container = QWidget()
        title_container.setObjectName("panelFrame")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(12, 4, 12, 8)
        title_layout.setSpacing(0)

        # Display label (default mode - read-only)
        self._title_label = QLabel()
        self._title_label.setObjectName("titleLabel")
        self._title_label.setStyleSheet(
            "QLabel#titleLabel {"
            "  font-size: 14px;"
            "  font-weight: bold;"
            "  padding: 2px 4px;"
            "}"
        )
        self._title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title_label.setToolTip("Double-click to rename")
        self._title_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._title_label.customContextMenuRequested.connect(self._show_title_context_menu)
        self._title_label.installEventFilter(self)
        title_layout.addWidget(self._title_label)

        # Edit field (hidden by default)
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Project Title")
        self._title_edit.setObjectName("titleEditField")
        self._title_edit.setStyleSheet(
            "QLineEdit#titleEditField {"
            "  background: rgba(255, 255, 255, 0.05);"
            "  border: 1px solid #007acc;"
            "  font-size: 14px;"
            "  font-weight: bold;"
            "  padding: 2px 4px;"
            "}"
        )
        self._title_edit.editingFinished.connect(self._on_title_edit_finished)
        self._title_edit.setVisible(False)
        title_layout.addWidget(self._title_edit)

        layout.addWidget(title_container)

        # -- Tree view ---------------------------------------------------------
        self._model = _ProjectFileSystemModel(self)
        self._model.setReadOnly(True)
        # Show only the Name column; hide Size / Type / Date Modified.
        self._tree = _ExplorerTreeView()
        self._tree.setModel(self._model)
        for col in range(1, self._model.columnCount()):
            self._tree.hideColumn(col)
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setAcceptDrops(True)
        self._tree.viewport().setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self._tree.external_drop.connect(self._on_external_drop)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.clicked.connect(self._on_single_click)

        self._delete_selected_action = QAction(self)
        self._delete_selected_action.setShortcut(QKeySequence.StandardKey.Delete)
        self._delete_selected_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._delete_selected_action.triggered.connect(self._on_delete_key_pressed)
        self._tree.addAction(self._delete_selected_action)
        layout.addWidget(self._tree, 1)  # stretch factor 1

        # -- Placeholder (shown when no project is loaded) ---------------------
        self._placeholder = QLabel("Open or create a project\nto get started.")
        self._placeholder.setObjectName("subtitleLabel")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        layout.addWidget(self._placeholder, 1)

        # Start with no project loaded.
        self.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_project(self, working_dir: Path, title: str) -> None:
        """Configure the panel to display the contents of *working_dir*."""
        self._working_dir = working_dir

        # Title (display mode)
        self._title_label.setText(title)
        self._title_label.setVisible(True)
        self._title_edit.setVisible(False)

        # File model
        root_path = str(working_dir)
        self._model.set_project_root(working_dir)
        self._model.setRootPath(root_path)
        self._model.setFilter(
            QDir.Filter.AllDirs
            | QDir.Filter.Files
            | QDir.Filter.NoDotAndDotDot
        )
        root_index = self._model.index(root_path)
        self._tree.setRootIndex(root_index)
        self._tree.setVisible(True)

        self._model.directoryLoaded.connect(self._apply_root_visibility)
        self._apply_root_visibility()

        self._placeholder.setVisible(False)

    def clear(self) -> None:
        """Reset the panel to its empty / no-project state."""
        self._working_dir = None
        self._title_label.clear()
        self._title_label.setVisible(False)
        self._title_edit.clear()
        self._title_edit.setVisible(False)
        self._tree.setVisible(False)
        self._placeholder.setVisible(True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_root_visibility(self) -> None:
        """Hide root-level entries that are not canonical project folders."""
        if self._working_dir is None:
            return
        root_index = self._model.index(str(self._working_dir))
        if not root_index.isValid():
            return
        for row in range(self._model.rowCount(root_index)):
            child_index = self._model.index(row, 0, root_index)
            name = self._model.fileName(child_index)
            hide = name not in _PROJECT_FOLDERS
            self._tree.setRowHidden(row, root_index, hide)

    def eventFilter(self, obj, event):  # noqa: N802
        """Detect double-click on the title label to enter edit mode."""
        if obj is self._title_label and event.type() == QEvent.Type.MouseButtonDblClick:
            self._start_title_edit()
            return True
        return super().eventFilter(obj, event)

    def _start_title_edit(self) -> None:
        """Switch from display label to editable QLineEdit."""
        self._title_edit.setText(self._title_label.text())
        self._title_label.setVisible(False)
        self._title_edit.setVisible(True)
        self._title_edit.setFocus()
        self._title_edit.selectAll()

    def _on_title_edit_finished(self) -> None:
        """Finish editing: switch back to label, emit signal if changed."""
        text = self._title_edit.text().strip()
        if text:
            self._title_label.setText(text)
            self.title_changed.emit(text)
        self._title_edit.setVisible(False)
        self._title_label.setVisible(True)

    def _show_title_context_menu(self, pos) -> None:
        """Show context menu on the title label with Rename option."""
        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(self._start_title_edit)
        menu.addAction(rename_action)
        menu.exec(self._title_label.mapToGlobal(pos))

    def _on_single_click(self, index: QModelIndex) -> None:
        """Handle single-click: toggle expand/collapse for folders, open files."""
        if not index.isValid():
            return
        if self._model.isDir(index):
            if self._tree.isExpanded(index):
                self._tree.collapse(index)
            else:
                self._tree.expand(index)
        else:
            path = self._model.filePath(index)
            if path:
                self.file_selected.emit(path)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _resolve_target_folder(self, index: QModelIndex) -> Optional[str]:
        """Walk up from *index* to find which project folder it belongs to.

        Returns the folder name (e.g. ``"Exams"``) or ``None``.
        """
        if self._working_dir is None or not index.isValid():
            return None

        path = Path(self._model.filePath(index))
        try:
            rel = path.relative_to(self._working_dir)
        except ValueError:
            return None

        parts = rel.parts
        if parts and parts[0] in _PROJECT_FOLDERS:
            return parts[0]
        return None

    def _show_context_menu(self, pos) -> None:  # noqa: ANN001
        """Build and show an appropriate context menu at *pos*."""
        if self._working_dir is None:
            return

        index = self._tree.indexAt(pos)
        menu = QMenu(self)

        if index.isValid():
            selected_indexes = self._tree.selectionModel().selectedRows(0)
            if not any(i == index for i in selected_indexes):
                selected_indexes = [index]

            selected_paths = self._paths_from_indexes(selected_indexes)

            multi_selection = len(selected_paths) > 1
            file_path = Path(self._model.filePath(index))
            is_dir = self._model.isDir(index)
            target_folder = self._resolve_target_folder(index)

            # "Open" -- files only, single selection
            if not is_dir and not multi_selection:
                open_action = QAction("Open", self)
                open_action.triggered.connect(lambda: self.file_selected.emit(str(file_path)))
                menu.addAction(open_action)
                menu.addSeparator()

            # "Import Files..." -- only on directories, single selection
            if is_dir and target_folder and not multi_selection:
                import_action = QAction("Import Files...", self)
                import_action.triggered.connect(lambda: self.import_requested.emit(target_folder))
                menu.addAction(import_action)

            # "New Folder" / "New File" -- only on directories,
            # NOT inside Grading Reports (managed by the app).
            is_grading_reports = (target_folder == GRADING_REPORTS_DIR)
            if is_dir and not is_grading_reports and not multi_selection:
                new_folder_action = QAction("New Folder", self)
                new_folder_action.triggered.connect(lambda: self._create_new_folder(file_path))
                menu.addAction(new_folder_action)

                new_file_action = QAction("New File", self)
                new_file_action.triggered.connect(lambda: self._create_new_file(file_path))
                menu.addAction(new_file_action)

            # "Delete" -- don't allow deleting top-level project folders themselves.
            deletable_paths = self._filter_deletable_paths(selected_paths)

            if deletable_paths:
                menu.addSeparator()
                label = f"Delete Selected ({len(deletable_paths)})" if len(deletable_paths) > 1 else "Delete"
                delete_action = QAction(label, self)
                delete_action.triggered.connect(
                    lambda checked=False, paths=deletable_paths: self._delete_items(paths)
                )
                menu.addAction(delete_action)

        else:
            # Right-click on empty area -- no useful actions.
            return

        if not menu.isEmpty():
            menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # File operations triggered by context menu
    # ------------------------------------------------------------------

    def _on_delete_key_pressed(self) -> None:
        """Delete currently selected items when Delete key is pressed."""
        if self._working_dir is None:
            return
        selected_indexes = self._tree.selectionModel().selectedRows(0)
        selected_paths = self._paths_from_indexes(selected_indexes)
        deletable_paths = self._filter_deletable_paths(selected_paths)
        if deletable_paths:
            self._delete_items(deletable_paths)

    def _paths_from_indexes(self, indexes: list[QModelIndex]) -> list[Path]:
        """Convert model indexes to unique filesystem paths."""
        paths: list[Path] = []
        for index in indexes:
            if not index.isValid():
                continue
            path = Path(self._model.filePath(index))
            if path not in paths:
                paths.append(path)
        return paths

    def _filter_deletable_paths(self, paths: list[Path]) -> list[Path]:
        """Return only paths that are allowed to be deleted."""
        deletable_paths: list[Path] = []
        for path in paths:
            selected_idx = self._model.index(str(path))
            selected_is_dir = selected_idx.isValid() and self._model.isDir(selected_idx)
            selected_is_top_level_folder = (
                selected_is_dir
                and path.parent == self._working_dir
                and path.name in _PROJECT_FOLDERS
            )
            if not selected_is_top_level_folder:
                deletable_paths.append(path)
        return deletable_paths

    def _on_external_drop(self, dropped_paths: list[Path], index: QModelIndex) -> None:
        """Handle drag-and-drop imports into the selected/target folder."""
        target_dir = self._resolve_drop_target_dir(index)
        if target_dir is None:
            QMessageBox.warning(
                self,
                "Drop Not Allowed",
                "Please select a destination folder in the navigation panel.",
            )
            return
        self._copy_paths_into_directory(dropped_paths, target_dir)

    def _resolve_drop_target_dir(self, index: QModelIndex) -> Optional[Path]:
        """Resolve which directory should receive dropped files/folders."""
        if self._working_dir is None:
            return None

        target_dir: Optional[Path] = None
        if index.isValid():
            candidate = Path(self._model.filePath(index))
            target_dir = candidate if self._model.isDir(index) else candidate.parent
        else:
            selected = self._tree.selectionModel().selectedRows(0)
            if selected:
                candidate = Path(self._model.filePath(selected[0]))
                target_dir = candidate if self._model.isDir(selected[0]) else candidate.parent

        if target_dir is None:
            return None
        if not target_dir.exists() or not target_dir.is_dir():
            return None
        try:
            target_dir.relative_to(self._working_dir)
        except ValueError:
            return None
        return target_dir

    def _copy_paths_into_directory(self, sources: list[Path], target_dir: Path) -> None:
        """Copy dropped files/folders into target_dir with safety checks."""
        copied = 0
        errors: list[str] = []
        for source in sources:
            if not source.exists():
                errors.append(f"{source.name}: source not found.")
                continue

            destination = target_dir / source.name
            if destination.exists():
                errors.append(f"{source.name}: destination already exists.")
                continue
            if source == target_dir or target_dir in source.parents:
                errors.append(f"{source.name}: invalid destination.")
                continue

            try:
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
                copied += 1
            except OSError as exc:
                errors.append(f"{source.name}: {exc}")

        if errors:
            QMessageBox.warning(self, "Import Error", "Some items could not be added:\n\n" + "\n".join(errors))
        if copied > 0:
            logger.info("Imported %s item(s) into %s", copied, target_dir)

    def _create_new_folder(self, parent_dir: Path) -> None:
        """Create a new folder inside *parent_dir* with a default name."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, "New Folder", "Folder name:", text="New Folder"
        )
        if ok and name.strip():
            target = parent_dir / name.strip()
            try:
                target.mkdir(parents=True, exist_ok=True)
                logger.info("Created folder: %s", target)
            except OSError as exc:
                QMessageBox.warning(self, "Error", f"Could not create folder:\n{exc}")

    def _create_new_file(self, parent_dir: Path) -> None:
        """Create a new empty file inside *parent_dir*."""
        from PySide6.QtWidgets import QInputDialog

        # Detect if we are inside the Rules folder
        is_rules = False
        if self._working_dir is not None:
            try:
                rel = parent_dir.relative_to(self._working_dir)
                is_rules = bool(rel.parts) and rel.parts[0] == RULES_DIR
            except ValueError:
                pass

        default_name = "untitled.md" if is_rules else "untitled.txt"
        name, ok = QInputDialog.getText(
            self, "New File", "File name:", text=default_name
        )
        if ok and name.strip():
            name = name.strip()

            # Enforce .md extension in Rules folder
            if is_rules and not name.lower().endswith(".md"):
                name = Path(name).stem + ".md"
                QMessageBox.information(
                    self, "Rules Folder",
                    f"Files in the Rules folder must be Markdown (.md).\n"
                    f"The file will be created as: {name}",
                )

            target = parent_dir / name
            if target.exists():
                QMessageBox.warning(
                    self, "File Exists", f"A file named '{name}' already exists."
                )
                return
            try:
                target.touch()
                logger.info("Created file: %s", target)
            except OSError as exc:
                QMessageBox.warning(self, "Error", f"Could not create file:\n{exc}")

    def _delete_item(self, path: Path) -> None:
        """Delete a file or directory after user confirmation."""
        self._delete_items([path])

    def _delete_items(self, paths: list[Path]) -> None:
        """Delete one or many files/directories after user confirmation."""
        unique_paths: list[Path] = []
        for path in paths:
            if path not in unique_paths:
                unique_paths.append(path)
        if not unique_paths:
            return

        if len(unique_paths) == 1:
            path = unique_paths[0]
            kind = "folder" if path.is_dir() else "file"
            message = f"Are you sure you want to delete this {kind}?\n\n{path.name}"
        else:
            message = (
                f"Are you sure you want to delete {len(unique_paths)} selected items?\n\n"
                "This action cannot be undone."
            )

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Give listeners (e.g. center tabs) a chance to release file handles
        # before Windows-level deletion is attempted.
        self.items_about_to_delete.emit([str(path) for path in unique_paths])

        errors: list[str] = []
        deleted_paths: list[str] = []
        for path in unique_paths:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    logger.info("Deleted folder: %s", path)
                    deleted_paths.append(str(path))
                else:
                    path.unlink()
                    logger.info("Deleted file: %s", path)
                    deleted_paths.append(str(path))
            except OSError as exc:
                errors.append(f"{path.name}: {exc}")

        if deleted_paths:
            self.items_deleted.emit(deleted_paths)

        if errors:
            QMessageBox.warning(self, "Error", "Could not delete some items:\n\n" + "\n".join(errors))
