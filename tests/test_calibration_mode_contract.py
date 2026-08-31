"""R2 생산자·R4 소비자·계약 문서의 calibration mode 일치 검증."""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from engine.evaluation.calibration_modes import (
    CALIBRATION_MODES,
    MODE_DEV_MOCK,
    MODE_OFFICIAL,
    MODE_OFFICIAL_CODE_CHANGE,
    MODE_OFFICIAL_OFFLINE_CODE_CHANGE,
    MODE_OFFLINE_REHEARSAL,
    OFFICIAL_CALIBRATION_MODES,
    calibration_mode_issue,
)
from scripts.calibration_report import _resolve_mode

ROOT = Path(__file__).resolve().parents[1]

# 통합 레포에서 엔진 문서는 대시보드 문서와 섞이지 않도록 `docs/engine/` 아래 둔다.
DOCS = ROOT / "docs" / "engine"


def test_calibration_report_resolves_only_ssot_modes():
    cases = (
        (Namespace(official=False, no_langsmith=False, no_prompt_change_required=False), MODE_DEV_MOCK),
        (Namespace(official=True, no_langsmith=True, no_prompt_change_required=False), MODE_OFFLINE_REHEARSAL),
        (Namespace(official=True, no_langsmith=False, no_prompt_change_required=False), MODE_OFFICIAL),
        (Namespace(official=True, no_langsmith=False, no_prompt_change_required=True), MODE_OFFICIAL_CODE_CHANGE),
        (
            Namespace(official=True, no_langsmith=True, no_prompt_change_required=True),
            MODE_OFFICIAL_OFFLINE_CODE_CHANGE,
        ),
    )

    resolved = {_resolve_mode(args) for args, _ in cases}
    assert resolved == set(CALIBRATION_MODES)
    for args, expected in cases:
        assert _resolve_mode(args) == expected


def test_only_langsmith_validated_modes_are_official_evidence():
    assert OFFICIAL_CALIBRATION_MODES == {
        MODE_OFFICIAL,
        MODE_OFFICIAL_CODE_CHANGE,
    }
    for mode in OFFICIAL_CALIBRATION_MODES:
        assert calibration_mode_issue(
            mode,
            official_validation_passed=True,
            langsmith_required=True,
        ) is None


def test_contract_documents_list_every_calibration_mode():
    paths = (
        DOCS / "evidence_bundle_schema.md",
        DOCS / "symphony_proof_plan.md",
        DOCS / "audit_demo_runbook.md",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        missing = [mode for mode in CALIBRATION_MODES if f"`{mode}`" not in text]
        assert not missing, f"{path.relative_to(ROOT)}에 calibration mode 문서화 누락: {missing}"
