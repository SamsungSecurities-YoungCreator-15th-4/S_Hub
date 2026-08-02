"""실행 1회분의 감사 증거 묶음(evidence bundle)을 생성한다.

사용 예:
  python scripts/make_evidence_bundle.py --state run_state.json --out evidence/run-001

번들 계약(파일명·필수 키·"없음" 표기)은 app/evidence/schema.py가 SSOT다.
이 스크립트는 상태를 해석만 하고 그래프·노드를 실행하지 않는다.

run_graph.py가 `--evidence-bundle`로 실행 종료 직후 make_bundle()을 in-process로
호출한다. 이 파일을 직접 부르는 경로(--state/--out)는 이미 덤프해 둔 state로
번들을 다시 만들 때 쓴다.
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
    CALIBRATION_COMPARISON_REQUIRED_KEYS,
    CALIBRATION_FILENAME,
    CALIBRATION_GRADE_KEYS,
    CALIBRATION_MISMATCH_EXCLUSION_REASON,
    CALIBRATION_REPORT_SCHEMA_VERSION,
    CALIBRATION_SOURCE_PATH,
    CALIBRATION_UNAVAILABLE_NOTE,
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
    calibration_summary_from_report,
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
                "않는다. state를 입력으로 받는 번들에서는 채울 수 없으며, 싣으려면 "
                "노드 실행 순서를 state에 남기는 변경이 먼저 필요하다."
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
        "rejected_citations": _rejected_citations(state),
    }


def _rejected_citations(state: dict) -> object:
    """탈락 인용 기록. 키가 없는 과거 state에서는 기존대로 available:false다."""
    rejections = state.get("citation_rejections")
    if not isinstance(rejections, list):
        return unavailable(
            "state.citation_rejections",
            note=(
                "이 실행은 탈락 인용을 기록하지 않는 버전에서 생성됐다. "
                "app/nodes/rag_cite.py가 citation_rejections를 채우면 실린다."
            ),
        )
    return [
        {
            # 재작성 루프에서 시도별로 누적되므로, 어느 시도의 탈락인지 함께 싣는다.
            "attempt": _get(rejection, "attempt"),
            "topic": _get(rejection, "topic"),
            "chunk_id": _get(rejection, "chunk_id"),
            "cited_source": _get(rejection, "cited_source"),
            "cited_locator": _get(rejection, "cited_locator"),
            "quote": _get(rejection, "quote"),
            "reason": _get(rejection, "reason"),
            "original_comparison": _field(
                rejection,
                "original_comparison",
                "state.citation_rejections[].original_comparison",
            ),
        }
        for rejection in rejections
        if isinstance(rejection, dict)
    ]


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


def _calibration_side(report: dict | None, key: str, *, note: str) -> object:
    """`v1`/`v2` 한쪽. 채울 값이 없으면 사유와 원본 경로를 남긴다."""
    summary = calibration_summary_from_report((report or {}).get(key))
    if summary is None:
        return unavailable(f"{CALIBRATION_SOURCE_PATH}.{key}", note=note)
    return summary


def _calibration_comparison(report: dict | None, *, note: str) -> object:
    """v1·v2 비교. 계약 키가 하나라도 없으면 부분 결과를 만들지 않는다."""
    comparison = (report or {}).get("comparison")
    if not isinstance(comparison, dict):
        return unavailable(f"{CALIBRATION_SOURCE_PATH}.comparison", note=note)
    missing = [key for key in CALIBRATION_COMPARISON_REQUIRED_KEYS if key not in comparison]
    if missing:
        # 일부만 실으면 감사자가 "비교했는데 값이 빈 칸"으로 읽는다. 통째로 없음 처리한다.
        return unavailable(
            f"{CALIBRATION_SOURCE_PATH}.comparison",
            note=f"비교 계약 키 누락: {', '.join(missing)}",
        )
    return {key: comparison[key] for key in CALIBRATION_COMPARISON_REQUIRED_KEYS}


def _calibration_source(report: dict | None) -> object:
    """수치가 어떤 등급의 실행에서 나왔는지. 일치율보다 먼저 봐야 하는 값이다."""
    if not isinstance(report, dict):
        return unavailable(CALIBRATION_SOURCE_PATH, note=CALIBRATION_UNAVAILABLE_NOTE)
    missing = [key for key in CALIBRATION_GRADE_KEYS if key not in report]
    if missing:
        # 등급을 모르면 수치도 못 믿는다. 일부만 적어 "공식인 척"하게 두지 않는다.
        return unavailable(
            CALIBRATION_SOURCE_PATH,
            note=f"실행 등급 표시 누락: {', '.join(missing)}",
        )
    return {key: report[key] for key in CALIBRATION_GRADE_KEYS}


def _calibration_schema_is_supported(report: dict | None) -> bool:
    """모르는 스키마 버전의 리포트에서는 수치를 옮기지 않는다.

    필드 이름이 같아도 뜻이 달라졌을 수 있다. 조용히 옮기면 감사 증거에 다른
    의미의 숫자가 실린다 — 버전이 안 맞으면 값을 비우고 사유를 남긴다.
    """
    if not isinstance(report, dict):
        return False
    return report.get("schema_version") == CALIBRATION_REPORT_SCHEMA_VERSION


def build_calibration(report: object) -> dict:
    """R2 calibration 요약. **R2 진행 상태와 무관하게 항상 생성된다.**

    `hard_stop_record`가 성공 실행에서도 `blocked=false`로 만들어지는 것과 같은
    원칙이다 — 파일이 아예 없으면 감사자는 "안 만든 것"과 "아직 못 잰 것"을
    구분할 수 없다. 못 잰 것은 못 쟀다고 사유와 함께 적는다.

    `report`는 `scripts/calibration_report.py --out` 산출물이다. 실행 1회분 state가
    아니라 사례집 전체를 judge에 돌린 결과라 state에서는 나올 수 없다.

    `source`를 `v1`보다 앞에 두는 이유 — 같은 일치율이라도 `dev_mock`에서 나온
    수치와 `official`에서 나온 수치는 증거로서 값이 다르다. 등급이 안 보이면
    감사자가 개발용 리허설 숫자를 공식 실측으로 읽는다.
    """
    payload = report if isinstance(report, dict) else None
    source = _calibration_source(payload)
    note = CALIBRATION_UNAVAILABLE_NOTE
    if payload is not None and not _calibration_schema_is_supported(payload):
        # "리포트를 안 줬다"와 "줬는데 못 읽는다"는 다른 사실이다. 섞지 않는다.
        note = (
            f"calibration 리포트 schema_version={payload.get('schema_version')!r}는 "
            f"이 번들이 해석하는 {CALIBRATION_REPORT_SCHEMA_VERSION!r}가 아니다. "
            "필드 뜻이 달라졌을 수 있어 수치를 옮기지 않는다."
        )
        payload = None
    return {
        "source": source,
        "v1": _calibration_side(payload, "v1", note=note),
        "v2": _calibration_side(payload, "v2", note=note),
        "comparison": _calibration_comparison(payload, note=note),
        "mismatch_detail_excluded": CALIBRATION_MISMATCH_EXCLUSION_REASON,
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
            # 앞의 3개가 docs/reproducibility_scope.md §2가 선언한 재현 지문이다.
            # 하나라도 빠지면 감사자가 summary.md 한 장으로 재현 범위를 확인할 수
            # 없어 replay_diff.json을 따로 열어야 한다.
            f"- config_hash: {_value_or_dash(hashes.get('config_hash'))}",
            f"- computation_hash: {_value_or_dash(hashes.get('computation_hash'))}",
            f"- approval_hash: {_value_or_dash(hashes.get('approval_hash'))}",
            f"- report_hash: {report_hash} (번들이 report 전문에서 계산, 재현 지문 아님)",
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
def make_bundle(
    state: dict,
    out_dir: Path,
    *,
    run_id: str,
    generated_at: str,
    calibration: object = None,
) -> Path:
    """번들 한 벌을 만든다.

    `calibration`은 `scripts/calibration_report.py --out` 산출물이다. 넘기지 않아도
    calibration 파일은 만들어지며, 그 경우 `available:false`로 사유가 실린다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    git_sha = _git_sha()

    trace = build_trace(state)
    judge_rationale = build_judge_rationale(state)
    citation_verification = build_citation_verification(state)
    hard_stop = build_hard_stop_record(state)
    replay = build_replay_diff(state)
    llm_audit = build_llm_audit(state, git_sha)
    calibration_summary_payload = build_calibration(calibration)

    report = _get(state, "report") or {}
    report_hash = sha256_of_dict(report) if report else "-"

    payloads = {
        TRACE_FILENAME: trace,
        JUDGE_RATIONALE_FILENAME: judge_rationale,
        CITATION_VERIFICATION_FILENAME: citation_verification,
        HARD_STOP_RECORD_FILENAME: hard_stop,
        REPLAY_DIFF_FILENAME: replay,
        LLM_AUDIT_FILENAME: llm_audit,
        CALIBRATION_FILENAME: calibration_summary_payload,
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


def _load_calibration(path: Path | None) -> object:
    """calibration 리포트를 읽는다. 경로를 준 이상 못 읽으면 조용히 넘기지 않는다."""
    if path is None:
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise SystemExit("--calibration JSON은 최상위가 객체여야 합니다.")
    return report


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
    parser.add_argument(
        "--calibration",
        type=Path,
        default=None,
        metavar="PATH",
        help="R2 calibration 리포트 JSON (scripts/calibration_report.py --out 산출물)",
    )
    args = parser.parse_args()

    state = json.loads(args.state.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise SystemExit("--state JSON은 최상위가 객체여야 합니다.")

    calibration = _load_calibration(args.calibration)
    run_id = _resolve_run_id(state, args.run_id)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_dir = make_bundle(
        state,
        args.out,
        run_id=run_id,
        generated_at=generated_at,
        calibration=calibration,
    )

    print(f"증거 번들 생성 완료: {out_dir}")
    for filename in sorted(p.name for p in out_dir.iterdir()):
        print(f"  - {filename}")
    print(f"bundle_hash: {(out_dir / BUNDLE_HASH_FILENAME).read_text().strip()}")


if __name__ == "__main__":
    main()
