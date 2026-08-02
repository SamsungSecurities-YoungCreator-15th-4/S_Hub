"""감사 증거 묶음(evidence bundle)의 계약 SSOT.

번들 파일명·필수 키·"근거 없음" 표기 방식을 이 파일 하나에서 정한다.
스크립트(`scripts/make_evidence_bundle.py`)와 테스트는 여기 선언된 상수만 쓰고
문자열을 따로 하드코딩하지 않는다.

두 가지 원칙을 계약으로 못박는다.

1. **없음과 안 채움을 구분한다** — 상태에 값이 없으면 조용히 비우지 않고
   `unavailable(...)`로 사유와 원본 키 경로를 남긴다.
2. **키 이름을 새로 만들지 않는다** — hard stop 관련 키는
   `app/nodes/manual_review_gate.py`가 실제로 기록하는 이름을 그대로 옮긴다.
   번들이 파생시킨 값(`blocked` 등)은 `derived_from`에 근거 경로를 함께 적는다.
"""
from __future__ import annotations

from typing import Any, TypedDict

from app.judge.axes import AXIS_EN_TO_KO
from app.utils.hashing import sha256_of_dict

BUNDLE_SCHEMA_VERSION = "1.1"

# --- 파일명 ---------------------------------------------------------------
MANIFEST_FILENAME = "manifest.json"
SUMMARY_FILENAME = "summary.md"
TRACE_FILENAME = "trace.json"
JUDGE_RATIONALE_FILENAME = "judge_rationale.json"
CITATION_VERIFICATION_FILENAME = "citation_verification.json"
HARD_STOP_RECORD_FILENAME = "hard_stop_record.json"
REPLAY_DIFF_FILENAME = "replay_diff.json"
LLM_AUDIT_FILENAME = "llm_audit.json"
CALIBRATION_FILENAME = "calibration_summary.json"
BUNDLE_HASH_FILENAME = "bundle_hash.txt"

#: manifest에 sha256이 기록되는 대상. manifest 자신과 bundle_hash는 제외한다
#: (manifest는 이들을 담는 그릇이고, bundle_hash는 manifest의 해시라서 순환한다).
HASHED_FILENAMES = (
    SUMMARY_FILENAME,
    TRACE_FILENAME,
    JUDGE_RATIONALE_FILENAME,
    CITATION_VERIFICATION_FILENAME,
    HARD_STOP_RECORD_FILENAME,
    REPLAY_DIFF_FILENAME,
    LLM_AUDIT_FILENAME,
    CALIBRATION_FILENAME,
)

#: 번들 디렉터리에 반드시 생성되는 전체 파일 목록.
BUNDLE_FILENAMES = (MANIFEST_FILENAME, *HASHED_FILENAMES, BUNDLE_HASH_FILENAME)


# --- "근거 없음" 표기 -------------------------------------------------------
def unavailable(source_path: str, **extra: Any) -> dict:
    """상태에 값이 없음을 명시한다. 조용한 누락과 구분하기 위한 유일한 통로."""
    return {"available": False, "reason": f"{source_path} 없음", **extra}


# --- manifest --------------------------------------------------------------
class GeneratedBy(TypedDict):
    script: str
    git_sha: Any  # str | dict — git 조회 실패 시 unavailable(...) 형태


class Manifest(TypedDict):
    schema_version: str
    run_id: str
    generated_at: str
    generated_by: GeneratedBy
    files: dict[str, str]


MANIFEST_REQUIRED_KEYS = (
    "schema_version",
    "run_id",
    "generated_at",
    "generated_by",
    "files",
)


# --- trace -----------------------------------------------------------------
class TraceRecord(TypedDict):
    trace_id: Any
    langsmith_trace_url: Any
    langsmith_trace_urls: Any
    langsmith_project: Any
    node_execution_order: Any


TRACE_REQUIRED_KEYS = (
    "trace_id",
    "langsmith_trace_url",
    "langsmith_trace_urls",
    "langsmith_project",
    "node_execution_order",
)


# --- judge 판정 사유 --------------------------------------------------------
class JudgeRationale(TypedDict):
    passed: Any
    reason: Any
    score: Any
    judge_retries: Any
    judge_max_retries: Any
    checks: Any
    rubric: Any
    manual_review_flags: Any
    judge_feedback: Any


JUDGE_RATIONALE_REQUIRED_KEYS = (
    "passed",
    "reason",
    "score",
    "judge_retries",
    "judge_max_retries",
    "checks",
    "rubric",
    "manual_review_flags",
    "judge_feedback",
)


# --- 인용 검증 --------------------------------------------------------------
class CitationVerification(TypedDict):
    citation_count: Any
    verified_citation_count: Any
    citations: Any
    rejected_citations: Any


CITATION_VERIFICATION_REQUIRED_KEYS = (
    "citation_count",
    "verified_citation_count",
    "citations",
    "rejected_citations",
)


# --- hard stop 기록 ---------------------------------------------------------
#: `app/nodes/manual_review_gate.py`가 `report.governance.manual_review_gate`에
#: 실제로 기록하는 키. 이름을 바꾸지 않고 그대로 옮긴다.
MANUAL_REVIEW_GATE_KEYS = (
    "status",
    "trigger",
    "policy_version",
    "trace_id",
    "stopped_at",
    "stopped_at_basis",
    "judge_passed",
    "judge_retries",
    "judge_max_retries",
    "failed_axes",
    "computation_hash",
    "decision_hash",
)

#: hard stop 기록이 상태에서 값을 읽어오는 원본 경로. 감사자가 번들의 모든 값을
#: 원본 state 키로 되짚을 수 있도록 파일에 함께 싣는다.
HARD_STOP_SOURCE_PATHS = {
    "report_status": "report.status",
    "report_finalized": "report.finalized",
    "confirmation_allowed": "report.governance.confirmation_allowed",
    "export_allowed": "report.governance.export_allowed",
    "manual_review_required": "report.governance.manual_review_required",
    "confirmation_blocked_reason": "report.governance.confirmation_blocked_reason",
    "manual_review_gate": "report.governance.manual_review_gate",
}

#: `blocked`은 상태에 존재하는 키가 아니라 번들이 파생시킨 값이다.
#: 성공 실행에서도 파일을 반드시 만들기 위해 필요하며, 근거 경로를 함께 적는다.
BLOCKED_DERIVED_FROM = "report.governance.manual_review_gate.status == 'blocked'"


class HardStopRecord(TypedDict):
    blocked: bool
    blocked_derived_from: str
    report_status: Any
    report_finalized: Any
    confirmation_allowed: Any
    export_allowed: Any
    manual_review_required: Any
    confirmation_blocked_reason: Any
    manual_review_gate: Any
    source_paths: dict[str, str]


HARD_STOP_RECORD_REQUIRED_KEYS = (
    "blocked",
    "blocked_derived_from",
    "report_status",
    "report_finalized",
    "confirmation_allowed",
    "export_allowed",
    "manual_review_required",
    "confirmation_blocked_reason",
    "manual_review_gate",
    "source_paths",
)


# --- 재실행 해시 대조 -------------------------------------------------------
class ReplayDiff(TypedDict):
    status: str
    hashes: Any
    note: str


REPLAY_DIFF_REQUIRED_KEYS = ("status", "hashes", "note")

#: 1회 실행분의 해시만 싣는 자리표시다. run_graph.py 배선(#148)은 번들을 자동
#: 생성할 뿐 2회 실행 대조를 하지 않으므로, 이 표시는 R5 재현 검증에서 채워질
#: 때까지 유지한다 — 번들이 "재현 증명까지 완료"로 읽히면 안 된다.
REPLAY_DIFF_PLACEHOLDER_STATUS = "single_run_only"
REPLAY_DIFF_PLACEHOLDER_NOTE = (
    "이 번들은 1회 실행분 해시만 기록한다. 동일 입력 2회 실행 대조는 아직 "
    "수행되지 않았으므로 재현성이 증명된 것이 아니다. R5 재현 검증에서 채운다."
)


# --- LLM 감사 ---------------------------------------------------------------
class LLMAudit(TypedDict):
    prompt_hash: Any
    model_version: Any
    ips_extraction_meta: Any
    raw_prompt_and_response: Any


LLM_AUDIT_REQUIRED_KEYS = (
    "prompt_hash",
    "model_version",
    "ips_extraction_meta",
    "raw_prompt_and_response",
)

#: 프롬프트·응답 원문이 상태에 없는 것은 결함이 아니라 `app/llm/audit.py`의
#: 의도된 설계("비밀값 없이 기록")다. 번들은 그 사실과 복원 경로를 명시한다.
RAW_LLM_UNAVAILABLE_REASON = (
    "state에 LLM 프롬프트·응답 원문 미저장 (감사는 해시 기반)"
)
RAW_LLM_RECOVERY_NOTE = "레포의 해당 커밋에서 프롬프트 원문 복원 가능"
RAW_LLM_OBSERVABILITY = "응답 원문 관측은 LangSmith trace 담당"


# --- calibration 요약 (R2 계약) ---------------------------------------------
#: 축 키는 문자열을 새로 만들지 않고 app/judge/axes.py의 영문 키를 그대로 쓴다.
#:
#: #137 최초 제안은 사람이 채우는 빈 골격(`None` 자리표시)이었고 top-level에
#: agreement·false_negative·false_positive를 따로 뒀다. #137 리뷰(다경) 지적대로
#: 이 값들은 confusion_matrix의 파생값이라 두 곳에 손으로 적으면 한쪽만 고쳐져
#: 어긋날 수 있다 — 감사 증거에서는 치명적이다. 그래서 빈 골격을 없애고,
#: `calibration_summary()`가 #136이 병합한 `app/evaluation/`의 집계 결과에서
#: 전량 계산해 채우는 구조로 바꿨다. 사람이 채울 칸은 남기지 않는다.
CALIBRATION_SUMMARY_REQUIRED_KEYS = (
    "prompt_version",
    "evalset_hash",
    "evalset_case_count",
    "total",
    "confusion_matrix",
    "derived",
    "per_axis",
)

#: confusion_matrix가 유일한 원본이고, 아래 키는 전부 거기서 계산된 파생값이다.
#: 사람이 적는 값이 아니라는 것을 계약으로 못박는다.
CALIBRATION_DERIVED_KEYS = ("match", "match_rate", "false_negative", "false_positive")

#: `calibration_summary.json`의 최상위 골격. `v1`·`v2`·`comparison`은 R2 진행 상태와
#: 무관하게 **항상 존재한다** — 채울 값이 없으면 `unavailable(...)`이 들어간다.
#: `hard_stop_record`가 성공 실행에서도 `blocked=false`로 반드시 생성되는 것과 같은
#: 원칙이다. 파일이 없는 것과 "아직 측정하지 않았다"는 감사에서 다른 의미다.
CALIBRATION_FILE_REQUIRED_KEYS = (
    "source",
    "v1",
    "v2",
    "comparison",
    "mismatch_detail_excluded",
)

#: 수치가 **어떤 등급의 실행에서 나왔는가**. 일치율만 싣고 등급을 빼면, 개발용
#: mock으로 뽑은 수치와 공식 실행 수치가 번들에서 똑같이 보인다 — 감사에서
#: 치명적이다. `scripts/calibration_report.py`가 리포트 최상위에 남기는 값을
#: 이름 그대로 옮긴다.
#:
#: 허용 `mode`는 `app.evaluation.calibration_modes.CALIBRATION_MODES`가 SSOT다.
#: 공식 제출 가능 모드는 `OFFICIAL_CALIBRATION_MODES`로 별도 구분한다.
#: `langsmith_required=false`면 `--no-langsmith`로 LangSmith 요건을 낮춘 실행이라
#: R2 공식 제출 등급이 아니다(`validate_official_case_set`의 기본값은 요구함).
CALIBRATION_GRADE_KEYS = (
    "schema_version",
    "mode",
    "official_validation_passed",
    "langsmith_required",
)

#: 이 어댑터가 해석할 수 있는 calibration 리포트 스키마 버전.
#: `scripts/calibration_report.py`의 `SCHEMA_VERSION`과 같아야 하며,
#: `tests/test_evidence_bundle.py`가 두 값을 대조한다. 모르는 버전의 리포트는
#: 필드 뜻이 달라졌을 수 있으므로 수치를 옮기지 않고 "없음"으로 처리한다.
CALIBRATION_REPORT_SCHEMA_VERSION = "1"

#: v1·v2 비교가 들어갈 자리. 필드명은 `app/evaluation/judge_calibration.py`의
#: `VersionComparison`을 그대로 옮긴다 — 번들이 이름을 새로 만들면 원본과 어긋난다.
#: 값은 R2가 v2를 재측정한 뒤에만 채워지며, 그 전에는 지어내지 않고 비워 둔다.
CALIBRATION_COMPARISON_REQUIRED_KEYS = (
    "before",
    "after",
    "match_rate_delta",
    "false_negative_delta",
    "false_positive_delta",
    "axis_before",
    "axis_after",
    "before_code_sha",
    "after_code_sha",
)

#: calibration 입력의 원본 경로. state가 아니라 `scripts/calibration_report.py --out`이
#: 만드는 별도 산출물이라, 없을 때의 `unavailable(...)` 사유가 이 경로를 가리킨다.
CALIBRATION_SOURCE_PATH = "R2 calibration 리포트 입력"

#: 왜 state가 아닌 외부 입력인가 — calibration은 실행 1회분 state가 아니라
#: 사례집 전체를 judge에 돌린 결과라, 그래프 한 번의 최종 state에는 존재할 수 없다.
CALIBRATION_UNAVAILABLE_NOTE = (
    "calibration은 실행 1회분 state가 아니라 사례집 전체 judge 결과의 집계다. "
    "scripts/calibration_report.py --out 산출물을 --calibration으로 넘기면 실린다."
)

#: 오판 사례 상세(`find_mismatches`)는 번들에 싣지 않는다. `Mismatch.human_rationale`이
#: 사람 라벨 원문이라 번들에 실으면 답안지가 증거물로 새어 나간다. 원인 분석은
#: `scripts/calibration_report.py --out` 산출물이 담당하고, 번들은 집계값만 싣는다.
CALIBRATION_MISMATCH_EXCLUSION_REASON = (
    "오판 사례 상세는 사람 라벨 원문(human_rationale)을 포함하므로 번들에 싣지 않는다. "
    "scripts/calibration_report.py --out 산출물을 참조한다."
)

#: prompt_version이 필요한 이유 — 일치율은 프롬프트가 바뀌면 함께 움직인다.
#: 어떤 프롬프트로 잰 수치인지 붙어 있지 않으면 개선 전후 비교가 성립하지 않고,
#: LangSmith 감사 로그의 prompt_hash와 대조할 수도 없다.
CALIBRATION_PROMPT_VERSION_RATIONALE = (
    "일치율·혼동행렬은 프롬프트 버전에 종속된 수치다. 버전이 없으면 개선 전후 "
    "비교와 LangSmith prompt_hash 대조가 불가능하다."
)

#: evalset_hash가 필요한 이유 — 일치율은 (프롬프트 × 평가셋)의 함수다.
#: 프롬프트가 그대로여도 평가셋에 어려운 사례가 추가되거나 라벨이 바뀌면
#: 일치율이 움직이는데, 평가셋 정체성이 없으면 그것을 "judge 성능 저하"로
#: 오진한다. 손으로 관리하는 버전 문자열은 사례를 바꾸고 버전을 올리는 걸
#: 잊는 drift가 생기므로 쓰지 않고, 내용 해시로 자동·위변조 감지되게 한다.
CALIBRATION_EVALSET_HASH_RATIONALE = (
    "일치율은 (프롬프트 × 평가셋)의 함수다. 평가셋 정체성이 없으면 사례 추가·"
    "라벨 변경으로 인한 변동을 judge 성능 변화로 오진한다. 수동 버전 문자열은 "
    "drift가 생기므로 내용 해시로 고정한다."
)


def evalset_hash(records: list) -> str:
    """평가셋의 정체성 해시 — 사례 집합·본문·사람 라벨을 함께 고정한다.

    `records`는 `app.evaluation.calibration_schema.CalibrationRecord` 목록이다.

    해시 대상에 사람 라벨(`human_passed`·`human_fail_axes`)을 포함하는 이유:
    사례 본문(`case_content_sha256`)만 고정하면 **같은 본문을 다시 라벨링해
    정답을 바꾼 경우**를 못 잡는다. 그 경우 judge가 전혀 변하지 않아도 일치율이
    움직이므로, 라벨까지 해시에 넣어야 "같은 시험지·같은 정답지"가 증명된다.

    judge 실행 쪽 메타데이터(prompt_version·model_version·code_sha)는 넣지
    않는다 — 그건 "무엇으로 쟀는가"이고, 이 해시는 "무엇을 쟀는가"다. 둘을
    섞으면 프롬프트만 바꾼 v1·v2 비교에서 평가셋이 달라진 것처럼 보인다.
    """
    payload = {
        "cases": [
            {
                "case_id": record.case_id,
                "case_content_sha256": record.case_content_sha256,
                "human_passed": record.human_passed,
                "human_fail_axes": list(record.human_fail_axes),
            }
            for record in sorted(records, key=lambda record: record.case_id)
        ]
    }
    return sha256_of_dict(payload)


def calibration_summary(records: list, *, prompt_version: str) -> dict:
    """calibration 요약을 records에서 전량 계산한다. 사람이 채우는 칸은 없다.

    `records`는 `app.evaluation.calibration_schema.merge_records()`의 결과다.
    집계는 #136이 병합한 `app.evaluation.judge_calibration`에 위임하고, 이
    함수는 번들 파일 모양으로 옮기기만 한다 — 계산 로직을 두 벌로 만들지 않는다.

    필드명은 `OverallMetrics`/`AxisMetrics`를 그대로 따른다(`match`·`match_rate`).
    #137 최초 제안의 `agreement`는 쓰지 않는다 — 병합된 코드가 SSOT다.
    """
    from app.evaluation.judge_calibration import (
        calculate_axis_metrics,
        calculate_overall_metrics,
    )

    overall = calculate_overall_metrics(records)
    axis_metrics = calculate_axis_metrics(records)
    return {
        "prompt_version": prompt_version,
        "evalset_hash": evalset_hash(records),
        "evalset_case_count": overall.total,
        "total": overall.total,
        "confusion_matrix": {
            "true_positive": overall.true_positive,
            "true_negative": overall.true_negative,
            "false_positive": overall.false_positive,
            "false_negative": overall.false_negative,
        },
        "derived": {
            "match": overall.match,
            "match_rate": overall.match_rate,
            "false_negative": overall.false_negative,
            "false_positive": overall.false_positive,
        },
        "per_axis": {
            axis_en: {
                "axis_ko": AXIS_EN_TO_KO[axis_en],
                "total": metrics.total,
                "confusion_matrix": {
                    "true_positive": metrics.true_positive,
                    "true_negative": metrics.true_negative,
                    "false_positive": metrics.false_positive,
                    "false_negative": metrics.false_negative,
                },
                "derived": {
                    "match": metrics.match,
                    "match_rate": metrics.match_rate,
                    "false_negative": metrics.false_negative,
                    "false_positive": metrics.false_positive,
                },
                # 결함이 드문 축은 match_rate가 과장된다 — 20건 중 1건 결함을
                # 놓치면 match_rate 95%인데 defect_recall 0%다. 함께 싣는다.
                "human_fail_support": metrics.human_fail_support,
                "defect_recall": metrics.defect_recall,
            }
            for axis_en, metrics in axis_metrics.items()
        },
    }


#: `asdict()`가 tuple을 list로 풀어 놓는 필드. 되돌릴 때 원래 타입으로 맞춘다.
_RECORD_TUPLE_FIELDS = (
    "human_fail_axes",
    "judge_fail_axes",
    "judge_checks",
    "judge_failed_required_checks",
    "manual_review_flags",
)


def calibration_summary_from_report(side: object) -> dict | None:
    """`scripts/calibration_report.py --out`의 `v1`/`v2` 한쪽을 번들 요약으로 바꾼다.

    리포트에 이미 `overall`·`axis_metrics`가 들어 있지만 그것을 그대로 옮기지
    않는다. 옮기면 집계 로직이 두 벌이 되어 한쪽만 고쳐지는 순간 번들과 리포트가
    갈린다 — 이 파일이 처음부터 막으려던 것이 그 상황이다. 대신 `records`를
    `CalibrationRecord`로 되돌려 `calibration_summary()`에 그대로 태운다.
    계산 경로가 하나뿐이면 두 산출물은 구조적으로 같은 값을 낼 수밖에 없다.

    입력이 이 형태가 아니면 추측해서 채우지 않고 `None`을 돌려준다 —
    호출자가 `unavailable(...)`로 사유를 남긴다.
    """
    from app.evaluation.calibration_schema import CalibrationRecord

    if not isinstance(side, dict):
        return None
    raw_records = side.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        return None

    records = []
    for raw in raw_records:
        if not isinstance(raw, dict):
            return None
        fields = dict(raw)
        for name in _RECORD_TUPLE_FIELDS:
            if name in fields and isinstance(fields[name], list):
                fields[name] = tuple(fields[name])
        try:
            records.append(CalibrationRecord(**fields))
        except TypeError:
            # 필드가 늘거나 줄면 조용히 일부만 채우지 않고 통째로 없음 처리한다.
            return None

    prompt_versions = {record.prompt_version for record in records}
    if len(prompt_versions) != 1:
        # 한 run 안에서 prompt_version이 갈리면 "어느 프롬프트로 잰 수치인가"가
        # 성립하지 않는다. validate_run_consistency가 막는 상황이지만,
        # 검증을 건너뛴 입력이 들어와도 번들이 값을 지어내지 않도록 여기서도 막는다.
        return None
    return calibration_summary(records, prompt_version=prompt_versions.pop())
