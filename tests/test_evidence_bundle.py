"""감사 증거 묶음(evidence bundle) 골격·계약 테스트."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evidence.schema import (
    BUNDLE_FILENAMES,
    BUNDLE_HASH_FILENAME,
    BUNDLE_SCHEMA_VERSION,
    CALIBRATION_SUMMARY_REQUIRED_KEYS,
    CITATION_VERIFICATION_FILENAME,
    HARD_STOP_RECORD_FILENAME,
    HARD_STOP_RECORD_REQUIRED_KEYS,
    HASHED_FILENAMES,
    JUDGE_RATIONALE_FILENAME,
    LLM_AUDIT_FILENAME,
    MANIFEST_FILENAME,
    SUMMARY_FILENAME,
    TRACE_FILENAME,
    calibration_summary_template,
)
from app.judge.axes import AXIS_EN_TO_KO
from app.utils.hashing import sha256_of_file
from scripts.make_evidence_bundle import make_bundle

ROOT = Path(__file__).resolve().parents[1]
GENERATED_AT = "2026-07-30T00:00:00+00:00"


def _passing_state() -> dict:
    """judge 통과·확정된 성공 실행 상태의 최소 형태."""
    return {
        "trace_id": "run-evidence-001",
        "run_config": {
            "as_of_date": "2026-07-03",
            "config_hash": "config-hash-value",
            "judge_max_retries": 3,
            "observability": {"langsmith_project": "Orchestration_Team4"},
            "audit": {
                "llm": {
                    "judge_eval": {
                        "latest": {
                            "attempt": 1,
                            "prompt_hash": {
                                "aggregate_sha256": "aggregate-hash",
                                "items": {"judge": "prompt-hash"},
                            },
                            "model_version": {
                                "deployment": "ai-insight-llm",
                                "model": "gpt-4o-2024-11-20",
                                "api_version": "2025-01-01-preview",
                            },
                        }
                    }
                }
            },
        },
        "ips_extraction_meta": {"model": "gpt-4o", "prompt_version": "ips-extract-v2"},
        "metrics": {"meta": {"computation_hash": "computation-hash-value"}},
        "judge_retries": 1,
        "judge_feedback": "",
        "judge": {
            "passed": True,
            "score": 1.0,
            "reason": "필수 품질 점검 통과",
            "checks": [
                {
                    "name": "source_validity",
                    "passed": True,
                    "required": True,
                    "detail": "출처 정책 게이트 충족",
                },
                {
                    "name": "citation_content_contract",
                    "passed": True,
                    "required": True,
                    "detail": "인용 1건 일치",
                },
            ],
            "rubric": {
                axis: {"passed": True, "reason": f"{axis} 통과"}
                for axis in AXIS_EN_TO_KO
            },
            "manual_review_flags": [],
        },
        "citations": [
            {
                "claim": "VaR 해석",
                "quote": "99% 신뢰수준의 VaR은 손실 추정치다.",
                "source": "methodology.pdf",
                "chunk_id": "methodology.pdf::0001",
                "verified": True,
                "extra": {
                    "chunk_text": "99% 신뢰수준의 VaR은 손실 추정치다.",
                    "category": "methodology",
                    "evidence_role": "방법론 근거",
                    "published_at": "2026-01-01",
                    "provenance": {
                        "source": "methodology.pdf",
                        "chunk_id": "methodology.pdf::0001",
                        "claim": "VaR 해석",
                        "quote_sha256": "quote-hash",
                        "chunk_text_sha256": "chunk-hash",
                        "locator": {},
                    },
                },
            }
        ],
        "report": {
            "status": "confirmed",
            "finalized": True,
            "as_of_date": "2026-07-03",
            "governance": {
                "report_status": "confirmed",
                "finalized": True,
                "confirmation_allowed": True,
                "export_allowed": True,
                "manual_review_required": False,
                "confirmation_blocked_reason": "",
                "langsmith_trace_url": "https://smith.example/trace",
                "langsmith_trace_urls": {"input": "https://smith.example/input"},
                "langsmith_project": "Orchestration_Team4",
            },
            "reproducibility": {
                "config_hash": "config-hash-value",
                "computation_hash": "computation-hash-value",
                "approval_hash": "approval-hash-value",
            },
        },
    }


def _blocked_state() -> dict:
    """재시도 소진으로 manual_review_gate에서 차단된 상태."""
    state = _passing_state()
    state["judge"]["passed"] = False
    state["judge"]["reason"] = "필수 품질 점검 실패: citation_content_contract"
    state["judge"]["checks"][1]["passed"] = False
    state["judge_retries"] = 3
    state["report"]["status"] = "pending_manual_review"
    state["report"]["finalized"] = False
    state["report"]["governance"].update(
        {
            "report_status": "pending_manual_review",
            "finalized": False,
            "confirmation_allowed": False,
            "export_allowed": False,
            "manual_review_required": True,
            "confirmation_blocked_reason": "필수 품질 점검 실패",
            "manual_review_gate": {
                "status": "blocked",
                "trigger": "judge_retries_exhausted",
                "trace_id": "run-evidence-001",
                "judge_passed": False,
                "judge_retries": 3,
                "judge_max_retries": 3,
                "failed_axes": ["citation_content_contract"],
                "computation_hash": "computation-hash-value",
                "decision_hash": "decision-hash-value",
            },
        }
    )
    return state


def _build(tmp_path: Path, state: dict, *, run_id="run-evidence-001", at=GENERATED_AT) -> Path:
    return make_bundle(state, tmp_path / run_id, run_id=run_id, generated_at=at)


def _read_json(out: Path, filename: str) -> dict:
    return json.loads((out / filename).read_text(encoding="utf-8"))


def test_bundle_creates_every_contract_file(tmp_path):
    out = _build(tmp_path, _passing_state())

    assert sorted(p.name for p in out.iterdir()) == sorted(BUNDLE_FILENAMES)
    assert len(BUNDLE_FILENAMES) == 9


def test_manifest_hashes_match_actual_files(tmp_path):
    out = _build(tmp_path, _passing_state())
    manifest = _read_json(out, MANIFEST_FILENAME)

    assert manifest["schema_version"] == BUNDLE_SCHEMA_VERSION
    assert set(manifest["files"]) == set(HASHED_FILENAMES)
    for filename, digest in manifest["files"].items():
        assert digest == sha256_of_file(str(out / filename))

    bundle_hash = (out / BUNDLE_HASH_FILENAME).read_text(encoding="utf-8").strip()
    assert bundle_hash == sha256_of_file(str(out / MANIFEST_FILENAME))


def test_missing_fields_are_recorded_as_unavailable_not_silently_empty(tmp_path):
    out = _build(tmp_path, {"trace_id": "run-empty"}, run_id="run-empty")

    judge = _read_json(out, JUDGE_RATIONALE_FILENAME)
    assert judge["passed"] == {"available": False, "reason": "state.judge.passed 없음"}
    assert judge["checks"]["available"] is False
    assert judge["checks"]["reason"] == "state.judge.checks 없음"

    citations = _read_json(out, CITATION_VERIFICATION_FILENAME)
    assert citations["citations"]["available"] is False
    assert citations["citation_count"] == 0

    hard_stop = _read_json(out, HARD_STOP_RECORD_FILENAME)
    assert hard_stop["report_status"]["available"] is False
    assert hard_stop["report_status"]["reason"] == "report.status 없음"


def test_intentionally_empty_values_are_not_reported_as_missing(tmp_path):
    """빈 문자열·빈 리스트는 '없음'이 아니라 '비어 있음'이라는 정보다.

    확정 리포트의 confirmation_blocked_reason=""를 '없음'으로 적으면, 차단 사유가
    없다는 사실과 필드가 누락됐다는 사실을 감사에서 구분할 수 없게 된다.
    """
    state = _passing_state()
    assert state["report"]["governance"]["confirmation_blocked_reason"] == ""
    assert state["judge"]["manual_review_flags"] == []
    out = _build(tmp_path, state)

    hard_stop = _read_json(out, HARD_STOP_RECORD_FILENAME)
    assert hard_stop["confirmation_blocked_reason"] == ""

    judge = _read_json(out, JUDGE_RATIONALE_FILENAME)
    assert judge["manual_review_flags"] == []
    assert judge["judge_feedback"] == ""


def test_node_execution_order_and_rejected_citations_are_explicit_gaps(tmp_path):
    """state에 아예 없는 항목은 빈 값이 아니라 사유와 함께 기록되어야 한다."""
    out = _build(tmp_path, _passing_state())

    trace = _read_json(out, TRACE_FILENAME)
    assert trace["node_execution_order"]["available"] is False
    assert "run_graph.py" in trace["node_execution_order"]["note"]

    citations = _read_json(out, CITATION_VERIFICATION_FILENAME)
    assert citations["rejected_citations"]["available"] is False
    assert "rag_cite.py" in citations["rejected_citations"]["note"]


def test_hard_stop_record_is_written_for_successful_run(tmp_path):
    out = _build(tmp_path, _passing_state())
    hard_stop = _read_json(out, HARD_STOP_RECORD_FILENAME)

    assert set(HARD_STOP_RECORD_REQUIRED_KEYS) <= set(hard_stop)
    assert hard_stop["blocked"] is False
    assert hard_stop["export_allowed"] is True
    assert hard_stop["manual_review_gate"]["available"] is False


def test_hard_stop_record_adopts_manual_review_gate_keys_verbatim(tmp_path):
    out = _build(tmp_path, _blocked_state())
    hard_stop = _read_json(out, HARD_STOP_RECORD_FILENAME)

    assert hard_stop["blocked"] is True
    assert hard_stop["export_allowed"] is False
    gate = hard_stop["manual_review_gate"]
    # manual_review_gate.py가 기록한 키를 이름 그대로 싣는다.
    assert gate["status"] == "blocked"
    assert gate["trigger"] == "judge_retries_exhausted"
    assert gate["failed_axes"] == ["citation_content_contract"]
    assert gate["decision_hash"] == "decision-hash-value"


def test_llm_audit_marks_raw_text_unavailable_with_recovery_path(tmp_path):
    out = _build(tmp_path, _passing_state())
    audit = _read_json(out, LLM_AUDIT_FILENAME)

    raw = audit["raw_prompt_and_response"]
    assert raw["available"] is False
    assert "해시 기반" in raw["reason"]
    assert re.fullmatch(r"[0-9a-f]{40}", raw["recovery"]["git_sha"])
    assert raw["recovery"]["prompt_hash_items"]["judge_eval"] == {"judge": "prompt-hash"}
    assert audit["model_version"]["judge_eval"]["model"] == "gpt-4o-2024-11-20"


def test_generated_by_contains_real_git_sha(tmp_path):
    out = _build(tmp_path, _passing_state())
    manifest = _read_json(out, MANIFEST_FILENAME)

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert manifest["generated_by"]["git_sha"] == expected
    assert manifest["generated_by"]["script"] == "scripts/make_evidence_bundle.py"


def test_same_state_produces_identical_content_except_timestamp(tmp_path):
    state = _passing_state()
    first = _build(tmp_path / "a", state, at="2026-07-30T00:00:00+00:00")
    second = _build(tmp_path / "b", state, at="2026-07-31T09:30:00+00:00")

    for filename in HASHED_FILENAMES:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()

    first_manifest = _read_json(first, MANIFEST_FILENAME)
    second_manifest = _read_json(second, MANIFEST_FILENAME)
    assert first_manifest["generated_at"] != second_manifest["generated_at"]
    first_manifest.pop("generated_at")
    second_manifest.pop("generated_at")
    assert first_manifest == second_manifest


def test_summary_reports_failed_axes_in_korean(tmp_path):
    out = _build(tmp_path, _blocked_state())
    summary = (out / SUMMARY_FILENAME).read_text(encoding="utf-8")

    assert "차단(hard stop): 예" in summary
    assert "리포트 확정(finalized): False" in summary
    # 6축은 한글·영문 병기, 그 외 필수 검사는 영문 그대로.
    assert "citation_content_contract" in summary
    assert "config_hash: config-hash-value" in summary

    passing = _build(tmp_path / "ok", _passing_state(), run_id="run-ok")
    passing_summary = (passing / SUMMARY_FILENAME).read_text(encoding="utf-8")
    assert "차단(hard stop): 아니오" in passing_summary
    assert "없음 (필수 검사 전부 통과)" in passing_summary


def test_judge_rationale_labels_axes_in_both_languages(tmp_path):
    out = _build(tmp_path, _passing_state())
    judge = _read_json(out, JUDGE_RATIONALE_FILENAME)

    by_axis = {check["axis_en"]: check for check in judge["checks"]}
    assert by_axis["source_validity"]["axis_ko"] == AXIS_EN_TO_KO["source_validity"]
    # 6축이 아닌 필수 검사는 한글 표기를 지어내지 않는다.
    assert by_axis["citation_content_contract"]["axis_ko"] is None
    assert "axis_ko_note" in by_axis["citation_content_contract"]

    assert set(judge["rubric"]) == set(AXIS_EN_TO_KO)


def test_calibration_template_axis_keys_come_from_axes_ssot():
    template = calibration_summary_template()

    assert set(CALIBRATION_SUMMARY_REQUIRED_KEYS) <= set(template)
    assert set(template["per_axis"]) == set(AXIS_EN_TO_KO)
    for axis_en, axis_ko in AXIS_EN_TO_KO.items():
        assert template["per_axis"][axis_en]["axis_ko"] == axis_ko
