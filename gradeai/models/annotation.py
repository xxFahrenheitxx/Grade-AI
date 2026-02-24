"""Annotation data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Annotation:
    """An annotation overlaid on an exam document.

    Coordinates are normalized (0.0 to 1.0) relative to page dimensions,
    making them zoom-independent.
    """

    page: int
    x: float
    y: float
    text: str
    annotation_type: str = "comment"  # "highlight", "comment", "correction", "checkmark", "cross"
    source: str = "manual"  # "ai" or "manual"
    color: str = "#FFD700"
    width: float = 0.0
    height: float = 0.0
    question_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "text": self.text,
            "color": self.color,
            "annotation_type": self.annotation_type,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "question_id": self.question_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Annotation:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            page=data["page"],
            x=data["x"],
            y=data["y"],
            width=data.get("width", 0.0),
            height=data.get("height", 0.0),
            text=data["text"],
            color=data.get("color", "#FFD700"),
            annotation_type=data.get("annotation_type", "comment"),
            source=data.get("source", "manual"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            question_id=data.get("question_id"),
        )
