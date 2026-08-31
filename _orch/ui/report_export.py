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
    # 판정 결과로 막힌 것과 상태를 읽지 못한 것을 구분한다. 둘 다 비활성이지만
    # 원인이 다르다 — 형식이 깨진 리포트에 "Judge 미통과"라고 적으면 사용자는
    # 있지도 않은 판정 결과를 찾게 되고, 실제 원인(상태 유실)은 가려진다.
    if not _report_status_is_readable(report):
        return PDFExportState(
            enabled=False,
            help_text="리포트 상태를 확인할 수 없어 PDF 저장을 비활성화했습니다.",
        )
    return PDFExportState(
        enabled=False,
        help_text="Judge 미통과 또는 수동검토 대기 리포트는 PDF로 저장할 수 없습니다.",
    )


def _report_status_is_readable(report: object) -> bool:
    """리포트가 판정 상태를 말할 수 있는 형태인가.

    `status`가 비어 있으면 통과·차단 어느 쪽으로도 해석할 수 없다. 실패 폐쇄는
    `report_is_exportable`이 이미 담당하므로, 여기서는 안내문 분기만 정한다.
    """
    if not isinstance(report, dict):
        return False
    status = report.get("status")
    return isinstance(status, str) and bool(status.strip())
