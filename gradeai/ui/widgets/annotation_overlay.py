"""Transparent overlay widget for displaying annotations on documents."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from gradeai.models.annotation import Annotation


class AnnotationItem(QGraphicsRectItem):
    """A single annotation displayed on a document page."""

    def __init__(
        self,
        annotation: Annotation,
        page_width: float,
        page_height: float,
        page_y_offset: float,
        parent=None,
    ) -> None:
        self.annotation = annotation

        # Convert normalized coordinates to pixel coordinates
        x = annotation.x * page_width
        y = annotation.y * page_height + page_y_offset
        w = max(annotation.width * page_width, 20)
        h = max(annotation.height * page_height, 16)

        super().__init__(0, 0, w, h, parent)
        self.setPos(x, y)

        # Keep the item selectable while avoiding big overlays.
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setPen(QPen(Qt.PenStyle.NoPen))

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip(annotation.text)

        self._draw_annotation(annotation, w)

    def _draw_annotation(self, annotation: Annotation, width: float) -> None:
        """Draw handwritten-style annotation text for readability."""
        color = QColor(annotation.color)
        text_item = QGraphicsTextItem(annotation.text or "", self)
        font = QFont("Comic Sans MS", 10, QFont.Weight.Medium)
        font.setStyleHint(QFont.StyleHint.Cursive)
        text_item.setFont(font)
        text_item.setDefaultTextColor(color)
        text_item.setTextWidth(max(120.0, width - 4.0))
        text_item.setPos(2, 1)

    def hoverEnterEvent(self, event) -> None:
        for item in self.childItems():
            if isinstance(item, QGraphicsTextItem):
                hover_color = QColor(self.annotation.color)
                hover_color = hover_color.lighter(115)
                item.setDefaultTextColor(hover_color)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        for item in self.childItems():
            if isinstance(item, QGraphicsTextItem):
                item.setDefaultTextColor(QColor(self.annotation.color))
        super().hoverLeaveEvent(event)


class AnnotationEditDialog(QDialog):
    """Dialog for creating or editing an annotation."""

    def __init__(self, annotation: Optional[Annotation] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Annotation" if annotation else "New Annotation")
        self.setMinimumWidth(400)

        self._annotation = annotation
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Annotation Text:"))
        self._text_edit = QPlainTextEdit()
        self._text_edit.setMaximumHeight(100)
        if self._annotation:
            self._text_edit.setPlainText(self._annotation.text)
        layout.addWidget(self._text_edit)

        layout.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["comment", "highlight", "correction", "checkmark", "cross"])
        if self._annotation:
            idx = self._type_combo.findText(self._annotation.annotation_type)
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)
        layout.addWidget(self._type_combo)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def text(self) -> str:
        return self._text_edit.toPlainText()

    @property
    def annotation_type(self) -> str:
        return self._type_combo.currentText()


class AnnotationOverlay:
    """Manages annotation items on a QGraphicsScene.

    This is not a widget itself but a controller that adds/removes
    AnnotationItem objects to/from a QGraphicsScene (typically owned
    by a PDFViewer or ImageViewer).
    """

    annotation_edited = None  # Set by parent as callback
    annotation_deleted = None  # Set by parent as callback
    annotation_added = None  # Set by parent as callback

    def __init__(self, scene: QGraphicsScene) -> None:
        self._scene = scene
        self._items: dict[str, AnnotationItem] = {}  # annotation.id -> item
        self._page_dimensions: list[tuple[float, float, float]] = []  # (width, height, y_offset)

    def set_page_dimensions(self, dimensions: list[tuple[float, float, float]]) -> None:
        """Set page dimensions for coordinate mapping.

        Each tuple: (page_width_px, page_height_px, page_y_offset_px)
        """
        self._page_dimensions = dimensions

    def load_annotations(self, annotations: list[Annotation]) -> None:
        """Display a list of annotations on the scene."""
        self.clear()
        for annotation in annotations:
            self._add_item(annotation)

    def add_annotation(self, annotation: Annotation) -> None:
        """Add a single annotation to the scene."""
        self._add_item(annotation)

    def remove_annotation(self, annotation_id: str) -> None:
        """Remove an annotation from the scene."""
        item = self._items.pop(annotation_id, None)
        if item:
            self._scene.removeItem(item)

    def update_annotation(self, annotation: Annotation) -> None:
        """Update an existing annotation."""
        self.remove_annotation(annotation.id)
        self._add_item(annotation)

    def clear(self) -> None:
        """Remove all annotation items."""
        for item in self._items.values():
            self._scene.removeItem(item)
        self._items.clear()

    def _add_item(self, annotation: Annotation) -> None:
        """Create and add an AnnotationItem to the scene."""
        if annotation.page < len(self._page_dimensions):
            pw, ph, py = self._page_dimensions[annotation.page]
        else:
            # Fallback dimensions
            pw, ph, py = 800, 1100, 0

        item = AnnotationItem(annotation, pw, ph, py)
        self._scene.addItem(item)
        self._items[annotation.id] = item

    def get_annotation_at(self, scene_pos: QPointF) -> Optional[Annotation]:
        """Find which annotation (if any) is at the given scene position."""
        for ann_id, item in self._items.items():
            if item.contains(item.mapFromScene(scene_pos)):
                return item.annotation
        return None
