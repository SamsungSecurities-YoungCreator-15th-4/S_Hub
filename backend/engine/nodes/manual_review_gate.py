"""Judge 재시도 소진 후 확정·다운로드를 차단하는 결정론적 Hard Stop 노드."""

from __future__ import annotations

import json
from datetime import date, datetime

from engine.hard_stop_policy import resolve_hard_stop_policy_version
from engine.nodes.assemble_report import (
    BASE_TITLE,
    PENDING_STATUS_LABEL,
    PENDING_TITLE_PREFIX,
    STATUS_PENDING_MANUAL_REVIEW,
    assemble_report,
)
from engine.nodes.judge_eval import resolve_max_judge_retries
from engine.state import RiskState
from engine.utils.hashing import sha256_of_dict

GATE_STATUS_BLOCKED = "blocked"
GATE_TRIGGER = "judge_retries_exhausted"
HARD_STOP_NOTICE = (
    "Judge 필수 검사를 통과하지 못한 채 재시도 상한에 도달하여 "
    "manual_review_gate에서 확정·다운로드가 차단되었습니다."
)


def _failed_axes(judge: dict, judge_feedback: object) -> list[str]:
    checks = judge.get("checks")
    axes = {
        str(check.get("name"))
        for check in (checks if isinstance(checks, list) else [])
        if isinstance(check, dict)
        and check.get("required") is True
        and check.get("passed") is not True
        and check.get("name")
    }
    if isinstance(judge_feedback, str) and judge_feedback.strip():
        try:
            parsed = json.loads(judge_feedback)
        except json.JSONDecodeError:
            parsed = {}
        failures = parsed.get("failed_axes") if isinstance(parsed, dict) else []
        axes.update(
            str(item.get("axis"))
            for item in (failures if isinstance(failures, list) else [])
            if isinstance(item, dict) and item.get("axis")
        )
    return sorted(axes)


def _unavailable_stopped_at(reason: str) -> dict:
    """시각 메타데이터가 없어도 Hard Stop을 중단하지 않고 사유를 남긴다."""
    return {"available": False, "reason": reason}


def _logical_stopped_at(state: RiskState) -> tuple[object, str | None]:
    """재현 가능한 논리적 차단 기준시각과 원본 경로를 반환한다.

    노드 안에서 벽시계를 읽으면 같은 state의 출력이 달라진다. 따라서 승인 잠금일
    또는 설정 기준일을 사용하고, 실제 번들 생성 시각은 R4 manifest.generated_at,
    실제 실행 시각은 LangSmith trace가 담당한다.

    이 값은 차단 판단에 필수적인 데이터가 아니다. 누락·형식 오류가 있더라도
    예외를 던지지 않고 unavailable 표식을 반환해 fail-closed 종착점을 보장한다.
    """
    approval = state.get("approval")
    approval = approval if isinstance(approval, dict) else {}
    run_config = state.get("run_config")
    run_config = run_config if isinstance(run_config, dict) else {}
    if approval.get("locked_as_of"):
        raw = approval["locked_as_of"]
        basis = "approval.locked_as_of"
    else:
        raw = run_config.get("as_of_date")
        basis = "run_config.as_of_date" if raw else None
    if not isinstance(raw, str) or not raw.strip():
        return (
            _unavailable_stopped_at(
                "approval.locked_as_of와 run_config.as_of_date가 모두 없음"
            ),
            basis,
        )
    value = raw.strip()
    if "T" not in value:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            return (
                _unavailable_stopped_at(
                    f"{basis or 'stopped_at 기준값'}이 ISO 8601 날짜가 아님: {value!r}"
                ),
                basis,
            )
        return f"{parsed_date.isoformat()}T00:00:00+00:00", basis
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return (
            _unavailable_stopped_at(
                f"{basis or 'stopped_at 기준값'}이 ISO 8601 시각이 아님: {value!r}"
            ),
            basis,
        )
    if parsed.tzinfo is None:
        return (
            _unavailable_stopped_at(
                f"{basis or 'stopped_at 기준값'} 시각에 timezone이 없음: {value!r}"
            ),
            basis,
        )
    return parsed.isoformat(), basis


def manual_review_gate(state: RiskState) -> dict:
    """실패 리포트를 미확정 상태로 고정하고 외부 제공 경로를 닫는다.

    이 노드는 사람 검토를 자동 승인하지 않는다. R4가 수집할 수 있는 차단 사유와
    결정 지문을 report.governance.manual_review_gate에 남긴 뒤 그래프를 종료한다.
    """
    report = assemble_report(state)["report"]
    judge = state.get("judge")
    judge = judge if isinstance(judge, dict) else {}
    judge_retries = state.get("judge_retries") or 0
    judge_max_retries = resolve_max_judge_retries(state)
    failed_axes = _failed_axes(judge, state.get("judge_feedback"))
    # decision_hash는 같은 판단 내용이면 같은 값이어야 한다. trace_id와 stopped_at은
    # 실행 식별·시각 메타데이터이므로 표시에는 남기되 해시 입력에서는 제외한다.
    decision_content = {
        "status": GATE_STATUS_BLOCKED,
        "trigger": GATE_TRIGGER,
        "policy_version": resolve_hard_stop_policy_version(),
        "judge_passed": judge.get("passed") is True,
        "judge_retries": judge_retries,
        "judge_max_retries": judge_max_retries,
        "failed_axes": failed_axes,
        "computation_hash": (
            ((state.get("metrics") or {}).get("meta") or {}).get("computation_hash")
        ),
    }
    stopped_at, stopped_at_basis = _logical_stopped_at(state)
    decision = {
        **decision_content,
        "trace_id": state.get("trace_id"),
        "stopped_at": stopped_at,
        "stopped_at_basis": stopped_at_basis,
        "decision_hash": sha256_of_dict(decision_content),
    }

    report["title"] = PENDING_TITLE_PREFIX + BASE_TITLE
    report["status"] = STATUS_PENDING_MANUAL_REVIEW
    report["finalized"] = False
    report["status_label"] = PENDING_STATUS_LABEL
    report["summary"] = {
        **(report.get("summary") or {}),
        "judge_passed": False,
        "status": STATUS_PENDING_MANUAL_REVIEW,
        "finalized": False,
    }
    report["governance"] = {
        **(report.get("governance") or {}),
        "judge_passed": False,
        "report_status": STATUS_PENDING_MANUAL_REVIEW,
        "finalized": False,
        "confirmation_allowed": False,
        "export_allowed": False,
        "manual_review_required": True,
        "confirmation_blocked_reason": (
            judge.get("reason") or "Judge 필수 품질 점검 미통과"
        ),
        "manual_review_gate": decision,
    }
    report["warnings"] = list(
        dict.fromkeys([HARD_STOP_NOTICE, *(report.get("warnings") or [])])
    )
    return {"report": report}
