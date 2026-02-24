"""Project management service."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from gradeai.constants import EXAM_PAPERS_DIR, EXAMS_DIR, GRADING_REPORTS_DIR
from gradeai.models.exam_paper_template import ExamPaperTemplate
from gradeai.models.grading_report import GradingReport
from gradeai.models.project import GradeProject
from gradeai.utils.file_utils import get_grading_report_path, get_template_path
from gradeai.utils.zip_utils import cleanup_working_dir, extract_grd, pack_grd


class ProjectService:
    """Handles creating, opening, saving, and managing projects."""

    def __init__(self) -> None:
        self._current_project: Optional[GradeProject] = None

    @property
    def project(self) -> Optional[GradeProject]:
        return self._current_project

    def create_project(
        self,
        title: str,
        working_dir: Path,
        exam_sources: Optional[list[Path]] = None,
        solution_sources: Optional[list[Path]] = None,
        rule_sources: Optional[list[Path]] = None,
        exam_paper_sources: Optional[list[Path]] = None,
    ) -> GradeProject:
        """Create a new project with the given title and optional initial files."""
        project = GradeProject(title=title, working_dir=working_dir)
        project.create_directories()
        self._copy_default_prompts(project)

        if exam_sources:
            self.import_exams(project, exam_sources)
        if solution_sources:
            self._import_files(project.solutions_dir, solution_sources)
        if rule_sources:
            self._import_files(project.rules_dir, rule_sources)
        if exam_paper_sources:
            self._import_files(project.exam_papers_dir, exam_paper_sources)

        project.save_metadata()
        self._current_project = project
        return project

    def open_grd(self, grd_path: Path) -> GradeProject:
        """Open a .grd project file."""
        working_dir = extract_grd(grd_path)
        project = GradeProject.load_metadata(working_dir)
        project.grd_file_path = grd_path
        # Ensure Exam Papers dir exists (backward compat for older projects)
        project.exam_papers_dir.mkdir(parents=True, exist_ok=True)
        self._current_project = project
        return project

    def save_grd(self, project: GradeProject, grd_path: Optional[Path] = None) -> Path:
        """Save the current project as a .grd file."""
        save_path = grd_path or project.grd_file_path
        if save_path is None:
            raise ValueError("No save path specified and project has no existing .grd path")
        project.mark_modified()
        project.save_metadata()
        pack_grd(project.working_dir, save_path)
        project.grd_file_path = save_path
        return save_path

    def close_project(self, project: GradeProject) -> None:
        """Close a project and clean up temporary files if extracted from .grd."""
        if project.grd_file_path and "gradeai_" in str(project.working_dir):
            cleanup_working_dir(project.working_dir)
        self._current_project = None

    def import_exams(self, project: GradeProject, sources: list[Path]) -> None:
        """Import exam files/folders into the Exams directory and mirror to Grading Reports."""
        self._import_files(project.exams_dir, sources)
        self.mirror_exam_structure(project)
        project.mark_modified()

    def mirror_exam_structure(self, project: GradeProject) -> None:
        """Ensure Grading Reports mirrors the Exams directory structure (folders only)."""
        exams_dir = project.exams_dir
        reports_dir = project.grading_reports_dir
        if not exams_dir.exists():
            return
        for dirpath in exams_dir.rglob("*"):
            if dirpath.is_dir():
                rel = dirpath.relative_to(exams_dir)
                (reports_dir / rel).mkdir(parents=True, exist_ok=True)

    def get_or_create_grading_report(
        self, project: GradeProject, exam_path: Path
    ) -> GradingReport:
        """Get existing grading report for an exam, or create a new empty one."""
        report_path = get_grading_report_path(exam_path, project.working_dir)
        if report_path.exists():
            return GradingReport.load(report_path)

        rel_path = exam_path.relative_to(project.working_dir).as_posix()
        report = GradingReport(exam_file_path=rel_path)
        report.save(report_path)
        return report

    def save_grading_report(self, project: GradeProject, report: GradingReport) -> None:
        """Save a grading report to its corresponding file."""
        exam_path = project.working_dir / report.exam_file_path
        report_path = get_grading_report_path(exam_path, project.working_dir)
        report.save(report_path)
        project.mark_modified()

    def get_all_grading_reports(self, project: GradeProject) -> list[GradingReport]:
        """Load all grading reports in the project."""
        reports = []
        reports_dir = project.grading_reports_dir
        if not reports_dir.exists():
            return reports
        for json_file in reports_dir.rglob("*.json"):
            try:
                reports.append(GradingReport.load(json_file))
            except Exception:
                continue
        return reports

    # ------------------------------------------------------------------
    # Exam paper template management
    # ------------------------------------------------------------------

    def get_template(
        self, project: GradeProject, exam_paper_path: Path
    ) -> Optional[ExamPaperTemplate]:
        """Get cached template for an exam paper, or None if not yet analyzed."""
        template_path = get_template_path(exam_paper_path, project.working_dir)
        if template_path.exists():
            return ExamPaperTemplate.load(template_path)
        return None

    def save_template(
        self, project: GradeProject, template: ExamPaperTemplate, exam_paper_path: Path
    ) -> None:
        """Save an analyzed template to the .templates directory."""
        template_path = get_template_path(exam_paper_path, project.working_dir)
        template.save(template_path)
        project.mark_modified()

    def get_all_templates(self, project: GradeProject) -> list[ExamPaperTemplate]:
        """Load all cached exam paper templates."""
        templates_dir = project.exam_papers_dir / ".templates"
        if not templates_dir.exists():
            return []
        templates = []
        for json_file in templates_dir.rglob("*.json"):
            try:
                templates.append(ExamPaperTemplate.load(json_file))
            except Exception:
                continue
        return templates

    def list_exam_paper_relative_paths(self, project: GradeProject) -> list[str]:
        """List all exam paper files as relative paths (excluding .templates)."""
        if not project.exam_papers_dir.exists():
            return []
        return [
            str(f.relative_to(project.working_dir).as_posix())
            for f in project.exam_papers_dir.rglob("*")
            if f.is_file() and ".templates" not in f.parts
        ]

    def list_solution_relative_paths(self, project: GradeProject) -> list[str]:
        """List all solution files as relative paths."""
        if not project.solutions_dir.exists():
            return []
        return [
            str(f.relative_to(project.working_dir).as_posix())
            for f in project.solutions_dir.rglob("*")
            if f.is_file()
        ]

    # ------------------------------------------------------------------
    # File import helpers
    # ------------------------------------------------------------------

    def _import_files(self, target_dir: Path, sources: list[Path]) -> None:
        """Copy files/folders into a target directory."""
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in sources:
            dest = target_dir / source.name
            if source.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
            elif source.is_file():
                shutil.copy2(source, dest)

    def _copy_default_prompts(self, project: GradeProject) -> None:
        """Copy default system prompts into the project."""
        prompts_src = Path(__file__).parent.parent / "prompts"
        if prompts_src.exists():
            for prompt_file in prompts_src.glob("*.md"):
                dest = project.prompts_dir / prompt_file.name
                if not dest.exists():
                    shutil.copy2(prompt_file, dest)
