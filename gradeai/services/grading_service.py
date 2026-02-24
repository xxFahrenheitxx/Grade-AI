"""Grading orchestration service."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from gradeai.models.annotation import Annotation
from gradeai.models.exam_paper_template import ExamPaperTemplate, TemplateQuestion
from gradeai.models.grading_report import Criterion, GradingReport, QuestionScore
from gradeai.services.ai_client import AIClient, GradingResponse
from gradeai.services.document_parser import build_grading_context, extract_content_blocks

logger = logging.getLogger(__name__)


class GradingService:
    """Orchestrates the AI grading pipeline."""

    def __init__(self, api_key: str, provider: str = "anthropic", model: str = "claude-sonnet-4-6") -> None:
        self.ai_client = AIClient(api_key=api_key, provider=provider, model=model)
        self.provider = provider
        self.model = model

    def grade_exam(
        self,
        exam_path: Path,
        solution_paths: list[Path],
        rule_paths: list[Path],
        prompts_dir: Path,
        existing_report: Optional[GradingReport] = None,
        point_maximums: Optional[dict[str, float]] = None,
        exam_paper_path: Optional[Path] = None,
    ) -> GradingReport:
        """Run the full AI grading pipeline for a single exam.

        Args:
            exam_path: Path to the exam file.
            solution_paths: Paths to solution/answer key files.
            rule_paths: Paths to grading rule files.
            prompts_dir: Directory containing system prompt files.
            existing_report: If provided, update this report rather than creating new.
            point_maximums: Previously set point maximums per question title.
            exam_paper_path: Optional path to the official exam paper.

        Returns:
            A GradingReport with questions, criteria, scores, and annotations.
        """
        # Load system prompt
        system_prompt = self._load_prompt(prompts_dir, "grading_system_prompt.md")

        # Build multi-modal content
        content_blocks = build_grading_context(
            exam_path, solution_paths, rule_paths, exam_paper_path=exam_paper_path,
        )

        # Call AI
        logger.info("Calling AI for grading: %s", exam_path.name)
        response = self.ai_client.grade_exam(system_prompt, content_blocks)

        # Convert response to GradingReport
        report = self._response_to_report(response, exam_path, point_maximums)

        return report

    def detect_questions(
        self,
        exam_path: Path,
        prompts_dir: Path,
    ) -> list[QuestionScore]:
        """Detect questions and answers in an exam document.

        Returns a list of QuestionScore objects with titles and numbers
        (no grading, just detection).
        """
        system_prompt = self._load_prompt(prompts_dir, "question_detection_prompt.md")
        content_blocks = extract_content_blocks(exam_path)

        response = self.ai_client.detect_questions(system_prompt, content_blocks)

        questions = []
        for q in response.questions:
            questions.append(QuestionScore(
                question_id=str(uuid.uuid4()),
                question_title=q.question_title,
                question_number=q.question_number,
                points_possible=q.points_possible,
            ))

        return questions

    def analyze_exam_paper(
        self,
        exam_paper_path: Path,
        prompts_dir: Path,
    ) -> ExamPaperTemplate:
        """Analyze a blank exam paper and extract a question template.

        Returns an ExamPaperTemplate with questions, points, and full question text.
        """
        system_prompt = self._load_prompt(prompts_dir, "exam_paper_analysis_prompt.md")
        content_blocks = extract_content_blocks(exam_paper_path)

        response = self.ai_client.analyze_exam_paper(system_prompt, content_blocks)

        questions = []
        for q in response.questions:
            questions.append(TemplateQuestion(
                question_id=str(uuid.uuid4()),
                question_title=q.question_title,
                question_number=q.question_number,
                points_possible=q.points_possible,
                question_text=q.question_text,
            ))

        return ExamPaperTemplate(
            exam_paper_path=exam_paper_path.name,
            questions=questions,
            total_points=response.total_points,
            analyzed_at=datetime.now(),
            ai_model_used=f"{self.provider}:{self.model}",
        )

    def match_exam_to_paper(
        self,
        exam_path: Path,
        available_templates: list[ExamPaperTemplate],
        prompts_dir: Path,
    ) -> Optional[str]:
        """Use AI to match a student exam to the best matching exam paper template.

        Returns the exam_paper_path of the best matching template, or None.
        """
        if not available_templates:
            return None

        system_prompt = self._load_prompt(prompts_dir, "exam_matching_prompt.md")

        # Build content: student exam + summaries of each template
        content_blocks: list[dict[str, object]] = []
        content_blocks.append({"type": "text", "text": "## Student Exam\n"})
        content_blocks.extend(extract_content_blocks(exam_path))

        content_blocks.append({"type": "text", "text": "\n\n## Available Exam Paper Templates\n"})
        for i, template in enumerate(available_templates):
            summary = f"\n### Template {i}: {template.exam_paper_path}\n"
            summary += f"Questions: {len(template.questions)}\n"
            for q in template.questions:
                pts = f" ({q.points_possible} pts)" if q.points_possible else ""
                summary += f"- Q{q.question_number}: {q.question_title}{pts}\n"
                if q.question_text:
                    summary += f"  Text: {q.question_text[:300]}\n"
            content_blocks.append({"type": "text", "text": summary})

        response = self.ai_client.match_exam_to_paper(system_prompt, content_blocks)

        if (
            response.matched_template_index is not None
            and 0 <= response.matched_template_index < len(available_templates)
            and response.confidence >= 0.6
        ):
            return available_templates[response.matched_template_index].exam_paper_path
        return None

    def calculate_grade(
        self,
        report: GradingReport,
        rule_paths: list[Path],
        prompts_dir: Path,
    ) -> str:
        """Calculate grade from grading report + rules using dedicated AI prompt."""
        system_prompt = self._load_prompt(prompts_dir, "grade_calculation_prompt.md")

        report_payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        total_awarded = report.total_points_awarded
        total_possible = report.total_points_possible
        percentage = report.percentage
        points_summary_lines = []
        for q in report.questions:
            awarded = f"{q.points_awarded:.2f}"
            possible = "?" if q.points_possible is None else f"{q.points_possible:.2f}"
            points_summary_lines.append(
                f"- Q{q.question_number} ({q.question_title}): {awarded} / {possible}"
            )

        points_summary_block = (
            "Computed points summary (from report):\n"
            f"- Total awarded: {total_awarded:.2f}\n"
            f"- Total possible: {'?' if total_possible is None else f'{total_possible:.2f}'}\n"
            f"- Percentage: {'?' if percentage is None else f'{percentage:.2f}%'}\n"
            "- Per question:\n"
            + ("\n".join(points_summary_lines) if points_summary_lines else "- [No questions]")
        )
        content_blocks: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    "Grading report JSON:\n"
                    f"{report_payload}"
                ),
            },
            {
                "type": "text",
                "text": points_summary_block,
            },
        ]

        for rule_path in rule_paths:
            try:
                rule_blocks = extract_content_blocks(rule_path)
            except Exception:
                logger.warning("Failed to extract rule file: %s", rule_path, exc_info=True)
                continue
            content_blocks.append(
                {
                    "type": "text",
                    "text": f"Rule file: {rule_path.name}",
                }
            )
            content_blocks.extend(rule_blocks)

        return self.ai_client.calculate_grade(system_prompt, content_blocks)

    def _response_to_report(
        self,
        response: GradingResponse,
        exam_path: Path,
        point_maximums: Optional[dict[str, float]] = None,
    ) -> GradingReport:
        """Convert an AI GradingResponse to a GradingReport model."""
        point_maximums = point_maximums or {}

        questions = []
        for q_resp in response.questions:
            criteria = []
            for c_resp in q_resp.criteria:
                criteria.append(Criterion(
                    id=str(uuid.uuid4()),
                    description=c_resp.description,
                    points_awarded=c_resp.points_awarded,
                    feedback=c_resp.feedback,
                ))

            justification_parts: list[str] = []
            for criterion in criteria:
                reason = criterion.feedback.strip() or criterion.description.strip()
                if reason:
                    justification_parts.append(f"{criterion.points_awarded:+.2f} pts: {reason}")

            # Use AI-detected max points, or fallback to stored maximums
            points_possible = q_resp.points_possible
            manually_set = False
            if points_possible is None and q_resp.question_title in point_maximums:
                points_possible = point_maximums[q_resp.question_title]
                manually_set = True

            questions.append(QuestionScore(
                question_id=str(uuid.uuid4()),
                question_title=q_resp.question_title,
                question_number=q_resp.question_number,
                criteria=criteria,
                justification=" | ".join(justification_parts),
                points_possible=points_possible,
                manually_set_max=manually_set,
            ))

        annotations = []
        first_anchor_by_question: dict[int, object] = {}
        for a_resp in response.annotations:
            first_anchor_by_question.setdefault(a_resp.question_number, a_resp)

        for idx, q in enumerate(questions):
            anchor = first_anchor_by_question.get(q.question_number)
            if anchor is not None:
                page = max(0, int(anchor.page))
                y = max(0.02, min(anchor.y, 0.95))
            else:
                page = 0
                y = min(0.90, 0.08 + idx * 0.08)

            x = 0.72
            width = 0.25
            height = 0.035

            reason_chunks: list[str] = []
            for criterion in q.criteria:
                reason = criterion.feedback.strip() or criterion.description.strip()
                if not reason:
                    continue
                reason_chunks.append(f"{criterion.points_awarded:+.2f} pts: {reason}")
                if len(reason_chunks) >= 3:
                    break
            if not reason_chunks:
                reason_chunks.append(f"{q.points_awarded:+.2f} pts au total")

            annotation_text = " | ".join(reason_chunks)

            annotations.append(Annotation(
                id=str(uuid.uuid4()),
                page=page,
                x=x,
                y=y,
                width=width,
                height=height,
                text=annotation_text,
                annotation_type="comment",
                source="ai",
                question_id=q.question_id,
                color="#C62828",
            ))

        rel_path = exam_path.name  # Will be set properly by caller
        report = GradingReport(
            id=str(uuid.uuid4()),
            exam_file_path=rel_path,
            student_name=response.student_name,
            questions=questions,
            annotations=annotations,
            graded_at=datetime.now(),
            graded_by="ai",
            ai_model_used=f"{self.provider}:{self.model}",
        )

        return report

    def _load_prompt(self, prompts_dir: Path, filename: str) -> str:
        """Load a system prompt from file."""
        prompt_path = prompts_dir / filename
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # Fallback to built-in prompts
        builtin_path = Path(__file__).parent.parent / "prompts" / filename
        if builtin_path.exists():
            return builtin_path.read_text(encoding="utf-8")

        raise FileNotFoundError(f"System prompt not found: {filename}")

    @staticmethod
    def _annotation_color(annotation_type: str) -> str:
        """Return a color for an annotation type."""
        colors = {
            "highlight": "#2E7D32",
            "comment": "#C62828",
            "correction": "#F14C4C",
            "checkmark": "#89D185",
            "cross": "#F14C4C",
        }
        return colors.get(annotation_type, "#C62828")
