"""R2 캘리브레이션 스키마·계산 로직 테스트 — 전부 mock 데이터로 검증한다.

실제 R1 사례 20건은 생성형 AI에 입력하지 않는다는 팀 방침에 따라, 이 테스트는
실제 사례 내용을 전혀 참조하지 않는다. case_001~case_004는 여기서만 쓰는
가상 사례이며, 실제 사례집이 도착하면 이 테스트가 아니라 실행 결과 파일이
merge_records에 들어간다.
"""
from __future__ import annotations

import pytest

from app.evaluation.calibration_schema import (
    CalibrationRecord,
    CalibrationSchemaError,
    merge_records,
    normalize_human_label,
    normalize_judge_result,
)
from app.evaluation.judge_calibration import (
    build_confusion_matrix,
    calculate_axis_metrics,
    calculate_overall_metrics,
    compare_versions,
    find_mismatches,
)
from app.judge.rubric import AXIS_NAMES


def _rubric(fail_axes: tuple[str, ...] = ()) -> dict:
    return {axis: {"passed": axis not in fail_axes, "reason": "mock"} for axis in AXIS_NAMES}


def _human(case_id: str, label: str, fail_axes: list[str] | None = None) -> dict:
    return {
        "id": case_id,
        "label": label,
        "fail_axes": fail_axes or [],
        "rationale": f"{case_id} rationale",
    }


def _judge(
    case_id: str,
    passed: bool,
    fail_axes_en: tuple[str, ...] = (),
    *,
    prompt_version: str = "v1",
) -> dict:
    return {
        "case_id": case_id,
        "passed": passed,
        "reason": f"{case_id} judge reason",
        "rubric": _rubric(fail_axes_en),
        "prompt_version": prompt_version,
        "prompt_hash": f"hash-{prompt_version}",
        "model_version": "gpt-mock-2026",
        "trace_id": f"trace-{case_id}-{prompt_version}",
        "code_sha": "deadbeef",
    }


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

    def test_missing_id_raises(self):
        with pytest.raises(CalibrationSchemaError, match="id가 없습니다"):
            normalize_human_label({"label": "pass"})

    def test_invalid_label_raises(self):
        with pytest.raises(CalibrationSchemaError, match="pass\\|fail"):
            normalize_human_label(_human("c1", "FAIL"))

    def test_pass_with_fail_axes_raises(self):
        with pytest.raises(CalibrationSchemaError, match="label=pass"):
            normalize_human_label(_human("c1", "pass", ["출처"]))

    def test_fail_without_fail_axes_raises(self):
        with pytest.raises(CalibrationSchemaError, match="label=fail"):
            normalize_human_label(_human("c1", "fail", []))

    def test_unknown_axis_name_raises(self):
        with pytest.raises(CalibrationSchemaError, match="알 수 없는"):
            normalize_human_label(_human("c1", "fail", ["출 처"]))


class TestNormalizeJudgeResult:
    def test_valid(self):
        result = normalize_judge_result(_judge("c1", False, ("hallucination",)))
        assert result.case_id == "c1"
        assert result.passed is False
        assert result.fail_axes == ("hallucination",)
        assert result.axis_reasons["hallucination"] == "mock"
        assert result.prompt_version == "v1"
        assert result.prompt_hash == "hash-v1"
        assert result.model_version == "gpt-mock-2026"
        assert result.trace_id == "trace-c1-v1"
        assert result.code_sha == "deadbeef"

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

    @pytest.mark.parametrize(
        "field", ["prompt_version", "prompt_hash", "model_version", "trace_id", "code_sha"]
    )
    def test_missing_metadata_field_raises(self, field):
        raw = _judge("c1", True)
        del raw[field]
        with pytest.raises(CalibrationSchemaError, match=field):
            normalize_judge_result(raw)

    @pytest.mark.parametrize(
        "field", ["prompt_version", "prompt_hash", "model_version", "trace_id", "code_sha"]
    )
    def test_blank_metadata_field_raises(self, field):
        raw = _judge("c1", True)
        raw[field] = "   "
        with pytest.raises(CalibrationSchemaError, match=field):
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
        """match_rate만 보면 95%처럼 보이는 케이스도 defect_recall로 실제 탐지력을 드러낸다."""
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
        assert by_id["case_002"].judge_axis_reasons == {"source_validity": "mock"}
        assert by_id["case_003"].judge_axis_reasons == {"disclaimer": "mock"}


class TestCompareVersions:
    def test_v2_fixes_false_negative(self, records_v1):
        human_v2 = HUMAN_LABELS_V1
        judge_v2 = [
            _judge("case_001", True, prompt_version="v2"),
            _judge("case_002", False, ("source_validity",), prompt_version="v2"),  # v2에서 탐지
            _judge("case_003", False, ("disclaimer",), prompt_version="v2"),  # 오탐은 그대로
            _judge("case_004", False, ("numeric_consistency",), prompt_version="v2"),
        ]
        records_v2 = merge_records(human_v2, judge_v2)

        comparison = compare_versions(records_v1, records_v2)

        assert comparison.before.match_rate == 0.5
        assert comparison.after.match_rate == 0.75
        assert comparison.match_rate_delta == 0.25
        assert comparison.false_negative_delta == -1
        assert comparison.false_positive_delta == 0
        assert comparison.axis_after["source_validity"].false_negative == 0
        assert comparison.axis_after["source_validity"].defect_recall == 1.0

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
