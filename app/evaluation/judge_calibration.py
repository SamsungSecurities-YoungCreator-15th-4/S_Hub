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

from app.evaluation.calibration_schema import CalibrationRecord, validate_official_case_set
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
    judge_failed_required_checks: tuple[str, ...]  # 6축 밖 시스템 검사 실패
    judge_failed_check_reasons: dict[str, str]  # 위 검사들의 detail


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
        failed_check_reasons = {
            check["name"]: check["detail"]
            for check in record.judge_checks
            if check["name"] in record.judge_failed_required_checks
        }
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
                judge_failed_required_checks=record.judge_failed_required_checks,
                judge_failed_check_reasons=failed_check_reasons,
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
    before_code_sha: str
    after_code_sha: str


def _system_check_signature(record: CalibrationRecord) -> dict[str, tuple[bool, bool]]:
    """judge_checks 중 6축(rubric) 밖의 시스템 검사만 (required, passed)로 요약한다.

    6축 검사는 fail_axes/judge_axis_reasons가 이미 R2의 본 관심사(judge가
    무엇을 놓쳤는가)로 비교하므로 여기서 다시 보지 않는다.
    """
    return {
        check["name"]: (check["required"], check["passed"])
        for check in record.judge_checks
        if check["name"] not in AXIS_NAMES
    }


def _assert_same_evaluation_target(
    before_records: list[CalibrationRecord],
    after_records: list[CalibrationRecord],
) -> None:
    """v1·v2가 같은 정답지·같은 사례 본문으로 채점됐는지 확인한다.

    사람 라벨이 v1·v2 사이에 달라지면, judge가 전혀 개선되지 않아도 라벨이
    바뀐 것만으로 match_rate가 오른 것처럼 계산돼 비교 자체가 무효가 된다.
    사례 본문(case_content_sha256)이 달라지는 것도 같은 문제다 — judge
    프롬프트가 아니라 "시험 문제 자체"가 바뀐 것일 수 있다. as_of_date(기준일)도
    같은 이유로 검사한다 — judge의 disclaimer/numeric_consistency 축이 쓰는
    expected_dates의 재료라 판정에 영향을 주지만, metrics/explanations/citations
    와 물리적으로 분리된 값이라 case_content_sha256만으로는 못 잡을 수 있다.
    strict_citation_gate도 같은 성격이다 — source_validity/citation_content_contract
    의 엄격도를 바꾸는 판정 기준이라, 이게 v1·v2 사이에 달라지면 프롬프트를
    안 고쳐도 PASS 비율이 변한다. 6축 밖 judge_checks(시스템 검사)도 이름·
    required·passed까지 비교한다 — 이름만 같다고 조건이 같다는 보장은 없다.
    예를 들어 citation_routing_contract는 v1·v2 모두 존재하면서도 run_config에
    보존된 RAG routing record 내용이 달라지면 PASS/FAIL이 바뀔 수 있다. 이건
    새 포괄 해시 필드를 만드는 대신 이미 기록된 judge_checks에서 직접
    비교한다(6축 자체는 fail_axes/judge_axis_reasons로 이미 비교하므로 여기서는
    AXIS_NAMES에 속하지 않는 검사만 본다).
    """
    before_by_id = {record.case_id: record for record in before_records}
    after_by_id = {record.case_id: record for record in after_records}
    label_mismatched = sorted(
        case_id
        for case_id, before_record in before_by_id.items()
        if (
            before_record.human_passed != after_by_id[case_id].human_passed
            or before_record.human_fail_axes != after_by_id[case_id].human_fail_axes
        )
    )
    if label_mismatched:
        raise ValueError(
            "v1·v2의 사람 정답이 다릅니다. 같은 case_id는 human_passed·"
            f"human_fail_axes가 같아야 비교할 수 있습니다: {label_mismatched}"
        )
    content_mismatched = sorted(
        case_id
        for case_id, before_record in before_by_id.items()
        if before_record.case_content_sha256 != after_by_id[case_id].case_content_sha256
    )
    if content_mismatched:
        raise ValueError(
            "v1·v2의 사례 본문(case_content_sha256)이 다릅니다. 같은 리포트를 "
            f"채점했는지 확인하세요: {content_mismatched}"
        )
    as_of_date_mismatched = sorted(
        case_id
        for case_id, before_record in before_by_id.items()
        if before_record.as_of_date != after_by_id[case_id].as_of_date
    )
    if as_of_date_mismatched:
        raise ValueError(
            f"v1·v2의 as_of_date(기준일)가 다릅니다: {as_of_date_mismatched}"
        )
    strict_gate_mismatched = sorted(
        case_id
        for case_id, before_record in before_by_id.items()
        if before_record.strict_citation_gate != after_by_id[case_id].strict_citation_gate
    )
    if strict_gate_mismatched:
        raise ValueError(
            f"v1·v2의 strict_citation_gate가 다릅니다: {strict_gate_mismatched}"
        )
    system_checks_mismatched = sorted(
        case_id
        for case_id, before_record in before_by_id.items()
        if (
            _system_check_signature(before_record)
            != _system_check_signature(after_by_id[case_id])
        )
    )
    if system_checks_mismatched:
        raise ValueError(
            "v1·v2에서 6축 밖 시스템 검사(judge_checks)의 이름·required·passed 중 "
            "하나라도 다릅니다(예: RAG routing audit 존재 여부·내용 변화). 같은 조건에서 "
            f"실행했는지 확인하세요: {system_checks_mismatched}"
        )


def compare_versions(
    before_records: list[CalibrationRecord],
    after_records: list[CalibrationRecord],
) -> VersionComparison:
    """동일 case_id·동일 사람 라벨 20건을 v1(before)·v2(after)로 재실행한 결과를 비교한다.

    before_code_sha/after_code_sha를 결과에 싣는 이유: compare_official_versions()
    는 v1·v2의 code_sha 동일성을 더 이상 요구하지 않는다(judge LLM축 프롬프트가
    app/judge/rubric.py에 하드코딩돼 있어, 진짜 프롬프트 개선이면 code_sha가
    바뀌는 게 정상이라서). 그런데 code_sha가 다르면 "프롬프트만 바뀌었다"는
    보장은 없다 — 결정론 축 로직 등 다른 코드가 같이 바뀌었어도 이 함수는
    통과시킨다. 이 사실이 docstring에만 있고 산출물에 없으면 증거를 검토하는
    사람이 v1·v2 코드가 달랐다는 것 자체를 알 수 없으므로, 두 code_sha를 결과에
    그대로 남긴다.
    """
    before_ids = {record.case_id for record in before_records}
    after_ids = {record.case_id for record in after_records}
    if before_ids != after_ids:
        raise ValueError(
            "v1·v2 비교는 동일 case_id 집합에서만 가능합니다. "
            f"v1에만 있음: {sorted(before_ids - after_ids)}, "
            f"v2에만 있음: {sorted(after_ids - before_ids)}"
        )
    _assert_same_evaluation_target(before_records, after_records)
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
        before_code_sha=before_records[0].code_sha,
        after_code_sha=after_records[0].code_sha,
    )


def compare_official_versions(
    before_records: list[CalibrationRecord],
    after_records: list[CalibrationRecord],
    *,
    require_langsmith: bool = True,
) -> VersionComparison:
    """R2 공식 v1·v2 비교 — compare_versions()에 제출 요건 검증을 더한 wrapper.

    각 실행이 validate_official_case_set()을 통과해야 하고(정확히 20건·1차
    판정·run 내부 일관성), v1·v2 사이에서는 model_version이 같고 prompt_version은
    달라야 한다.

    code_sha는 v1·v2 간 동일성을 요구하지 않는다 — 지금 judge의 LLM축
    프롬프트(hallucination/false_precision)는 app/judge/rubric.py에 문자열로
    하드코딩돼 있어, 프롬프트를 실제로 고치는 유일한 방법이 코드 수정이다.
    즉 진짜 개선이면 code_sha가 반드시 달라진다 — 여기서 동일성을 요구하면
    R2가 요구하는 "v1 측정 → 개선 → v2 재측정" 자체를 이 함수가 거부하게 된다.
    대신 prompt_hash가 case_id별로 전부 같은지 확인한다 — prompt_hash는 사례
    payload까지 포함해 렌더링한 프롬프트의 해시라, 템플릿이 조금이라도
    바뀌면 사실상 항상 달라진다. case_content_sha256(사례 본문)은 이미
    v1·v2 동일성이 강제되므로, 템플릿이 바뀌었다면 20건 전부의 prompt_hash가
    달라지는 게 정상이다 — 반대로 템플릿이 그대로면 20건 전부 같다. 그래서
    "일부만 같음"도 "전부 같음"과 마찬가지로 이상 신호다(한 건이라도
    prompt_hash가 우연히 같다면, 같은 본문·같은 조건에서 렌더링이 비결정적이라는
    뜻일 수 있다) — 하나라도 같은 case_id가 있으면 거부한다.
    """
    validate_official_case_set(before_records, require_langsmith=require_langsmith)
    validate_official_case_set(after_records, require_langsmith=require_langsmith)
    before_first, after_first = before_records[0], after_records[0]
    if before_first.model_version != after_first.model_version:
        raise ValueError(
            f"v1·v2는 동일한 model_version으로 실행해야 합니다: "
            f"v1={before_first.model_version}, v2={after_first.model_version}"
        )
    if before_first.prompt_version == after_first.prompt_version:
        raise ValueError(f"v1·v2의 prompt_version이 같습니다({before_first.prompt_version}) — 비교할 변화가 없습니다.")
    before_by_id = {record.case_id: record for record in before_records}
    after_by_id = {record.case_id: record for record in after_records}
    unchanged_prompt_hash_cases = sorted(
        case_id
        for case_id in before_by_id
        if before_by_id[case_id].prompt_hash == after_by_id[case_id].prompt_hash
    )
    if unchanged_prompt_hash_cases:
        raise ValueError(
            "prompt_version은 다르지만 다음 사례는 v1·v2의 prompt_hash가 같습니다 — "
            f"실제 judge 프롬프트가 안 바뀌었거나 렌더링이 비결정적일 수 있습니다: {unchanged_prompt_hash_cases}"
        )
    return compare_versions(before_records, after_records)
