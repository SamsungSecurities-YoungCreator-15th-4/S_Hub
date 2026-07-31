"""Streamlit 리포트 PDF 저장 버튼의 실패 폐쇄 상태 계약."""

from __future__ import annotations

from dataclasses import dataclass

from app.nodes.assemble_report import report_is_exportable


@dataclass(frozen=True)
class PDFExportState:
    """리포트 확정 상태에서 파생한 PDF 저장 UI 상태."""

    enabled: bool
    help_text: str


def pdf_export_state(report: object) -> PDFExportState:
    """확정·Judge 통과 계약을 모두 만족할 때만 PDF 저장을 허용한다."""
    if report_is_exportable(report):
        return PDFExportState(
            enabled=True,
            help_text="브라우저 인쇄 대화상자에서 PDF로 저장할 수 있습니다.",
        )
    return PDFExportState(
        enabled=False,
        help_text="Judge 미통과 또는 수동검토 대기 리포트는 PDF로 저장할 수 없습니다.",
    )
