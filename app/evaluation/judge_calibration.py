"""사람 정답과 judge 실행 결과의 일치율·혼동행렬·6축 분석 — 순수 계산 로직.

실행·기록 담당이 만드는 CalibrationRecord 목록(calibration_schema.merge_records
참조)을 입력으로 받는다. 이 모듈은 judge를 호출하지 않고 이미 나온 결과만
집계하므로 실제 R1 사례 20건 없이도 mock 데이터로 전부 검증할 수 있다.

혼동행렬 정의는 사람의 fail을 "결함(위험) positive"로 둔다:
- false_negative = 사람 fail, judge pass → 결함을 놓침(가장 위험)
- false_positive = 사람 pass, judge fail → 정상을 과잉 차단
"""
from __future__ import annotations

from dataclasses import dataclass

from app.evaluation.calibration_schema import CalibrationRecord
from app.judge.axes import to_ko
from app.judge.rubric import AXIS_NAMES


@dataclass(frozen=True)
class OverallMetrics:
    total: int
    match: int
    match_rate: float
    true_positive: int
    true_negative: int
    false_negative: int
    false_positive: int


def calculate_overall_metrics(records: list[CalibrationRecord]) -> OverallMetrics:
    if not records:
        raise ValueError("records가 비어 있습니다.")
    tp = tn = fn = fp = 0
    for record in records:
        human_fail = not record.human_passed
        judge_fail = not record.judge_passed
        if human_fail and judge_fail:
            tp += 1
        elif not human_fail and not judge_fail:
            tn += 1
        elif human_fail and not judge_fail:
            fn += 1
        else:
            fp += 1
    total = len(records)
    return OverallMetrics(
        total=total,
        match=tp + tn,
        match_rate=round((tp + tn) / total, 4),
        true_positive=tp,
        true_negative=tn,
        false_negative=fn,
        false_positive=fp,
    )


def build_confusion_matrix(records: list[CalibrationRecord]) -> dict[str, dict[str, int]]:
    metrics = calculate_overall_metrics(records)
    return {
        "human_pass": {
            "judge_pass": metrics.true_negative,
            "judge_fail": metrics.false_positive,
        },
        "human_fail": {
            "judge_pass": metrics.false_negative,
            "judge_fail": metrics.true_positive,
        },
    }


@dataclass(frozen=True)
class AxisMetrics:
    """축 하나의 성능. match_rate는 결함이 드물면 과장되므로 defect_recall을 같이 본다.

    예: 20건 중 해당 축 결함이 1건뿐이고 judge가 그 1건을 놓치면
    match_rate=19/20=95%지만 defect_recall=0/1=0%다 — "축 성능 95%"만
    발표하면 안 되는 이유가 이 값이다.
    """

    axis: str
    axis_ko: str
    total: int
    match: int
    match_rate: float
    true_positive: int
    true_negative: int
    false_negative: int
    false_positive: int
    human_fail_support: int  # 사람이 이 축을 fail로 지정한 건수 (tp + fn)
    human_pass_support: int  # 사람이 이 축을 fail로 지정하지 않은 건수 (tn + fp)
    defect_recall: float | None  # tp / human_fail_support, 결함이 0건이면 None


def calculate_axis_metrics(records: list[CalibrationRecord]) -> dict[str, AxisMetrics]:
    if not records:
        raise ValueError("records가 비어 있습니다.")
    total = len(records)
    result: dict[str, AxisMetrics] = {}
    for axis in AXIS_NAMES:
        tp = tn = fn = fp = 0
        for record in records:
            human_fail_axis = axis in record.human_fail_axes
            judge_fail_axis = axis in record.judge_fail_axes
            if human_fail_axis and judge_fail_axis:
                tp += 1
            elif not human_fail_axis and not judge_fail_axis:
                tn += 1
            elif human_fail_axis and not judge_fail_axis:
                fn += 1
            else:
                fp += 1
        human_fail_support = tp + fn
        human_pass_support = tn + fp
        result[axis] = AxisMetrics(
            axis=axis,
            axis_ko=to_ko(axis),
            total=total,
            match=tp + tn,
            match_rate=round((tp + tn) / total, 4),
            true_positive=tp,
            true_negative=tn,
            false_negative=fn,
            false_positive=fp,
            human_fail_support=human_fail_support,
            human_pass_support=human_pass_support,
            defect_recall=round(tp / human_fail_support, 4) if human_fail_support else None,
        )
    return result


@dataclass(frozen=True)
class Mismatch:
    """오판 사례 1건. axis_mismatch는 최종 판정이 맞아도 축 판단이 다르면 채워진다."""

    case_id: str
    error_type: str  # "false_negative" | "false_positive" | "axis_mismatch_only"
    human_fail_axes: tuple[str, ...]
    judge_fail_axes: tuple[str, ...]
    axis_mismatch: tuple[str, ...]
    judge_reason: str
    human_rationale: str
    judge_axis_reasons: dict[str, str]  # axis_mismatch 축만. 오판 원인 분석용


def find_mismatches(records: list[CalibrationRecord]) -> list[Mismatch]:
    mismatches: list[Mismatch] = []
    for record in records:
        human_fail = not record.human_passed
        judge_fail = not record.judge_passed
        axis_mismatch = tuple(
            axis
            for axis in AXIS_NAMES
            if (axis in record.human_fail_axes) != (axis in record.judge_fail_axes)
        )
        if human_fail == judge_fail and not axis_mismatch:
            continue
        if human_fail and not judge_fail:
            error_type = "false_negative"
        elif not human_fail and judge_fail:
            error_type = "false_positive"
        else:
            error_type = "axis_mismatch_only"
        mismatches.append(
            Mismatch(
                case_id=record.case_id,
                error_type=error_type,
                human_fail_axes=record.human_fail_axes,
                judge_fail_axes=record.judge_fail_axes,
                axis_mismatch=axis_mismatch,
                judge_reason=record.judge_reason,
                human_rationale=record.human_rationale,
                judge_axis_reasons={
                    axis: record.judge_axis_reasons[axis] for axis in axis_mismatch
                },
            )
        )
    return mismatches


@dataclass(frozen=True)
class VersionComparison:
    before: OverallMetrics
    after: OverallMetrics
    match_rate_delta: float
    false_negative_delta: int
    false_positive_delta: int
    axis_before: dict[str, AxisMetrics]
    axis_after: dict[str, AxisMetrics]


def _assert_matching_human_labels(
    before_records: list[CalibrationRecord],
    after_records: list[CalibrationRecord],
) -> None:
    """v1·v2가 같은 정답지로 채점됐는지 확인한다.

    사람 라벨이 v1·v2 사이에 달라지면, judge가 전혀 개선되지 않아도 라벨이
    바뀐 것만으로 match_rate가 오른 것처럼 계산돼 비교 자체가 무효가 된다.
    """
    before_by_id = {record.case_id: record for record in before_records}
    after_by_id = {record.case_id: record for record in after_records}
    mismatched = sorted(
        case_id
        for case_id, before_record in before_by_id.items()
        if (
            before_record.human_passed != after_by_id[case_id].human_passed
            or before_record.human_fail_axes != after_by_id[case_id].human_fail_axes
        )
    )
    if mismatched:
        raise ValueError(
            "v1·v2의 사람 정답이 다릅니다. 같은 case_id는 human_passed·"
            f"human_fail_axes가 같아야 비교할 수 있습니다: {mismatched}"
        )


def compare_versions(
    before_records: list[CalibrationRecord],
    after_records: list[CalibrationRecord],
) -> VersionComparison:
    """동일 case_id·동일 사람 라벨 20건을 v1(before)·v2(after)로 재실행한 결과를 비교한다."""
    before_ids = {record.case_id for record in before_records}
    after_ids = {record.case_id for record in after_records}
    if before_ids != after_ids:
        raise ValueError(
            "v1·v2 비교는 동일 case_id 집합에서만 가능합니다. "
            f"v1에만 있음: {sorted(before_ids - after_ids)}, "
            f"v2에만 있음: {sorted(after_ids - before_ids)}"
        )
    _assert_matching_human_labels(before_records, after_records)
    before = calculate_overall_metrics(before_records)
    after = calculate_overall_metrics(after_records)
    return VersionComparison(
        before=before,
        after=after,
        match_rate_delta=round(after.match_rate - before.match_rate, 4),
        false_negative_delta=after.false_negative - before.false_negative,
        false_positive_delta=after.false_positive - before.false_positive,
        axis_before=calculate_axis_metrics(before_records),
        axis_after=calculate_axis_metrics(after_records),
    )
