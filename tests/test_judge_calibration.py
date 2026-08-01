"""R2 캘리브레이션 스키마·계산 로직 테스트 — 전부 mock 데이터로 검증한다.

실제 R1 사례 20건은 생성형 AI에 입력하지 않는다는 팀 방침에 따라, 이 테스트는
실제 사례 내용을 전혀 참조하지 않는다. case_001~case_004 등은 여기서만 쓰는
가상 사례이며, 실제 사례집이 도착하면 이 테스트가 아니라 실행 결과 파일이
merge_records에 들어간다.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import replace

import pytest

from app.evaluation.calibration_schema import (
    CalibrationRecord,
    CalibrationSchemaError,
    EXPECTED_CASE_IDS,
    build_judge_result,
    merge_records,
    normalize_human_label,
    normalize_judge_result,
    validate_official_case_set,
    validate_run_consistency,
)
from app.evaluation.judge_calibration import (
    build_confusion_matrix,
    calculate_axis_metrics,
    calculate_overall_metrics,
    compare_official_versions,
    compare_versions,
    find_mismatches,
)
from app.judge.axes import to_ko
from app.judge.rubric import AXIS_NAMES


def _sha256_hex(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _rubric(fail_axes: tuple[str, ...] = ()) -> dict:
    return {axis: {"passed": axis not in fail_axes, "reason": "mock reason"} for axis in AXIS_NAMES}


def _checks(*, rubric_fail_axes: tuple[str, ...] = (), failed_required_checks: tuple[str, ...] = ()) -> list[dict]:
    checks = [
        {"name": axis, "passed": axis not in rubric_fail_axes, "required": True, "detail": "mock axis detail"}
        for axis in AXIS_NAMES
    ]
    system_checks = {
        "metrics_present": True,
        "computation_hash_present": True,
        "citations_all_verified": True,
        "citation_content_contract": True,
    }
    for name in failed_required_checks:
        system_checks[name] = False
    checks.extend(
        {"name": name, "passed": passed, "required": True, "detail": "mock system detail"}
        for name, passed in system_checks.items()
    )
    return checks


def _human(case_id: str, label: str, fail_axes: list[str] | None = None) -> dict:
    return {
        "id": case_id,
        "label": label,
        "fail_axes": fail_axes or [],
        "rationale": f"{case_id} rationale",
    }


def _model_version(deployment: str = "gpt-mock") -> dict:
    return {"deployment": deployment, "model": "gpt-mock-2026", "api_version": "2026-01-01"}


def _judge(
    case_id: str,
    passed: bool,
    fail_axes_en: tuple[str, ...] = (),
    *,
    prompt_version: str = "v1",
    code_sha: str = "deadbeef",
    judge_attempt: int = 1,
    failed_required_checks: tuple[str, ...] = (),
    case_content_seed: str | None = None,
    langsmith_run_id: str | None = None,
    langsmith_trace_url: str | None = None,
    as_of_date: str = "2026-06-30",
    strict_citation_gate: bool = False,
) -> dict:
    return {
        "case_id": case_id,
        "passed": passed,
        "reason": f"{case_id} judge reason",
        "rubric": _rubric(fail_axes_en),
        "checks": _checks(rubric_fail_axes=fail_axes_en, failed_required_checks=failed_required_checks),
        "judge_attempt": judge_attempt,
        "judge_feedback": "" if passed else f"{case_id} rewrite feedback",
        "manual_review_flags": [],
        "prompt_version": prompt_version,
        "prompt_hash": _sha256_hex(f"{prompt_version}-{case_id}"),
        "model_version": _model_version(),
        "trace_id": f"trace-{case_id}-{prompt_version}",
        "langsmith_run_id": langsmith_run_id,
        "langsmith_trace_url": langsmith_trace_url,
        "code_sha": code_sha,
        "case_content_sha256": _sha256_hex(case_content_seed or case_id),
        "as_of_date": as_of_date,
        "strict_citation_gate": strict_citation_gate,
    }


def _ko_for(axis_en: str) -> str:
    return to_ko(axis_en)


def _fake_judge_output(*, as_of_date: str = "2026-06-30", strict_citation_gate: bool = False) -> dict:
    """build_judge_result()의 자체 로직(as_of_date 교차검증 등)만 단위 테스트하기
    위한 최소 judge_eval() 반환값 모양. 실제 judge_eval() 계약 자체는
    test_build_judge_result_accepts_real_judge_eval_output()이 별도로 검증한다."""
    return {
        "judge_retries": 1,
        "judge_feedback": "",
        "run_config": {
            "as_of_date": as_of_date,
            "strict_citation_gate": strict_citation_gate,
            "audit": {
                "llm": {
                    "judge_eval": {
                        "latest": {
                            "prompt_hash": {"aggregate_sha256": _sha256_hex("fake")},
                            "model_version": _model_version(),
                        }
                    }
                }
            },
        },
        "judge": {
            "passed": True,
            "reason": "fake pass",
            "rubric": _rubric(),
            "checks": _checks(),
            "manual_review_flags": [],
        },
    }


def _no_langsmith(record: CalibrationRecord) -> CalibrationRecord:
    return replace(record, langsmith_run_id=None, langsmith_trace_url=None)


# case_001: 사람 pass, judge pass → TN
# case_002: 사람 fail(출처=source_validity), judge pass → FN (결함 놓침)
# case_003: 사람 pass, judge fail(면책=disclaimer) → FP (오탐)
# case_004: 사람 fail(수치 정합=numeric_consistency), judge도 동일 축 fail → TP
HUMAN_LABELS_V1 = [
    _human("case_001", "pass"),
    _human("case_002", "fail", ["출처"]),
    _human("case_003", "pass"),
    _human("case_004", "fail", ["수치 정합"]),
]
JUDGE_RESULTS_V1 = [
    _judge("case_001", True),
    _judge("case_002", True),
    _judge("case_003", False, ("disclaimer",)),
    _judge("case_004", False, ("numeric_consistency",)),
]


@pytest.fixture
def records_v1() -> list[CalibrationRecord]:
    return merge_records(HUMAN_LABELS_V1, JUDGE_RESULTS_V1)


class TestNormalizeHumanLabel:
    def test_valid_pass(self):
        case_id, human_passed, fail_axes, rationale = normalize_human_label(_human("c1", "pass"))
        assert case_id == "c1"
        assert human_passed is True
        assert fail_axes == ()

    def test_valid_fail_translates_korean_axis(self):
        _, human_passed, fail_axes, _ = normalize_human_label(
            _human("c1", "fail", ["출처", "면책"])
        )
        assert human_passed is False
        assert fail_axes == ("source_validity", "disclaimer")

    def test_fail_axes_order_is_normalized(self):
        """입력 순서가 달라도 같은 정답이면 같은 tuple이 나와야 v1·v2 비교가 안정적이다."""
        _, _, fail_axes_a, _ = normalize_human_label(_human("c1", "fail", ["면책", "출처"]))
        _, _, fail_axes_b, _ = normalize_human_label(_human("c2", "fail", ["출처", "면책"]))
        assert fail_axes_a == fail_axes_b

    def test_missing_id_raises(self):
        with pytest.raises(CalibrationSchemaError, match="id가 없습니다"):
            normalize_human_label({"label": "pass"})

    def test_invalid_label_raises(self):
        with pytest.raises(CalibrationSchemaError, match="pass\\|fail"):
            normalize_human_label(_human("c1", "FAIL"))

    def test_missing_fail_axes_key_raises(self):
        raw = _human("c1", "pass")
        del raw["fail_axes"]
        with pytest.raises(CalibrationSchemaError, match="fail_axes 필드가 없습니다"):
            normalize_human_label(raw)

    def test_non_list_fail_axes_does_not_silently_become_empty(self):
        """fail_axes=0처럼 falsy인 잘못된 타입이 `or []`로 조용히 통과하면 안 된다."""
        raw = _human("c1", "pass")
        raw["fail_axes"] = 0
        with pytest.raises(CalibrationSchemaError, match="list여야 합니다"):
            normalize_human_label(raw)

    def test_duplicate_axis_raises(self):
        with pytest.raises(CalibrationSchemaError, match="중복"):
            normalize_human_label(_human("c1", "fail", ["출처", "출처"]))

    def test_pass_with_fail_axes_raises(self):
        with pytest.raises(CalibrationSchemaError, match="label=pass"):
            normalize_human_label(_human("c1", "pass", ["출처"]))

    def test_fail_without_fail_axes_raises(self):
        with pytest.raises(CalibrationSchemaError, match="label=fail"):
            normalize_human_label(_human("c1", "fail", []))

    def test_unknown_axis_name_raises(self):
        with pytest.raises(CalibrationSchemaError, match="알 수 없는"):
            normalize_human_label(_human("c1", "fail", ["출 처"]))

    def test_non_string_rationale_raises(self):
        raw = _human("c1", "pass")
        raw["rationale"] = {"not": "a string"}
        with pytest.raises(CalibrationSchemaError, match="rationale"):
            normalize_human_label(raw)


class TestNormalizeJudgeResult:
    def test_valid(self):
        result = normalize_judge_result(_judge("c1", False, ("hallucination",)))
        assert result.case_id == "c1"
        assert result.passed is False
        assert result.fail_axes == ("hallucination",)
        assert result.axis_reasons["hallucination"] == "mock reason"
        assert result.prompt_version == "v1"
        assert result.model_version == _model_version()
        assert result.trace_id == "trace-c1-v1"
        assert result.code_sha == "deadbeef"
        assert result.judge_attempt == 1
        assert result.langsmith_run_id is None

    def test_missing_axis_raises(self):
        raw = _judge("c1", True)
        del raw["rubric"]["disclaimer"]
        with pytest.raises(CalibrationSchemaError, match="6축"):
            normalize_judge_result(raw)

    def test_non_bool_passed_raises(self):
        raw = _judge("c1", True)
        raw["passed"] = "true"
        with pytest.raises(CalibrationSchemaError, match="bool"):
            normalize_judge_result(raw)

    @pytest.mark.parametrize("field", ["prompt_version", "trace_id"])
    def test_missing_metadata_field_raises(self, field):
        raw = _judge("c1", True)
        del raw[field]
        with pytest.raises(CalibrationSchemaError, match=field):
            normalize_judge_result(raw)

    def test_blank_prompt_version_raises(self):
        raw = _judge("c1", True)
        raw["prompt_version"] = "   "
        with pytest.raises(CalibrationSchemaError, match="prompt_version"):
            normalize_judge_result(raw)

    def test_non_hex_prompt_hash_raises(self):
        raw = _judge("c1", True)
        raw["prompt_hash"] = "not-a-hash"
        with pytest.raises(CalibrationSchemaError, match="prompt_hash"):
            normalize_judge_result(raw)

    def test_non_hex_case_content_sha256_raises(self):
        raw = _judge("c1", True)
        raw["case_content_sha256"] = "short"
        with pytest.raises(CalibrationSchemaError, match="case_content_sha256"):
            normalize_judge_result(raw)

    def test_short_code_sha_is_accepted(self):
        """git short SHA(7자)는 sha256이 아니라 별도 검증 규칙을 쓴다."""
        result = normalize_judge_result(_judge("c1", True, code_sha="abc1234"))
        assert result.code_sha == "abc1234"

    def test_model_version_must_be_dict(self):
        raw = _judge("c1", True)
        raw["model_version"] = "gpt-mock-2026"
        with pytest.raises(CalibrationSchemaError, match="model_version은 dict"):
            normalize_judge_result(raw)

    def test_model_version_missing_key_raises(self):
        raw = _judge("c1", True)
        del raw["model_version"]["api_version"]
        with pytest.raises(CalibrationSchemaError, match="api_version"):
            normalize_judge_result(raw)

    def test_model_version_all_blank_raises(self):
        raw = _judge("c1", True)
        raw["model_version"] = {"deployment": None, "model": None, "api_version": None}
        with pytest.raises(CalibrationSchemaError, match="deployment·model"):
            normalize_judge_result(raw)

    def test_optional_langsmith_fields_pass_through(self):
        raw = _judge("c1", True)
        raw["langsmith_run_id"] = "b6f1c9d0-6e2e-4a3b-9b1a-7f2a6a0c9e11"
        raw["langsmith_trace_url"] = "https://smith.langchain.com/runs/b6f1c9d0-6e2e-4a3b-9b1a-7f2a6a0c9e11"
        result = normalize_judge_result(raw)
        assert result.langsmith_run_id == "b6f1c9d0-6e2e-4a3b-9b1a-7f2a6a0c9e11"
        assert result.langsmith_trace_url == "https://smith.langchain.com/runs/b6f1c9d0-6e2e-4a3b-9b1a-7f2a6a0c9e11"

    def test_blank_langsmith_field_raises(self):
        raw = _judge("c1", True)
        raw["langsmith_run_id"] = "   "
        with pytest.raises(CalibrationSchemaError, match="langsmith_run_id"):
            normalize_judge_result(raw)

    def test_non_uuid_langsmith_run_id_raises(self):
        """LangSmith run ID는 유효한 UUID여야 한다 — "abc" 같은 placeholder를 거부한다."""
        raw = _judge("c1", True)
        raw["langsmith_run_id"] = "abc-123"
        with pytest.raises(CalibrationSchemaError, match="UUID"):
            normalize_judge_result(raw)

    def test_langsmith_run_id_is_normalized_to_lowercase_standard_form(self):
        """대소문자·하이픈 유무만 다른 동일 UUID가 문자열 비교로 중복 검사를
        우회하지 않도록, 표준형(소문자, 하이픈 포함)으로 정규화해서 저장한다."""
        raw = _judge("c1", True)
        raw["langsmith_run_id"] = "B6F1C9D0-6E2E-4A3B-9B1A-7F2A6A0C9E11"
        result = normalize_judge_result(raw)
        assert result.langsmith_run_id == "b6f1c9d0-6e2e-4a3b-9b1a-7f2a6a0c9e11"

    def test_checks_missing_raises(self):
        raw = _judge("c1", True)
        del raw["checks"]
        with pytest.raises(CalibrationSchemaError, match="checks"):
            normalize_judge_result(raw)

    def test_as_of_date_missing_raises(self):
        raw = _judge("c1", True)
        del raw["as_of_date"]
        with pytest.raises(CalibrationSchemaError, match="as_of_date"):
            normalize_judge_result(raw)

    def test_as_of_date_non_iso_format_raises(self):
        raw = _judge("c1", True)
        raw["as_of_date"] = "2026/06/30"
        with pytest.raises(CalibrationSchemaError, match="YYYY-MM-DD"):
            normalize_judge_result(raw)

    def test_as_of_date_valid_iso_format_is_accepted(self):
        result = normalize_judge_result(_judge("c1", True, as_of_date="2026-07-15"))
        assert result.as_of_date == "2026-07-15"

    @pytest.mark.parametrize("compact_or_week_form", ["20260715", "2026-W27-1"])
    def test_as_of_date_rejects_non_dash_iso_forms(self, compact_or_week_form):
        """date.fromisoformat()은 압축형·주차형도 받아들이지만, 이 필드는 문자열
        동등 비교로만 쓰이므로 표기를 YYYY-MM-DD로 못박아야 한다 — 그렇지 않으면
        같은 날짜가 "20260715"·"2026-07-15"처럼 다른 문자열로 들어와 v1·v2
        일관성 검사가 실제로는 같은 날짜인데 다르다고 잘못 판단할 수 있다."""
        raw = _judge("c1", True)
        raw["as_of_date"] = compact_or_week_form
        with pytest.raises(CalibrationSchemaError, match="YYYY-MM-DD"):
            normalize_judge_result(raw)

    def test_as_of_date_rejects_nonexistent_calendar_date(self):
        raw = _judge("c1", True)
        raw["as_of_date"] = "2026-02-30"
        with pytest.raises(CalibrationSchemaError, match="실재하는 날짜"):
            normalize_judge_result(raw)

    def test_strict_citation_gate_missing_raises(self):
        raw = _judge("c1", True)
        del raw["strict_citation_gate"]
        with pytest.raises(CalibrationSchemaError, match="strict_citation_gate"):
            normalize_judge_result(raw)

    def test_strict_citation_gate_non_bool_raises(self):
        raw = _judge("c1", True)
        raw["strict_citation_gate"] = "true"
        with pytest.raises(CalibrationSchemaError, match="strict_citation_gate"):
            normalize_judge_result(raw)

    def test_strict_citation_gate_true_is_accepted(self):
        result = normalize_judge_result(_judge("c1", True, strict_citation_gate=True))
        assert result.strict_citation_gate is True

    def test_failed_required_check_outside_rubric_is_captured(self):
        """citation_content_contract처럼 6축 밖의 필수 검사 실패가 소실되면 안 된다."""
        raw = _judge("c1", False, failed_required_checks=("citation_content_contract",))
        result = normalize_judge_result(raw)
        assert result.fail_axes == ()  # 6축 rubric은 전부 통과
        assert result.failed_required_checks == ("citation_content_contract",)

    def test_rubric_and_checks_axis_mismatch_raises(self):
        """rubric[축]과 checks[축]이 서로 다른 손상된 입력은 거부해야 한다.

        6축 이름과 같은 checks 항목만 있으면 failed_required_checks에서
        제외되기 때문에, rubric만 보고 fail_axes를 판단하면 이 불일치를
        놓친다 — 그래서 rubric과 checks[축]을 직접 대조해야 한다.
        """
        raw = _judge("c1", True)
        raw["rubric"]["hallucination"]["passed"] = False  # checks[hallucination]은 여전히 True
        with pytest.raises(CalibrationSchemaError, match="판정이 다릅니다"):
            normalize_judge_result(raw)

    def test_duplicate_check_name_raises(self):
        raw = _judge("c1", True)
        raw["checks"].append(dict(raw["checks"][0]))
        with pytest.raises(CalibrationSchemaError, match="중복"):
            normalize_judge_result(raw)

    def test_axis_check_missing_from_checks_raises(self):
        raw = _judge("c1", True)
        raw["checks"] = [c for c in raw["checks"] if c["name"] != "disclaimer"]
        with pytest.raises(CalibrationSchemaError, match="6축 검사 disclaimer가 없습니다"):
            normalize_judge_result(raw)

    def test_hidden_failed_system_check_with_passed_true_raises(self):
        """6축은 전부 일치해도, 6축 밖 시스템 검사 실패를 숨기고 passed=true라 주장하면 거부한다."""
        raw = _judge("c1", False, failed_required_checks=("citation_content_contract",))
        raw["passed"] = True
        with pytest.raises(CalibrationSchemaError, match="checks의 필수 검사 결과"):
            normalize_judge_result(raw)

    def test_passed_false_with_no_failure_reason_raises(self):
        raw = _judge("c1", True)  # 모든 축·검사가 통과 상태
        raw["passed"] = False  # 그런데 passed만 거짓으로 조작
        with pytest.raises(CalibrationSchemaError, match="checks의 필수 검사 결과"):
            normalize_judge_result(raw)

    def test_judge_feedback_required_when_failed(self):
        raw = _judge("c1", False, ("hallucination",))
        raw["judge_feedback"] = ""
        with pytest.raises(CalibrationSchemaError, match="judge_feedback"):
            normalize_judge_result(raw)

    def test_judge_feedback_non_string_raises_even_when_passed(self):
        """PASS 사례라도 judge_feedback 타입이 잘못되면 조용히 ""로 바꾸지 않고 거부한다."""
        raw = _judge("c1", True)
        raw["judge_feedback"] = {"unexpected": "dict"}
        with pytest.raises(CalibrationSchemaError, match="judge_feedback은 문자열"):
            normalize_judge_result(raw)

    def test_manual_review_flags_missing_key_raises(self):
        raw = _judge("c1", True)
        del raw["manual_review_flags"]
        with pytest.raises(CalibrationSchemaError, match="manual_review_flags 필드가 없습니다"):
            normalize_judge_result(raw)

    def test_manual_review_flags_falsy_non_list_does_not_silently_pass(self):
        """manual_review_flags=0처럼 falsy인 잘못된 타입이 조용히 []로 통과하면 안 된다."""
        raw = _judge("c1", True)
        raw["manual_review_flags"] = 0
        with pytest.raises(CalibrationSchemaError, match="manual_review_flags는"):
            normalize_judge_result(raw)

    def test_manual_review_flags_blank_entry_raises(self):
        raw = _judge("c1", True)
        raw["manual_review_flags"] = ["   "]
        with pytest.raises(CalibrationSchemaError, match="manual_review_flags는"):
            normalize_judge_result(raw)

    def test_model_version_non_string_subvalue_raises(self):
        raw = _judge("c1", True)
        raw["model_version"]["deployment"] = 123
        with pytest.raises(CalibrationSchemaError, match="model_version.deployment"):
            normalize_judge_result(raw)

    @pytest.mark.parametrize("bad_attempt", [0, -1, True, "1"])
    def test_invalid_judge_attempt_raises(self, bad_attempt):
        raw = _judge("c1", True)
        raw["judge_attempt"] = bad_attempt
        with pytest.raises(CalibrationSchemaError, match="judge_attempt"):
            normalize_judge_result(raw)


class TestMergeRecords:
    def test_merges_by_case_id(self, records_v1):
        assert [r.case_id for r in records_v1] == [
            "case_001",
            "case_002",
            "case_003",
            "case_004",
        ]
        record = records_v1[3]
        assert record.human_passed is False
        assert record.judge_passed is False
        assert record.human_fail_axes == ("numeric_consistency",)
        assert record.trace_id == "trace-case_004-v1"
        assert record.code_sha == "deadbeef"
        assert record.judge_attempt == 1
        assert record.judge_failed_required_checks == ()

    def test_mismatched_ids_raise(self):
        with pytest.raises(CalibrationSchemaError, match="일치하지 않습니다"):
            merge_records(HUMAN_LABELS_V1, JUDGE_RESULTS_V1[:-1])

    def test_duplicate_id_raises(self):
        with pytest.raises(CalibrationSchemaError, match="중복"):
            merge_records(HUMAN_LABELS_V1 + [_human("case_001", "pass")], JUDGE_RESULTS_V1)


class TestOverallMetrics:
    def test_counts_and_rate(self, records_v1):
        metrics = calculate_overall_metrics(records_v1)
        assert metrics.total == 4
        assert metrics.true_positive == 1
        assert metrics.true_negative == 1
        assert metrics.false_negative == 1
        assert metrics.false_positive == 1
        assert metrics.match == 2
        assert metrics.match_rate == 0.5

    def test_empty_records_raise(self):
        with pytest.raises(ValueError):
            calculate_overall_metrics([])


class TestConfusionMatrix:
    def test_matrix_shape(self, records_v1):
        matrix = build_confusion_matrix(records_v1)
        assert matrix == {
            "human_pass": {"judge_pass": 1, "judge_fail": 1},
            "human_fail": {"judge_pass": 1, "judge_fail": 1},
        }


class TestAxisMetrics:
    def test_source_validity_has_one_false_negative(self, records_v1):
        axis_metrics = calculate_axis_metrics(records_v1)
        source = axis_metrics["source_validity"]
        assert source.match == 3
        assert source.false_negative == 1
        assert source.false_positive == 0
        assert source.axis_ko == "출처"

    def test_disclaimer_has_one_false_positive(self, records_v1):
        axis_metrics = calculate_axis_metrics(records_v1)
        disclaimer = axis_metrics["disclaimer"]
        assert disclaimer.match == 3
        assert disclaimer.false_positive == 1
        assert disclaimer.false_negative == 0

    def test_untouched_axes_match_fully_and_have_no_defect_support(self, records_v1):
        axis_metrics = calculate_axis_metrics(records_v1)
        for axis in ("hallucination", "false_precision", "prohibited_expression"):
            assert axis_metrics[axis].match == 4
            assert axis_metrics[axis].match_rate == 1.0
            assert axis_metrics[axis].human_fail_support == 0
            assert axis_metrics[axis].defect_recall is None

    def test_numeric_consistency_matches_on_true_positive(self, records_v1):
        axis_metrics = calculate_axis_metrics(records_v1)
        numeric = axis_metrics["numeric_consistency"]
        assert numeric.match == 4
        assert numeric.true_positive == 1
        assert numeric.human_fail_support == 1
        assert numeric.defect_recall == 1.0

    def test_source_validity_defect_recall_is_zero_despite_high_match_rate(self, records_v1):
        """match_rate만 보면 75%처럼 보여도 defect_recall로 실제 탐지력을 드러낸다."""
        source = calculate_axis_metrics(records_v1)["source_validity"]
        assert source.match_rate == 0.75
        assert source.human_fail_support == 1
        assert source.defect_recall == 0.0


class TestFindMismatches:
    def test_returns_only_mismatched_cases(self, records_v1):
        mismatches = find_mismatches(records_v1)
        assert {m.case_id for m in mismatches} == {"case_002", "case_003"}

    def test_error_types(self, records_v1):
        by_id = {m.case_id: m for m in find_mismatches(records_v1)}
        assert by_id["case_002"].error_type == "false_negative"
        assert by_id["case_002"].axis_mismatch == ("source_validity",)
        assert by_id["case_003"].error_type == "false_positive"
        assert by_id["case_003"].axis_mismatch == ("disclaimer",)

    def test_includes_judge_reason_for_mismatched_axes_only(self, records_v1):
        by_id = {m.case_id: m for m in find_mismatches(records_v1)}
        assert by_id["case_002"].judge_axis_reasons == {"source_validity": "mock reason"}
        assert by_id["case_003"].judge_axis_reasons == {"disclaimer": "mock reason"}


class TestRunConsistency:
    def test_consistent_run_passes(self, records_v1):
        validate_run_consistency(records_v1)  # 예외 없이 통과

    def test_different_prompt_version_raises(self):
        judge = [
            _judge("case_001", True),
            _judge("case_002", True),
            _judge("case_003", False, ("disclaimer",)),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records = merge_records(HUMAN_LABELS_V1, judge)
        with pytest.raises(CalibrationSchemaError, match="prompt_version"):
            validate_run_consistency(records)

    def test_different_code_sha_raises(self):
        judge = [
            _judge("case_001", True),
            _judge("case_002", True),
            _judge("case_003", False, ("disclaimer",)),
            _judge("case_004", False, ("numeric_consistency",), code_sha="cafef00d"),
        ]
        records = merge_records(HUMAN_LABELS_V1, judge)
        with pytest.raises(CalibrationSchemaError, match="한 실행"):
            validate_run_consistency(records)

    def test_different_as_of_date_raises(self):
        judge = [
            _judge("case_001", True),
            _judge("case_002", True),
            _judge("case_003", False, ("disclaimer",)),
            _judge("case_004", False, ("numeric_consistency",), as_of_date="2026-07-15"),
        ]
        records = merge_records(HUMAN_LABELS_V1, judge)
        with pytest.raises(CalibrationSchemaError, match="as_of_date"):
            validate_run_consistency(records)

    def test_different_strict_citation_gate_raises(self):
        judge = [
            _judge("case_001", True),
            _judge("case_002", True),
            _judge("case_003", False, ("disclaimer",)),
            _judge("case_004", False, ("numeric_consistency",), strict_citation_gate=True),
        ]
        records = merge_records(HUMAN_LABELS_V1, judge)
        with pytest.raises(CalibrationSchemaError, match="strict_citation_gate"):
            validate_run_consistency(records)


def _uuid_for(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def _official_20_records(*, prompt_version: str = "v1") -> list[CalibrationRecord]:
    """6축 전부 최소 1건 결함을 포함하는 case_001~020 mock 세트. LangSmith 필드까지 채운다."""
    defect_case_ids = [f"case_{i:03d}" for i in range(1, len(AXIS_NAMES) + 1)]

    def _with_langsmith(case_id: str, **kwargs) -> dict:
        run_id = _uuid_for(f"{case_id}-{prompt_version}")
        return _judge(
            case_id,
            langsmith_run_id=run_id,
            langsmith_trace_url=f"https://smith.langchain.com/runs/{run_id}",
            prompt_version=prompt_version,
            **kwargs,
        )

    human = [
        _human(case_id, "fail", [_ko_for(axis)])
        for axis, case_id in zip(AXIS_NAMES, defect_case_ids)
    ]
    judge = [
        _with_langsmith(case_id, passed=False, fail_axes_en=(axis,))
        for axis, case_id in zip(AXIS_NAMES, defect_case_ids)
    ]
    for i in range(1, 21):
        case_id = f"case_{i:03d}"
        if case_id in defect_case_ids:
            continue
        human.append(_human(case_id, "pass"))
        judge.append(_with_langsmith(case_id, passed=True))
    return merge_records(human, judge)


class TestOfficialCaseSet:
    def test_valid_20_case_set_passes(self):
        validate_official_case_set(_official_20_records())  # LangSmith 필드까지 포함해 통과

    def test_wrong_count_raises(self):
        records = _official_20_records()[:-1]
        with pytest.raises(CalibrationSchemaError, match="20건"):
            validate_official_case_set(records)

    def test_missing_langsmith_run_id_raises_by_default(self):
        """require_langsmith 기본값(True)에서는 LangSmith run ID 누락을 잡아야 한다."""
        records = _official_20_records()
        records = [
            r if r.case_id != "case_020" else _no_langsmith(r) for r in records
        ]
        with pytest.raises(CalibrationSchemaError, match="LangSmith run ID"):
            validate_official_case_set(records)

    def test_duplicate_langsmith_run_id_raises(self):
        """사례마다 별도 LangSmith run이어야 한다 — 같은 run ID를 재사용하면 거부한다."""
        records = _official_20_records()
        shared_run_id = records[0].langsmith_run_id
        records = [
            replace(r, langsmith_run_id=shared_run_id) if r.case_id == "case_002" else r
            for r in records
        ]
        with pytest.raises(CalibrationSchemaError, match="중복된 run ID"):
            validate_official_case_set(records)

    def test_non_first_attempt_raises(self):
        """20건 전체를 채우되 한 건만 judge_attempt=2로 만들어 그 검증만 걸리게 한다."""
        defect_case_ids = [f"case_{i:03d}" for i in range(1, len(AXIS_NAMES) + 1)]
        human = [
            _human(case_id, "fail", [_ko_for(axis)])
            for axis, case_id in zip(AXIS_NAMES, defect_case_ids)
        ]
        judge = [
            _judge(case_id, False, (axis,))
            for axis, case_id in zip(AXIS_NAMES, defect_case_ids)
        ]
        for i in range(1, 21):
            case_id = f"case_{i:03d}"
            if case_id in defect_case_ids:
                continue
            human.append(_human(case_id, "pass"))
            attempt = 2 if case_id == "case_020" else 1
            judge.append(_judge(case_id, True, judge_attempt=attempt))
        records = merge_records(human, judge)
        with pytest.raises(CalibrationSchemaError, match="1차 판정"):
            validate_official_case_set(records, require_langsmith=False)

    def test_uncovered_axis_raises(self):
        covered_axes = [axis for axis in AXIS_NAMES if axis != "hallucination"]
        defect_ids = [f"case_{i:03d}" for i in range(1, len(covered_axes) + 1)]
        human = [
            _human(case_id, "fail", [_ko_for(axis)]) for axis, case_id in zip(covered_axes, defect_ids)
        ]
        judge = [_judge(case_id, False, (axis,)) for axis, case_id in zip(covered_axes, defect_ids)]
        for i in range(1, 21):
            case_id = f"case_{i:03d}"
            if case_id in defect_ids:
                continue
            human.append(_human(case_id, "pass"))
            judge.append(_judge(case_id, True))
        records = merge_records(human, judge)
        with pytest.raises(CalibrationSchemaError, match="6축"):
            validate_official_case_set(records, require_langsmith=False)


class TestCompareVersions:
    def test_v2_fixes_false_negative(self, records_v1):
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2"),
            _judge("case_002", False, ("source_validity",), prompt_version="v2"),  # v2에서 탐지
            _judge("case_003", False, ("disclaimer",), prompt_version="v2"),  # 오탐은 그대로
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)

        comparison = compare_versions(records_v1, records_v2)

        assert comparison.before.match_rate == 0.5
        assert comparison.after.match_rate == 0.75
        assert comparison.match_rate_delta == 0.25
        assert comparison.false_negative_delta == -1
        assert comparison.false_positive_delta == 0
        assert comparison.axis_after["source_validity"].false_negative == 0
        assert comparison.axis_after["source_validity"].defect_recall == 1.0

    def test_code_sha_is_surfaced_even_when_different(self, records_v1):
        """code_sha 동일성은 더 이상 강제하지 않지만, 값 자체는 결과에 남아야
        v1·v2 코드가 실제로 달랐는지 산출물만 보고 알 수 있다."""
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2", code_sha="cafef00d"),
            _judge("case_002", False, ("source_validity",), prompt_version="v2", code_sha="cafef00d"),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2", code_sha="cafef00d"),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2", code_sha="cafef00d"),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)

        comparison = compare_versions(records_v1, records_v2)

        assert comparison.before_code_sha == "deadbeef"
        assert comparison.after_code_sha == "cafef00d"

    def test_mismatched_case_ids_raise(self, records_v1):
        with pytest.raises(ValueError, match="동일 case_id"):
            compare_versions(records_v1, records_v1[:-1])

    def test_different_human_label_raises(self, records_v1):
        """사람 정답이 v1·v2 사이에 달라지면 judge 개선 여부와 무관하게 비교를 거부한다."""
        human_v2_relabeled = [
            _human("case_001", "pass"),
            _human("case_002", "pass"),  # v1에서는 fail이었는데 v2에서 정답이 바뀜
            _human("case_003", "pass"),
            _human("case_004", "fail", ["수치 정합"]),
        ]
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2"),
            _judge("case_002", True, prompt_version="v2"),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2"),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records_v2_relabeled = merge_records(human_v2_relabeled, judge_v2)

        with pytest.raises(ValueError, match="사람 정답이 다릅니다"):
            compare_versions(records_v1, records_v2_relabeled)

    def test_different_case_content_raises(self, records_v1):
        """사례 본문이 바뀌면(시험 문제가 바뀐 것) judge 개선 효과로 오인하면 안 된다."""
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2", case_content_seed="case_001-rewritten"),
            _judge("case_002", True, prompt_version="v2"),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2"),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)
        with pytest.raises(ValueError, match="사례 본문"):
            compare_versions(records_v1, records_v2)

    def test_different_as_of_date_raises(self, records_v1):
        """기준일이 다르면 case_content_sha256이 같아도(내용이 우연히 동일해도) 잡아야 한다."""
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2", as_of_date="2026-07-15"),
            _judge("case_002", True, prompt_version="v2", as_of_date="2026-07-15"),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2", as_of_date="2026-07-15"),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2", as_of_date="2026-07-15"),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)
        with pytest.raises(ValueError, match="as_of_date"):
            compare_versions(records_v1, records_v2)

    def test_different_strict_citation_gate_raises(self, records_v1):
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2", strict_citation_gate=True),
            _judge("case_002", True, prompt_version="v2", strict_citation_gate=True),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2", strict_citation_gate=True),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2", strict_citation_gate=True),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)
        with pytest.raises(ValueError, match="strict_citation_gate"):
            compare_versions(records_v1, records_v2)


class TestCompareOfficialVersions:
    def test_valid_v1_v2_passes(self):
        v1 = _official_20_records(prompt_version="v1")
        v2 = _official_20_records(prompt_version="v2")
        comparison = compare_official_versions(v1, v2)
        assert comparison.before.total == 20
        assert comparison.after.total == 20

    def test_different_code_sha_is_allowed(self):
        """LLM축 프롬프트가 rubric.py에 하드코딩돼 있어, 진짜 프롬프트 개선이면 code_sha가
        달라지는 게 정상이다 — 이걸 막으면 R2가 요구하는 v1→v2 개선 자체가 불가능해진다."""
        v1 = _official_20_records(prompt_version="v1")
        v2 = [replace(r, code_sha="cafef00d") for r in _official_20_records(prompt_version="v2")]
        comparison = compare_official_versions(v1, v2)
        assert comparison.before.total == 20
        assert comparison.after.total == 20

    def test_identical_prompt_hash_despite_different_prompt_version_raises(self):
        """prompt_version 라벨만 바뀌고 실제 prompt_hash가 20건 전부 동일하면,
        진짜 프롬프트가 안 바뀐 것으로 보고 거부해야 한다."""
        v1 = _official_20_records(prompt_version="v1")
        v2_raw = _official_20_records(prompt_version="v2")
        v1_by_id = {record.case_id: record for record in v1}
        v2 = [replace(record, prompt_hash=v1_by_id[record.case_id].prompt_hash) for record in v2_raw]
        with pytest.raises(ValueError, match="prompt_hash"):
            compare_official_versions(v1, v2)

    def test_single_case_with_identical_prompt_hash_raises(self):
        """20건 중 단 1건만 v1·v2의 prompt_hash가 같아도 거부해야 한다.

        템플릿이 바뀌었다면 case_content_sha256이 이미 v1·v2 동일함을 보장하는
        상태에서 렌더링 결과가 전부 달라지는 게 정상이다 — 일부만 같다는 건
        "라벨만 바뀜"이 아니라 렌더링이 비결정적이라는 이상 신호이므로, 전부
        동일한 경우와 마찬가지로 잡아야 한다(all()이 아니라 any() 논리).
        """
        v1 = _official_20_records(prompt_version="v1")
        v2_raw = _official_20_records(prompt_version="v2")
        v1_by_id = {record.case_id: record for record in v1}
        target_case_id = v2_raw[0].case_id
        v2 = [
            replace(record, prompt_hash=v1_by_id[record.case_id].prompt_hash)
            if record.case_id == target_case_id
            else record
            for record in v2_raw
        ]
        with pytest.raises(ValueError, match=re.escape(target_case_id)):
            compare_official_versions(v1, v2)

    def test_different_model_version_raises(self):
        v1 = _official_20_records(prompt_version="v1")
        v2 = [
            replace(r, model_version={"deployment": "other", "model": "other-model", "api_version": "x"})
            for r in _official_20_records(prompt_version="v2")
        ]
        with pytest.raises(ValueError, match="동일한 model_version"):
            compare_official_versions(v1, v2)

    def test_same_prompt_version_raises(self):
        v1 = _official_20_records(prompt_version="v1")
        v2 = _official_20_records(prompt_version="v1")
        with pytest.raises(ValueError, match="prompt_version이 같습니다"):
            compare_official_versions(v1, v2)

    def test_invalid_case_set_is_rejected_before_comparison(self):
        v1 = _official_20_records(prompt_version="v1")[:-1]  # 19건
        v2 = _official_20_records(prompt_version="v2")
        with pytest.raises(CalibrationSchemaError, match="20건"):
            compare_official_versions(v1, v2)


class TestBuildJudgeResultCrossChecks:
    def test_as_of_date_matching_run_config_is_accepted(self):
        result = build_judge_result(
            case_id="c1",
            judge_output=_fake_judge_output(as_of_date="2026-06-30"),
            trace_id="trace-c1",
            prompt_version="v1",
            code_sha="deadbeef",
            case_content_sha256=_sha256_hex("c1"),
            as_of_date="2026-06-30",
        )
        assert result["as_of_date"] == "2026-06-30"

    def test_as_of_date_mismatching_run_config_raises(self):
        """호출자가 실수로 다른 날짜를 넘기면, judge_output의 실제 실행값과
        대조해 조용히 틀린 값이 감사 기록에 남지 않게 한다."""
        with pytest.raises(CalibrationSchemaError, match="as_of_date"):
            build_judge_result(
                case_id="c1",
                judge_output=_fake_judge_output(as_of_date="2026-06-30"),
                trace_id="trace-c1",
                prompt_version="v1",
                code_sha="deadbeef",
                case_content_sha256=_sha256_hex("c1"),
                as_of_date="2026-07-15",  # 실제 실행값(2026-06-30)과 다름
            )

    def test_as_of_date_missing_from_judge_output_raises(self):
        """judge_output.run_config에 as_of_date가 아예 없으면, 호출자 값만
        조용히 신뢰하지 않고 거부한다."""
        judge_output = _fake_judge_output()
        del judge_output["run_config"]["as_of_date"]
        with pytest.raises(CalibrationSchemaError, match="as_of_date가 없습니다"):
            build_judge_result(
                case_id="c1",
                judge_output=judge_output,
                trace_id="trace-c1",
                prompt_version="v1",
                code_sha="deadbeef",
                case_content_sha256=_sha256_hex("c1"),
                as_of_date="2026-06-30",
            )


class TestJudgeCheckNamesConsistency:
    def test_different_check_names_raises(self, records_v1):
        """RAG routing audit 존재 여부처럼 필수 검사 항목 자체가 v1·v2에서 달라지면 잡아야 한다."""
        extra_check = {
            "name": "citation_routing_contract",
            "passed": True,
            "required": True,
            "detail": "mock routing detail",
        }
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2"),
            _judge("case_002", True, prompt_version="v2"),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2"),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)
        records_v2 = [
            replace(record, judge_checks=(*record.judge_checks, extra_check))
            if record.case_id == "case_001"
            else record
            for record in records_v2
        ]
        with pytest.raises(ValueError, match="이름·required·passed 중"):
            compare_versions(records_v1, records_v2)

    def test_same_check_name_different_passed_raises(self, records_v1):
        """이름은 같아도 시스템 검사의 passed 값이 v1·v2 사이에 다르면 잡아야 한다.

        예: citation_routing_contract가 v1·v2 모두 존재하지만, run_config의
        RAG routing record 내용이 달라져 한쪽만 실패하는 경우. 이름 집합
        비교만으로는 이 차이를 놓친다.
        """

        def _with_routing_check(passed: bool) -> dict:
            return {
                "name": "citation_routing_contract",
                "passed": passed,
                "required": True,
                "detail": "mock routing detail",
            }

        judge_v1 = [
            _judge("case_001", True),
            _judge("case_002", True),
            _judge("case_003", False, ("disclaimer",)),
            _judge("case_004", False, ("numeric_consistency",)),
        ]
        records_v1_with_routing = merge_records(HUMAN_LABELS_V1, judge_v1)
        records_v1_with_routing = [
            replace(record, judge_checks=(*record.judge_checks, _with_routing_check(True)))
            for record in records_v1_with_routing
        ]
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2"),
            _judge("case_002", True, prompt_version="v2"),
            _judge("case_003", False, ("disclaimer",), prompt_version="v2"),
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records_v2 = merge_records(HUMAN_LABELS_V1, judge_v2)
        records_v2 = [
            replace(record, judge_checks=(*record.judge_checks, _with_routing_check(False)))
            for record in records_v2
        ]
        with pytest.raises(ValueError, match="이름·required·passed 중"):
            compare_versions(records_v1_with_routing, records_v2)


def test_expected_case_ids_constant_has_20_entries():
    assert len(EXPECTED_CASE_IDS) == 20
    assert EXPECTED_CASE_IDS == {f"case_{i:03d}" for i in range(1, 21)}


def test_build_judge_result_accepts_real_judge_eval_output(monkeypatch):
    """실제 judge_eval() 반환값이 build_judge_result → normalize_judge_result를 그대로 통과하는지 확인한다.

    스키마가 실제 judge_eval() 계약과 어긋나면(중첩 구조·필드명 변경 등)
    여기서 먼저 깨져야 한다 — mock으로만 만든 JudgeResult는 이런 계약 드리프트를
    잡지 못한다. EC-01은 기존 judge 회귀 평가셋의 결함 없는 기준 사례다.

    model_version_record()를 가짜 함수로 바꿔치기하는 이유: 이 함수는 실제
    Azure 배포 환경변수·LLM 응답 메타데이터에서 deployment를 읽는데, 이
    테스트는 로컬 오프라인 실행이라 둘 다 없어 원래는 전부 None이 나온다(그럼
    normalize_judge_result가 정상적으로 거부한다 — 스키마는 맞다는 뜻). 여기서는
    실제 비밀값을 전혀 읽지 않고, app/llm/audit.py의 with_llm_audit()가 호출하는
    이 함수 하나만 테스트 동안 가짜 값으로 대체해 구조 계약만 검증한다.
    """
    monkeypatch.setattr(
        "app.llm.audit.model_version_record",
        lambda llm=None, responses=(): {
            "deployment": "test-deployment",
            "model": "test-model",
            "api_version": "2026-01-01",
        },
    )
    from app.nodes.judge_eval import judge_eval
    from tests.test_judge_eval_evalset import _PassingLLM, build_eval_case

    case = build_eval_case("EC-01")
    judge_output = judge_eval(case["state"], llm=_PassingLLM())

    raw = build_judge_result(
        case_id="case_smoke_ec01",
        judge_output=judge_output,
        trace_id="trace-smoke-ec01",
        prompt_version="v1",
        code_sha="deadbeef",
        case_content_sha256=_sha256_hex("case_smoke_ec01"),
        as_of_date=case["state"]["run_config"]["as_of_date"],
    )
    result = normalize_judge_result(raw)

    assert result.passed is True
    assert result.fail_axes == ()
    assert result.failed_required_checks == ()
    assert result.judge_attempt == 1
    assert result.strict_citation_gate is False


def test_build_judge_result_accepts_real_judge_eval_failure_output(monkeypatch):
    """실패 경로도 build_judge_result → normalize_judge_result를 통과하는지 확인한다.

    위 테스트(EC-01)는 결함 없는 PASS 사례 하나만 검증한다 — 실제 오판 분석에서
    다룰 건 대부분 FAIL 사례이므로, judge.passed=False·judge_feedback 비어있지
    않음·실패축 보존까지 실제 judge_eval() 출력으로 확인해 둔다. EC-04는 본문
    수치를 metrics와 다르게 바꿔 numeric_consistency를 실패시키는 기존 회귀
    평가셋 사례다.
    """
    monkeypatch.setattr(
        "app.llm.audit.model_version_record",
        lambda llm=None, responses=(): {
            "deployment": "test-deployment",
            "model": "test-model",
            "api_version": "2026-01-01",
        },
    )
    from app.nodes.judge_eval import judge_eval
    from tests.test_judge_eval_evalset import _PassingLLM, build_eval_case

    case = build_eval_case("EC-04")
    judge_output = judge_eval(case["state"], llm=_PassingLLM())

    raw = build_judge_result(
        case_id="case_smoke_ec04",
        judge_output=judge_output,
        trace_id="trace-smoke-ec04",
        prompt_version="v1",
        code_sha="deadbeef",
        case_content_sha256=_sha256_hex("case_smoke_ec04"),
        as_of_date=case["state"]["run_config"]["as_of_date"],
    )
    result = normalize_judge_result(raw)

    assert result.passed is False
    assert "numeric_consistency" in result.fail_axes
    assert result.judge_feedback.strip() != ""
    assert result.judge_attempt == 1
    assert result.strict_citation_gate is False


def test_build_judge_result_extracts_strict_citation_gate_true_from_real_judge_eval(monkeypatch):
    """strict_citation_gate=True 경로가 실제로 자동 추출·기록되는지 확인한다.

    위 두 테스트(EC-01·EC-04)는 둘 다 _base_state()의 기본값(False)이라, 지금까지
    "run_config에서 제대로 뽑아오는가"를 True 값으로는 검증한 적이 없었다. EC-03은
    strict_citation_gate=True로 source_validity를 실패시키는 기존 회귀 평가셋
    사례라, True 경로·자동 추출·엄격 게이트 실패를 한 번에 검증한다.
    """
    monkeypatch.setattr(
        "app.llm.audit.model_version_record",
        lambda llm=None, responses=(): {
            "deployment": "test-deployment",
            "model": "test-model",
            "api_version": "2026-01-01",
        },
    )
    from app.nodes.judge_eval import judge_eval
    from tests.test_judge_eval_evalset import _PassingLLM, build_eval_case

    case = build_eval_case("EC-03")
    judge_output = judge_eval(case["state"], llm=_PassingLLM())

    raw = build_judge_result(
        case_id="case_smoke_ec03",
        judge_output=judge_output,
        trace_id="trace-smoke-ec03",
        prompt_version="v1",
        code_sha="deadbeef",
        case_content_sha256=_sha256_hex("case_smoke_ec03"),
        as_of_date=case["state"]["run_config"]["as_of_date"],
    )
    result = normalize_judge_result(raw)

    assert result.strict_citation_gate is True
    assert result.passed is False
    assert "source_validity" in result.fail_axes
