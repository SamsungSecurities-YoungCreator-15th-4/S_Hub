"""R2 캘리브레이션 입력 계약 — 사람 라벨과 judge 실행 결과를 연결하는 SSOT.

이 파일이 R2 "평가·오류 분석" 담당과 "실행·기록" 담당 사이의 인터페이스다.
실행·기록 담당은 아래 HumanLabel·JudgeResult 형태로 파일(JSONL 등)을 만들면
되고, 집계 로직(judge_calibration.py)은 merge_records가 만드는
CalibrationRecord만 소비한다. 필드명·표기를 바꾸면 양쪽이 함께 깨지므로
바꿀 때는 같이 조율한다.

judge_eval()의 실제 반환 계약(app/nodes/judge_eval.py)과 감사 기록
(app/llm/audit.py, app/observability/langsmith.py)을 그대로 반영한다:

- ``judge.passed``는 6축 rubric뿐 아니라 preflight 형태 검사·인용 계약 검사
  (예: ``citation_content_contract``)까지 합친 결과다. 그래서 이 스키마는
  rubric 실패(fail_axes)와 그 외 필수 검사 실패(failed_required_checks)를
  분리해서 보존한다 — 어느 쪽 실패인지 합치면 안 된다.
- ``prompt_hash``는 사례 payload까지 포함해 렌더링한 프롬프트의 해시라
  같은 프롬프트 버전이어도 사례마다 값이 다른 게 정상이다. "같은 실행인가"는
  ``prompt_version``/``model_version``/``code_sha``로 확인하고(→
  ``validate_run_consistency``), ``prompt_hash``로 확인하지 않는다.
- ``model_version``은 문자열이 아니라 ``app.llm.audit.model_version_record()``
  가 반환하는 ``{deployment, model, api_version}`` dict다.
- ``trace_id``는 LangSmith run ID가 아니라 내부 상관관계 ID
  (``app.observability.langsmith.prepare_trace_invocation``)다. 실제
  LangSmith 식별자는 별도 필드 ``langsmith_run_id``/``langsmith_trace_url``
  이며, LangSmith가 꺼져 있으면 비어 있을 수 있어 선택 필드로 둔다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal, NamedTuple, TypedDict

from app.judge.axes import to_en
from app.judge.rubric import AXIS_NAMES

Label = Literal["pass", "fail"]

_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

EXPECTED_CASE_COUNT = 20
EXPECTED_CASE_IDS = frozenset(f"case_{i:03d}" for i in range(1, EXPECTED_CASE_COUNT + 1))


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
    """judge_eval() 실행 결과 + 실행 메타데이터를 사례 단위로 포장한 레코드.

    passed/reason/rubric/checks/manual_review_flags는 judge_eval()의 반환값
    judge를 그대로 옮긴다. judge_attempt는 judge_retries를(재시도 상한 소진
    전 첫 판정인지 구분하기 위해 이름을 명확히 함), judge_feedback도 그대로
    옮긴다. case_content_sha256은 이번 판정에 쓰인 사례 리포트 본문의
    SHA-256이며, 실행·기록 담당이 로컬에서 계산해 채운다(본문 자체는 전달하지
    않는다).
    """

    case_id: str
    passed: bool
    reason: str
    rubric: dict[str, dict]
    checks: list[dict]
    judge_attempt: int
    judge_feedback: str
    manual_review_flags: list[str]
    prompt_version: str
    prompt_hash: str
    model_version: dict
    trace_id: str
    langsmith_run_id: str | None
    langsmith_trace_url: str | None
    code_sha: str
    case_content_sha256: str


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
    judge_checks: tuple[dict, ...]
    judge_failed_required_checks: tuple[str, ...]
    judge_attempt: int
    judge_feedback: str
    manual_review_flags: tuple[str, ...]
    prompt_version: str
    prompt_hash: str
    model_version: dict
    trace_id: str
    langsmith_run_id: str | None
    langsmith_trace_url: str | None
    code_sha: str
    case_content_sha256: str


class CalibrationSchemaError(ValueError):
    """사람 라벨·judge 결과가 이 계약을 위반할 때 발생한다."""


def _normalize_fail_axes(raw_axes: object, *, case_id: str) -> tuple[str, ...]:
    if not isinstance(raw_axes, list):
        raise CalibrationSchemaError(f"{case_id}: fail_axes는 list여야 합니다.")
    axes_en: set[str] = set()
    for ko in raw_axes:
        if not isinstance(ko, str):
            raise CalibrationSchemaError(f"{case_id}: fail_axes 원소는 문자열이어야 합니다 (받은 값: {ko!r}).")
        try:
            en = to_en(ko)
        except ValueError as exc:
            raise CalibrationSchemaError(f"{case_id}: {exc}") from exc
        if en in axes_en:
            raise CalibrationSchemaError(f"{case_id}: fail_axes에 '{ko}'가 중복됩니다.")
        axes_en.add(en)
    # AXIS_NAMES 순서로 정규화한다 — 입력 순서가 달라도 같은 정답이면 같은
    # tuple이 나와야 compare_versions()의 동일성 비교가 순서에 흔들리지 않는다.
    return tuple(axis for axis in AXIS_NAMES if axis in axes_en)


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
    if "fail_axes" not in raw:
        raise CalibrationSchemaError(f"{case_id}: fail_axes 필드가 없습니다.")
    fail_axes = _normalize_fail_axes(raw["fail_axes"], case_id=case_id)
    if label == "pass" and fail_axes:
        raise CalibrationSchemaError(f"{case_id}: label=pass인데 fail_axes가 비어있지 않습니다.")
    if label == "fail" and not fail_axes:
        raise CalibrationSchemaError(f"{case_id}: label=fail인데 fail_axes가 비어있습니다.")
    rationale = raw.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise CalibrationSchemaError(f"{case_id}: rationale은 비어있지 않은 문자열이어야 합니다.")
    return case_id, label == "pass", fail_axes, rationale


class NormalizedJudgeResult(NamedTuple):
    """normalize_judge_result()의 반환값. 필드가 많아 위치 기반 tuple 대신 이름으로 접근한다."""

    case_id: str
    passed: bool
    fail_axes: tuple[str, ...]
    reason: str
    axis_reasons: dict[str, str]
    checks: tuple[dict, ...]
    failed_required_checks: tuple[str, ...]
    judge_attempt: int
    judge_feedback: str
    manual_review_flags: tuple[str, ...]
    prompt_version: str
    prompt_hash: str
    model_version: dict
    trace_id: str
    langsmith_run_id: str | None
    langsmith_trace_url: str | None
    code_sha: str
    case_content_sha256: str


def _require_nonempty_str(raw: dict, key: str, *, case_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CalibrationSchemaError(
            f"{case_id}: {key}는 비어있지 않은 문자열이어야 합니다 "
            "(재현성·감사 추적에 필요합니다)."
        )
    return value


def _require_pattern(raw: dict, key: str, pattern: re.Pattern, *, case_id: str, hint: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise CalibrationSchemaError(f"{case_id}: {key}는 {hint}여야 합니다.")
    return value.lower()


def _optional_nonempty_str(raw: dict, key: str, *, case_id: str) -> str | None:
    if key not in raw or raw[key] is None:
        return None
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise CalibrationSchemaError(f"{case_id}: {key}는 None이거나 비어있지 않은 문자열이어야 합니다.")
    return value


def _require_model_version(raw: dict, *, case_id: str) -> dict:
    value = raw.get("model_version")
    if not isinstance(value, dict):
        raise CalibrationSchemaError(
            f"{case_id}: model_version은 dict여야 합니다 "
            "(app.llm.audit.model_version_record()의 {deployment, model, api_version} 구조)."
        )
    for key in ("deployment", "model", "api_version"):
        if key not in value:
            raise CalibrationSchemaError(f"{case_id}: model_version에 {key} 키가 없습니다.")
    if not value.get("deployment") and not value.get("model"):
        raise CalibrationSchemaError(f"{case_id}: model_version.deployment·model이 둘 다 비어 있습니다.")
    return value


def _normalize_checks(raw_checks: object, *, case_id: str) -> tuple[dict, ...]:
    if not isinstance(raw_checks, list) or not raw_checks:
        raise CalibrationSchemaError(f"{case_id}: checks는 비어있지 않은 list여야 합니다.")
    normalized: list[dict] = []
    for check in raw_checks:
        if not isinstance(check, dict):
            raise CalibrationSchemaError(f"{case_id}: checks 원소는 dict여야 합니다.")
        name, passed, required, detail = (
            check.get("name"),
            check.get("passed"),
            check.get("required"),
            check.get("detail"),
        )
        if not isinstance(name, str) or not name:
            raise CalibrationSchemaError(f"{case_id}: checks[].name이 비어있습니다.")
        if not isinstance(passed, bool):
            raise CalibrationSchemaError(f"{case_id}: checks[{name}].passed는 bool이어야 합니다.")
        if not isinstance(required, bool):
            raise CalibrationSchemaError(f"{case_id}: checks[{name}].required는 bool이어야 합니다.")
        if not isinstance(detail, str) or not detail.strip():
            raise CalibrationSchemaError(f"{case_id}: checks[{name}].detail은 비어있지 않은 문자열이어야 합니다.")
        normalized.append({"name": name, "passed": passed, "required": required, "detail": detail})
    return tuple(normalized)


def normalize_judge_result(raw: dict) -> NormalizedJudgeResult:
    """JudgeResult 원본 dict를 검증·정규화해 NormalizedJudgeResult로 반환한다."""
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
        axis_reason = entry.get("reason")
        if not isinstance(axis_reason, str) or not axis_reason.strip():
            raise CalibrationSchemaError(f"{case_id}: rubric[{axis}].reason은 비어있지 않은 문자열이어야 합니다.")
        axis_reasons[axis] = axis_reason
        if not entry["passed"]:
            fail_axes.append(axis)
    fail_axes_t = tuple(fail_axes)

    checks = _normalize_checks(raw.get("checks"), case_id=case_id)
    failed_required_checks = tuple(
        sorted(
            check["name"]
            for check in checks
            if check["required"] and not check["passed"] and check["name"] not in AXIS_NAMES
        )
    )

    # judge_eval()은 passed = (모든 required 검사 통과)로 정의한다(preflight +
    # rubric 전부 포함). 그래서 passed와 fail_axes·failed_required_checks는
    # 서로 모순될 수 없다 — 모순되면 입력이 조작·손상된 것으로 보고 거부한다.
    if passed and (fail_axes_t or failed_required_checks):
        raise CalibrationSchemaError(
            f"{case_id}: passed=true인데 실패한 축·필수 검사가 있습니다 "
            f"(fail_axes={fail_axes_t}, failed_required_checks={failed_required_checks})."
        )
    if not passed and not fail_axes_t and not failed_required_checks:
        raise CalibrationSchemaError(f"{case_id}: passed=false인데 실패 원인(축·필수 검사)이 하나도 없습니다.")

    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise CalibrationSchemaError(f"{case_id}: reason은 비어있지 않은 문자열이어야 합니다.")

    judge_feedback = raw.get("judge_feedback")
    if passed:
        judge_feedback = judge_feedback if isinstance(judge_feedback, str) else ""
    elif not isinstance(judge_feedback, str) or not judge_feedback.strip():
        raise CalibrationSchemaError(f"{case_id}: passed=false면 judge_feedback이 비어있지 않아야 합니다.")

    manual_review_flags_raw = raw.get("manual_review_flags") or []
    if not isinstance(manual_review_flags_raw, list) or not all(
        isinstance(flag, str) for flag in manual_review_flags_raw
    ):
        raise CalibrationSchemaError(f"{case_id}: manual_review_flags는 문자열 list여야 합니다.")

    judge_attempt = raw.get("judge_attempt")
    if isinstance(judge_attempt, bool) or not isinstance(judge_attempt, int) or judge_attempt < 1:
        raise CalibrationSchemaError(f"{case_id}: judge_attempt는 1 이상 정수여야 합니다.")

    return NormalizedJudgeResult(
        case_id=case_id,
        passed=passed,
        fail_axes=fail_axes_t,
        reason=reason,
        axis_reasons=axis_reasons,
        checks=checks,
        failed_required_checks=failed_required_checks,
        judge_attempt=judge_attempt,
        judge_feedback=judge_feedback,
        manual_review_flags=tuple(manual_review_flags_raw),
        prompt_version=_require_nonempty_str(raw, "prompt_version", case_id=case_id),
        prompt_hash=_require_pattern(
            raw, "prompt_hash", _SHA256_HEX_RE, case_id=case_id, hint="64자리 SHA-256 16진 문자열"
        ),
        model_version=_require_model_version(raw, case_id=case_id),
        trace_id=_require_nonempty_str(raw, "trace_id", case_id=case_id),
        langsmith_run_id=_optional_nonempty_str(raw, "langsmith_run_id", case_id=case_id),
        langsmith_trace_url=_optional_nonempty_str(raw, "langsmith_trace_url", case_id=case_id),
        code_sha=_require_pattern(raw, "code_sha", _GIT_SHA_RE, case_id=case_id, hint="7~40자리 git SHA(16진)"),
        case_content_sha256=_require_pattern(
            raw, "case_content_sha256", _SHA256_HEX_RE, case_id=case_id, hint="64자리 SHA-256 16진 문자열"
        ),
    )


def merge_records(
    human_labels: Iterable[dict],
    judge_results: Iterable[dict],
) -> list[CalibrationRecord]:
    """사람 라벨과 judge 결과를 case_id로 합쳐 CalibrationRecord 목록을 만든다.

    두 입력의 case_id 집합이 정확히 같아야 한다 — 한쪽에만 있는 사례가 있으면
    비교가 불완전하므로 조용히 무시하지 않고 즉시 실패한다. 이 함수는 개수·ID
    형식을 강제하지 않는다(mock 데이터 개발 용도) — R2 공식 제출 전에는
    validate_official_case_set()을 별도로 호출한다.
    """
    human_by_id: dict[str, tuple[bool, tuple[str, ...], str]] = {}
    for raw in human_labels:
        case_id, human_passed, human_fail_axes, rationale = normalize_human_label(raw)
        if case_id in human_by_id:
            raise CalibrationSchemaError(f"{case_id}: 사람 라벨이 중복됩니다.")
        human_by_id[case_id] = (human_passed, human_fail_axes, rationale)

    judge_by_id: dict[str, NormalizedJudgeResult] = {}
    for raw in judge_results:
        judge_result = normalize_judge_result(raw)
        if judge_result.case_id in judge_by_id:
            raise CalibrationSchemaError(f"{judge_result.case_id}: judge 결과가 중복됩니다.")
        judge_by_id[judge_result.case_id] = judge_result

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
        j = judge_by_id[case_id]
        records.append(
            CalibrationRecord(
                case_id=case_id,
                human_passed=human_passed,
                human_fail_axes=human_fail_axes,
                human_rationale=rationale,
                judge_passed=j.passed,
                judge_fail_axes=j.fail_axes,
                judge_reason=j.reason,
                judge_axis_reasons=j.axis_reasons,
                judge_checks=j.checks,
                judge_failed_required_checks=j.failed_required_checks,
                judge_attempt=j.judge_attempt,
                judge_feedback=j.judge_feedback,
                manual_review_flags=j.manual_review_flags,
                prompt_version=j.prompt_version,
                prompt_hash=j.prompt_hash,
                model_version=j.model_version,
                trace_id=j.trace_id,
                langsmith_run_id=j.langsmith_run_id,
                langsmith_trace_url=j.langsmith_trace_url,
                code_sha=j.code_sha,
                case_content_sha256=j.case_content_sha256,
            )
        )
    return records


def validate_run_consistency(records: list[CalibrationRecord]) -> None:
    """한 번의 공식 실행(run) 안에서 prompt_version·model_version·code_sha가 전부 같은지 확인한다.

    prompt_hash·case_content_sha256·trace_id는 사례마다 달라지는 게 정상이므로
    여기서 검사하지 않는다 — 이 함수는 "같은 실행인가"를 증명하고, 그 값들은
    compare_versions()가 "같은 사례인가"를 증명하는 데 쓴다.
    """
    if not records:
        raise ValueError("records가 비어 있습니다.")
    first = records[0]
    mismatched = sorted(
        record.case_id
        for record in records[1:]
        if (
            record.prompt_version != first.prompt_version
            or record.model_version != first.model_version
            or record.code_sha != first.code_sha
        )
    )
    if mismatched:
        raise CalibrationSchemaError(
            "한 실행(run) 안에서는 prompt_version·model_version·code_sha가 전부 같아야 합니다. "
            f"{first.case_id}과(와) 다른 사례: {mismatched}"
        )


def validate_official_case_set(records: list[CalibrationRecord]) -> None:
    """R2 공식 제출 실행인지 엄격 검증한다. mock/부분 데이터 개발에는 쓰지 않는다."""
    ids = {record.case_id for record in records}
    if ids != EXPECTED_CASE_IDS:
        raise CalibrationSchemaError(
            f"공식 사례집은 정확히 {sorted(EXPECTED_CASE_IDS)} {EXPECTED_CASE_COUNT}건이어야 합니다. "
            f"누락: {sorted(EXPECTED_CASE_IDS - ids)}, 초과: {sorted(ids - EXPECTED_CASE_IDS)}"
        )
    non_first_attempt = sorted(record.case_id for record in records if record.judge_attempt != 1)
    if non_first_attempt:
        raise CalibrationSchemaError(
            "공식 성능 비교는 judge 1차 판정만 사용해야 합니다(재작성 루프를 거친 결과는 "
            f"섞으면 안 됩니다). judge_attempt != 1인 사례: {non_first_attempt}"
        )
    validate_run_consistency(records)
    uncovered_axes = [
        axis for axis in AXIS_NAMES if not any(axis in record.human_fail_axes for record in records)
    ]
    if uncovered_axes:
        raise CalibrationSchemaError(f"6축 전부 결함 사례가 최소 1건 있어야 합니다. 누락된 축: {uncovered_axes}")
