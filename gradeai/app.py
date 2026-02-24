"""Application setup and initialization."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from gradeai.constants import APP_NAME, APP_ORGANIZATION
from gradeai.models.settings import AppSettings
from gradeai.ui.main_window import MainWindow
from gradeai.ui.scrollbar_manager import ScrollbarAutoHideManager
from gradeai.ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def setup_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _set_windows_app_user_model_id() -> None:
    """Set a stable Windows AppUserModelID for taskbar icon grouping."""
    if not sys.platform.startswith("win"):
        return
    app_id = f"{APP_ORGANIZATION}.{APP_NAME}".replace(" ", "")
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        logger.debug("Could not set Windows AppUserModelID", exc_info=True)


def create_app() -> tuple[QApplication, MainWindow]:
    """Create and configure the application and main window."""
    setup_logging()
    _set_windows_app_user_model_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app_icon = QIcon(str(ASSETS_DIR / "ico.png"))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Load settings
    settings = AppSettings.load()

    # Apply theme
    theme_manager = ThemeManager(app, settings.theme)

    # Create main window
    window = MainWindow(app_settings=settings, theme_manager=theme_manager)
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    # Keep a strong reference on the window for the app lifetime.
    window._scrollbar_manager = ScrollbarAutoHideManager(app, window)  # type: ignore[attr-defined]

    return app, window


def run() -> int:
    """Run the Grade AI application."""
    app, window = create_app()
    window.show()
    return app.exec()
