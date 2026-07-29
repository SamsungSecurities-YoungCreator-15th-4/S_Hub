"""R2 캘리브레이션 입력 계약 — 사람 라벨과 judge 실행 결과를 연결하는 SSOT.

이 파일이 R2 "평가·오류 분석" 담당과 "실행·기록" 담당 사이의 인터페이스다.
실행·기록 담당은 아래 HumanLabel·JudgeResult 형태로 파일(JSONL 등)을 만들면
되고, 집계 로직(judge_calibration.py)은 merge_records가 만드는
CalibrationRecord만 소비한다. 필드명·표기를 바꾸면 양쪽이 함께 깨지므로
바꿀 때는 같이 조율한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, TypedDict

from app.judge.axes import to_en
from app.judge.rubric import AXIS_NAMES

Label = Literal["pass", "fail"]


class HumanLabel(TypedDict, total=False):
    """R1 사례집 frontmatter를 그대로 옮긴 사람 정답 레코드.

    필드명·표기는 starter-kit/labeling-guide-template.md §4와 동일해야 한다.
    fail_axes는 한글 축 이름(§4 허용값)이며, label=fail일 때만 채운다.
    """

    id: str
    label: Label
    fail_axes: list[str]
    rationale: str


class JudgeResult(TypedDict, total=False):
    """judge_eval()의 반환값 judge를 사례 단위로 포장한 실행 결과 레코드.

    rubric은 app.nodes.judge_eval.judge_eval()이 반환하는 judge["rubric"]과
    동일한 구조(영문 축 키 → {"passed": bool, "reason": str})다.
    """

    case_id: str
    passed: bool
    reason: str
    rubric: dict[str, dict]
    prompt_version: str
    prompt_hash: str
    model_version: str
    trace_id: str
    code_sha: str


@dataclass(frozen=True)
class CalibrationRecord:
    """사람 라벨과 judge 결과를 case_id로 합친 평가 단위 레코드."""

    case_id: str
    human_passed: bool
    human_fail_axes: tuple[str, ...]
    human_rationale: str
    judge_passed: bool
    judge_fail_axes: tuple[str, ...]
    judge_reason: str
    judge_axis_reasons: dict[str, str]


class CalibrationSchemaError(ValueError):
    """사람 라벨·judge 결과가 이 계약을 위반할 때 발생한다."""


def _normalize_fail_axes(raw_axes: object, *, case_id: str) -> tuple[str, ...]:
    if not isinstance(raw_axes, list):
        raise CalibrationSchemaError(f"{case_id}: fail_axes는 list여야 합니다.")
    axes_en: list[str] = []
    for ko in raw_axes:
        try:
            axes_en.append(to_en(ko))
        except ValueError as exc:
            raise CalibrationSchemaError(f"{case_id}: {exc}") from exc
    return tuple(axes_en)


def normalize_human_label(raw: dict) -> tuple[str, bool, tuple[str, ...], str]:
    """HumanLabel 원본 dict를 (case_id, passed, fail_axes_en, rationale)로 검증·정규화한다."""
    case_id = raw.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise CalibrationSchemaError("사람 라벨에 id가 없습니다.")
    label = raw.get("label")
    if label not in ("pass", "fail"):
        raise CalibrationSchemaError(
            f"{case_id}: label은 pass|fail이어야 합니다 (받은 값: {label!r})."
        )
    fail_axes = _normalize_fail_axes(raw.get("fail_axes") or [], case_id=case_id)
    if label == "pass" and fail_axes:
        raise CalibrationSchemaError(f"{case_id}: label=pass인데 fail_axes가 비어있지 않습니다.")
    if label == "fail" and not fail_axes:
        raise CalibrationSchemaError(f"{case_id}: label=fail인데 fail_axes가 비어있습니다.")
    rationale = str(raw.get("rationale") or "")
    return case_id, label == "pass", fail_axes, rationale


def normalize_judge_result(
    raw: dict,
) -> tuple[str, bool, tuple[str, ...], str, dict[str, str]]:
    """JudgeResult 원본 dict를 (case_id, passed, fail_axes_en, reason, axis_reasons)로 정규화한다."""
    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise CalibrationSchemaError("judge 결과에 case_id가 없습니다.")
    passed = raw.get("passed")
    if not isinstance(passed, bool):
        raise CalibrationSchemaError(f"{case_id}: passed는 bool이어야 합니다.")
    rubric = raw.get("rubric")
    if not isinstance(rubric, dict) or set(rubric) != set(AXIS_NAMES):
        raise CalibrationSchemaError(f"{case_id}: rubric은 6축 {AXIS_NAMES}를 모두 포함해야 합니다.")
    fail_axes: list[str] = []
    axis_reasons: dict[str, str] = {}
    for axis in AXIS_NAMES:
        entry = rubric[axis]
        if not isinstance(entry, dict) or not isinstance(entry.get("passed"), bool):
            raise CalibrationSchemaError(f"{case_id}: rubric[{axis}].passed는 bool이어야 합니다.")
        axis_reasons[axis] = str(entry.get("reason") or "")
        if not entry["passed"]:
            fail_axes.append(axis)
    reason = str(raw.get("reason") or "")
    return case_id, passed, tuple(fail_axes), reason, axis_reasons


def merge_records(
    human_labels: Iterable[dict],
    judge_results: Iterable[dict],
) -> list[CalibrationRecord]:
    """사람 라벨과 judge 결과를 case_id로 합쳐 CalibrationRecord 목록을 만든다.

    두 입력의 case_id 집합이 정확히 같아야 한다 — 한쪽에만 있는 사례가 있으면
    비교가 불완전하므로 조용히 무시하지 않고 즉시 실패한다.
    """
    human_by_id: dict[str, tuple[bool, tuple[str, ...], str]] = {}
    for raw in human_labels:
        case_id, human_passed, human_fail_axes, rationale = normalize_human_label(raw)
        if case_id in human_by_id:
            raise CalibrationSchemaError(f"{case_id}: 사람 라벨이 중복됩니다.")
        human_by_id[case_id] = (human_passed, human_fail_axes, rationale)

    judge_by_id: dict[str, tuple[bool, tuple[str, ...], str, dict[str, str]]] = {}
    for raw in judge_results:
        case_id, judge_passed, judge_fail_axes, reason, axis_reasons = normalize_judge_result(raw)
        if case_id in judge_by_id:
            raise CalibrationSchemaError(f"{case_id}: judge 결과가 중복됩니다.")
        judge_by_id[case_id] = (judge_passed, judge_fail_axes, reason, axis_reasons)

    human_ids = set(human_by_id)
    judge_ids = set(judge_by_id)
    if human_ids != judge_ids:
        raise CalibrationSchemaError(
            "사람 라벨과 judge 결과의 case_id가 일치하지 않습니다. "
            f"judge 결과 누락: {sorted(human_ids - judge_ids)}, "
            f"사람 라벨 누락: {sorted(judge_ids - human_ids)}"
        )

    records = []
    for case_id in sorted(human_ids):
        human_passed, human_fail_axes, rationale = human_by_id[case_id]
        judge_passed, judge_fail_axes, judge_reason, axis_reasons = judge_by_id[case_id]
        records.append(
            CalibrationRecord(
                case_id=case_id,
                human_passed=human_passed,
                human_fail_axes=human_fail_axes,
                human_rationale=rationale,
                judge_passed=judge_passed,
                judge_fail_axes=judge_fail_axes,
                judge_reason=judge_reason,
                judge_axis_reasons=axis_reasons,
            )
        )
    return records
