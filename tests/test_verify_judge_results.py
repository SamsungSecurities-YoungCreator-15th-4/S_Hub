"""verify_judge_results(제출 등급 사전 점검)의 동작 검증.

judge 판정(JudgeResult)만 다루므로 방화벽 무관이다.
"""
from __future__ import annotations

import pytest

from scripts.judge_runner import record_cases
from scripts.verify_judge_results import verify_results
from tests.test_judge_eval_evalset import (
    DETERMINISTIC_CASE_IDS,
    _PassingLLM,
    build_eval_case,
)

FAKE_CODE_SHA = "deadbeef"


@pytest.fixture(autouse=True)
def _hermetic_offline_env(monkeypatch):
    """이 모듈의 offline 검증이 로컬 .env나 다른 테스트 상태에 흔들리지 않게 격리한다.

    .env가 있으면 test 스위트의 load_dotenv가 AZURE_OPENAI_DEPLOYMENT를 os.environ에
    올리고, model_version_record가 그 값을 읽어 offline 결과마저 제출 등급으로
    통과시킨다. offline 신호(모델 정보 없음)를 정확히 재현하려면 Azure 배포 변수와
    강제실패 변수를 지워 진짜 offline 환경을 만든다(테스트 위생, 제품 동작과 무관).
    """
    for name in (
        "RISK_FORCE_JUDGE_FAIL",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)


def _cases() -> list[dict]:
    # 강제실패(force_judge_fail)는 제출 등급 계약을 의도적으로 깨므로 제외한다.
    return [
        {"case_id": cid, "state": build_eval_case(cid)["state"]}
        for cid in DETERMINISTIC_CASE_IDS
        if not build_eval_case(cid)["state"].get("demo_options", {}).get("force_judge_fail")
    ]


@pytest.fixture
def _stub_model_version(monkeypatch):
    monkeypatch.setattr(
        "app.llm.audit.model_version_record",
        lambda llm=None, responses=(): {
            "deployment": "test-deployment",
            "model": "test-model",
            "api_version": "2026-01-01",
        },
    )


def test_submission_grade_results_pass(_stub_model_version):
    """model_version이 채워진 결과는 전부 계약을 통과한다(실패 목록 비어 있음)."""
    results = record_cases(
        _cases(), llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    assert verify_results(results) == []


def test_offline_results_are_flagged():
    """오프라인(가짜 LLM, model_version 빔) 결과는 제출 등급 미달로 잡힌다."""
    results = record_cases(
        _cases(), llm=_PassingLLM(), prompt_version="v1", code_sha=FAKE_CODE_SHA
    )
    failures = verify_results(results)
    assert len(failures) == len(results)  # 전 건이 걸려야 한다
    assert all("model_version" in reason for _, reason in failures)
