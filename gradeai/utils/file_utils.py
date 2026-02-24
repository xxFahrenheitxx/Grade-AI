"""File I/O and type detection utilities."""

from __future__ import annotations

from pathlib import Path

from gradeai.constants import (
    CODE_EXTENSIONS,
    EXAM_PAPERS_DIR,
    EXCEL_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MARKDOWN_EXTENSIONS,
    PDF_EXTENSIONS,
    TEXT_EXTENSIONS,
    WORD_EXTENSIONS,
)


def get_file_category(path: Path) -> str:
    """Return the viewer category for a file based on its extension.

    Returns one of: "pdf", "image", "word", "excel", "code", "markdown", "text", "unknown"
    """
    ext = path.suffix.lower()
    if ext in PDF_EXTENSIONS:
        return "pdf"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in WORD_EXTENSIONS:
        return "word"
    if ext in EXCEL_EXTENSIONS:
        return "excel"
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in MARKDOWN_EXTENSIONS:
        return "markdown"
    if ext in TEXT_EXTENSIONS:
        return "text"
    return "unknown"


def get_relative_path(file_path: Path, project_dir: Path) -> str:
    """Get the relative path of a file within a project."""
    try:
        return file_path.relative_to(project_dir).as_posix()
    except ValueError:
        return file_path.name


def is_exam_file(file_path: Path, project_dir: Path) -> bool:
    """Check if a file is inside the Exams directory."""
    try:
        rel = file_path.relative_to(project_dir)
        parts = rel.parts
        return len(parts) > 0 and parts[0] == "Exams"
    except ValueError:
        return False


def get_grading_report_path(exam_path: Path, project_dir: Path) -> Path:
    """Get the corresponding grading report path for an exam file.

    Maps Exams/StudentA/exam.pdf -> Grading Reports/StudentA/exam.json
    """
    rel = exam_path.relative_to(project_dir / "Exams")
    return project_dir / "Grading Reports" / rel.with_suffix(".json")


def is_exam_paper_file(file_path: Path, project_dir: Path) -> bool:
    """Check if a file is inside the Exam Papers directory (excluding .templates)."""
    try:
        rel = file_path.relative_to(project_dir)
        parts = rel.parts
        return len(parts) > 0 and parts[0] == EXAM_PAPERS_DIR and ".templates" not in parts
    except ValueError:
        return False


def get_template_path(exam_paper_path: Path, project_dir: Path) -> Path:
    """Get the template JSON path for an exam paper file.

    Maps Exam Papers/X.pdf -> Exam Papers/.templates/X.json
    """
    rel = exam_paper_path.relative_to(project_dir / EXAM_PAPERS_DIR)
    return project_dir / EXAM_PAPERS_DIR / ".templates" / rel.with_suffix(".json")


def copy_tree(src: Path, dst: Path) -> None:
    """Recursively copy a directory tree, preserving structure."""
    import shutil
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    elif src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            copy_tree(item, dst / item.name)
