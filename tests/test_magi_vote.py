"""MAGI 반복 호출 하네스의 집계·불변식 검증 — judge는 전부 모의한다.

실제 Azure 호출 테스트는 만들지 않는다. 이 하네스가 재는 것은 judge의 흔들림이고,
그 흔들림을 테스트에서 재현하려면 비결정성에 의존해야 해서 테스트 자체가 흔들린다.
여기서 고정하는 것은 **3표가 주어졌을 때 하네스가 무엇을 답하는가**다.
"""
from __future__ import annotations

import pytest

from app.judge.rubric import AXIS_NAMES
from scripts.magi_vote import (
    DETERMINISTIC_AXES,
    EXIT_DETERMINISTIC_DRIFT,
    EXIT_OK,
    EXIT_RUN_FAILURE,
    LLM_AXES,
    MAGI_CONTROL_TARGETS,
    MAGI_PRIMARY_TARGETS,
    MAGI_RUNS,
    MAGI_TARGETS,
    aggregate,
    build_report,
    deterministic_violations,
    exit_code_for,
    expected_calls,
    is_split,
    majority_passed,
    run_case,
    unanimous_passed,
)

PASS_AXES = {name: True for name in AXIS_NAMES}


def judge_output(axes: dict) -> dict:
    """judge_eval 반환값 중 이 하네스가 읽는 부분만 만든 모의 출력."""
    return {
        "judge": {
            "passed": all(axes.values()),
            "rubric": {
                name: {"passed": passed, "reason": f"{name}:{passed}"}
                for name, passed in axes.items()
            },
        },
        "run_config": {
            "audit": {
                "llm": {
                    "judge_eval": {
                        "latest": {
                            "prompt_hash": {"aggregate_sha256": "ph-fixed"},
                            "model_version": {
                                "deployment": "test-deployment",
                                "model": "test-model",
                                "api_version": "2024-10-21",
                            },
                        }
                    }
                }
            }
        },
    }


@pytest.fixture
def scripted_judge(monkeypatch):
    """호출 순서대로 정해진 축 판정을 돌려주는 가짜 judge를 심는다."""

    def install(sequences: list[dict]):
        remaining = list(sequences)

        def fake_judge_eval(state, *, llm=None):
            if not remaining:
                raise AssertionError("예상보다 많이 호출됐습니다")
            axes = remaining.pop(0)
            if isinstance(axes, Exception):
                raise axes
            return judge_output(axes)

        monkeypatch.setattr("app.nodes.judge_eval.judge_eval", fake_judge_eval)
        return remaining

    return install


def make_case(case_id: str = "case_003") -> dict:
    return {"case_id": case_id, "state": {"metrics": {}, "explanations": [], "citations": []}}


# --- 표본 상수 ---------------------------------------------------------------
def test_sample_is_five_primary_and_two_control():
    """표본은 실행 시점에 정해지지 않는다 — 상수로 동결돼 있어야 한다."""
    assert len(MAGI_PRIMARY_TARGETS) == 5
    assert len(MAGI_CONTROL_TARGETS) == 2
    assert len(MAGI_TARGETS) == 7
    assert not set(MAGI_PRIMARY_TARGETS) & set(MAGI_CONTROL_TARGETS)
    # judge_inputs 파일명 규약(case_NNN)과 같은 형식이어야 로더가 찾는다.
    assert all(case_id.startswith("case_") for case_id in MAGI_TARGETS)


def test_axis_split_covers_all_six_axes():
    """LLM 2축 + 결정론 4축이 AXIS_NAMES를 빠짐없이 나눈다."""
    assert set(LLM_AXES) | set(DETERMINISTIC_AXES) == set(AXIS_NAMES)
    assert not set(LLM_AXES) & set(DETERMINISTIC_AXES)
    assert len(DETERMINISTIC_AXES) == 4


# --- 예상 호출 수 ------------------------------------------------------------
def test_expected_calls():
    """사례 7건 × 3회 = judge 21회, LLM 축이 2개라 LLM 호출 42회."""
    plan = expected_calls()
    assert plan == {
        "cases": 7,
        "runs_per_case": 3,
        "judge_invocations": 21,
        "llm_calls": 42,
    }
    assert expected_calls(("case_001",), 3)["llm_calls"] == 6


# --- 투표 규칙 ---------------------------------------------------------------
@pytest.mark.parametrize(
    "votes, unanimous, majority, split",
    [
        ([True, True, True], True, True, False),
        ([True, True, False], False, True, True),
        ([True, False, False], False, False, True),
        ([False, False, False], False, False, False),
    ],
)
def test_vote_rules(votes, unanimous, majority, split):
    """3표 조합 4가지 전부 — 만장일치·다수결·갈림 여부."""
    assert unanimous_passed(votes) is unanimous
    assert majority_passed(votes) is majority
    assert is_split(votes) is split


def test_rules_disagree_exactly_when_split():
    """두 규칙이 갈리는 조합만 rules_disagree로 잡힌다 (2-1일 때)."""
    record = _record_with_llm_votes([True, True, False])
    summary = aggregate([record])
    block = summary["per_case"][0]["axes"]["hallucination"]
    assert block["unanimous_passed"] is False
    assert block["majority_passed"] is True
    assert block["rules_disagree"] is True
    assert summary["rule_comparison"]["divergent_count"] >= 1


# --- 집계 -------------------------------------------------------------------
def _record_with_llm_votes(hallucination_votes: list[bool]) -> dict:
    """hallucination 축만 갈린 3회 실행 기록을 만든다."""
    runs = []
    for index, vote in enumerate(hallucination_votes, 1):
        axes = dict(PASS_AXES)
        axes["hallucination"] = vote
        runs.append(
            {
                "run_index": index,
                "judge_passed": all(axes.values()),
                "axes": {
                    name: (
                        {"passed": passed, "reason": "r"}
                        if name in LLM_AXES
                        else {"passed": passed}
                    )
                    for name, passed in axes.items()
                },
                "prompt_hash": "ph-fixed",
                "model_version": {"model": "test-model"},
            }
        )
    return {
        "case_id": "case_003",
        "group": "primary",
        "case_content_sha256": "sha",
        "status": "ok",
        "runs": runs,
    }


def test_canonical_unit_is_llm_axes_combined():
    """정본 단위는 LLM 축 합산 — 한 축만 갈려도 '흔들린 사례' 1건이다."""
    summary = aggregate([_record_with_llm_votes([True, False, True])])
    assert summary["canonical_unit"] == "llm_axes_combined"
    assert summary["unstable_cases"] == 1
    assert summary["unstable_case_ids"] == ["case_003"]
    assert summary["per_case"][0]["llm_axis_unstable"] is True
    # 축별 분리도 함께 나오되 주의 문구가 붙는다.
    assert summary["per_axis"]["hallucination"]["split_cases"] == 1
    assert summary["per_axis"]["false_precision"]["split_cases"] == 0
    assert "위조정밀도 표본이 2건" in summary["per_axis_caveat"]


def test_stable_case_is_not_counted_as_unstable():
    summary = aggregate([_record_with_llm_votes([True, True, True])])
    assert summary["unstable_cases"] == 0
    assert summary["per_case"][0]["llm_axis_unstable"] is False
    assert summary["rule_comparison"]["divergent_count"] == 0


# --- 결정론 축 불변식 ---------------------------------------------------------
def test_deterministic_axis_split_is_flagged_as_violation():
    """결정론 4축이 3회 중 갈리면 흔들림이 아니라 결함으로 잡는다."""
    record = _record_with_llm_votes([True, True, True])
    record["runs"][1]["axes"]["source_validity"]["passed"] = False

    violations = deterministic_violations([record])
    assert len(violations) == 1
    assert violations[0]["case_id"] == "case_003"
    assert violations[0]["axis"] == "source_validity"
    assert violations[0]["votes"] == [True, False, True]
    # 흔들림 통계에는 섞이지 않는다.
    assert aggregate([record])["unstable_cases"] == 0
    assert aggregate([record])["per_case"][0]["deterministic_stable"] is False


def test_llm_axis_split_is_not_a_deterministic_violation():
    assert deterministic_violations([_record_with_llm_votes([True, False, True])]) == []


# --- 종료 코드 ---------------------------------------------------------------
def test_exit_code_ok():
    report = build_report([_record_with_llm_votes([True, False, True])], header={})
    assert exit_code_for(report) == EXIT_OK


def test_exit_code_deterministic_drift():
    record = _record_with_llm_votes([True, True, True])
    record["runs"][0]["axes"]["disclaimer"]["passed"] = False
    report = build_report([record], header={})
    assert report["deterministic_axis_violation_count"] == 1
    assert exit_code_for(report) == EXIT_DETERMINISTIC_DRIFT


def test_call_failure_records_case_and_exits_nonzero(scripted_judge):
    """재시도 후에도 실패하면 사례를 실패로 남기고 비정상 종료 코드로 끝낸다."""
    boom = RuntimeError("Azure 429")
    scripted_judge([boom, boom])  # 최초 호출 + 재시도 1회 모두 실패

    record = run_case(make_case(), llm=object(), runs=MAGI_RUNS)
    assert record["status"] == "failed"
    assert record["failure"]["run_index"] == 1
    assert record["failure"]["error_type"] == "RuntimeError"
    assert record["runs"] == []  # 반쪽 표본은 투표에 쓰지 않는다

    report = build_report([record], header={})
    assert report["summary"]["cases_failed"] == ["case_003"]
    assert exit_code_for(report) == EXIT_RUN_FAILURE


def test_failure_wins_over_drift():
    """둘 다 나면 실행 실패가 우선한다 — 실패 사례는 3표를 못 채운다."""
    drifted = _record_with_llm_votes([True, True, True])
    drifted["runs"][0]["axes"]["disclaimer"]["passed"] = False
    failed = {
        "case_id": "case_011",
        "group": "primary",
        "status": "failed",
        "runs": [],
        "failure": {"run_index": 1, "error_type": "RuntimeError", "error": "boom"},
    }
    report = build_report([drifted, failed], header={})
    assert exit_code_for(report) == EXIT_RUN_FAILURE


# --- 실행 배선 ---------------------------------------------------------------
def test_run_case_retries_once_then_succeeds(scripted_judge):
    """1회 재시도로 회복되면 정상 기록이다."""
    axes = dict(PASS_AXES)
    scripted_judge([RuntimeError("일시 오류"), axes, axes, axes])

    record = run_case(make_case(), llm=object(), runs=MAGI_RUNS)
    assert record["status"] == "ok"
    assert len(record["runs"]) == MAGI_RUNS


def test_run_case_records_three_independent_votes(scripted_judge):
    """3회 호출의 축별 판정과 LLM 축 이유 문구가 원본 그대로 남는다."""
    votes = []
    for vote in (True, False, True):
        axes = dict(PASS_AXES)
        axes["false_precision"] = vote
        votes.append(axes)
    scripted_judge(votes)

    record = run_case(make_case(), llm=object(), runs=3)
    assert [run["run_index"] for run in record["runs"]] == [1, 2, 3]
    assert [
        run["axes"]["false_precision"]["passed"] for run in record["runs"]
    ] == [True, False, True]
    # LLM 축은 이유 문구까지, 결정론 축은 판정만 남긴다.
    assert "reason" in record["runs"][0]["axes"]["false_precision"]
    assert "reason" not in record["runs"][0]["axes"]["source_validity"]
    assert record["group"] == "primary"
    assert record["runs"][0]["prompt_hash"] == "ph-fixed"


def test_header_records_sampling_condition_and_null_result_phrasing():
    """흔들림 0을 '흔들림 없음'으로 일반화하지 않도록 조건이 산출물에 남는다."""
    from scripts.magi_vote import build_header

    header = build_header(
        [_record_with_llm_votes([True, True, True])],
        code_sha="deadbeef",
        evalset_hash="evalset-sha",
        temperature=0.0,
        seed=None,
        runs=3,
    )
    assert header["temperature"] == 0.0
    assert header["seed"] is None
    assert "일반화하지 않는다" in header["null_result_phrasing"]
    assert header["prompt_hash"] == "ph-fixed"


def test_control_group_is_labelled():
    assert run_case.__doc__  # 문서화된 공개 함수
    from scripts.magi_vote import aggregate_case

    record = _record_with_llm_votes([True, True, True])
    record["case_id"] = MAGI_CONTROL_TARGETS[0]
    record["group"] = "control"
    summary = aggregate([record])
    assert summary["by_group"]["control"]["cases"] == 1
    assert summary["by_group"]["primary"]["cases"] == 0
    assert aggregate_case(record)["group"] == "control"
