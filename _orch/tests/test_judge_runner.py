"""judge_runner(R2 실행·기록)의 배선 검증 — EC 회귀 평가셋 기준.

이 테스트는 R1 정답 사례집이 오기 전, 러너가 (1) 사례를 judge_eval에 돌려
(2) 지은님의 JudgeResult 계약을 만족하는 결과를 뽑고 (3) v1·v2 대조 앵커
(case_content_sha256)가 사례 내용에만 종속되는지 검증한다.

EC 회귀 평가셋(EC-01~)은 시스템 테스트용이며 R1 정답 사례집(goldenset)이 아니다.
"""
from __future__ import annotations

import json

import pytest

from app.evaluation.calibration_schema import normalize_judge_result
from scripts.judge_runner import (
    case_content_sha256,
    record_case,
    record_cases,
    write_results,
)
from tests.test_judge_eval_evalset import (
    DETERMINISTIC_CASE_IDS,
    _PassingLLM,
    build_eval_case,
)

# 테스트는 실제 커밋 조회(subprocess)에 의존하지 않도록 유효 형식의 가짜 SHA를 쓴다.
FAKE_CODE_SHA = "deadbeef"


@pytest.fixture(autouse=True)
def _stub_model_version(monkeypatch):
    """오프라인에선 model_version_record가 빈 값을 반환한다(실제 Azure 배포·응답
    메타데이터가 없어서). 실제 비밀값을 전혀 읽지 않고 이 함수 하나만 가짜 값으로
    대체해 배선을 검증한다 — 지은님 통합테스트와 동일한 방식."""
    monkeypatch.setattr(
        "app.llm.audit.model_version_record",
        lambda llm=None, responses=(): {
            "deployment": "test-deployment",
            "model": "test-model",
            "api_version": "2026-01-01",
        },
    )


def _ec_cases() -> list[dict]:
    return [
        {"case_id": case_id, "state": build_eval_case(case_id)["state"]}
        for case_id in DETERMINISTIC_CASE_IDS
    ]


def _is_forced_failure(case: dict) -> bool:
    """force_judge_fail은 데모용 강제 실패 주입이다 — 실제 검사는 통과하는데 판정만
    False로 만들어 normalize의 passed==checks 불변식을 의도적으로 깬다. 실제 R1
    캘리브레이션 입력엔 없는 값이므로 제출 등급 계약 검증에서 제외한다."""
    return bool(case["state"].get("demo_options", {}).get("force_judge_fail"))


def test_runner_produces_a_result_for_every_case():
    """배선 검증: 러너가 전 사례에 대해 JudgeResult를 충실히 생산한다(강제실패 포함)."""
    results = record_cases(
        _ec_cases(), llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    assert len(results) == len(DETERMINISTIC_CASE_IDS)
    assert all(
        r["prompt_version"] == "v1" and r["code_sha"] == FAKE_CODE_SHA for r in results
    )


def test_non_forced_results_pass_submission_grade_contract():
    """강제실패가 아닌 사례의 결과는 지은님 JudgeResult 계약(normalize)을 통과한다.

    실제 R1 캘리브레이션엔 force_judge_fail이 없으므로, 실사용 경로의 출력이 모두
    제출 등급 계약을 만족함을 이 부분집합으로 검증한다.
    """
    cases = [case for case in _ec_cases() if not _is_forced_failure(case)]
    assert cases  # 강제실패가 아닌 사례가 존재해야 검증이 의미 있다
    results = record_cases(
        cases, llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    for result in results:
        normalized = normalize_judge_result(result)
        assert normalized.prompt_version == "v1"
        assert normalized.code_sha == FAKE_CODE_SHA
        assert len(normalized.case_content_sha256) == 64


def test_case_content_hash_ignores_human_label():
    """사람 라벨을 state에 끼워 넣어도 case_content_sha256이 변하지 않아야 한다.

    러너의 해시가 judge 입력 내용(metrics·explanations·citations)에만 종속되고
    사람 정답에는 영향받지 않음을 증명한다 — leakage 경계의 코드적 근거.
    """
    state = build_eval_case(DETERMINISTIC_CASE_IDS[0])["state"]
    baseline = case_content_sha256(state)
    contaminated = dict(state)
    contaminated["label"] = "fail"
    contaminated["rationale"] = "정답 해설(있어선 안 되지만 방어적으로 무시되어야 함)"
    assert case_content_sha256(contaminated) == baseline


def test_v1_v2_share_case_content_hash_but_differ_in_prompt_version():
    """같은 사례를 v1·v2로 돌리면 case_content_sha256은 같고 prompt_version만 달라야 한다.

    개선 전후 비교(compare_official_versions)가 성립하는 전제를 러너 수준에서 확인한다.
    """
    case = {
        "case_id": DETERMINISTIC_CASE_IDS[0],
        "state": build_eval_case(DETERMINISTIC_CASE_IDS[0])["state"],
    }
    v1 = record_case(case, llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA)
    v2 = record_case(case, llm=_PassingLLM(), prompt_version="v2", code_sha=FAKE_CODE_SHA)
    assert v1["case_content_sha256"] == v2["case_content_sha256"]
    assert v1["prompt_version"] == "v1"
    assert v2["prompt_version"] == "v2"


def test_freeze_commit_is_recorded_when_provided():
    """freeze_commit을 넘기면 결과에 감사 앵커로 기록된다(계약은 미지 필드로 무시)."""
    case = {
        "case_id": DETERMINISTIC_CASE_IDS[0],
        "state": build_eval_case(DETERMINISTIC_CASE_IDS[0])["state"],
    }
    result = record_case(
        case,
        llm=_PassingLLM(),
        prompt_version="v1",
        code_sha=FAKE_CODE_SHA,
        freeze_commit="58d5e2b0",
    )
    assert result["freeze_commit"] == "58d5e2b0"


def test_langsmith_none_when_no_project():
    """langsmith_project 미지정(오프라인/키 없음)이면 run id/URL을 None으로 둔다.

    실제 기록이 없는데 run id만 채워 '유령 링크'를 만들지 않기 위한 정직한 기본값.
    """
    case = {
        "case_id": DETERMINISTIC_CASE_IDS[0],
        "state": build_eval_case(DETERMINISTIC_CASE_IDS[0])["state"],
    }
    result = record_case(
        case, llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    assert result["langsmith_run_id"] is None
    assert result["langsmith_trace_url"] is None


def test_prompt_hash_is_recorded():
    """결과에 프롬프트 집계 해시가 기록된다(v1↔v2 '프롬프트만 달랐다' 증명 앵커)."""
    case = {
        "case_id": DETERMINISTIC_CASE_IDS[0],
        "state": build_eval_case(DETERMINISTIC_CASE_IDS[0])["state"],
    }
    result = record_case(
        case, llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    assert len(result["prompt_hash"]) == 64


def test_freeze_commit_absent_by_default():
    """freeze_commit 미지정(EC 리허설)이면 결과에 필드를 남기지 않는다."""
    case = {
        "case_id": DETERMINISTIC_CASE_IDS[0],
        "state": build_eval_case(DETERMINISTIC_CASE_IDS[0])["state"],
    }
    result = record_case(
        case, llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    assert "freeze_commit" not in result


def test_run_manifest_has_auto_fields_and_empty_verifications(tmp_path):
    """실행 요약 카드는 자동 4필드를 채우고 verifications는 빈 배열로 둔다.

    verifications는 사람이 사후에 손으로 채우는 자리라 러너는 비워만 둔다(계약).
    """
    from scripts.judge_runner import manifest_path_for, write_run_manifest

    out = tmp_path / "judge_v1_results.json"
    manifest_out = write_run_manifest(
        out,
        prompt_version="v1",
        code_sha="deadbeef",
        freeze_commit="58d5e2b4",
        input_set_hash="a" * 64,
    )
    assert manifest_out == manifest_path_for(out) == tmp_path / "judge_v1_results.manifest.json"
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert manifest["prompt_version"] == "v1"
    assert manifest["code_sha"] == "deadbeef"
    assert manifest["freeze_commit"] == "58d5e2b4"
    assert manifest["input_set_hash"] == "a" * 64
    assert manifest["executed_at"]  # ISO 시각 문자열 존재
    assert "langsmith_run" in manifest
    assert manifest["verifications"] == []


def test_write_results_roundtrip_is_stable(tmp_path):
    results = record_cases(
        _ec_cases(), llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    out = write_results(results, tmp_path / "judge_v1_results.json")
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded == results
