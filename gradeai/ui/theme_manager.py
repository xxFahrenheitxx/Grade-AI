"""Theme manager for loading and applying QSS stylesheets."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication

from gradeai.constants import THEME_DARK, THEME_LIGHT

logger = logging.getLogger(__name__)

# Resolve the project root: this file lives at gradeai/ui/theme_manager.py,
# so the project root is two levels up from this file's directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_THEMES_DIR = _PROJECT_ROOT / "assets" / "themes"

_FALLBACK_QSS = {
    THEME_DARK: """
QWidget { background-color: #1e1f22; color: #e8e9eb; }
QMainWindow, QDialog, QMenuBar, QMenu, QToolBar, QStatusBar { background-color: #1e1f22; color: #e8e9eb; }
QFrame#startScreen { background-color: #1e1f22; }
QWidget#leftPanel { border-right: 1px solid #596272; }
QFrame#rightPanelFrame { border-left: 1px solid #596272; }
QSplitter::handle { background-color: #596272; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QLabel#titleLabel { color: #f3f4f6; }
QLabel#subtitleLabel { color: #b4bac4; }
QPushButton { background-color: #2d3138; border: 1px solid #3a3f48; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover { background-color: #383e47; }
QPushButton:pressed { background-color: #2a2f36; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { background-color: #252932; border: 1px solid #3a3f48; border-radius: 6px; padding: 4px 6px; color: #e8e9eb; }
QScrollArea, QListView, QTreeView, QTableView { background-color: #252932; border: 1px solid #3a3f48; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; border: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; border: none; }
QScrollBar::handle:vertical { background: rgba(153, 163, 178, 180); min-height: 24px; border-radius: 5px; }
QScrollBar::handle:horizontal { background: rgba(153, 163, 178, 180); min-width: 24px; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: rgba(184, 192, 205, 220); }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: transparent; border: none; width: 0; height: 0; }
QHeaderView::section { background-color: #2d3138; color: #d9dde4; border: 0; padding: 4px 6px; }
QMenu::item:selected { background-color: #3a3f48; }
""",
    THEME_LIGHT: """
QWidget { background-color: #f6f7fb; color: #1f2937; }
QMainWindow, QDialog, QMenuBar, QMenu, QToolBar, QStatusBar { background-color: #f6f7fb; color: #1f2937; }
QFrame#startScreen { background-color: #f6f7fb; }
QWidget#leftPanel { border-right: 1px solid #3a3f48; }
QFrame#rightPanelFrame { border-left: 1px solid #3a3f48; }
QSplitter::handle { background-color: #3a3f48; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }
QLabel#titleLabel { color: #111827; }
QLabel#subtitleLabel { color: #4b5563; }
QPushButton { background-color: #ffffff; border: 1px solid #d3d7de; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover { background-color: #f3f5f8; }
QPushButton:pressed { background-color: #e9edf3; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { background-color: #ffffff; border: 1px solid #d3d7de; border-radius: 6px; padding: 4px 6px; color: #1f2937; }
QScrollArea, QListView, QTreeView, QTableView { background-color: #ffffff; border: 1px solid #d3d7de; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; border: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; border: none; }
QScrollBar::handle:vertical { background: rgba(93, 106, 125, 150); min-height: 24px; border-radius: 5px; }
QScrollBar::handle:horizontal { background: rgba(93, 106, 125, 150); min-width: 24px; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: rgba(70, 80, 96, 190); }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: transparent; border: none; width: 0; height: 0; }
QHeaderView::section { background-color: #eef1f6; color: #1f2937; border: 0; padding: 4px 6px; }
QMenu::item:selected { background-color: #e8edf7; }
""",
}


def _qss_path(theme_name: str) -> Path:
    """Return the path to the QSS file for the given theme name."""
    return _THEMES_DIR / f"{theme_name}.qss"


def _load_qss(theme_name: str) -> str:
    """Read and return the QSS stylesheet content for *theme_name*.

    Returns an empty string if the file cannot be read so the application
    can still function without a stylesheet.
    """
    path = _qss_path(theme_name)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Theme file not found: %s", path)
        fallback = _FALLBACK_QSS.get(theme_name, "")
        if fallback:
            logger.info("Using built-in fallback stylesheet for theme: %s", theme_name)
        return fallback
    except OSError as exc:
        logger.warning("Failed to read theme file %s: %s", path, exc)
        fallback = _FALLBACK_QSS.get(theme_name, "")
        if fallback:
            logger.info("Using built-in fallback stylesheet for theme: %s", theme_name)
        return fallback


class ThemeManager:
    """Manages the active application theme (dark / light).

    Usage::

        manager = ThemeManager(app)
        manager.apply_theme(THEME_DARK)
        manager.toggle_theme()          # switches to light
        current = manager.current_theme  # "light"
    """

    def __init__(self, app: QApplication, initial_theme: str = THEME_DARK) -> None:
        self._app = app
        self._current_theme: str = ""
        self.apply_theme(initial_theme)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_theme(self) -> str:
        """Return the name of the currently active theme."""
        return self._current_theme

    def apply_theme(self, theme_name: str) -> None:
        """Load and apply the QSS stylesheet for *theme_name*.

        Parameters
        ----------
        theme_name:
            One of :pydata:`THEME_DARK` or :pydata:`THEME_LIGHT`.
        """
        if theme_name not in (THEME_DARK, THEME_LIGHT):
            logger.warning(
                "Unknown theme '%s'; falling back to '%s'.", theme_name, THEME_DARK
            )
            theme_name = THEME_DARK

        qss = _load_qss(theme_name)
        self._app.setStyleSheet(qss)
        self._current_theme = theme_name
        logger.info("Applied theme: %s", theme_name)

    def toggle_theme(self) -> str:
        """Switch between dark and light themes.

        Returns the name of the newly applied theme.
        """
        new_theme = THEME_LIGHT if self._current_theme == THEME_DARK else THEME_DARK
        self.apply_theme(new_theme)
        return new_theme

    @staticmethod
    def available_themes() -> list[str]:
        """Return a list of available theme names based on files on disk."""
        themes: list[str] = []
        for name in (THEME_DARK, THEME_LIGHT):
            if _qss_path(name).is_file():
                themes.append(name)
        return themes
