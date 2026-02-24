"""Exam report synthesis dialog."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPageLayout, QPageSize, QPainter, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QStyle,
    QStyleOptionHeader,
    QVBoxLayout,
)

from gradeai.services.report_generator import ExamReportSummary, ReportGenerator


class _RotatedQuestionHeader(QHeaderView):
    """Horizontal header that rotates question labels by 90 degrees."""

    def __init__(
        self,
        question_start: int,
        question_end: int,
        orientation: Qt.Orientation,
        parent=None,
    ) -> None:
        super().__init__(orientation, parent)
        self._question_start = question_start
        self._question_end = question_end
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

    def _is_question_column(self, logical_index: int) -> bool:
        return self._question_start <= logical_index < self._question_end

    def paintSection(self, painter: QPainter, rect, logicalIndex: int) -> None:  # noqa: N802
        if not self._is_question_column(logicalIndex):
            super().paintSection(painter, rect, logicalIndex)
            return

        option = QStyleOptionHeader()
        self.initStyleOption(option)
        option.rect = rect
        option.section = logicalIndex
        option.text = ""
        self.style().drawControl(QStyle.ControlElement.CE_Header, option, painter, self)

        raw_text = self.model().headerData(  # type: ignore[union-attr]
            logicalIndex,
            self.orientation(),
            Qt.ItemDataRole.DisplayRole,
        )
        if not raw_text:
            return

        # Keep the beginning readable by eliding the tail when vertical space is limited.
        metrics = QFontMetrics(self.font())
        available_length = max(20, rect.height() - 12)
        text = metrics.elidedText(str(raw_text), Qt.TextElideMode.ElideRight, available_length)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.translate(rect.center())
        painter.rotate(-90)
        draw_rect = QRect(
            -rect.height() // 2,
            -rect.width() // 2,
            rect.height(),
            rect.width(),
        )
        painter.drawText(draw_rect, int(Qt.AlignmentFlag.AlignCenter), str(text))
        painter.restore()


class ExamReportDialog(QDialog):
    """Dialog displaying a synthesis table of all graded exams."""

    def __init__(self, summary: ExamReportSummary, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exam Report")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self._summary = summary
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header stats
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel(f"Total Exams: {self._summary.exam_count}"))
        stats_layout.addWidget(QLabel(f"Graded: {self._summary.graded_count}"))
        avg = self._summary.average_percentage
        avg_text = f"{avg:.1f}%" if avg is not None else "N/A"
        avg_label = QLabel(f"Average: {avg_text}")
        avg_label.setObjectName("headerLabel")
        stats_layout.addWidget(avg_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Table
        self._table = QTableWidget()
        self._populate_table()
        layout.addWidget(self._table)

        # Export button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        print_btn = QPushButton("Print...")
        print_btn.clicked.connect(self._print_report)
        btn_layout.addWidget(print_btn)
        export_btn = QPushButton("Export CSV...")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _populate_table(self) -> None:
        titles = self._summary.question_titles
        col_count = 2 + len(titles) + 4  # Student, Exam, questions..., Total, Max, %, Grade
        self._table.setColumnCount(col_count)
        data_alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        question_start = 2
        question_end = 2 + len(titles)
        rotated_header = _RotatedQuestionHeader(
            question_start=question_start,
            question_end=question_end,
            orientation=Qt.Orientation.Horizontal,
            parent=self._table,
        )
        self._table.setHorizontalHeader(rotated_header)

        headers = ["Student", "Exam"]
        for title in titles:
            max_pts = self._summary.question_maxes.get(title)
            if max_pts is not None:
                headers.append(f"{title} ({max_pts:.0f})")
            else:
                headers.append(title)
        headers.extend(["Total", "Max", "%", "Grade"])
        self._table.setHorizontalHeaderLabels(headers)

        # +1 row for question success percentages (displayed at the bottom)
        self._table.setRowCount(len(self._summary.rows) + 1)

        for row_idx, row in enumerate(self._summary.rows):
            self._table.setItem(row_idx, 0, QTableWidgetItem(row.student_name))
            self._table.setItem(row_idx, 1, QTableWidgetItem(
                Path(row.exam_path).name
            ))

            for q_idx, title in enumerate(titles):
                score = row.question_scores.get(title)
                max_pts = row.question_maxes.get(title)
                if score is not None:
                    text = f"{score:.1f}"
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(data_alignment)

                    # Color code
                    if max_pts and max_pts > 0:
                        ratio = score / max_pts
                        if ratio >= 0.8:
                            item.setBackground(QColor(137, 209, 133, 60))
                        elif ratio >= 0.5:
                            item.setBackground(QColor(204, 167, 0, 60))
                        else:
                            item.setBackground(QColor(241, 76, 76, 60))
                else:
                    item = QTableWidgetItem("-")
                    item.setTextAlignment(data_alignment)

                self._table.setItem(row_idx, 2 + q_idx, item)

            # Total
            total_item = QTableWidgetItem(f"{row.total_awarded:.1f}")
            total_item.setTextAlignment(data_alignment)
            self._table.setItem(row_idx, 2 + len(titles), total_item)

            # Max
            max_text = f"{row.total_possible:.0f}" if row.total_possible is not None else "-"
            max_item = QTableWidgetItem(max_text)
            max_item.setTextAlignment(data_alignment)
            self._table.setItem(row_idx, 3 + len(titles), max_item)

            # Percentage
            pct_text = f"{row.percentage:.1f}%" if row.percentage is not None else "-"
            pct_item = QTableWidgetItem(pct_text)
            pct_item.setTextAlignment(data_alignment)
            self._table.setItem(row_idx, 4 + len(titles), pct_item)

            # Calculated Grade (persisted in grading report)
            grade_item = QTableWidgetItem(row.calculated_grade or "-")
            grade_item.setTextAlignment(data_alignment)
            self._table.setItem(row_idx, 5 + len(titles), grade_item)

        # Bottom row: per-question success rates
        rates_row = len(self._summary.rows)
        rates = self._summary.question_success_rates
        label_item = QTableWidgetItem("Success %")
        label_item.setTextAlignment(data_alignment)
        self._table.setItem(rates_row, 0, label_item)
        self._table.setItem(rates_row, 1, QTableWidgetItem(""))
        for q_idx, title in enumerate(titles):
            rate = rates.get(title)
            rate_text = f"{rate:.1f}%" if rate is not None else "-"
            item = QTableWidgetItem(rate_text)
            item.setTextAlignment(data_alignment)
            if rate is not None:
                if rate >= 70:
                    item.setBackground(QColor(137, 209, 133, 60))
                elif rate >= 50:
                    item.setBackground(QColor(204, 167, 0, 60))
                else:
                    item.setBackground(QColor(241, 76, 76, 60))
            self._table.setItem(rates_row, 2 + q_idx, item)
        self._table.setItem(rates_row, 2 + len(titles), QTableWidgetItem(""))
        self._table.setItem(rates_row, 3 + len(titles), QTableWidgetItem(""))
        self._table.setItem(rates_row, 4 + len(titles), QTableWidgetItem(""))
        self._table.setItem(rates_row, 5 + len(titles), QTableWidgetItem(""))

        # Resize
        header = self._table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(2, 2 + len(titles)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self._table.setColumnWidth(i, 44)
        for i in range(2 + len(titles), col_count):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setFixedHeight(170)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "exam_report.csv", "CSV Files (*.csv)"
        )
        if path:
            generator = ReportGenerator()
            generator.save_csv(self._summary, Path(path))

    def _print_report(self) -> None:
        paper_size, ok = QInputDialog.getItem(
            self,
            "Print Report",
            "Paper size:",
            ["A4", "A3"],
            0,
            False,
        )
        if not ok:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        page_id = (
            QPageSize.PageSizeId.A3
            if paper_size == "A3"
            else QPageSize.PageSizeId.A4
        )
        printer.setPageSize(QPageSize(page_id))

        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Exam Report")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        doc = QTextDocument(self)
        doc.setHtml(self._build_print_html())
        doc.print(printer)

    def _build_print_html(self) -> str:
        """Build a printable HTML snapshot of the current exam report."""
        titles = self._summary.question_titles
        rates = self._summary.question_success_rates
        avg = self._summary.average_percentage
        avg_text = f"{avg:.1f}%" if avg is not None else "N/A"

        header_cells = [
            "<th>Student</th>",
            "<th>Exam</th>",
        ]
        for title in titles:
            max_pts = self._summary.question_maxes.get(title)
            if max_pts is not None:
                label = f"{title} ({max_pts:.0f})"
            else:
                label = title
            header_cells.append(f"<th>{html.escape(label)}</th>")
        header_cells.extend(["<th>Total</th>", "<th>Max</th>", "<th>%</th>", "<th>Grade</th>"])

        body_rows: list[str] = []
        for row in self._summary.rows:
            cells = [
                f"<td>{html.escape(row.student_name)}</td>",
                f"<td>{html.escape(Path(row.exam_path).name)}</td>",
            ]
            for title in titles:
                score = row.question_scores.get(title)
                cells.append(f"<td>{'-' if score is None else f'{score:.1f}'}</td>")
            cells.append(f"<td>{row.total_awarded:.1f}</td>")
            cells.append(
                f"<td>{'-' if row.total_possible is None else f'{row.total_possible:.0f}'}</td>"
            )
            cells.append(
                f"<td>{'-' if row.percentage is None else f'{row.percentage:.1f}%'}</td>"
            )
            cells.append(f"<td>{html.escape(row.calculated_grade or '-')}</td>")
            body_rows.append("<tr>" + "".join(cells) + "</tr>")

        success_cells = ["<td><b>Success %</b></td>", "<td></td>"]
        for title in titles:
            rate = rates.get(title)
            success_cells.append(f"<td>{'-' if rate is None else f'{rate:.1f}%'}</td>")
        success_cells.extend(["<td></td>", "<td></td>", "<td></td>", "<td></td>"])
        body_rows.append("<tr>" + "".join(success_cells) + "</tr>")

        return (
            "<html><head><meta charset='utf-8'>"
            "<style>"
            "body { font-family: Arial, sans-serif; font-size: 9pt; }"
            "h2 { margin: 0 0 6px 0; }"
            ".stats { margin: 0 0 10px 0; }"
            "table { border-collapse: collapse; width: 100%; }"
            "th, td { border: 1px solid #777; padding: 4px 6px; text-align: left; }"
            "th { background: #eaeaea; }"
            "</style></head><body>"
            f"<h2>Exam Report</h2>"
            f"<p class='stats'>Total Exams: {self._summary.exam_count} | "
            f"Graded: {self._summary.graded_count} | Average: {avg_text}</p>"
            "<table><thead><tr>"
            + "".join(header_cells)
            + "</tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table></body></html>"
        )
