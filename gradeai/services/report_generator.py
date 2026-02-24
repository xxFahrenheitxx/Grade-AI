"""Exam report generator for synthesis tables."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from gradeai.models.grading_report import GradingReport


@dataclass
class ExamReportRow:
    """A single row in the exam report table."""
    exam_path: str
    student_name: str
    question_scores: dict[str, Optional[float]]  # question_title -> points_awarded
    question_maxes: dict[str, Optional[float]]  # question_title -> points_possible
    total_awarded: float
    total_possible: Optional[float]
    percentage: Optional[float]
    calculated_grade: Optional[str] = None


@dataclass
class ExamReportSummary:
    """Summary statistics for the exam report."""
    question_titles: list[str]
    question_maxes: dict[str, Optional[float]]
    rows: list[ExamReportRow] = field(default_factory=list)

    @property
    def average_percentage(self) -> Optional[float]:
        percentages = [r.percentage for r in self.rows if r.percentage is not None]
        if not percentages:
            return None
        return sum(percentages) / len(percentages)

    @property
    def question_success_rates(self) -> dict[str, Optional[float]]:
        """Percentage of correct answers per question (awarded/possible ratio average)."""
        rates: dict[str, Optional[float]] = {}
        for title in self.question_titles:
            max_pts = self.question_maxes.get(title)
            if max_pts is None or max_pts == 0:
                rates[title] = None
                continue
            scores = []
            for row in self.rows:
                awarded = row.question_scores.get(title)
                if awarded is not None:
                    scores.append(awarded / max_pts * 100)
            rates[title] = sum(scores) / len(scores) if scores else None
        return rates

    @property
    def exam_count(self) -> int:
        return len(self.rows)

    @property
    def graded_count(self) -> int:
        return len([r for r in self.rows if r.total_possible is not None])


class ReportGenerator:
    """Generates synthesis reports from grading data."""

    def generate_report(self, reports: list[GradingReport]) -> ExamReportSummary:
        """Build a synthesis report from all grading reports.

        Args:
            reports: List of GradingReport objects from the project.

        Returns:
            ExamReportSummary with rows and statistics.
        """
        if not reports:
            return ExamReportSummary(question_titles=[], question_maxes={}, rows=[])

        # Collect all unique question titles (ordered by first appearance)
        all_titles: list[str] = []
        all_maxes: dict[str, Optional[float]] = {}

        for report in reports:
            for q in report.questions:
                if q.question_title not in all_titles:
                    all_titles.append(q.question_title)
                if q.points_possible is not None:
                    all_maxes[q.question_title] = q.points_possible

        # Build rows
        rows: list[ExamReportRow] = []
        for report in reports:
            q_scores: dict[str, Optional[float]] = {}
            q_maxes: dict[str, Optional[float]] = {}

            for q in report.questions:
                q_scores[q.question_title] = q.points_awarded
                q_maxes[q.question_title] = q.points_possible

            rows.append(ExamReportRow(
                exam_path=report.exam_file_path,
                student_name=report.student_name or Path(report.exam_file_path).stem,
                question_scores=q_scores,
                question_maxes=q_maxes,
                total_awarded=report.total_points_awarded,
                total_possible=report.total_points_possible,
                percentage=report.percentage,
                calculated_grade=report.ai_grade,
            ))

        return ExamReportSummary(
            question_titles=all_titles,
            question_maxes=all_maxes,
            rows=rows,
        )

    def export_csv(self, summary: ExamReportSummary) -> str:
        """Export the report summary as a CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        header = ["Student", "Exam File"]
        for title in summary.question_titles:
            max_pts = summary.question_maxes.get(title)
            if max_pts is not None:
                header.append(f"{title} (/{max_pts})")
            else:
                header.append(title)
        header.extend(["Total", "Max", "Percentage", "Grade"])
        writer.writerow(header)

        # Data rows
        for row in summary.rows:
            data = [row.student_name, row.exam_path]
            for title in summary.question_titles:
                score = row.question_scores.get(title)
                data.append(f"{score:.1f}" if score is not None else "-")
            data.append(f"{row.total_awarded:.1f}")
            data.append(f"{row.total_possible:.1f}" if row.total_possible else "-")
            data.append(f"{row.percentage:.1f}%" if row.percentage else "-")
            data.append(row.calculated_grade or "-")
            writer.writerow(data)

        # Summary row
        summary_row = ["AVERAGE", ""]
        rates = summary.question_success_rates
        for title in summary.question_titles:
            rate = rates.get(title)
            summary_row.append(f"{rate:.1f}%" if rate is not None else "-")
        avg = summary.average_percentage
        summary_row.extend(["", "", f"{avg:.1f}%" if avg is not None else "-", ""])
        writer.writerow(summary_row)

        return output.getvalue()

    def save_csv(self, summary: ExamReportSummary, path: Path) -> None:
        """Save the report as a CSV file."""
        csv_text = self.export_csv(summary)
        path.write_text(csv_text, encoding="utf-8")
