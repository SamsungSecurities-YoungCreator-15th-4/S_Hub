"""Streamlit PDF 저장 버튼의 실패 폐쇄 상태 계약 테스트."""

from __future__ import annotations

from copy import deepcopy

from console.report_export import pdf_export_state


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


def test_malformed_report_does_not_claim_judge_failed():
    """상태를 읽지 못한 것을 'Judge 미통과'로 적으면 원인을 오도한다.

    둘 다 비활성이지만 사용자가 찾아야 할 것이 다르다 — 판정 결과인가,
    유실된 리포트 상태인가.
    """
    for report in (None, {}, [], {"governance": None}, {"status": "  "}):
        help_text = pdf_export_state(report).help_text
        assert "확인할 수 없어" in help_text, report
        assert "Judge 미통과" not in help_text, report


def test_blocked_report_still_explains_judge_or_manual_review():
    """상태가 읽히는 차단 리포트는 기존 안내문을 그대로 유지해야 한다."""
    report = deepcopy(CONFIRMED_REPORT)
    report["status"] = "pending_manual_review"

    state = pdf_export_state(report)
    assert state.enabled is False
    assert "Judge 미통과 또는 수동검토 대기" in state.help_text
