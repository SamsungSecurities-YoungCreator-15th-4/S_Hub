"""Hard Stop·정밀 인용 검증 계약의 단위·E2E·속성 테스트."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from langgraph.graph import END, START, StateGraph

from app.graph import route_after_judge
from app.evidence.schema import MANUAL_REVIEW_GATE_KEYS
from app.nodes.assemble_report import report_is_exportable
from app.nodes.judge_eval import resolve_max_judge_retries
from app.nodes.load_inputs import load_inputs
from app.nodes.manual_review_gate import (
    HARD_STOP_POLICY_PATH,
    manual_review_gate,
    resolve_hard_stop_policy_version,
)
from app.rag.citations import (
    Citation,
    citation_contract_issues,
    verify_citations,
)
from app.state import RiskState

ROOT = Path(__file__).resolve().parents[1]
JUDGE_MAX_RETRIES = load_inputs({})["run_config"]["judge_max_retries"]


def _failed_state(
    *,
    retries: int | None = None,
    maximum: int | None = None,
) -> dict:
    maximum = JUDGE_MAX_RETRIES if maximum is None else maximum
    retries = maximum if retries is None else retries
    return {
        "run_config": {
            "judge_max_retries": maximum,
            "strict_citation_gate": True,
        },
        "trace_id": "run-hard-stop",
        "metrics": {"meta": {"computation_hash": "calculation-hash"}},
        "judge_retries": retries,
        "judge": {
            "passed": False,
            "reason": "필수 품질 점검 실패: citation_content_contract",
            "checks": [
                {
                    "name": "citation_content_contract",
                    "required": True,
                    "passed": False,
                    "detail": "문서명과 chunk_id 불일치",
                }
            ],
            "manual_review_flags": [],
        },
    }


def test_verify_citations_rejects_real_quote_with_wrong_source_and_article():
    """문장이 진짜여도 문서명 또는 조항이 다르면 통과시키지 않는다."""
    quote = "일반금융소비자가 이해할 수 있도록 설명하여야 한다."
    chunk = {
        "chunk_id": "kcfp-art19.pdf::0001",
        "source": "kcfp-art19.pdf",
        "article": "제19조 제1항",
        "text": quote,
    }
    wrong_source = Citation(
        claim="설명의무",
        quote=quote,
        source="kcfp-art17.pdf",
        chunk_id=chunk["chunk_id"],
    )
    wrong_article = Citation(
        claim="설명의무",
        quote=quote,
        source=chunk["source"],
        chunk_id=chunk["chunk_id"],
        extra={"article": "제17조 제2항"},
    )
    missing_article = Citation(
        claim="설명의무",
        quote=quote,
        source=chunk["source"],
        chunk_id=chunk["chunk_id"],
    )

    verified, rejected = verify_citations(
        [wrong_source, wrong_article, missing_article],
        [chunk],
    )

    assert verified == []
    assert "문서명" in rejected[0]["reason"]
    assert "조항" in rejected[1]["reason"]
    assert "표기 누락" in rejected[2]["reason"]


def test_property_citation_identity_tampering_never_passes():
    quote = "스트레스 결과는 시나리오 가정과 함께 제시한다."
    chunk = {
        "chunk_id": "internal-rr.pdf::0007",
        "source": "internal-rr.pdf",
        "section": "제7조",
        "text": quote,
    }
    candidate = Citation(
        claim="스트레스 시나리오",
        quote=quote,
        source=chunk["source"],
        chunk_id=chunk["chunk_id"],
        extra={"section": "제7조"},
    )
    verified, rejected = verify_citations([candidate], [chunk])
    assert rejected == []

    payload = verified[0].to_dict()
    payload["extra"]["chunk_text"] = chunk["text"]
    assert citation_contract_issues(payload, require_chunk_text=True) == []

    for path, value, expected in (
        (("source",), "other.pdf", "문서명"),
        (("quote",), "원문에 없는 문장", "인용문"),
        (("claim",), "다른 주장", "조항/주장"),
        (("extra", "section"), "제8조", "조항/절/항"),
    ):
        tampered = deepcopy(payload)
        target = tampered
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert any(
            expected in issue
            for issue in citation_contract_issues(
                tampered,
                require_chunk_text=True,
            )
        )


@pytest.mark.parametrize("maximum", [1, 2, 3, 5, 20])
def test_property_retry_limit_routes_every_exhausted_failure_to_gate(maximum):
    before = _failed_state(retries=maximum - 1, maximum=maximum)
    exhausted = _failed_state(retries=maximum, maximum=maximum)
    beyond = _failed_state(retries=maximum + 7, maximum=maximum)

    assert route_after_judge(before) == "rag_cite"
    assert route_after_judge(exhausted) == "manual_review_gate"
    assert route_after_judge(beyond) == "manual_review_gate"


@pytest.mark.parametrize(
    ("judge_passed", "incoming_report"),
    [
        (False, {}),
        (False, {"finalized": True, "status": "confirmed"}),
        (True, {"finalized": True, "status": "confirmed"}),
    ],
)
def test_property_manual_review_gate_is_always_fail_closed(
    judge_passed,
    incoming_report,
):
    state = _failed_state()
    state["judge"]["passed"] = judge_passed
    state["report"] = incoming_report

    first = manual_review_gate(state)["report"]
    second = manual_review_gate(state)["report"]

    assert first == second
    assert first["finalized"] is False
    assert first["status"] == "pending_manual_review"
    assert first["governance"]["confirmation_allowed"] is False
    assert first["governance"]["export_allowed"] is False
    assert first["governance"]["manual_review_gate"]["decision_hash"]
    assert report_is_exportable(first) is False


def test_decision_hash_excludes_trace_id():
    """실제 재현 방해 원인이던 trace_id만 달라도 결정 지문은 같아야 한다."""
    first_state = _failed_state()
    second_state = deepcopy(first_state)
    first_state["trace_id"] = "trace-first"
    second_state["trace_id"] = "trace-second"

    first = manual_review_gate(first_state)["report"]["governance"]["manual_review_gate"]
    second = manual_review_gate(second_state)["report"]["governance"]["manual_review_gate"]

    assert first["trace_id"] != second["trace_id"]
    assert first["decision_hash"] == second["decision_hash"]


def test_manual_review_gate_records_policy_and_logical_stop_time():
    state = _failed_state()
    state["run_config"]["as_of_date"] = "2026-07-03"
    gate = manual_review_gate(state)["report"]["governance"]["manual_review_gate"]

    assert set(gate) == set(MANUAL_REVIEW_GATE_KEYS)
    assert gate["policy_version"] == resolve_hard_stop_policy_version()
    assert gate["stopped_at"] == "2026-07-03T00:00:00+00:00"
    assert gate["stopped_at_basis"] == "run_config.as_of_date"


@pytest.mark.parametrize(
    "bad_as_of_date",
    [None, "", "2026/07/03", "2026-07-03T12:00:00"],
)
def test_missing_or_invalid_stop_metadata_never_breaks_hard_stop(bad_as_of_date):
    """부가 시각 근거가 잘못돼도 terminal gate는 반드시 fail-closed로 끝난다."""
    state = _failed_state()
    if bad_as_of_date is not None:
        state["run_config"]["as_of_date"] = bad_as_of_date

    report = manual_review_gate(state)["report"]
    gate = report["governance"]["manual_review_gate"]

    assert report["status"] == "pending_manual_review"
    assert report["finalized"] is False
    assert report["governance"]["export_allowed"] is False
    assert gate["stopped_at"]["available"] is False
    assert gate["stopped_at"]["reason"]


def test_rule_1_retry_limit_requires_config_ssot():
    configured = load_inputs({})
    maximum = configured["run_config"]["judge_max_retries"]

    assert resolve_max_judge_retries(configured) == maximum
    for invalid in (None, True, 0, -1, "3"):
        state = {"run_config": {"judge_max_retries": invalid}}
        with pytest.raises(ValueError, match="judge_max_retries"):
            resolve_max_judge_retries(state)


def test_hard_stop_policy_version_uses_config_ssot():
    policy = yaml.safe_load(HARD_STOP_POLICY_PATH.read_text(encoding="utf-8"))

    assert resolve_hard_stop_policy_version() == policy["version"]


@pytest.mark.parametrize("invalid_policy", [None, {}, {"version": ""}, {"version": 1}])
def test_hard_stop_policy_version_rejects_invalid_config(
    invalid_policy,
    monkeypatch,
    tmp_path,
):
    import app.nodes.manual_review_gate as gate_module

    policy_path = tmp_path / "hard_stop_policy.yaml"
    policy_path.write_text(yaml.safe_dump(invalid_policy), encoding="utf-8")
    monkeypatch.setattr(gate_module, "HARD_STOP_POLICY_PATH", policy_path)
    gate_module.resolve_hard_stop_policy_version.cache_clear()

    with pytest.raises(ValueError, match="version"):
        gate_module.resolve_hard_stop_policy_version()


def test_rule_3_starter_kit_source_marking_mismatch_is_rejected():
    """강사 제공 FAIL 견본의 실제 인용 블록을 사용해 출처 표기 오류를 회귀 검증한다."""
    sample = (
        ROOT / "starter-kit" / "sample-case-02-fail-citation.md"
    ).read_text(encoding="utf-8")
    match = re.search(
        r'> "([^"]+)"\n> — 출처: (.+?), chunk_id: ([^\s]+)',
        sample,
    )
    assert match is not None
    quote, wrong_source, wrong_chunk_id = match.groups()
    correct_source = "「금융소비자 보호에 관한 법률」 제19조(설명의무) 제1항"
    correct_chunk_id = "kcfp-art19-001"
    correct_chunk = {
        "chunk_id": correct_chunk_id,
        "source": correct_source,
        "article": "제19조 제1항",
        "text": quote,
    }
    as_written = Citation(
        claim="설명의무",
        quote=quote,
        source=wrong_source,
        chunk_id=wrong_chunk_id,
        extra={"article": "제17조 제2항"},
    )
    wrong_label_on_correct_chunk = Citation(
        claim="설명의무",
        quote=quote,
        source=wrong_source,
        chunk_id=correct_chunk_id,
        extra={"article": "제17조 제2항"},
    )

    verified, rejected = verify_citations(
        [as_written, wrong_label_on_correct_chunk],
        [correct_chunk],
    )

    assert verified == []
    assert "존재하지 않는 chunk_id" in rejected[0]["reason"]
    assert "문서명" in rejected[1]["reason"]


def test_graph_e2e_exhausted_judge_stops_at_manual_review_gate():
    """실제 StateGraph 조건부 엣지에서 assemble_report를 우회해 gate로 끝난다."""
    graph = StateGraph(RiskState)

    def exhausted_judge(_: RiskState) -> dict:
        return _failed_state()

    graph.add_node("judge_eval", exhausted_judge)
    graph.add_node("manual_review_gate", manual_review_gate)
    graph.add_node("assemble_report", lambda state: {"report": {"unexpected": True}})
    graph.add_edge(START, "judge_eval")
    graph.add_conditional_edges(
        "judge_eval",
        route_after_judge,
        {
            "rag_cite": "judge_eval",
            "manual_review_gate": "manual_review_gate",
            "assemble_report": "assemble_report",
        },
    )
    graph.add_edge("manual_review_gate", END)
    graph.add_edge("assemble_report", END)
    compiled = graph.compile()

    updates = list(compiled.stream({}, stream_mode="updates"))
    node_order = [next(iter(update)) for update in updates]
    report = updates[-1]["manual_review_gate"]["report"]

    assert node_order == ["judge_eval", "manual_review_gate"]
    assert "unexpected" not in report
    assert report["governance"]["manual_review_gate"]["status"] == "blocked"
    assert report_is_exportable(report) is False


def test_manual_review_gate_exposes_feedback_only_failure_axis_for_r4():
    state = _failed_state()
    state["judge"]["checks"] = []
    state["judge_feedback"] = (
        '{"action":"rag_cite_rewrite","attempt":3,'
        '"failed_axes":[{"axis":"forced_failure","reason":"시연"}]}'
    )

    gate = manual_review_gate(state)["report"]["governance"]["manual_review_gate"]

    assert gate["failed_axes"] == ["forced_failure"]
