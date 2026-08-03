"""MAGI 반복 호출 하네스의 집계·불변식 검증 — judge는 전부 모의한다.

실제 Azure 호출 테스트는 만들지 않는다. 이 하네스가 재는 것은 judge의 흔들림이고,
그 흔들림을 테스트에서 재현하려면 비결정성에 의존해야 해서 테스트 자체가 흔들린다.
여기서 고정하는 것은 **3표가 주어졌을 때 하네스가 무엇을 답하는가**다.
"""
from __future__ import annotations

import pytest

import json
import re
from pathlib import Path

from scripts import magi_vote
from app.judge.rubric import AXIS_NAMES
from app.utils.hashing import sha256_of_dict
from scripts.magi_vote import (
    DETERMINISTIC_AXES,
    EXIT_DETERMINISTIC_DRIFT,
    EXIT_OK,
    EXIT_RUN_FAILURE,
    LLM_AXES,
    MAGI_CONTROL_COUNT,
    MAGI_PRIMARY_COUNT,
    MAGI_RUNS,
    MAGI_TARGETS_FILE,
    MAGI_TARGETS_SHA256,
    MagiTargets,
    aggregate,
    build_report,
    deterministic_violations,
    exit_code_for,
    expected_calls,
    is_split,
    load_targets,
    majority_passed,
    run_case,
    unanimous_passed,
)

# 테스트는 **실제 표본 ID를 쓰지 않는다.** 그 목록이 곧 사람 라벨의 파생값이라
# 소스에 적으면 비공개로 돌린 의미가 없다. 합성 ID로 동작만 검증한다.
FAKE_PRIMARY = tuple(f"case_9{index:02d}" for index in range(1, MAGI_PRIMARY_COUNT + 1))
FAKE_CONTROL = tuple(f"case_8{index:02d}" for index in range(1, MAGI_CONTROL_COUNT + 1))
FAKE_TARGETS = MagiTargets(primary=FAKE_PRIMARY, control=FAKE_CONTROL)

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


def make_case(case_id: str = "case_901") -> dict:
    return {"case_id": case_id, "state": {"metrics": {}, "explanations": [], "citations": []}}


def write_targets(tmp_path, payload: dict):
    path = tmp_path / "magi_targets.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path, sha256_of_dict(payload)


# --- 표본 (해시로 동결, 목록은 비공개) ----------------------------------------
def test_sample_size_is_five_primary_and_two_control():
    """표본 규모는 코드에 남는다 — 건수는 어느 사례인지를 드러내지 않는다."""
    assert MAGI_PRIMARY_COUNT == 5
    assert MAGI_CONTROL_COUNT == 2


def test_target_ids_are_not_in_source():
    """표본 ID가 소스에 평문으로 남으면 선정 규칙과 합쳐져 사람 라벨이 드러난다.

    라벨을 동적으로 읽지 않으려던 결정이 정적 노출로 바뀌지 않도록, 목록은
    비공개 파일에 두고 소스에는 커밋값만 남긴다.
    """
    assert MAGI_TARGETS_FILE.name == "magi_targets.json"  # 경로만 상수로 남는다
    assert len(MAGI_TARGETS_SHA256) == 64

    module_source = Path(magi_vote.__file__).read_text(encoding="utf-8")
    # `case_NNN` 형식의 사례 ID가 모듈 어디에도 없어야 한다.
    assert not re.search(r"case_\d{3}", module_source)


def test_load_targets_verifies_commitment(tmp_path):
    """목록이 커밋값과 다르면 실행하지 않는다 — 맞춰 주는 폴백은 없다."""
    payload = {"salt": "abc123", "primary": list(FAKE_PRIMARY), "control": list(FAKE_CONTROL)}
    path, digest = write_targets(tmp_path, payload)

    targets = load_targets(path, expected_sha256=digest)
    assert targets.primary == FAKE_PRIMARY
    assert targets.control == FAKE_CONTROL
    assert targets.group_of(FAKE_PRIMARY[0]) == "primary"
    assert targets.group_of(FAKE_CONTROL[0]) == "control"

    with pytest.raises(SystemExit, match="동결된 커밋값과 다릅니다"):
        load_targets(path, expected_sha256="0" * 64)


def test_load_targets_rejects_missing_file(tmp_path):
    with pytest.raises(SystemExit, match="표본 목록 파일이 없습니다"):
        load_targets(tmp_path / "없는파일.json")


def test_load_targets_rejects_wrong_sample_size(tmp_path):
    """건수가 어긋나면 커밋값이 맞아도 거부한다."""
    payload = {"salt": "abc123", "primary": list(FAKE_PRIMARY[:2]), "control": list(FAKE_CONTROL)}
    path, digest = write_targets(tmp_path, payload)
    with pytest.raises(SystemExit, match="표본 규모가 다릅니다"):
        load_targets(path, expected_sha256=digest)


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
    assert expected_calls(1, 3)["llm_calls"] == 6


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
        "case_id": FAKE_PRIMARY[0],
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
    assert summary["unstable_case_ids"] == [FAKE_PRIMARY[0]]
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
    assert violations[0]["case_id"] == FAKE_PRIMARY[0]
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

    record = run_case(make_case(), llm=object(), group="primary", runs=MAGI_RUNS)
    assert record["status"] == "failed"
    assert record["failure"]["run_index"] == 1
    assert record["failure"]["error_type"] == "RuntimeError"
    assert record["runs"] == []  # 반쪽 표본은 투표에 쓰지 않는다

    report = build_report([record], header={})
    assert report["summary"]["cases_failed"] == [FAKE_PRIMARY[0]]
    assert exit_code_for(report) == EXIT_RUN_FAILURE


def test_failure_wins_over_drift():
    """둘 다 나면 실행 실패가 우선한다 — 실패 사례는 3표를 못 채운다."""
    drifted = _record_with_llm_votes([True, True, True])
    drifted["runs"][0]["axes"]["disclaimer"]["passed"] = False
    failed = {
        "case_id": FAKE_PRIMARY[1],
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

    record = run_case(make_case(), llm=object(), group="primary", runs=MAGI_RUNS)
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

    record = run_case(make_case(), llm=object(), group="primary", runs=3)
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
        targets=FAKE_TARGETS,
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
    # 사전 고정 증명은 커밋값으로 남는다.
    assert header["targets_sha256"] == MAGI_TARGETS_SHA256


def test_header_records_axis_purity_limit():
    """LLM 축 단독 사례가 1건뿐이라는 해석 한계가 산출물에 남는다(R1 소유자 리뷰).

    어느 사례가 어느 축인지는 적지 않는다 — 그것이 곧 사람 라벨이다.
    """
    from scripts.magi_vote import build_header

    header = build_header(
        [_record_with_llm_votes([True, False, True])],
        targets=FAKE_TARGETS,
        code_sha="deadbeef",
        evalset_hash="evalset-sha",
        temperature=0.0,
        seed=None,
        runs=3,
    )
    caveat = header["axis_purity_caveat"]
    assert "단독으로 걸린 사례는 1건" in caveat
    assert "단정하지 않는다" in caveat
    assert not re.search(r"case_\d{3}", caveat)


def test_control_group_is_labelled():
    assert run_case.__doc__  # 문서화된 공개 함수
    from scripts.magi_vote import aggregate_case

    record = _record_with_llm_votes([True, True, True])
    record["case_id"] = FAKE_CONTROL[0]
    record["group"] = "control"
    summary = aggregate([record])
    assert summary["by_group"]["control"]["cases"] == 1
    assert summary["by_group"]["primary"]["cases"] == 0
    assert aggregate_case(record)["group"] == "control"


# --- 제출 번들 모드 -----------------------------------------------------------
#
# R5 라이브 재현 대비. 골든셋과 달리 사람 라벨이 없고, 흔들림이 '관측 대상'이
# 아니라 '제출 가부 신호'라 종료 코드가 달라진다.
def _dump(tmp_path, name: str, state: dict) -> Path:
    """run_graph.py --dump-state 산출물을 흉내 낸 파일을 만든다."""
    from app.evidence.state_dump import dump_state

    return dump_state(state, tmp_path / f"{name}.json")


def test_load_state_cases_strips_nondeterministic_keys(tmp_path):
    """trace_id는 걷어낸다 — 관측용 재호출이 제출 트레이스에 섞이면 안 된다."""
    state = {"trace_id": "run-abc", "metrics": {"a": 1}, "explanations": [], "citations": []}
    case = magi_vote.load_state_cases([_dump(tmp_path, "state_pass1", state)])[0]

    assert case["case_id"] == "state_pass1"
    assert "trace_id" not in case["state"]
    assert case["state"]["metrics"] == {"a": 1}
    assert len(case["state_sha256"]) == 64


def test_state_sha256_ignores_trace_id_but_tracks_content(tmp_path):
    """같은 산출물이면 같은 지문, 내용이 바뀌면 다른 지문이어야 대조에 쓸 수 있다."""
    base = {"trace_id": "run-1", "metrics": {"var": 1.0}}
    other_trace = {"trace_id": "run-2", "metrics": {"var": 1.0}}
    other_content = {"trace_id": "run-1", "metrics": {"var": 2.0}}

    first = magi_vote.load_state_cases([_dump(tmp_path, "a", base)])[0]
    second = magi_vote.load_state_cases([_dump(tmp_path, "b", other_trace)])[0]
    third = magi_vote.load_state_cases([_dump(tmp_path, "c", other_content)])[0]

    assert first["state_sha256"] == second["state_sha256"]
    assert first["state_sha256"] != third["state_sha256"]


def test_load_state_cases_rejects_duplicate_case_id(tmp_path):
    """파일 이름이 사례 ID다 — 겹치면 집계에서 조용히 섞이므로 멈춘다."""
    first = _dump(tmp_path, "state_pass1", {"metrics": {}})
    nested = tmp_path / "다른폴더"
    nested.mkdir()
    second = _dump(nested, "state_pass1", {"metrics": {}})

    with pytest.raises(SystemExit, match="사례 ID가 겹칩니다"):
        magi_vote.load_state_cases([first, second])


def test_load_state_cases_rejects_missing_file(tmp_path):
    with pytest.raises(SystemExit, match="찾을 수 없습니다"):
        magi_vote.load_state_cases([tmp_path / "없는파일.json"])


def test_submission_header_has_no_goldenset_identity_fields():
    """평가셋도 표본 동결도 없는 모드다 — 빈 값을 그럴듯하게 채우지 않는다."""
    header = magi_vote.build_header(
        [
            {
                "case_id": "state_pass1",
                "runs": [],
                "state_sha256": "a" * 64,
                "source_path": "out/state_pass1.json",
            }
        ],
        targets=None,
        code_sha="deadbeef",
        evalset_hash=None,
        temperature=0.0,
        seed=None,
        runs=MAGI_RUNS,
    )

    assert header["mode"] == "submission"
    assert header["targets"] is None
    assert header["targets_sha256"] is None
    assert header["evalset_hash"] is None
    assert header["axis_purity_caveat"] is None
    assert header["submission_states"] == [
        {
            "case_id": "state_pass1",
            "state_sha256": "a" * 64,
            "source_path": "out/state_pass1.json",
        }
    ]
    # 건수는 표본이 아니라 실제 대상 수에서 온다.
    assert header["cases"] == 1


def test_goldenset_header_still_declares_its_mode():
    header = magi_vote.build_header(
        [],
        targets=FAKE_TARGETS,
        code_sha="deadbeef",
        evalset_hash="0" * 64,
        temperature=0.0,
        seed=None,
        runs=MAGI_RUNS,
    )
    assert header["mode"] == "goldenset"
    assert header["submission_states"] is None
    assert header["targets_sha256"] == MAGI_TARGETS_SHA256


def test_submission_group_appears_in_aggregate():
    """primary·control 두 칸은 유지하고 submission을 덧붙인다."""
    record = _record_with_llm_votes([True, True, True])
    record["group"] = magi_vote.SUBMISSION_GROUP
    summary = aggregate([record])

    assert summary["by_group"][magi_vote.SUBMISSION_GROUP]["cases"] == 1
    assert summary["by_group"]["primary"]["cases"] == 0
    assert summary["by_group"]["control"]["cases"] == 0


def test_submission_mode_exits_nonzero_when_llm_axis_splits():
    """제출 모드에서 흔들림은 관측이 아니라 제출 가부 신호다."""
    record = _record_with_llm_votes([True, False, True])
    record["group"] = magi_vote.SUBMISSION_GROUP
    report = build_report([record], header={"mode": "submission"})

    assert report["summary"]["unstable_cases"] == 1
    assert exit_code_for(report) == magi_vote.EXIT_SUBMISSION_UNSTABLE


def test_goldenset_mode_stays_zero_when_llm_axis_splits():
    """같은 3표라도 골든셋 모드는 0으로 끝난다 — 그쪽은 흔들림을 재는 게 목적이다."""
    record = _record_with_llm_votes([True, False, True])
    report = build_report([record], header={"mode": "goldenset"})

    assert report["summary"]["unstable_cases"] == 1
    assert exit_code_for(report) == EXIT_OK


def test_deterministic_drift_wins_over_submission_instability():
    """결정론 축이 갈렸으면 그게 먼저다 — 코드 결함이 제출 가부보다 앞선다."""
    record = _record_with_llm_votes([True, False, True])
    record["group"] = magi_vote.SUBMISSION_GROUP
    record["runs"][0]["axes"]["disclaimer"]["passed"] = False
    report = build_report([record], header={"mode": "submission"})

    assert exit_code_for(report) == EXIT_DETERMINISTIC_DRIFT


def test_run_submission_records_which_dump_was_measured(scripted_judge, tmp_path):
    """어느 산출물을 쟀는지가 기록에 남아야 서류철과 대조할 수 있다."""
    scripted_judge([PASS_AXES, PASS_AXES, PASS_AXES])
    cases = magi_vote.load_state_cases(
        [_dump(tmp_path, "state_block", {"metrics": {}, "explanations": [], "citations": []})]
    )

    records = magi_vote.run_submission(cases, llm=object(), runs=MAGI_RUNS)

    assert records[0]["group"] == magi_vote.SUBMISSION_GROUP
    assert records[0]["state_sha256"] == cases[0]["state_sha256"]
    assert records[0]["source_path"] == cases[0]["source_path"]
    assert len(records[0]["runs"]) == MAGI_RUNS


def test_main_loads_env_before_building_the_llm(monkeypatch, capsys):
    """진입점이 .env를 읽어야 런북 §3.6 명령이 그대로 돈다.

    이 하네스는 judge_runner의 `_real_llm`만 빌려 쓰고 그 main()을 거치지 않는다.
    그래서 judge_runner가 자기 main()에서 하는 load_dotenv가 여기엔 적용되지 않고,
    빠지면 Azure 키가 .env에만 있는 환경에서 RuntimeError로 끝난다.
    """
    called: list[Path] = []
    monkeypatch.setattr(magi_vote, "load_dotenv", lambda path: called.append(path))
    monkeypatch.setattr(
        "sys.argv", ["magi_vote.py", "--dry-run", "--from-state", "없어도-되는-경로.json"]
    )
    monkeypatch.setattr(magi_vote, "load_state_cases", lambda paths: [])

    with pytest.raises(SystemExit) as exit_info:
        magi_vote.main()

    assert exit_info.value.code == EXIT_OK
    assert called == [magi_vote.ROOT / ".env"]
