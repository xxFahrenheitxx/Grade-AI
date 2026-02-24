"""Startup splash screen shown when no project is loaded."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gradeai.constants import PROJECT_EXTENSION

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


class StartScreen(QFrame):
    """Splash screen with project entry points and drop target."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_requested = Signal(str)
    project_dropped = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("startScreen")
        self.setAcceptDrops(True)
        self._recent_paths: list[str] = []
        self._setup_ui()

    def set_recent_projects(self, paths: list[str]) -> None:
        """Update the list of clickable recent projects."""
        self._recent_paths = list(paths)
        self._rebuild_recent_list()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 40, 48, 40)
        root.setSpacing(18)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo.setObjectName("logoLabel")
        logo_pixmap = QPixmap(str(ASSETS_DIR / "logo.png"))
        if not logo_pixmap.isNull():
            logo.setPixmap(
                logo_pixmap.scaledToWidth(
                    220,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        root.addWidget(logo)

        subtitle = QLabel("Create a new project, open a recent one, or drop a .grd file here.")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        actions_row.addStretch(1)

        self._new_btn = QPushButton("New Project")
        self._new_btn.setMinimumHeight(34)
        self._new_btn.clicked.connect(self.new_project_requested.emit)
        actions_row.addWidget(self._new_btn)

        self._open_btn = QPushButton("Open Project")
        self._open_btn.setObjectName("secondaryButton")
        self._open_btn.setMinimumHeight(34)
        self._open_btn.clicked.connect(self.open_project_requested.emit)
        actions_row.addWidget(self._open_btn)

        actions_row.addStretch(1)
        root.addLayout(actions_row)

        self._drop_zone = QLabel(f"Drag and drop a *{PROJECT_EXTENSION} file here")
        self._drop_zone.setObjectName("startScreenDropZone")
        self._drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_zone.setMinimumHeight(92)
        root.addWidget(self._drop_zone)

        recent_label = QLabel("Recent Projects")
        recent_label.setObjectName("headerLabel")
        root.addWidget(recent_label)

        self._recent_area = QScrollArea()
        self._recent_area.setObjectName("startScreenRecentArea")
        self._recent_area.setWidgetResizable(True)
        self._recent_area.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self._recent_area, 1)
        self._recent_area.viewport().setObjectName("startScreenRecentViewport")

        self._recent_container = QWidget()
        self._recent_container.setObjectName("startScreenRecentContainer")
        self._recent_layout = QVBoxLayout(self._recent_container)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(8)
        self._recent_area.setWidget(self._recent_container)

        self._rebuild_recent_list()

    def _rebuild_recent_list(self) -> None:
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self._recent_paths:
            empty = QLabel("No recent projects")
            empty.setObjectName("subtitleLabel")
            self._recent_layout.addWidget(empty)
            self._recent_layout.addStretch(1)
            return

        for path_str in self._recent_paths:
            path = Path(path_str)
            btn = QPushButton(path.name)
            btn.setObjectName("startScreenRecentButton")
            btn.setToolTip(path_str)
            btn.setMinimumHeight(30)
            btn.clicked.connect(lambda _checked=False, p=path_str: self.recent_project_requested.emit(p))
            self._recent_layout.addWidget(btn)
        self._recent_layout.addStretch(1)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.isLocalFile() and url.toLocalFile().lower().endswith(PROJECT_EXTENSION) for url in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            local_path = url.toLocalFile()
            if local_path.lower().endswith(PROJECT_EXTENSION):
                self.project_dropped.emit(local_path)
                event.acceptProposedAction()
                return
        event.ignore()
