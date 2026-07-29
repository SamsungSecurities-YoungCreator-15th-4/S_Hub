"""Hard Stop·정밀 인용 검증 계약의 단위·E2E·속성 테스트."""

from __future__ import annotations

from copy import deepcopy

import pytest
from langgraph.graph import END, START, StateGraph

from app.graph import route_after_judge
from app.nodes.assemble_report import report_is_exportable
from app.nodes.manual_review_gate import manual_review_gate
from app.rag.citations import (
    Citation,
    citation_contract_issues,
    verify_citations,
)
from app.state import RiskState


def _failed_state(*, retries: int = 3, maximum: int = 3) -> dict:
    return {
        "run_config": {"judge_max_retries": maximum, "strict_citation_gate": True},
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

    verified, rejected = verify_citations([wrong_source, wrong_article], [chunk])

    assert verified == []
    assert "문서명" in rejected[0]["reason"]
    assert "조항" in rejected[1]["reason"]


def test_verified_citation_provenance_detects_post_verification_tampering():
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
def test_retry_limit_ssot_property_routes_every_exhausted_failure_to_gate(maximum):
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
def test_manual_review_gate_fail_closed_property(judge_passed, incoming_report):
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
