"""실행 1회분의 감사 증거 묶음(evidence bundle)을 생성한다.

사용 예:
  python scripts/make_evidence_bundle.py --state run_state.json --out evidence/run-001

번들 계약(파일명·필수 키·"없음" 표기)은 app/evidence/schema.py가 SSOT다.
이 스크립트는 상태를 해석만 하고 그래프·노드를 실행하지 않는다.
run_graph.py에서 상태를 덤프해 자동 호출하는 배선은 다음 PR에서 다룬다.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evidence.schema import (  # noqa: E402
    BLOCKED_DERIVED_FROM,
    BUNDLE_HASH_FILENAME,
    BUNDLE_SCHEMA_VERSION,
    CITATION_VERIFICATION_FILENAME,
    HARD_STOP_RECORD_FILENAME,
    HARD_STOP_SOURCE_PATHS,
    HASHED_FILENAMES,
    JUDGE_RATIONALE_FILENAME,
    LLM_AUDIT_FILENAME,
    MANIFEST_FILENAME,
    RAW_LLM_OBSERVABILITY,
    RAW_LLM_RECOVERY_NOTE,
    RAW_LLM_UNAVAILABLE_REASON,
    REPLAY_DIFF_FILENAME,
    REPLAY_DIFF_PLACEHOLDER_NOTE,
    REPLAY_DIFF_PLACEHOLDER_STATUS,
    SUMMARY_FILENAME,
    TRACE_FILENAME,
    unavailable,
)
from app.judge.axes import AXIS_EN_TO_KO  # noqa: E402
from app.utils.hashing import sha256_of_dict, sha256_of_file  # noqa: E402

GATE_STATUS_BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# 공용 유틸
# ---------------------------------------------------------------------------
def _dumps(payload) -> str:
    """결정론적 직렬화 — 같은 내용이면 같은 바이트가 나와야 해시가 재현된다."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _get(mapping, key: str):
    """dict가 아닐 수 있는 값에서 안전하게 키를 꺼낸다."""
    return mapping.get(key) if isinstance(mapping, dict) else None


def _field(container, key: str, source_path: str, **extra):
    """상태에서 값을 읽되, 키가 없거나 None일 때만 '없음'으로 기록한다.

    빈 문자열·빈 리스트를 '없음'으로 적으면 안 된다. 확정 리포트의
    `confirmation_blocked_reason=""`나 통과 실행의 `manual_review_flags=[]`는
    값이 빠진 게 아니라 '차단 사유가 없다'는 정보 그 자체이기 때문이다.
    """
    if not isinstance(container, dict) or container.get(key) is None:
        return unavailable(source_path, **extra)
    return container[key]


def _section(value, source_path: str, **extra):
    """번들이 조립한 파생 값이 비면 '없음'을 명시한다."""
    if value in (None, {}, [], ""):
        return unavailable(source_path, **extra)
    return value


def _git_sha() -> object:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return unavailable("git rev-parse HEAD")
    sha = completed.stdout.strip()
    return sha or unavailable("git rev-parse HEAD")


def _axis_label(axis: object) -> dict:
    """축 이름을 한글·영문 병기로 만든다.

    6축 루브릭이 아닌 사전 검사(citation_content_contract 등)는 한글 규정 표기가
    없으므로 지어내지 않고 axis_ko=None으로 두고 사유를 남긴다.
    """
    axis_en = str(axis) if axis is not None else ""
    if axis_en in AXIS_EN_TO_KO:
        return {"axis_en": axis_en, "axis_ko": AXIS_EN_TO_KO[axis_en]}
    return {
        "axis_en": axis_en,
        "axis_ko": None,
        "axis_ko_note": "6축 루브릭 외 필수 검사 — 한글 규정 표기 없음",
    }


def _axis_display(axis: object) -> str:
    label = _axis_label(axis)
    if label["axis_ko"]:
        return f"{label['axis_ko']}({label['axis_en']})"
    return str(label["axis_en"])


# ---------------------------------------------------------------------------
# 섹션 조립
# ---------------------------------------------------------------------------
def build_trace(state: dict) -> dict:
    report = _get(state, "report") or {}
    governance = _get(report, "governance") or {}
    observability = _get(_get(state, "run_config") or {}, "observability") or {}
    return {
        "trace_id": _field(state, "trace_id", "state.trace_id"),
        "langsmith_trace_url": _section(
            governance.get("langsmith_trace_url") or observability.get("langsmith_trace_url"),
            "report.governance.langsmith_trace_url",
        ),
        "langsmith_trace_urls": _field(
            governance,
            "langsmith_trace_urls",
            "report.governance.langsmith_trace_urls",
        ),
        "langsmith_project": _section(
            governance.get("langsmith_project") or observability.get("langsmith_project"),
            "report.governance.langsmith_project",
        ),
        # 노드 실행 순서는 run_graph.py의 지역 변수로만 존재하고 state에 남지 않는다.
        "node_execution_order": unavailable(
            "state의 노드 실행 순서",
            note=(
                "run_graph.py가 스트리밍 중 지역 변수로만 수집하고 state에 기록하지 "
                "않는다. 상태 덤프 배선 PR에서 함께 싣는다."
            ),
        ),
    }


def build_judge_rationale(state: dict) -> dict:
    judge = _get(state, "judge") or {}
    run_config = _get(state, "run_config") or {}
    checks = judge.get("checks")
    rubric = judge.get("rubric")
    return {
        "passed": _field(judge, "passed", "state.judge.passed"),
        "reason": _field(judge, "reason", "state.judge.reason"),
        "score": _field(judge, "score", "state.judge.score"),
        "judge_retries": _field(state, "judge_retries", "state.judge_retries"),
        "judge_max_retries": _field(
            run_config,
            "judge_max_retries",
            "state.run_config.judge_max_retries",
        ),
        "checks": (
            [
                {
                    **_axis_label(check.get("name")),
                    "passed": check.get("passed"),
                    "required": check.get("required"),
                    "detail": check.get("detail"),
                }
                for check in checks
                if isinstance(check, dict)
            ]
            if isinstance(checks, list)
            else unavailable("state.judge.checks")
        ),
        "rubric": (
            {
                axis_en: {
                    **_axis_label(axis_en),
                    "passed": _get(result, "passed"),
                    "reason": _get(result, "reason"),
                }
                for axis_en, result in rubric.items()
            }
            if isinstance(rubric, dict)
            else unavailable("state.judge.rubric")
        ),
        "manual_review_flags": _field(
            judge,
            "manual_review_flags",
            "state.judge.manual_review_flags",
        ),
        "judge_feedback": _field(state, "judge_feedback", "state.judge_feedback"),
    }


def build_citation_verification(state: dict) -> dict:
    citations = state.get("citations")
    rows = citations if isinstance(citations, list) else []
    verified = [c for c in rows if isinstance(c, dict) and c.get("verified") is True]
    return {
        "citation_count": len(rows),
        "verified_citation_count": len(verified),
        "citations": (
            [
                {
                    "claim": citation.get("claim"),
                    "quote": citation.get("quote"),
                    "source": citation.get("source"),
                    "chunk_id": citation.get("chunk_id"),
                    "verified": citation.get("verified"),
                    "provenance": _field(
                        citation.get("extra"),
                        "provenance",
                        "state.citations[].extra.provenance",
                    ),
                    "chunk_text_present": bool(
                        str(_get(citation.get("extra"), "chunk_text") or "").strip()
                    ),
                    "evidence_role": _get(citation.get("extra"), "evidence_role"),
                    "category": _get(citation.get("extra"), "category"),
                    "published_at": _get(citation.get("extra"), "published_at"),
                }
                for citation in rows
                if isinstance(citation, dict)
            ]
            if isinstance(citations, list)
            else unavailable("state.citations")
        ),
        # 탈락 인용은 rag_cite가 log.warning으로만 남기고 state에 저장하지 않는다.
        "rejected_citations": unavailable(
            "state의 탈락 인용 기록",
            note=(
                "app/nodes/rag_cite.py가 verify_citations의 rejected를 로그로만 "
                "남기고 state에 저장하지 않는다. 번들에 실으려면 R2에 상태 기록을 "
                "요청해야 한다."
            ),
        ),
    }


def build_hard_stop_record(state: dict) -> dict:
    report = _get(state, "report") or {}
    governance = _get(report, "governance") or {}
    gate = governance.get("manual_review_gate")
    blocked = isinstance(gate, dict) and gate.get("status") == GATE_STATUS_BLOCKED
    return {
        # 성공 실행에서도 파일을 만들고 blocked=false를 명시한다.
        "blocked": blocked,
        "blocked_derived_from": BLOCKED_DERIVED_FROM,
        "report_status": _field(report, "status", "report.status"),
        "report_finalized": _field(report, "finalized", "report.finalized"),
        "confirmation_allowed": _field(
            governance,
            "confirmation_allowed",
            "report.governance.confirmation_allowed",
        ),
        "export_allowed": _field(
            governance,
            "export_allowed",
            "report.governance.export_allowed",
        ),
        "manual_review_required": _field(
            governance,
            "manual_review_required",
            "report.governance.manual_review_required",
        ),
        "confirmation_blocked_reason": _field(
            governance,
            "confirmation_blocked_reason",
            "report.governance.confirmation_blocked_reason",
        ),
        "manual_review_gate": (
            gate
            if isinstance(gate, dict) and gate
            else unavailable(
                "report.governance.manual_review_gate",
                note="차단되지 않은 실행에서는 manual_review_gate 노드가 실행되지 않는다.",
            )
        ),
        "source_paths": dict(HARD_STOP_SOURCE_PATHS),
    }


def build_replay_diff(state: dict) -> dict:
    report = _get(state, "report") or {}
    reproducibility = _get(report, "reproducibility") or {}
    run_config = _get(state, "run_config") or {}
    metrics_meta = _get(_get(state, "metrics") or {}, "meta") or {}
    return {
        "status": REPLAY_DIFF_PLACEHOLDER_STATUS,
        "hashes": {
            "config_hash": _section(
                reproducibility.get("config_hash") or run_config.get("config_hash"),
                "report.reproducibility.config_hash",
            ),
            "computation_hash": _section(
                reproducibility.get("computation_hash")
                or metrics_meta.get("computation_hash"),
                "report.reproducibility.computation_hash",
            ),
            "approval_hash": _field(
                reproducibility,
                "approval_hash",
                "report.reproducibility.approval_hash",
            ),
        },
        "note": REPLAY_DIFF_PLACEHOLDER_NOTE,
    }


def build_llm_audit(state: dict, git_sha: object) -> dict:
    run_config = _get(state, "run_config") or {}
    llm_audit = _get(_get(run_config, "audit") or {}, "llm") or {}
    prompt_hash = {}
    model_version = {}
    for component, record in llm_audit.items():
        latest = _get(record, "latest") or {}
        prompt_hash[str(component)] = latest.get("prompt_hash")
        model_version[str(component)] = latest.get("model_version")
    return {
        "prompt_hash": _section(prompt_hash, "state.run_config.audit.llm.*.latest.prompt_hash"),
        "model_version": _section(
            model_version,
            "state.run_config.audit.llm.*.latest.model_version",
        ),
        "ips_extraction_meta": _field(
            state,
            "ips_extraction_meta",
            "state.ips_extraction_meta",
        ),
        # 원문 미저장은 결함이 아니라 app/llm/audit.py의 의도된 설계다.
        "raw_prompt_and_response": {
            "available": False,
            "reason": RAW_LLM_UNAVAILABLE_REASON,
            "recovery": {
                "git_sha": git_sha,
                "prompt_hash_items": {
                    component: _get(record, "items")
                    for component, record in prompt_hash.items()
                    if isinstance(record, dict)
                },
                "note": RAW_LLM_RECOVERY_NOTE,
            },
            "observability": RAW_LLM_OBSERVABILITY,
        },
    }


# ---------------------------------------------------------------------------
# summary.md
# ---------------------------------------------------------------------------
def _value_or_dash(value) -> str:
    if isinstance(value, dict) and value.get("available") is False:
        return f"없음 ({value.get('reason')})"
    if value is None or value == "":
        return "-"
    return str(value)


def build_summary_md(
    state: dict,
    *,
    run_id: str,
    hard_stop: dict,
    trace: dict,
    replay: dict,
    report_hash: str,
) -> str:
    report = _get(state, "report") or {}
    judge = _get(state, "judge") or {}
    run_config = _get(state, "run_config") or {}
    checks = judge.get("checks")
    failed = [
        _axis_display(check.get("name"))
        for check in (checks if isinstance(checks, list) else [])
        if isinstance(check, dict)
        and check.get("required") is True
        and check.get("passed") is not True
    ]
    gate = hard_stop.get("manual_review_gate")
    if not failed and isinstance(gate, dict):
        failed = [_axis_display(axis) for axis in (gate.get("failed_axes") or [])]
    hashes = replay.get("hashes") or {}
    blocked = hard_stop.get("blocked")

    lines = [
        f"# 감사 증거 요약 — {run_id}",
        "",
        f"- 스키마 버전: {BUNDLE_SCHEMA_VERSION}",
        f"- 기준일(as_of_date): {_value_or_dash(run_config.get('as_of_date') or report.get('as_of_date'))}",
        f"- judge 통과: {_value_or_dash(judge.get('passed'))}",
        f"- 리포트 확정(finalized): {_value_or_dash(hard_stop.get('report_finalized'))}",
        f"- 리포트 상태: {_value_or_dash(hard_stop.get('report_status'))}",
        f"- 차단(hard stop): {'예' if blocked else '아니오'}",
        f"- 고객 제공·다운로드 허용(export_allowed): {_value_or_dash(hard_stop.get('export_allowed'))}",
        "",
        "## 실패 축",
        "",
    ]
    if failed:
        lines.extend(f"- {axis}" for axis in failed)
    else:
        lines.append("- 없음 (필수 검사 전부 통과)")
    lines.extend(
        [
            "",
            "## 차단 사유",
            "",
            f"{_value_or_dash(hard_stop.get('confirmation_blocked_reason')) or '-'}",
            "",
            "## 주요 해시",
            "",
            f"- config_hash: {_value_or_dash(hashes.get('config_hash'))}",
            f"- computation_hash: {_value_or_dash(hashes.get('computation_hash'))}",
            f"- report_hash: {report_hash} (번들이 report 전문에서 계산)",
            "",
            "## 추적",
            "",
            f"- trace_id: {_value_or_dash(trace.get('trace_id'))}",
            f"- LangSmith trace URL: {_value_or_dash(trace.get('langsmith_trace_url'))}",
            "",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 번들 생성
# ---------------------------------------------------------------------------
def make_bundle(state: dict, out_dir: Path, *, run_id: str, generated_at: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    git_sha = _git_sha()

    trace = build_trace(state)
    judge_rationale = build_judge_rationale(state)
    citation_verification = build_citation_verification(state)
    hard_stop = build_hard_stop_record(state)
    replay = build_replay_diff(state)
    llm_audit = build_llm_audit(state, git_sha)

    report = _get(state, "report") or {}
    report_hash = sha256_of_dict(report) if report else "-"

    payloads = {
        TRACE_FILENAME: trace,
        JUDGE_RATIONALE_FILENAME: judge_rationale,
        CITATION_VERIFICATION_FILENAME: citation_verification,
        HARD_STOP_RECORD_FILENAME: hard_stop,
        REPLAY_DIFF_FILENAME: replay,
        LLM_AUDIT_FILENAME: llm_audit,
    }
    for filename, payload in payloads.items():
        (out_dir / filename).write_text(_dumps(payload), encoding="utf-8")

    (out_dir / SUMMARY_FILENAME).write_text(
        build_summary_md(
            state,
            run_id=run_id,
            hard_stop=hard_stop,
            trace=trace,
            replay=replay,
            report_hash=report_hash,
        ),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "generated_by": {
            "script": "scripts/make_evidence_bundle.py",
            "git_sha": git_sha,
        },
        "files": {
            filename: sha256_of_file(str(out_dir / filename))
            for filename in HASHED_FILENAMES
        },
    }
    (out_dir / MANIFEST_FILENAME).write_text(_dumps(manifest), encoding="utf-8")

    bundle_hash = sha256_of_file(str(out_dir / MANIFEST_FILENAME))
    (out_dir / BUNDLE_HASH_FILENAME).write_text(bundle_hash + "\n", encoding="utf-8")
    return out_dir


def _resolve_run_id(state: dict, explicit: str | None) -> str:
    if explicit:
        return explicit
    trace_id = state.get("trace_id")
    if isinstance(trace_id, str) and trace_id.strip():
        return trace_id.strip()
    return "unknown-run"


def main() -> None:
    parser = argparse.ArgumentParser(description="실행 1회분 감사 증거 묶음 생성")
    parser.add_argument("--state", required=True, type=Path, help="실행 상태 JSON 경로")
    parser.add_argument("--out", required=True, type=Path, help="번들 출력 디렉터리")
    parser.add_argument("--run-id", default=None, help="번들 run_id (기본: state.trace_id)")
    args = parser.parse_args()

    state = json.loads(args.state.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise SystemExit("--state JSON은 최상위가 객체여야 합니다.")

    run_id = _resolve_run_id(state, args.run_id)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_dir = make_bundle(state, args.out, run_id=run_id, generated_at=generated_at)

    print(f"증거 번들 생성 완료: {out_dir}")
    for filename in sorted(p.name for p in out_dir.iterdir()):
        print(f"  - {filename}")
    print(f"bundle_hash: {(out_dir / BUNDLE_HASH_FILENAME).read_text().strip()}")


if __name__ == "__main__":
    main()
