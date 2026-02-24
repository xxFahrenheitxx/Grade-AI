"""Centre document panel with tabbed document viewers and split-view support."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gradeai.constants import EXAMS_DIR, SOLUTIONS_DIR, RULES_DIR
from gradeai.utils.file_utils import get_file_category

from gradeai.ui.widgets.annotation_toolbar import AnnotationToolbar
from gradeai.ui.widgets.loading_overlay import LoadingOverlay
from gradeai.ui.widgets.code_viewer import CodeViewer
from gradeai.ui.widgets.docx_viewer import DocxViewer
from gradeai.ui.widgets.image_viewer import ImageViewer
from gradeai.ui.widgets.markdown_viewer import MarkdownViewer
from gradeai.ui.widgets.pdf_viewer import PDFViewer
from gradeai.ui.widgets.spreadsheet_viewer import SpreadsheetViewer
from gradeai.ui.widgets.text_editor import TextEditor

logger = logging.getLogger(__name__)


def _is_editable_markdown(path: Path) -> bool:
    """Return True if the markdown file lives inside Solutions/ or Rules/.

    Files in these directories should be opened in the text editor for
    editing rather than the read-only preview.
    """
    path_str = path.as_posix()
    parts = Path(path_str).parts
    return SOLUTIONS_DIR in parts or RULES_DIR in parts


class _DocumentTab(QWidget):
    """Thin wrapper around a viewer widget that carries its file path."""

    def __init__(self, viewer: QWidget, file_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.viewer = viewer
        self.file_path = file_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(viewer)


class _TabBar(QTabWidget):
    """A ``QTabWidget`` with closeable tabs and middle-click-to-close."""

    tab_close_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.tabCloseRequested.connect(self.tab_close_requested)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Close a tab when middle-clicked."""
        if event.button() == Qt.MouseButton.MiddleButton:
            index = self.tabBar().tabAt(event.pos())
            if index >= 0:
                self.tab_close_requested.emit(index)
                return
        super().mousePressEvent(event)


class CenterPanel(QWidget):
    """The centre document panel of the IDE.

    Manages a tabbed document viewer that routes files to the correct viewer
    widget based on the file extension.  Supports closing, switching, and
    splitting views.

    Signals
    -------
    document_opened(str)
        Emitted with the file path (as string) when a document is opened.
    document_closed(str)
        Emitted with the file path when a tab is closed.
    active_document_changed(str)
        Emitted with the file path when the active (current) tab changes.
    """

    document_opened = Signal(str)
    document_closed = Signal(str)
    active_document_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Track open file paths -> tab indices (per tab widget)
        self._open_paths: dict[str, tuple[_TabBar, int]] = {}
        self._dirty_paths: dict[str, bool] = {}
        self._project_root: Optional[Path] = None

        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # A splitter that can hold one or two tab-bar widgets
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._layout.addWidget(self._splitter)

        # Primary tab widget
        self._primary_tabs = self._create_tab_widget()
        self._splitter.addWidget(self._primary_tabs)

        # Secondary tab widget (created lazily on split)
        self._secondary_tabs: Optional[_TabBar] = None

        # Placeholder label shown when no tabs are open
        self._placeholder = QLabel("Open a file from the explorer to begin.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 14px;")
        self._layout.addWidget(self._placeholder)

        # Loading overlay (shown during long operations)
        self._loading_overlay = LoadingOverlay(self)

        # Floating annotation toolbar (shown when an exam is active)
        self._annotation_toolbar = AnnotationToolbar(self)
        self._annotation_toolbar.setVisible(False)
        self._annotation_toolbar.setEnabled(False)

        self._update_placeholder_visibility()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def annotation_toolbar(self) -> AnnotationToolbar:
        """Expose the annotation toolbar for external signal connections."""
        return self._annotation_toolbar

    def show_loading(self, message: str = "Loading...", delay_ms: int = 500) -> None:
        """Show loading overlay after a configurable delay."""
        self._loading_overlay.show_after_delay(message, delay_ms=delay_ms)

    def hide_loading(self) -> None:
        """Hide the loading overlay."""
        self._loading_overlay.hide_loading()

    def set_project_root(self, project_root: Path) -> None:
        """Set current project root for UI-state path serialization."""
        self._project_root = project_root

    def open_document(self, path: Path, read_only: bool = False) -> None:
        """Open a document in the appropriate viewer.

        If the file is already open, the existing tab is activated instead of
        creating a duplicate.
        """
        path_key = str(path)

        # Switch to existing tab if already open
        if path_key in self._open_paths:
            tab_widget, idx = self._open_paths[path_key]
            tab_widget.setCurrentIndex(idx)
            return

        viewer = self._create_viewer(path, read_only)
        if viewer is None:
            logger.warning("No viewer available for: %s", path)
            return

        tab = _DocumentTab(viewer, path)
        target = self._active_tab_widget()
        index = target.addTab(tab, "")
        target.setTabToolTip(index, str(path))
        target.setCurrentIndex(index)
        self._set_tab_title(target, index, path.name, bold=False)

        # Record the mapping
        self._open_paths[path_key] = (target, index)
        self._dirty_paths[path_key] = False
        self._connect_dirty_tracking(viewer, path_key)

        self._update_placeholder_visibility()
        # Defer signal so the newly added tab can paint before heavier
        # post-open workflows in MainWindow run.
        QTimer.singleShot(0, lambda p=path_key: self.document_opened.emit(p))

    def split_view(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal) -> None:
        """Split the editor area so two documents can be viewed side-by-side."""
        if self._secondary_tabs is not None:
            # Already split -- just update orientation if needed
            self._splitter.setOrientation(orientation)
            return

        self._splitter.setOrientation(orientation)
        self._secondary_tabs = self._create_tab_widget()
        self._splitter.addWidget(self._secondary_tabs)

    def close_split(self) -> None:
        """Close the secondary split pane, moving any open tabs back to primary."""
        if self._secondary_tabs is None:
            return

        # Move remaining tabs to primary
        while self._secondary_tabs.count() > 0:
            widget = self._secondary_tabs.widget(0)
            previous_text = self._secondary_tabs.tabText(0)
            tooltip = self._secondary_tabs.tabToolTip(0)
            self._secondary_tabs.removeTab(0)
            if isinstance(widget, _DocumentTab):
                title = widget.file_path.name
            else:
                title = previous_text
            index = self._primary_tabs.addTab(widget, "")
            self._primary_tabs.setTabToolTip(index, tooltip)
            self._set_tab_title(self._primary_tabs, index, title, bold=False)
            # Update mapping
            if isinstance(widget, _DocumentTab):
                self._open_paths[str(widget.file_path)] = (
                    self._primary_tabs,
                    index,
                )

        self._secondary_tabs.setParent(None)  # type: ignore[arg-type]
        self._secondary_tabs.deleteLater()
        self._secondary_tabs = None

    def clear_all(self) -> None:
        """Close all open tabs and reset the panel."""
        # Close secondary split first
        self.close_split()
        # Close all primary tabs
        while self._primary_tabs.count() > 0:
            self._close_tab(self._primary_tabs, 0)
        self._open_paths.clear()
        self._dirty_paths.clear()
        self._update_placeholder_visibility()

    def load_annotations(self, annotations) -> None:
        """Load annotations onto the currently active document viewer.

        This is a no-op if the active viewer does not support annotations
        (only PDFViewer and ImageViewer support overlays).
        """
        tab_widget = self._active_tab_widget()
        widget = tab_widget.currentWidget()
        if isinstance(widget, _DocumentTab):
            viewer = widget.viewer
            # PDFViewer and ImageViewer inherit from ZoomableScrollArea
            # which has a QGraphicsScene that can host annotations
            from gradeai.ui.widgets.annotation_overlay import AnnotationOverlay
            if hasattr(viewer, '_scene'):
                if not hasattr(viewer, '_annotation_overlay'):
                    viewer._annotation_overlay = AnnotationOverlay(viewer._scene)
                if hasattr(viewer, "get_annotation_page_dimensions"):
                    dims = viewer.get_annotation_page_dimensions()
                    viewer._annotation_overlay.set_page_dimensions(dims)
                viewer._annotation_overlay.load_annotations(annotations)

    def save_active_document(self) -> bool:
        """Save the active document if it's a TextEditor with unsaved changes.

        Returns True if a file was saved, False otherwise.
        """
        tab_widget = self._active_tab_widget()
        widget = tab_widget.currentWidget()
        if isinstance(widget, _DocumentTab):
            viewer = widget.viewer
            if isinstance(viewer, TextEditor) and viewer.is_modified:
                viewer.save_file()
                return True
        return False

    def get_open_paths(self) -> list[str]:
        """Return a list of all currently open file paths."""
        return list(self._open_paths.keys())

    def close_document(self, path: Path | str) -> bool:
        """Close the tab for *path* if currently open.

        Returns True if a tab was closed, False if it was not open.
        """
        path_key = str(path)
        if path_key not in self._open_paths:
            return False
        tab_widget, idx = self._open_paths[path_key]
        self._close_tab(tab_widget, idx)
        return True

    def active_document_path(self) -> Optional[str]:
        """Return the file path of the currently active tab, or ``None``."""
        tab_widget = self._active_tab_widget()
        widget = tab_widget.currentWidget()
        if isinstance(widget, _DocumentTab):
            return str(widget.file_path)
        return None

    def get_ui_state(self) -> dict:
        """Get the current UI state (open files, active file)."""
        open_files = []
        for path_str in self._open_paths.keys():
            path = Path(path_str)
            if self._project_root:
                try:
                    open_files.append(path.relative_to(self._project_root).as_posix())
                    continue
                except ValueError:
                    pass
            open_files.append(path_str)

        active_file = self.active_document_path()
        if active_file and self._project_root:
            try:
                active_file = Path(active_file).relative_to(self._project_root).as_posix()
            except ValueError:
                pass

        state = {
            "open_files": open_files,
            "active_file": active_file,
        }
        return state

    def restore_ui_state(self, state: dict, project_working_dir: Path) -> None:
        """Restore the UI state (open files, active file)."""
        from gradeai.utils.file_utils import is_exam_file

        def _resolve_saved_path(saved_path: str) -> Path:
            path = Path(saved_path)
            if not path.is_absolute():
                return project_working_dir / path
            if path.exists():
                return path
            parts = list(path.parts)
            for marker in (EXAMS_DIR, SOLUTIONS_DIR, RULES_DIR, "Grading Reports"):
                if marker in parts:
                    idx = parts.index(marker)
                    return project_working_dir / Path(*parts[idx:])
            return path

        # Reopen files
        for file_path_str in state.get("open_files", []):
            file_path = _resolve_saved_path(file_path_str)
            if file_path.exists():
                read_only = is_exam_file(file_path, project_working_dir)
                self.open_document(file_path, read_only=read_only)

        # Restore active file
        active_file = state.get("active_file")
        active_file_key = None
        if active_file:
            active_path = _resolve_saved_path(active_file)
            active_file_key = str(active_path)
        if active_file_key and active_file_key in self._open_paths:
            tab_widget, idx = self._open_paths[active_file_key]
            tab_widget.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Viewer factory
    # ------------------------------------------------------------------

    def _create_viewer(self, path: Path, read_only: bool) -> Optional[QWidget]:
        """Instantiate the correct viewer widget for *path*."""
        category = get_file_category(path)
        viewer: Optional[QWidget] = None

        if category == "pdf":
            v = PDFViewer(self)
            v.load_file(path)
            viewer = v

        elif category == "image":
            v = ImageViewer(self)
            v.load_file(path)
            viewer = v

        elif category == "word":
            v = DocxViewer(self)
            v.load_file(path)
            viewer = v

        elif category == "excel":
            v = SpreadsheetViewer(self)
            v.load_file(path)
            viewer = v

        elif category == "code":
            v = CodeViewer(self)
            v.load_file(path)
            if not read_only:
                v.set_editable(True)
            viewer = v

        elif category == "markdown":
            # Markdown files in Solutions/Rules open as editable text;
            # otherwise they open in read-only preview mode.
            if not read_only and _is_editable_markdown(path):
                te = TextEditor(self)
                te.load_file(path)
                viewer = te
            else:
                mv = MarkdownViewer(self)
                mv.load_file(path)
                viewer = mv

        elif category == "text":
            te = TextEditor(self)
            te.load_file(path)
            if read_only:
                te.setReadOnly(True)
            viewer = te

        else:
            # Unknown type -- fall back to plain text
            te = TextEditor(self)
            te.load_file(path)
            te.setReadOnly(True)
            viewer = te

        return viewer

    # ------------------------------------------------------------------
    # Tab management helpers
    # ------------------------------------------------------------------

    def _create_tab_widget(self) -> _TabBar:
        """Create and wire up a new tab-bar widget."""
        tw = _TabBar(self)
        tw.tab_close_requested.connect(lambda idx, t=tw: self._close_tab(t, idx))
        tw.currentChanged.connect(lambda idx, t=tw: self._on_current_changed(t, idx))
        tw.tabBar().tabMoved.connect(lambda _from, _to, t=tw: self._rebuild_index_map(t))
        return tw

    def _active_tab_widget(self) -> _TabBar:
        """Return the tab widget that currently has focus (or primary)."""
        if self._secondary_tabs is not None and self._secondary_tabs.hasFocus():
            return self._secondary_tabs
        return self._primary_tabs

    def _close_tab(self, tab_widget: _TabBar, index: int) -> None:
        """Close the tab at *index* in *tab_widget*."""
        widget = tab_widget.widget(index)
        if isinstance(widget, _DocumentTab):
            path_key = str(widget.file_path)
            self._release_viewer_resources(widget.viewer)
            self._open_paths.pop(path_key, None)
            self._dirty_paths.pop(path_key, None)
            self.document_closed.emit(path_key)

        tab_widget.removeTab(index)
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()

        # Rebuild index mapping for remaining tabs in this widget
        self._rebuild_index_map(tab_widget)

        self._update_placeholder_visibility()

    def _release_viewer_resources(self, viewer: QWidget) -> None:
        """Release external resources for viewers that keep file handles."""
        release_method = getattr(viewer, "release_resources", None)
        if callable(release_method):
            try:
                release_method()
            except Exception:
                logger.exception("Error while releasing resources for %r", viewer)

    def _rebuild_index_map(self, tab_widget: _TabBar) -> None:
        """Re-synchronise the ``_open_paths`` index map after a tab change."""
        for idx in range(tab_widget.count()):
            widget = tab_widget.widget(idx)
            if isinstance(widget, _DocumentTab):
                path_key = str(widget.file_path)
                self._open_paths[path_key] = (tab_widget, idx)
                is_dirty = self._dirty_paths.get(path_key, False)
                self._set_tab_title(tab_widget, idx, widget.file_path.name, bold=is_dirty)

    def _on_current_changed(self, tab_widget: _TabBar, index: int) -> None:
        """Handle the active tab changing."""
        if index < 0:
            self._annotation_toolbar.setVisible(False)
            return
        widget = tab_widget.widget(index)
        if isinstance(widget, _DocumentTab):
            self.active_document_changed.emit(str(widget.file_path))
            self._annotation_toolbar.setVisible(False)
        else:
            self._annotation_toolbar.setVisible(False)

    def _position_annotation_toolbar(self) -> None:
        """Position the annotation toolbar at the bottom-centre of the panel."""
        return

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)

    def _update_placeholder_visibility(self) -> None:
        """Show the placeholder label only when no tabs are open."""
        has_tabs = self._primary_tabs.count() > 0 or (
            self._secondary_tabs is not None and self._secondary_tabs.count() > 0
        )
        self._placeholder.setVisible(not has_tabs)
        self._splitter.setVisible(has_tabs)

    def _connect_dirty_tracking(self, viewer: QWidget, path_key: str) -> None:
        """Track unsaved state for editable viewers and reflect it in tab title."""
        if isinstance(viewer, TextEditor):
            viewer.document().modificationChanged.connect(
                lambda modified, p=path_key: self._set_dirty_state(p, modified)
            )
            self._set_dirty_state(path_key, viewer.is_modified)
        elif isinstance(viewer, CodeViewer) and not viewer.isReadOnly():
            viewer.document().modificationChanged.connect(
                lambda modified, p=path_key: self._set_dirty_state(p, modified)
            )
            self._set_dirty_state(path_key, viewer.document().isModified())

    def _set_dirty_state(self, path_key: str, modified: bool) -> None:
        """Update unsaved marker for a tab and switch bold/regular title."""
        if path_key not in self._open_paths:
            return
        self._dirty_paths[path_key] = modified
        tab_widget, index = self._open_paths[path_key]
        file_name = Path(path_key).name
        self._set_tab_title(tab_widget, index, file_name, bold=modified)

    def _set_tab_title(self, tab_widget: _TabBar, index: int, title: str, bold: bool) -> None:
        """Render tab title with regular or bold font."""
        tab_widget.setTabText(index, "")
        label = QLabel(title)
        label.setObjectName("documentTabLabel")
        font = QFont(label.font())
        font.setBold(bold)
        label.setFont(font)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("padding-left: 10px;")
        tab_widget.tabBar().setTabButton(index, QTabBar.ButtonPosition.LeftSide, label)

        close_btn = QPushButton("\u00D7")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFlat(True)
        close_btn.setFixedSize(18, 18)
        close_color = "#FFFFFF" if self._is_dark_mode() else "#000000"
        close_btn.setStyleSheet(
            "QPushButton {"
            " border: none;"
            " background: transparent;"
            f" color: {close_color};"
            " font-size: 16px;"
            " font-weight: 600;"
            " padding: 0px;"
            " margin-right: 10px;"
            "}"
            "QPushButton:hover {"
            " background: rgba(127, 127, 127, 0.25);"
            " border-radius: 2px;"
            "}"
        )
        close_btn.setContentsMargins(0, 0, 0, 0)
        close_btn.clicked.connect(
            lambda _checked=False, t=tab_widget, b=close_btn: self._close_tab_from_button(t, b)
        )
        tab_widget.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, close_btn)

    def _close_tab_from_button(self, tab_widget: _TabBar, button: QPushButton) -> None:
        """Close the tab associated with a custom close button."""
        tab_bar = tab_widget.tabBar()
        for idx in range(tab_widget.count()):
            if tab_bar.tabButton(idx, QTabBar.ButtonPosition.RightSide) is button:
                self._close_tab(tab_widget, idx)
                return

    def _is_dark_mode(self) -> bool:
        """Infer dark vs light mode from panel background color."""
        return self.palette().window().color().lightness() < 128
