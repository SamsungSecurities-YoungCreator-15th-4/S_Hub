"""R1 무라벨 사례집 로더(app.evaluation.goldenset_loader)의 배선·비누출 검증.

이 테스트는 사례 '내용'을 출력하지 않는다(방화벽). 구조·개수·키·결정성만 확인한다.
정답(label/fail_axes/…)은 judge_inputs에 애초에 없고, 로더가 어떤 경로로도 state에
넣지 않음을 코드로 검증한다.
"""
from __future__ import annotations

import copy
import json

import pytest

from app.evaluation.goldenset_loader import (
    ALLOWED_STATE_KEYS,
    JUDGE_INPUTS_DIR,
    CaseFormatError,
    _load_manifest,
    input_set_hash,
    load_all_cases,
    load_case,
)

ANSWER_FIELDS = (
    "label",
    "fail_axes",
    "trap_type",
    "rationale",
    "labelers",
    "initial_agreement",
    "labeling_method",
)


def _case_paths() -> list:
    return sorted(JUDGE_INPUTS_DIR.glob("case_*.md"))


def test_loads_all_twenty_cases():
    cases = load_all_cases()
    assert len(cases) == 20
    assert [c["case_id"] for c in cases] == [f"case_{i:03d}" for i in range(1, 21)]


def test_state_uses_allowlist_only():
    """모든 사례 state의 최상위 키가 allowlist(metrics/explanations/citations)뿐이다."""
    for path in _case_paths():
        state = load_case(path)
        extra = set(state) - set(ALLOWED_STATE_KEYS)
        assert not extra, f"{path.name}: allowlist 밖 키 {sorted(extra)}"


def test_no_answer_fields_anywhere_in_state():
    """직렬화된 state 어디에도 정답 필드 이름이 남지 않는다(leakage 경계)."""
    for path in _case_paths():
        blob = json.dumps(load_case(path), ensure_ascii=False, default=str)
        for field in ANSWER_FIELDS:
            assert f'"{field}"' not in blob, f"{path.name}: state에 {field} 잔존"


def test_state_shape_is_judge_ready():
    """각 사례가 judge가 읽을 최소 구조(metrics.meta·설명·인용 리스트)를 갖춘다."""
    for path in _case_paths():
        state = load_case(path)
        assert isinstance(state["metrics"], dict)
        assert state["metrics"]["meta"]["data_period"]["end"]  # 기준일 존재
        assert state["metrics"]["meta"]["computation_hash"]  # 재현 해시 존재
        assert isinstance(state["explanations"], list) and state["explanations"]
        assert isinstance(state["citations"], list)


def test_load_case_is_deterministic():
    """같은 파일은 항상 같은 state로 로드된다(재현성)."""
    path = _case_paths()[0]
    assert load_case(path) == load_case(path)


def test_load_all_cases_verifies_manifest_integrity():
    """기본 로드가 manifest 동결 해시 대조를 통과한다(원본 20건 그대로)."""
    cases = load_all_cases()  # verify=True 기본 — 통과하면 무결성 OK
    assert len(cases) == 20


def test_input_set_hash_is_recorded_shape():
    """평가셋 식별 해시가 64자 hex다."""
    value = input_set_hash()
    assert len(value) == 64
    assert all(ch in "0123456789abcdef" for ch in value)


def test_tampered_body_hash_is_rejected():
    """본문 해시가 manifest와 어긋나면 로드가 거부된다(변조 탐지)."""
    manifest = copy.deepcopy(_load_manifest())
    manifest["cases"][0]["case_content_sha256"] = "0" * 64  # 손상 주입
    with pytest.raises(CaseFormatError):
        load_all_cases(manifest=manifest)


def test_runner_records_all_r1_cases_offline():
    """러너가 R1 사례 전부를 judge에 돌려 JudgeResult를 생산한다(배선 검증)."""
    from scripts.judge_runner import _load_r1_cases, record_cases
    from tests.test_judge_eval_evalset import _PassingLLM

    cases = _load_r1_cases()
    assert len(cases) == 20
    results = record_cases(
        cases, llm=_PassingLLM(), prompt_version="v1", code_sha="deadbeef"
    )
    assert len(results) == 20
    assert all(r["prompt_version"] == "v1" for r in results)
    # v1·v2 비교 앵커가 사례 내용에만 종속되도록 64자 해시가 채워져야 한다.
    assert all(len(r["case_content_sha256"]) == 64 for r in results)


def test_wrap_state_sets_as_of_date_from_case():
    """러너 스캐폴딩이 사례 기준일을 run_config.as_of_date로 승격한다(option A)."""
    from scripts.judge_runner import _wrap_state

    parsed = {
        "metrics": {"meta": {"data_period": {"end": "2026-07-24"}}},
        "explanations": [],
        "citations": [],
    }
    wrapped = _wrap_state(parsed, run_config_defaults={"as_of_date": "2000-01-01", "judge_max_retries": 3})
    assert wrapped["run_config"]["as_of_date"] == "2026-07-24"
    assert wrapped["run_config"]["judge_max_retries"] == 3
    assert wrapped["approval"]["status"] == "locked"
    # 스캐폴딩을 감싼 뒤에도 정답 필드는 없다.
    assert not set(wrapped) & set(ANSWER_FIELDS)
