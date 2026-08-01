"""Judge 재시도 소진 후 확정·다운로드를 차단하는 결정론적 Hard Stop 노드."""

from __future__ import annotations

import json
from datetime import date, datetime

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
HARD_STOP_POLICY_VERSION = "2026-08-01.v1"
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


def _logical_stopped_at(state: RiskState) -> str:
    """재현 가능한 논리적 차단 기준시각을 ISO 8601로 반환한다.

    노드 안에서 벽시계를 읽으면 같은 state의 출력이 달라진다. 따라서 승인 잠금일
    또는 설정 기준일을 사용하고, 실제 번들 생성 시각은 R4 manifest.generated_at,
    실제 실행 시각은 LangSmith trace가 담당한다.
    """
    approval = state.get("approval")
    approval = approval if isinstance(approval, dict) else {}
    run_config = state.get("run_config")
    run_config = run_config if isinstance(run_config, dict) else {}
    raw = approval.get("locked_as_of") or run_config.get("as_of_date")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            "manual_review_gate stopped_at 산출에 approval.locked_as_of 또는 "
            "run_config.as_of_date가 필요합니다."
        )
    value = raw.strip()
    if len(value) == 10:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "manual_review_gate stopped_at 기준값은 ISO 8601이어야 합니다: "
                f"{value!r}"
            ) from exc
        return f"{parsed_date.isoformat()}T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "manual_review_gate stopped_at 기준값은 ISO 8601이어야 합니다: "
            f"{value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            "manual_review_gate stopped_at 시각에는 timezone이 필요합니다: "
            f"{value!r}"
        )
    return parsed.isoformat()


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
        "policy_version": HARD_STOP_POLICY_VERSION,
        "judge_passed": judge.get("passed") is True,
        "judge_retries": judge_retries,
        "judge_max_retries": judge_max_retries,
        "failed_axes": failed_axes,
        "computation_hash": (
            ((state.get("metrics") or {}).get("meta") or {}).get("computation_hash")
        ),
    }
    decision = {
        **decision_content,
        "trace_id": state.get("trace_id"),
        "stopped_at": _logical_stopped_at(state),
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
