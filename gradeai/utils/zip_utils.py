"""ZIP utilities for .grd project files."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path


def extract_grd(grd_path: Path) -> Path:
    """Extract a .grd ZIP archive to a temporary working directory.

    Returns the path to the extracted directory.
    """
    working_dir = Path(tempfile.mkdtemp(prefix="gradeai_"))
    with zipfile.ZipFile(grd_path, "r") as zf:
        zf.extractall(working_dir)
    return working_dir


def pack_grd(working_dir: Path, grd_path: Path) -> None:
    """Pack a working directory into a .grd ZIP archive.

    Overwrites the target file if it already exists.
    """
    # Write to a temp file first, then move (atomic-ish save)
    tmp_path = grd_path.with_suffix(".grd.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in working_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(working_dir).as_posix()
                    zf.write(file_path, arcname)
        # Replace original
        if grd_path.exists():
            grd_path.unlink()
        tmp_path.rename(grd_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def cleanup_working_dir(working_dir: Path) -> None:
    """Remove a temporary working directory."""
    if working_dir.exists() and str(working_dir).find("gradeai_") != -1:
        shutil.rmtree(working_dir, ignore_errors=True)
