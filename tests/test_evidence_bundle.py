"""감사 증거 묶음(evidence bundle) 골격·계약 테스트."""
from __future__ import annotations

import hashlib
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
    CALIBRATION_DERIVED_KEYS,
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
    calibration_summary,
    evalset_hash,
)
from app.judge.axes import AXIS_EN_TO_KO, KOREAN_AXIS_NAMES, to_en
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


def _calibration_records(
    *,
    flip_label_of: str | None = None,
    change_body_of: str | None = None,
    extra_case: bool = False,
):
    """calibration 요약 검증용 합성 CalibrationRecord 20건.

    6축 각각에 fail 사례 1건을 두고 나머지는 pass로 채운다. judge는 사람 라벨과
    완전히 일치시켜 두고, 개별 테스트가 필요한 부분만 어긋나게 한다.
    """
    from app.evaluation.calibration_schema import merge_records

    axes_ko = list(KOREAN_AXIS_NAMES)
    human: list[dict] = []
    judge: list[dict] = []
    count = 21 if extra_case else 20
    for index in range(1, count + 1):
        case_id = f"case_{index:03d}"
        fail_axis = axes_ko[index - 1] if index <= len(axes_ko) else None
        label = "fail" if fail_axis else "pass"
        fail_axes = [fail_axis] if fail_axis else []
        if case_id == flip_label_of:
            label, fail_axes = ("pass", []) if label == "fail" else ("fail", [axes_ko[0]])
        human.append(
            {"id": case_id, "label": label, "fail_axes": fail_axes, "rationale": "합성 근거"}
        )

        judge_fail_ko = set(fail_axes)
        rubric = {
            to_en(axis_ko): {
                "passed": axis_ko not in judge_fail_ko,
                "reason": "합성 판정",
            }
            for axis_ko in axes_ko
        }
        checks = [
            {
                "name": to_en(axis_ko),
                "passed": axis_ko not in judge_fail_ko,
                "required": True,
                "detail": "합성 검사",
            }
            for axis_ko in axes_ko
        ]
        passed = not judge_fail_ko
        body_seed = f"{case_id}-changed" if case_id == change_body_of else case_id
        judge.append(
            {
                "case_id": case_id,
                "passed": passed,
                "reason": "합성 사유",
                "rubric": rubric,
                "checks": checks,
                "judge_attempt": 1,
                "judge_feedback": "" if passed else "합성 피드백",
                "manual_review_flags": [],
                "prompt_version": "v1",
                "prompt_hash": hashlib.sha256(case_id.encode()).hexdigest(),
                "model_version": {
                    "deployment": "d",
                    "model": "m",
                    "api_version": "2026-01-01",
                },
                "trace_id": f"trace-{case_id}",
                "langsmith_run_id": f"run-{case_id}",
                "langsmith_trace_url": None,
                "code_sha": "deadbeef",
                "case_content_sha256": hashlib.sha256(body_seed.encode()).hexdigest(),
                "as_of_date": "2026-07-03",
            }
        )
    return merge_records(human, judge)


def test_calibration_summary_axis_keys_come_from_axes_ssot():
    summary = calibration_summary(_calibration_records(), prompt_version="v1")

    assert set(CALIBRATION_SUMMARY_REQUIRED_KEYS) <= set(summary)
    assert set(summary["per_axis"]) == set(AXIS_EN_TO_KO)
    for axis_en, axis_ko in AXIS_EN_TO_KO.items():
        assert summary["per_axis"][axis_en]["axis_ko"] == axis_ko


def test_calibration_summary_has_no_hand_filled_placeholder():
    """사람이 채우는 빈 칸(None 자리표시)이 남아 있으면 안 된다 (#137 리뷰 지적)."""
    summary = calibration_summary(_calibration_records(), prompt_version="v1")

    assert summary["total"] == 20
    assert summary["derived"]["match"] == 20
    assert summary["derived"]["match_rate"] == 1.0
    # top-level에 파생값을 중복해서 두지 않는다 — 원본은 confusion_matrix 하나다.
    for key in CALIBRATION_DERIVED_KEYS:
        assert key not in summary, f"{key}가 top-level에 중복돼 있습니다."


def test_calibration_derived_values_always_match_confusion_matrix():
    """파생값이 matrix에서 계산되므로 둘이 어긋날 수 없다."""
    summary = calibration_summary(
        _calibration_records(flip_label_of="case_001"), prompt_version="v1"
    )
    matrix = summary["confusion_matrix"]
    derived = summary["derived"]

    assert derived["match"] == matrix["true_positive"] + matrix["true_negative"]
    assert derived["false_negative"] == matrix["false_negative"]
    assert derived["false_positive"] == matrix["false_positive"]
    assert derived["match_rate"] == round(derived["match"] / summary["total"], 4)
    for axis_summary in summary["per_axis"].values():
        axis_matrix = axis_summary["confusion_matrix"]
        assert axis_summary["derived"]["match"] == (
            axis_matrix["true_positive"] + axis_matrix["true_negative"]
        )


def test_evalset_hash_is_stable_for_same_evalset():
    assert evalset_hash(_calibration_records()) == evalset_hash(_calibration_records())


def test_evalset_hash_changes_when_case_body_changes():
    """사례 본문이 바뀌면 같은 평가셋이 아니다 — 시험 문제가 바뀐 것."""
    assert evalset_hash(_calibration_records()) != evalset_hash(
        _calibration_records(change_body_of="case_007")
    )


def test_evalset_hash_changes_when_human_label_changes():
    """본문이 같아도 라벨이 바뀌면 같은 정답지가 아니다.

    case_content_sha256만 해시했다면 이 경우를 놓친다 — judge가 전혀 변하지
    않아도 일치율이 움직이므로 반드시 잡혀야 한다.
    """
    assert evalset_hash(_calibration_records()) != evalset_hash(
        _calibration_records(flip_label_of="case_003")
    )


def test_evalset_hash_changes_when_case_is_added():
    """어려운 사례가 추가되면 일치율이 떨어져도 judge 성능 저하가 아니다."""
    assert evalset_hash(_calibration_records()) != evalset_hash(
        _calibration_records(extra_case=True)
    )


def test_evalset_hash_ignores_judge_run_metadata():
    """평가셋 해시는 '무엇을 쟀는가'다 — 프롬프트 버전이 달라도 같아야 한다.

    이게 깨지면 프롬프트만 바꾼 v1·v2 비교에서 평가셋이 달라진 것처럼 보인다.
    """
    records = _calibration_records()
    v1 = calibration_summary(records, prompt_version="v1")
    v2 = calibration_summary(records, prompt_version="v2")

    assert v1["evalset_hash"] == v2["evalset_hash"]
    assert v1["prompt_version"] != v2["prompt_version"]
