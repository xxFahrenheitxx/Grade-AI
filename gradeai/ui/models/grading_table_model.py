"""Qt table model for exam report synthesis."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from gradeai.services.report_generator import ExamReportSummary


class GradingTableModel(QAbstractTableModel):
    """Table model for the exam report dialog."""

    def __init__(self, summary: ExamReportSummary, parent=None) -> None:
        super().__init__(parent)
        self._summary = summary
        self._headers = self._build_headers()

    def _build_headers(self) -> list[str]:
        headers = ["Student", "Exam"]
        for title in self._summary.question_titles:
            max_pts = self._summary.question_maxes.get(title)
            if max_pts is not None:
                headers.append(f"{title} (/{max_pts:.0f})")
            else:
                headers.append(title)
        headers.extend(["Total", "Max", "%"])
        return headers

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._summary.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section < len(self._headers):
                return self._headers[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = self._summary.rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return row.student_name
            elif col == 1:
                return row.exam_path
            elif col < 2 + len(self._summary.question_titles):
                title = self._summary.question_titles[col - 2]
                score = row.question_scores.get(title)
                return f"{score:.1f}" if score is not None else "-"
            elif col == 2 + len(self._summary.question_titles):
                return f"{row.total_awarded:.1f}"
            elif col == 3 + len(self._summary.question_titles):
                return f"{row.total_possible:.0f}" if row.total_possible else "-"
            elif col == 4 + len(self._summary.question_titles):
                return f"{row.percentage:.1f}%" if row.percentage else "-"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col >= 2:
                return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.BackgroundRole:
            if 2 <= col < 2 + len(self._summary.question_titles):
                title = self._summary.question_titles[col - 2]
                score = row.question_scores.get(title)
                max_pts = row.question_maxes.get(title)
                if score is not None and max_pts and max_pts > 0:
                    ratio = score / max_pts
                    if ratio >= 0.8:
                        return QColor(137, 209, 133, 40)
                    elif ratio >= 0.5:
                        return QColor(204, 167, 0, 40)
                    else:
                        return QColor(241, 76, 76, 40)

        return None
