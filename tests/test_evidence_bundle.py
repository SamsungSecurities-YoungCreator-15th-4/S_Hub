"""감사 증거 묶음(evidence bundle) 골격·계약 테스트."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.evidence.schema import (
    BUNDLE_FILENAMES,
    BUNDLE_HASH_FILENAME,
    BUNDLE_SCHEMA_VERSION,
    CALIBRATION_COMPARISON_REQUIRED_KEYS,
    CALIBRATION_DERIVED_KEYS,
    CALIBRATION_FILE_REQUIRED_KEYS,
    CALIBRATION_FILENAME,
    CALIBRATION_GRADE_KEYS,
    CALIBRATION_REPORT_SCHEMA_VERSION,
    CALIBRATION_SOURCE_PATH,
    CALIBRATION_SUMMARY_REQUIRED_KEYS,
    CITATION_VERIFICATION_FILENAME,
    HARD_STOP_RECORD_FILENAME,
    HARD_STOP_RECORD_REQUIRED_KEYS,
    HASHED_FILENAMES,
    JUDGE_RATIONALE_FILENAME,
    LLM_AUDIT_FILENAME,
    MANIFEST_FILENAME,
    REPLAY_DIFF_FILENAME,
    SUMMARY_FILENAME,
    TRACE_FILENAME,
    calibration_summary,
    evalset_hash,
)
from engine.evaluation.calibration_modes import (
    CALIBRATION_MODES,
    MODE_OFFICIAL,
    MODE_OFFICIAL_CODE_CHANGE,
    MODE_OFFLINE_REHEARSAL,
    OFFICIAL_CALIBRATION_MODES,
)
from engine.judge.axes import AXIS_EN_TO_KO, KOREAN_AXIS_NAMES, to_en
from engine.utils.hashing import sha256_of_file
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
                "policy_version": "2026-08-01.v1",
                "trace_id": "run-evidence-001",
                "stopped_at": "2026-07-03T00:00:00+00:00",
                "stopped_at_basis": "run_config.as_of_date",
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


def _build(
    tmp_path: Path,
    state: dict,
    *,
    run_id="run-evidence-001",
    at=GENERATED_AT,
    calibration=None,
) -> Path:
    return make_bundle(
        state,
        tmp_path / run_id,
        run_id=run_id,
        generated_at=at,
        calibration=calibration,
    )


def _read_json(out: Path, filename: str) -> dict:
    return json.loads((out / filename).read_text(encoding="utf-8"))


def test_bundle_creates_every_contract_file(tmp_path):
    out = _build(tmp_path, _passing_state())

    assert sorted(p.name for p in out.iterdir()) == sorted(BUNDLE_FILENAMES)
    # 종수를 숫자로 박지 않는다. 파일이 늘 때마다 테스트를 고치게 되면 이 검사가
    # "상수를 따라 적었다"는 확인으로 퇴화한다. manifest·bundle_hash 2개만
    # 해시 대상 밖이라는 구조를 대신 고정한다.
    assert len(BUNDLE_FILENAMES) == len(HASHED_FILENAMES) + 2
    assert set(BUNDLE_FILENAMES) - set(HASHED_FILENAMES) == {
        MANIFEST_FILENAME,
        BUNDLE_HASH_FILENAME,
    }


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
    assert gate["policy_version"] == "2026-08-01.v1"
    assert gate["stopped_at"] == "2026-07-03T00:00:00+00:00"
    assert gate["stopped_at_basis"] == "run_config.as_of_date"
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
    from engine.evaluation.calibration_schema import merge_records

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
                "langsmith_run_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, case_id)),
                "langsmith_trace_url": None,
                "code_sha": "deadbeef",
                "case_content_sha256": hashlib.sha256(body_seed.encode()).hexdigest(),
                "as_of_date": "2026-07-03",
                "strict_citation_gate": False,
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


# ---------------------------------------------------------------------------
# calibration 파일 편입 (R4 — 개선 전후 비교표)
# ---------------------------------------------------------------------------
def _calibration_report(*, with_v2: bool = False) -> dict:
    """`scripts/calibration_report.py --out` 산출물의 최소 형태.

    번들이 소비하는 부분만 만든다 — v1/v2의 `records`와 `comparison`.

    v1·v2는 **같은 사례집·같은 사람 정답**을 다른 프롬프트로 잰 것이어야 한다
    (`compare_versions`가 사람 라벨 동일성을 강제한다). 그래서 사람 라벨은 그대로
    두고 v1에서 judge만 1건 놓치게 만들어 개선 전후를 만든다.
    """
    from dataclasses import asdict

    from engine.evaluation.judge_calibration import compare_versions

    base = _calibration_records()
    v1 = [
        replace(
            record,
            prompt_version="v1",
            prompt_hash=f"v1-{record.case_id}",
            # case_001은 사람이 fail로 매긴 사례다. v1 judge는 이를 놓친다(미탐).
            judge_passed=True if record.case_id == "case_001" else record.judge_passed,
            judge_fail_axes=() if record.case_id == "case_001" else record.judge_fail_axes,
        )
        for record in base
    ]
    report: dict = {
        "schema_version": CALIBRATION_REPORT_SCHEMA_VERSION,
        "mode": MODE_OFFICIAL,
        "official_validation_passed": True,
        "langsmith_required": True,
        "v1": {"records": [asdict(record) for record in v1]},
    }
    if with_v2:
        v2 = [
            replace(record, prompt_version="v2", prompt_hash=f"v2-{record.case_id}")
            for record in base
        ]
        report["v2"] = {"records": [asdict(record) for record in v2]}
        report["comparison"] = asdict(compare_versions(v1, v2))
    return report


def test_calibration_file_is_always_created_regardless_of_r2_progress(tmp_path):
    """R2 결과가 있든 없든 파일은 만들어진다.

    `hard_stop_record`가 성공 실행에서도 `blocked=false`로 생성되는 것과 같은
    원칙이다 — 파일이 아예 없으면 감사자는 "안 만든 것"과 "아직 못 잰 것"을
    구분할 수 없다.
    """
    without = _build(tmp_path, _passing_state(), run_id="run-no-r2")
    with_r2 = _build(
        tmp_path,
        _passing_state(),
        run_id="run-with-r2",
        calibration=_calibration_report(),
    )

    for out in (without, with_r2):
        assert (out / CALIBRATION_FILENAME).is_file()
        payload = _read_json(out, CALIBRATION_FILENAME)
        assert set(CALIBRATION_FILE_REQUIRED_KEYS) <= set(payload)


def test_calibration_records_absence_with_reason_not_silent_emptiness(tmp_path):
    """R2 결과가 없으면 빈 칸이 아니라 사유와 원본 경로가 실린다."""
    payload = _read_json(_build(tmp_path, _passing_state()), CALIBRATION_FILENAME)

    for key in ("v1", "v2", "comparison"):
        assert payload[key]["available"] is False
        assert CALIBRATION_SOURCE_PATH in payload[key]["reason"]
        assert payload[key]["reason"].endswith("없음")
        assert payload[key]["note"]


def test_calibration_v1_carries_match_fields_not_agreement(tmp_path):
    """파생 지표 이름은 `match`·`match_rate`다 — `agreement`가 아니다.

    #137 최초 제안이 쓴 `agreement`는 병합된 `app/evaluation/` 코드에 없다.
    번들이 이름을 새로 만들면 원본과 대조가 불가능해진다.
    """
    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=_calibration_report()),
        CALIBRATION_FILENAME,
    )
    v1 = payload["v1"]

    assert set(CALIBRATION_SUMMARY_REQUIRED_KEYS) <= set(v1)
    assert set(v1["derived"]) == set(CALIBRATION_DERIVED_KEYS)
    assert "agreement" not in json.dumps(payload, ensure_ascii=False)
    # 파생값은 confusion_matrix에서만 나온다.
    matrix = v1["confusion_matrix"]
    assert v1["derived"]["match"] == matrix["true_positive"] + matrix["true_negative"]


def test_calibration_comparison_slot_is_filled_only_when_v2_exists(tmp_path):
    """v1·v2 비교 자리는 계약으로 존재하되, 값은 재측정 전까지 비어 있다."""
    v1_only = _read_json(
        _build(
            tmp_path,
            _passing_state(),
            run_id="run-v1-only",
            calibration=_calibration_report(),
        ),
        CALIBRATION_FILENAME,
    )
    # 값이 실린 자리에는 available 키 자체가 없다 — §5 표기는 없을 때만 붙는다.
    assert "available" not in v1_only["v1"]
    assert v1_only["comparison"]["available"] is False

    both = _read_json(
        _build(
            tmp_path,
            _passing_state(),
            run_id="run-v1-v2",
            calibration=_calibration_report(with_v2=True),
        ),
        CALIBRATION_FILENAME,
    )
    assert set(both["comparison"]) == set(CALIBRATION_COMPARISON_REQUIRED_KEYS)
    assert both["v1"]["prompt_version"] != both["v2"]["prompt_version"]


def test_comparison_requires_evalset_hash():
    """비교 계약에 evalset_hash가 있어야 '같은 사례·같은 라벨로 쟀다'가 증명된다.

    code_sha 두 개는 '무엇으로 쟀는가'만 말한다. 이 키가 빠지면 감사에서 "일치율이
    오른 게 judge가 좋아진 겁니까, 그 사이에 사례나 정답을 바꾼 겁니까"에 답할 수 없다.
    """
    assert "evalset_hash" in CALIBRATION_COMPARISON_REQUIRED_KEYS


def test_calibration_comparison_without_evalset_hash_is_rejected(tmp_path):
    """evalset_hash가 없는 비교는 빈칸으로 싣지 않고 통째로 '없음' 표기로 나간다.

    부분 결과를 만들면 감사자가 "비교는 했는데 평가셋만 안 적었다"로 읽는다.
    검증 실패를 통과로 만드는 폴백은 두지 않는다(fail-closed).
    """
    report = _calibration_report(with_v2=True)
    del report["comparison"]["evalset_hash"]

    payload = _read_json(
        _build(tmp_path, _passing_state(), run_id="run-no-evalset", calibration=report),
        CALIBRATION_FILENAME,
    )

    assert payload["comparison"]["available"] is False
    # 어느 키가 빠졌는지 사유에 적는다 — "없음"만 적으면 원인을 못 찾는다.
    assert "evalset_hash" in payload["comparison"]["note"]
    # 다른 키는 그대로였으므로 v1·v2 수치 자체는 살아 있다 — 비교만 막힌다.
    assert "available" not in payload["v1"]
    assert payload["v1"]["derived"]["match_rate"] is not None


def test_calibration_never_carries_human_rationale(tmp_path):
    """사람 라벨 원문은 번들에 실리지 않는다 — 답안지가 증거물로 새면 안 된다."""
    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=_calibration_report(with_v2=True)),
        CALIBRATION_FILENAME,
    )
    # 데이터가 실리는 자리만 본다. mismatch_detail_excluded는 "왜 안 싣는가"를
    # 설명하는 문장이라 필드 이름이 등장하는 것이 정상이다.
    data = json.dumps(
        {key: payload[key] for key in ("v1", "v2", "comparison")}, ensure_ascii=False
    )

    assert "합성 근거" not in data
    assert "human_rationale" not in data
    assert "records" not in data


def test_summary_carries_all_three_reproducibility_fingerprints(tmp_path):
    """`summary.md` 한 장으로 재현 지문 3종이 다 보여야 한다.

    `docs/reproducibility_scope.md` §2가 선언한 지문은 config_hash·
    computation_hash·approval_hash 셋이다. 하나라도 빠지면 5분 감사 대응에서
    `replay_diff.json`을 따로 열어야 한다.
    """
    out = _build(tmp_path, _passing_state())
    summary = (out / SUMMARY_FILENAME).read_text(encoding="utf-8")
    hashes = _read_json(out, REPLAY_DIFF_FILENAME)["hashes"]

    for name in ("config_hash", "computation_hash", "approval_hash"):
        assert f"- {name}: {hashes[name]}" in summary
    # report_hash는 재현 지문이 아니라 번들 파생값이라는 표시가 붙어 있어야 한다.
    assert "report_hash:" in summary
    assert "재현 지문 아님" in summary


def test_summary_marks_missing_fingerprint_instead_of_blank(tmp_path):
    """지문이 없으면 빈칸이 아니라 §5 누락 표기로 나간다."""
    summary = (
        _build(tmp_path, {"trace_id": "run-empty"}, run_id="run-empty") / SUMMARY_FILENAME
    ).read_text(encoding="utf-8")

    assert "- approval_hash: 없음 (report.reproducibility.approval_hash 없음)" in summary


def test_calibration_carries_run_grade_not_just_numbers(tmp_path):
    """수치보다 먼저 "어떤 등급의 실행에서 나왔는가"가 보여야 한다.

    같은 일치율이라도 `dev_mock`에서 나온 값과 `official`에서 나온 값은 증거로서
    값이 다르다. 등급이 빠지면 감사자가 개발용 리허설 숫자를 공식 실측으로 읽는다.
    """
    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=_calibration_report()),
        CALIBRATION_FILENAME,
    )

    assert set(payload["source"]) == set(CALIBRATION_GRADE_KEYS)
    assert payload["source"]["mode"] == MODE_OFFICIAL
    assert payload["source"]["langsmith_required"] is True


@pytest.mark.parametrize("missing", CALIBRATION_GRADE_KEYS)
def test_calibration_grade_absence_drops_numbers_too(tmp_path, missing):
    """등급 키가 하나라도 빠지면 **수치도 싣지 않는다** — fail-closed.

    등급만 "없음"으로 적고 일치율은 그대로 내보내면, 감사자가 등급 줄을
    지나쳤을 때 출처를 알 수 없는 수치를 공식 결과로 읽는다. 등급 4개 각각에
    대해 검사한다 — 하나만 검사하면 나머지 경로가 열려 있어도 통과한다.
    """
    report = _calibration_report(with_v2=True)
    del report[missing]

    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=report, run_id=f"run-{missing}"),
        CALIBRATION_FILENAME,
    )

    assert payload["source"]["available"] is False
    assert missing in payload["source"]["note"]
    for key in ("v1", "v2", "comparison"):
        assert payload[key]["available"] is False, f"{missing} 누락인데 {key} 수치가 남았습니다"
        assert "실행 등급" in payload[key]["note"]
    # 수치가 한 조각도 새지 않았는지 본문으로 확인한다.
    data = json.dumps({k: payload[k] for k in ("v1", "v2", "comparison")}, ensure_ascii=False)
    assert "match_rate" not in data
    assert "confusion_matrix" not in data


def test_calibration_rehearsal_grade_is_visible_in_bundle(tmp_path):
    """`--no-langsmith`로 낮춘 실행은 번들에서 그대로 드러나야 한다.

    R2는 LangSmith 실행 기록 제출이 요구사항이라 `validate_official_case_set`의
    `require_langsmith` 기본값이 True다. 이를 낮춰 돌린 실행은 공식 등급이
    아니며, 번들이 그 사실을 감추면 안 된다.
    """
    report = _calibration_report()
    report["mode"] = MODE_OFFLINE_REHEARSAL
    report["langsmith_required"] = False

    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=report), CALIBRATION_FILENAME
    )

    assert payload["source"]["mode"] == MODE_OFFLINE_REHEARSAL
    assert payload["source"]["langsmith_required"] is False
    # 등급이 낮아도 수치 자체는 그대로 싣는다 — 감추는 것이 아니라 등급을 밝힌다.
    assert "available" not in payload["v1"]


def test_calibration_official_code_change_grade_is_accepted(tmp_path):
    """LangSmith까지 검증한 코드 개선 비교는 공식 R4 증거로 전달된다."""
    report = _calibration_report(with_v2=True)
    report["mode"] = MODE_OFFICIAL_CODE_CHANGE

    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=report), CALIBRATION_FILENAME
    )

    assert payload["source"]["mode"] in OFFICIAL_CALIBRATION_MODES
    assert payload["source"]["official_validation_passed"] is True
    assert payload["source"]["langsmith_required"] is True
    assert "available" not in payload["v1"]
    assert "available" not in payload["comparison"]


@pytest.mark.parametrize(
    "grade_update, expected_note",
    [
        ({"mode": "offical_typo"}, "알 수 없는 calibration mode"),
        (
            {"mode": MODE_OFFICIAL, "langsmith_required": False},
            "검증 메타데이터 불일치",
        ),
        ({"official_validation_passed": "true"}, "bool이어야 한다"),
    ],
)
def test_calibration_unknown_or_inconsistent_grade_drops_numbers(
    tmp_path, grade_update, expected_note
):
    """알 수 없거나 모순된 등급은 수치까지 제거하는 fail-closed 계약이다."""
    report = _calibration_report(with_v2=True)
    report.update(grade_update)

    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=report), CALIBRATION_FILENAME
    )

    assert payload["source"]["available"] is False
    assert expected_note in payload["source"]["note"]
    assert str(list(CALIBRATION_MODES)) in payload["source"]["note"]
    for key in ("v1", "v2", "comparison"):
        assert payload[key]["available"] is False
        assert "실행 등급" in payload[key]["note"]


def test_calibration_numbers_are_dropped_on_unknown_report_schema(tmp_path):
    """모르는 스키마 버전에서는 수치를 옮기지 않는다.

    필드 이름이 같아도 뜻이 달라졌을 수 있다. 조용히 옮기면 감사 증거에 다른
    의미의 숫자가 실린다.
    """
    report = _calibration_report(with_v2=True)
    report["schema_version"] = "99"

    payload = _read_json(
        _build(tmp_path, _passing_state(), calibration=report), CALIBRATION_FILENAME
    )

    for key in ("v1", "v2", "comparison"):
        assert payload[key]["available"] is False
        assert "schema_version" in payload[key]["note"]
    # 등급 표시 자체는 남는다 — 무엇을 받았는지는 기록한다.
    assert payload["source"]["schema_version"] == "99"


def test_bundle_adapter_tracks_calibration_report_schema_version():
    """어댑터가 아는 버전과 리포트 생산자의 버전이 갈리면 잡는다.

    `scripts/calibration_report.py`의 주석이 "이 값으로 호환성을 확인할 수 있도록
    처음부터 박아둔다"고 적은 그 대조다. 생산자가 버전을 올리면 이 테스트가
    어댑터도 함께 손보게 만든다.
    """
    from scripts.calibration_report import SCHEMA_VERSION

    assert CALIBRATION_REPORT_SCHEMA_VERSION == SCHEMA_VERSION
