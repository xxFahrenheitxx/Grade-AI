"""Global auto-hide/fade behavior for application scrollbars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPropertyAnimation, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QAbstractScrollArea,
    QGraphicsOpacityEffect,
    QScrollBar,
    QWidget,
)
from shiboken6 import isValid


@dataclass
class _BarState:
    effect: QGraphicsOpacityEffect
    fade_in: QPropertyAnimation
    fade_out: QPropertyAnimation
    hide_timer: QTimer


class ScrollbarAutoHideManager(QObject):
    """Attach Safari-like fade in/out behavior to all app scrollbars."""

    def __init__(self, app: QApplication, root: QWidget) -> None:
        super().__init__(app)
        self._app = app
        self._root = root
        self._states: dict[QScrollBar, _BarState] = {}
        self._app.installEventFilter(self)
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(800)
        self._scan_timer.timeout.connect(self._scan_for_scroll_areas)
        self._scan_timer.start()
        self._register_widget_tree(root)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register_widget_tree(self, widget: QWidget) -> None:
        if not self._is_alive(widget):
            return
        for area in widget.findChildren(QAbstractScrollArea):
            self._register_area(area)
        for bar in widget.findChildren(QScrollBar):
            self._register_scrollbar(bar)

    @staticmethod
    def _is_alive(obj: object) -> bool:
        try:
            return bool(obj is not None and isValid(obj))
        except RuntimeError:
            return False

    def _scan_for_scroll_areas(self) -> None:
        """Discover scroll areas created dynamically after startup."""
        if not self._is_alive(self._root):
            self._scan_timer.stop()
            return
        self._register_widget_tree(self._root)

    def _register_widget(self, widget: QObject) -> None:
        if not self._is_alive(widget):
            return
        if isinstance(widget, QWidget):
            try:
                widget.installEventFilter(self)
            except RuntimeError:
                return

    def _register_area(self, area: QAbstractScrollArea) -> None:
        if not self._is_alive(area):
            return
        self._register_widget(area)
        try:
            viewport = area.viewport()
        except RuntimeError:
            return
        if viewport is not None:
            self._register_widget(viewport)
        try:
            vbar = area.verticalScrollBar()
            hbar = area.horizontalScrollBar()
        except RuntimeError:
            return
        self._register_scrollbar(vbar)
        self._register_scrollbar(hbar)

    def _register_scrollbar(self, bar: Optional[QScrollBar]) -> None:
        if (
            bar is None
            or not isinstance(bar, QScrollBar)
            or not self._is_alive(bar)
            or bar in self._states
        ):
            return

        effect = QGraphicsOpacityEffect(bar)
        effect.setOpacity(0.0)
        bar.setGraphicsEffect(effect)

        fade_in = QPropertyAnimation(effect, b"opacity", bar)
        fade_in.setDuration(120)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        fade_out = QPropertyAnimation(effect, b"opacity", bar)
        fade_out.setDuration(140)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        hide_timer = QTimer(bar)
        hide_timer.setSingleShot(True)
        hide_timer.setInterval(500)
        hide_timer.timeout.connect(lambda b=bar: self._hide_if_idle(b))

        self._states[bar] = _BarState(
            effect=effect,
            fade_in=fade_in,
            fade_out=fade_out,
            hide_timer=hide_timer,
        )

        self._register_widget(bar)
        bar.valueChanged.connect(lambda _v, b=bar: self._show_temporarily(b))
        bar.rangeChanged.connect(lambda _mn, _mx, b=bar: self._on_range_changed(b))
        bar.destroyed.connect(lambda _=None, b=bar: self._states.pop(b, None))
        self._on_range_changed(bar)

    # ------------------------------------------------------------------
    # Behavior
    # ------------------------------------------------------------------

    def _on_range_changed(self, bar: QScrollBar) -> None:
        if not self._is_alive(bar):
            self._states.pop(bar, None)
            return
        state = self._states.get(bar)
        if not state:
            return
        try:
            maximum = bar.maximum()
        except RuntimeError:
            self._states.pop(bar, None)
            return
        if maximum <= 0:
            state.hide_timer.stop()
            state.fade_in.stop()
            state.fade_out.stop()
            state.effect.setOpacity(0.0)

    def _show_temporarily(self, bar: QScrollBar) -> None:
        if not self._is_alive(bar):
            self._states.pop(bar, None)
            return
        try:
            maximum = bar.maximum()
        except RuntimeError:
            self._states.pop(bar, None)
            return
        if maximum <= 0:
            return
        state = self._states.get(bar)
        if not state:
            return
        state.fade_out.stop()
        state.fade_in.stop()
        state.fade_in.setStartValue(state.effect.opacity())
        state.fade_in.setEndValue(1.0)
        state.fade_in.start()
        state.hide_timer.start()

    def _hide_if_idle(self, bar: QScrollBar) -> None:
        if not self._is_alive(bar):
            self._states.pop(bar, None)
            return
        state = self._states.get(bar)
        if not state:
            return
        if bar.underMouse():
            state.hide_timer.start()
            return
        state.fade_in.stop()
        state.fade_out.stop()
        state.fade_out.setStartValue(state.effect.opacity())
        state.fade_out.setEndValue(0.0)
        state.fade_out.start()

    def _show_area_scrollbars(self, area: QAbstractScrollArea) -> None:
        if not self._is_alive(area):
            return
        try:
            self._show_temporarily(area.verticalScrollBar())
            self._show_temporarily(area.horizontalScrollBar())
        except RuntimeError:
            return

    @staticmethod
    def _parent_scroll_area(obj: QObject) -> Optional[QAbstractScrollArea]:
        parent = obj
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                return parent
            parent = parent.parent()
        return None

    # ------------------------------------------------------------------
    # Event filter
    # ------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        event_type = event.type()

        if event_type == QEvent.Type.Wheel:
            if not self._is_alive(watched):
                return super().eventFilter(watched, event)
            area = self._parent_scroll_area(watched)
            if area is not None:
                self._show_area_scrollbars(area)

        if isinstance(watched, QScrollBar):
            state = self._states.get(watched)
            if state is not None:
                if event_type in (
                    QEvent.Type.Enter,
                    QEvent.Type.HoverEnter,
                    QEvent.Type.HoverMove,
                    QEvent.Type.MouseMove,
                    QEvent.Type.MouseButtonPress,
                ):
                    self._show_temporarily(watched)
                elif event_type in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                    state.hide_timer.start(120)

        return super().eventFilter(watched, event)
