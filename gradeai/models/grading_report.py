"""Grading report data models."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from gradeai.models.annotation import Annotation


@dataclass
class Criterion:
    """A single evaluation criterion within a question."""

    description: str
    points_awarded: float
    feedback: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "points_awarded": self.points_awarded,
            "feedback": self.feedback,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Criterion:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            description=data["description"],
            points_awarded=data["points_awarded"],
            feedback=data.get("feedback", ""),
        )


@dataclass
class QuestionScore:
    """Score breakdown for a single exam question."""

    question_title: str
    question_number: int
    criteria: list[Criterion] = field(default_factory=list)
    justification: str = ""
    points_awarded_override: Optional[float] = None
    points_possible: Optional[float] = None
    manually_set_max: bool = False
    question_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def points_awarded(self) -> float:
        """Total points = sum of all criteria points."""
        if self.points_awarded_override is not None:
            return self.points_awarded_override
        return sum(c.points_awarded for c in self.criteria)

    @property
    def is_coherent(self) -> bool:
        """Check if awarded points are coherent with max points."""
        if self.points_possible is None:
            return True
        return self.points_awarded <= self.points_possible + 0.001

    @property
    def has_max_points(self) -> bool:
        return self.points_possible is not None

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question_title": self.question_title,
            "question_number": self.question_number,
            "justification": self.justification,
            "points_awarded_override": self.points_awarded_override,
            "points_possible": self.points_possible,
            "manually_set_max": self.manually_set_max,
            "criteria": [c.to_dict() for c in self.criteria],
        }

    @classmethod
    def from_dict(cls, data: dict) -> QuestionScore:
        return cls(
            question_id=data.get("question_id", str(uuid.uuid4())),
            question_title=data["question_title"],
            question_number=data["question_number"],
            justification=data.get("justification", ""),
            points_awarded_override=data.get("points_awarded_override"),
            points_possible=data.get("points_possible"),
            manually_set_max=data.get("manually_set_max", False),
            criteria=[Criterion.from_dict(c) for c in data.get("criteria", [])],
        )


@dataclass
class GradingReport:
    """Complete grading report for a single exam file."""

    exam_file_path: str  # Relative path within project (e.g., "Exams/StudentA/exam.pdf")
    questions: list[QuestionScore] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    student_name: Optional[str] = None
    ai_grade: Optional[str] = None
    graded_at: Optional[datetime] = None
    graded_by: str = "manual"  # "ai" or "manual"
    ai_model_used: Optional[str] = None
    associated_exam_paper: Optional[str] = None  # Relative path to exam paper
    associated_solution: Optional[str] = None     # Relative path to solution
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def total_points_awarded(self) -> float:
        return sum(q.points_awarded for q in self.questions)

    @property
    def total_points_possible(self) -> Optional[float]:
        """Total max points, or None if any question has no max defined."""
        if not self.questions:
            return None
        if any(q.points_possible is None for q in self.questions):
            return None
        return sum(q.points_possible for q in self.questions)

    @property
    def can_compute_grade(self) -> bool:
        return self.total_points_possible is not None and self.total_points_possible > 0

    @property
    def percentage(self) -> Optional[float]:
        if not self.can_compute_grade:
            return None
        return (self.total_points_awarded / self.total_points_possible) * 100

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exam_file_path": self.exam_file_path,
            "student_name": self.student_name,
            "ai_grade": self.ai_grade,
            "graded_at": self.graded_at.isoformat() if self.graded_at else None,
            "graded_by": self.graded_by,
            "ai_model_used": self.ai_model_used,
            "associated_exam_paper": self.associated_exam_paper,
            "associated_solution": self.associated_solution,
            "questions": [q.to_dict() for q in self.questions],
            "annotations": [a.to_dict() for a in self.annotations],
        }

    @classmethod
    def from_dict(cls, data: dict) -> GradingReport:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            exam_file_path=data["exam_file_path"],
            student_name=data.get("student_name"),
            ai_grade=data.get("ai_grade"),
            graded_at=datetime.fromisoformat(data["graded_at"]) if data.get("graded_at") else None,
            graded_by=data.get("graded_by", "manual"),
            ai_model_used=data.get("ai_model_used"),
            associated_exam_paper=data.get("associated_exam_paper"),
            associated_solution=data.get("associated_solution"),
            questions=[QuestionScore.from_dict(q) for q in data.get("questions", [])],
            annotations=[Annotation.from_dict(a) for a in data.get("annotations", [])],
        )

    def save(self, path: Path) -> None:
        """Save report to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> GradingReport:
        """Load report from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
