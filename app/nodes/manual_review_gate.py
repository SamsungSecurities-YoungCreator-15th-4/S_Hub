"""Judge 재시도 소진 후 확정·다운로드를 차단하는 결정론적 Hard Stop 노드."""

from __future__ import annotations

import json

from app.nodes.assemble_report import (
    BASE_TITLE,
    PENDING_STATUS_LABEL,
    PENDING_TITLE_PREFIX,
    STATUS_PENDING_MANUAL_REVIEW,
    assemble_report,
)
from app.nodes.judge_eval import resolve_max_judge_retries
from app.state import RiskState
from app.utils.hashing import sha256_of_dict

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
    decision = {
        "status": GATE_STATUS_BLOCKED,
        "trigger": GATE_TRIGGER,
        "trace_id": state.get("trace_id"),
        "judge_passed": judge.get("passed") is True,
        "judge_retries": judge_retries,
        "judge_max_retries": judge_max_retries,
        "failed_axes": failed_axes,
        "computation_hash": (
            ((state.get("metrics") or {}).get("meta") or {}).get("computation_hash")
        ),
    }
    decision["decision_hash"] = sha256_of_dict(decision)

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
