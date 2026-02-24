"""Exam paper template data models."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TemplateQuestion:
    """A question extracted from a blank exam paper."""

    question_title: str
    question_number: int
    points_possible: Optional[float] = None
    question_text: str = ""
    question_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question_title": self.question_title,
            "question_number": self.question_number,
            "points_possible": self.points_possible,
            "question_text": self.question_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TemplateQuestion:
        return cls(
            question_id=data.get("question_id", str(uuid.uuid4())),
            question_title=data["question_title"],
            question_number=data["question_number"],
            points_possible=data.get("points_possible"),
            question_text=data.get("question_text", ""),
        )


@dataclass
class ExamPaperTemplate:
    """Cached analysis of a blank exam paper."""

    exam_paper_path: str  # Relative path within project, e.g. "Exam Papers/midterm.pdf"
    questions: list[TemplateQuestion] = field(default_factory=list)
    total_points: Optional[float] = None
    analyzed_at: Optional[datetime] = None
    ai_model_used: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exam_paper_path": self.exam_paper_path,
            "questions": [q.to_dict() for q in self.questions],
            "total_points": self.total_points,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "ai_model_used": self.ai_model_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExamPaperTemplate:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            exam_paper_path=data["exam_paper_path"],
            questions=[TemplateQuestion.from_dict(q) for q in data.get("questions", [])],
            total_points=data.get("total_points"),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]) if data.get("analyzed_at") else None,
            ai_model_used=data.get("ai_model_used"),
        )

    def save(self, path: Path) -> None:
        """Save template to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ExamPaperTemplate:
        """Load template from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
