"""Streamlit PDF 저장 버튼의 실패 폐쇄 상태 계약 테스트."""

from __future__ import annotations

from copy import deepcopy

from ui.report_export import pdf_export_state


CONFIRMED_REPORT = {
    "status": "confirmed",
    "finalized": True,
    "judge": {"passed": True},
    "governance": {
        "report_status": "confirmed",
        "confirmation_allowed": True,
        "export_allowed": True,
    },
}


def test_pdf_export_is_enabled_only_for_fully_confirmed_report():
    state = pdf_export_state(CONFIRMED_REPORT)

    assert state.enabled is True
    assert "PDF로 저장" in state.help_text


def test_pdf_export_is_disabled_when_any_hard_stop_contract_field_fails():
    mutations = (
        ("status", "pending_manual_review"),
        ("finalized", False),
        ("judge.passed", False),
        ("governance.report_status", "pending_manual_review"),
        ("governance.confirmation_allowed", False),
        ("governance.export_allowed", False),
    )

    for path, value in mutations:
        report = deepcopy(CONFIRMED_REPORT)
        if "." in path:
            parent, child = path.split(".", 1)
            report[parent][child] = value
        else:
            report[path] = value

        state = pdf_export_state(report)
        assert state.enabled is False, path
        assert "저장할 수 없습니다" in state.help_text


def test_pdf_export_is_disabled_for_missing_or_malformed_report():
    for report in (None, {}, [], {"governance": None}):
        assert pdf_export_state(report).enabled is False
