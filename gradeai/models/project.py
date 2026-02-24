"""Project data model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from gradeai.constants import (
    EXAM_PAPERS_DIR,
    EXAMS_DIR,
    GRADING_REPORTS_DIR,
    PROJECT_META_FILE,
    PROMPTS_DIR,
    RULES_DIR,
    SOLUTIONS_DIR,
)


@dataclass
class ProjectSettings:
    """Per-project settings that persist in project.json."""

    selected_solutions: list[str] = field(default_factory=list)
    selected_rules: list[str] = field(default_factory=list)
    point_maximums: dict[str, float] = field(default_factory=dict)
    grading_scale: dict[str, object] = field(default_factory=lambda: {
        "type": "percentage",
        "thresholds": {"A": 90, "B": 80, "C": 70, "D": 60, "F": 0},
    })

    def to_dict(self) -> dict:
        return {
            "selected_solutions": self.selected_solutions,
            "selected_rules": self.selected_rules,
            "point_maximums": self.point_maximums,
            "grading_scale": self.grading_scale,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectSettings:
        return cls(
            selected_solutions=data.get("selected_solutions", []),
            selected_rules=data.get("selected_rules", []),
            point_maximums=data.get("point_maximums", {}),
            grading_scale=data.get("grading_scale", {
                "type": "percentage",
                "thresholds": {"A": 90, "B": 80, "C": 70, "D": 60, "F": 0},
            }),
        )


@dataclass
class GradeProject:
    """Represents a Grade AI project."""

    title: str
    working_dir: Path
    grd_file_path: Optional[Path] = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    settings: ProjectSettings = field(default_factory=ProjectSettings)

    @property
    def exams_dir(self) -> Path:
        return self.working_dir / EXAMS_DIR

    @property
    def solutions_dir(self) -> Path:
        return self.working_dir / SOLUTIONS_DIR

    @property
    def rules_dir(self) -> Path:
        return self.working_dir / RULES_DIR

    @property
    def grading_reports_dir(self) -> Path:
        return self.working_dir / GRADING_REPORTS_DIR

    @property
    def exam_papers_dir(self) -> Path:
        return self.working_dir / EXAM_PAPERS_DIR

    @property
    def prompts_dir(self) -> Path:
        return self.working_dir / PROMPTS_DIR

    @property
    def meta_file(self) -> Path:
        return self.working_dir / PROJECT_META_FILE

    def create_directories(self) -> None:
        """Create all project subdirectories."""
        for d in [self.exams_dir, self.solutions_dir, self.rules_dir,
                  self.exam_papers_dir, self.grading_reports_dir, self.prompts_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def mark_modified(self) -> None:
        self.modified_at = datetime.now()

    def save_metadata(self) -> None:
        """Save project metadata to project.json."""
        data = {
            "version": "1.0",
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "settings": self.settings.to_dict(),
        }
        self.meta_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load_metadata(cls, working_dir: Path) -> GradeProject:
        """Load project from an extracted working directory."""
        meta_file = working_dir / PROJECT_META_FILE
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        return cls(
            title=data["title"],
            working_dir=working_dir,
            created_at=datetime.fromisoformat(data["created_at"]),
            modified_at=datetime.fromisoformat(data["modified_at"]),
            settings=ProjectSettings.from_dict(data.get("settings", {})),
        )
