"""Streamlit 감사 번들 생성·Hard Stop 표시 계약 테스트."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest
from streamlit.testing.v1 import AppTest

import console.index_supply
from engine.evidence.schema import BUNDLE_FILENAMES, HARD_STOP_RECORD_FILENAME
from console.evidence_export import EvidenceDownload, build_evidence_download


@pytest.fixture(autouse=True)
def _prepared_rag_index(monkeypatch):
    console.index_supply._cached_ensure_index.clear()
    monkeypatch.setattr(
        console.index_supply,
        "ensure_deployment_index",
        lambda **_kwargs: object(),
    )
    yield
    console.index_supply._cached_ensure_index.clear()


def _blocked_report() -> dict:
    gate = {
        "status": "blocked",
        "trigger": "judge_retries_exhausted",
        "policy_version": "2026-08-01.v1",
        "judge_retries": 3,
        "judge_max_retries": 3,
        "failed_axes": ["source_validity"],
        "decision_hash": "decision-123",
    }
    return {
        "title": "[미확정 · 수동검토 대기] 리스크 리포트",
        "status": "pending_manual_review",
        "status_label": "미확정 — judge 미통과로 수동검토 대기",
        "finalized": False,
        "as_of_date": "2026-07-03",
        "summary": {"portfolio": {"total_value_krw": 0}, "risk": {}},
        "citations": [],
        "warnings": [],
        "judge": {"passed": False, "checks": []},
        "governance": {
            "judge_passed": False,
            "judge_retries": 3,
            "judge_max_retries": 3,
            "report_status": "pending_manual_review",
            "finalized": False,
            "confirmation_allowed": False,
            "export_allowed": False,
            "strict_citation_gate": True,
            "manual_review_gate": gate,
        },
        "reproducibility": {},
        "disclaimer": "검토용 자료",
    }


def test_evidence_zip_contains_complete_r4_contract_for_blocked_state():
    report = _blocked_report()
    state = {
        "trace_id": "trace/blocked 01",
        "report": report,
        "judge": report["judge"],
        "judge_retries": 3,
        "citations": [],
        "citation_rejections": [],
    }

    download = build_evidence_download(
        state,
        generated_at="2026-08-03T00:00:00+00:00",
    )

    assert download.run_id == "ui-trace-blocked-01"
    assert download.filename.endswith(".zip")
    assert len(download.bundle_hash) == 64
    with zipfile.ZipFile(BytesIO(download.data)) as archive:
        assert set(archive.namelist()) == set(BUNDLE_FILENAMES)
        hard_stop = json.loads(archive.read(HARD_STOP_RECORD_FILENAME))
    assert hard_stop["blocked"] is True
    assert hard_stop["manual_review_gate"]["decision_hash"] == "decision-123"


def test_blocked_ui_disables_pdf_but_exposes_manual_review_and_evidence_bundle():
    app = AppTest.from_file("ui/app.py")
    app.session_state["report"] = _blocked_report()
    app.session_state["evidence_download"] = EvidenceDownload(
        filename="symphony-evidence-ui-test.zip",
        data=b"zip-data",
        bundle_hash="a" * 64,
        run_id="ui-test",
    )

    app.run(timeout=20)

    assert not app.exception
    assert app.button(key="save_report_pdf").disabled is True
    assert any("수동검토 이관 정보" in expander.label for expander in app.expander)
    markdown = "\n".join(element.value for element in app.markdown)
    assert "judge_retries_exhausted" in markdown
    assert "decision-123" in markdown
    assert "번들 생성 완료" in markdown
    assert "감사 번들 해시" in markdown
    assert "a" * 64 in markdown
