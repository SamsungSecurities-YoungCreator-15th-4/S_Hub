"""judge_eval 6축 루브릭 단위·E2E 테스트 — 실제 Azure 호출 없음."""
from __future__ import annotations

import json

from app.graph import route_after_judge
from app.judge.rubric import (
    disclaimer,
    false_precision,
    hallucination,
    numeric_consistency,
    prohibited_expression,
    prohibited_manual_flags,
    source_validity,
)
from app.nodes.judge_eval import (
    MANUAL_REVIEW_WARNING,
    judge_eval,
)
from app.nodes.load_inputs import load_inputs
from app.nodes.manual_review_gate import manual_review_gate

AS_OF_DATE = "2026-06-30"
JUDGE_MAX_RETRIES = load_inputs({})["run_config"]["judge_max_retries"]
DISCLAIMER_TEXT = (
    f"기준일 {AS_OF_DATE}의 과거 데이터 기반 추정치이며 투자 권유가 아니고, "
    "원금 또는 수익을 보장하지 않습니다. 실제 결과와 다를 수 있습니다. "
    "최종 의사결정 책임은 고객과 담당 PB에게 있습니다."
)
METRICS = {
    "confidence": 0.99,
    "horizons": {"1d": {"var_krw": 30_000_000}},
    "meta": {
        "computation_hash": "metric-hash",
        "data_period": {"end": AS_OF_DATE},
    },
}
VERIFIED_CITATION = {
    "claim": "VaR 설명",
    "quote": "99% 신뢰수준의 VaR은 손실 추정치다.",
    "source": "methodology.pdf",
    "chunk_id": "methodology.pdf::0001",
    "verified": True,
    "extra": {"chunk_text": "99% 신뢰수준의 VaR은 손실 추정치다."},
}


class _AxisLLM:
    def __init__(self, *, hallucination_passed: bool = True, precision_passed: bool = True):
        self.answers = {
            "hallucination": hallucination_passed,
            "false_precision": precision_passed,
        }
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        axis = next(name for name in self.answers if f"판정 축: {name}" in prompt)
        passed = self.answers[axis]
        return json.dumps(
            {
                "passed": passed,
                "reason": f"{axis} {'통과' if passed else '실패'}",
            },
            ensure_ascii=False,
        )


def _explanations(text: str) -> list[dict]:
    return [{"topic": "설명", "text": text, "revision": 0}]


def _normal_state() -> dict:
    return {
        "run_config": {
            "as_of_date": AS_OF_DATE,
            "strict_citation_gate": True,
            "judge_max_retries": JUDGE_MAX_RETRIES,
        },
        "approval": {"status": "locked"},
        "metrics": METRICS,
        "explanations": _explanations(DISCLAIMER_TEXT),
        "citations": [VERIFIED_CITATION],
    }


def test_source_validity_pass_and_fail():
    passed, reason = source_validity([VERIFIED_CITATION], strict=True)
    assert passed is True
    assert reason == "출처 정책 게이트 충족: 검증 통과 인용 1건"
    assert source_validity([], strict=False)[0] is True
    passed, reason = source_validity([], strict=True)
    assert passed is False
    assert "0건" in reason


def test_numeric_consistency_pass_and_fail():
    good = _explanations(
        f"기준일 {AS_OF_DATE}, 99% 신뢰수준에서 1일 VaR은 약 3,000만원입니다."
    )
    assert numeric_consistency(good, METRICS, {AS_OF_DATE})[0] is True

    bad = _explanations(
        f"기준일 {AS_OF_DATE}, 99% 신뢰수준에서 1일 VaR은 4,000만원입니다."
    )
    passed, reason = numeric_consistency(bad, METRICS, {AS_OF_DATE})
    assert passed is False
    assert "4,000만원" in reason


def test_numeric_consistency_preserves_confidence_key_for_list_values():
    explanations = _explanations("99% 신뢰수준은 약 100일 중 1일의 초과를 뜻합니다.")

    assert numeric_consistency(
        explanations,
        {"confidence": [0.99]},
    )[0] is True


def test_numeric_consistency_ignores_unitless_ordinals_and_counts():
    explanations = _explanations("2가지 요인 중 1순위 위험을 설명합니다.")

    assert numeric_consistency(explanations, {})[0] is True


def test_numeric_consistency_accepts_portfolio_weight_without_citation():
    portfolio = [
        {"asset_class": "domestic_equity", "value_krw": 500, "weight": 0.5},
        {"asset_class": "cash", "value_krw": 500, "weight": 0.5},
    ]
    explanations = _explanations(
        f"기준일 {AS_OF_DATE} 기준 국내주식 비중은 50%입니다."
    )

    passed, reason = numeric_consistency(
        explanations, METRICS, {AS_OF_DATE}, None, portfolio
    )

    assert passed is True
    assert "engine_metric=2" in reason


def test_numeric_consistency_fails_when_weights_do_not_sum_to_100():
    portfolio = [
        {"asset_class": "domestic_equity", "value_krw": 500, "weight": 0.5},
        {"asset_class": "cash", "value_krw": 300, "weight": 0.3},
    ]
    explanations = _explanations(DISCLAIMER_TEXT)

    passed, reason = numeric_consistency(
        explanations, METRICS, {AS_OF_DATE}, None, portfolio
    )

    assert passed is False
    assert "자산군 비중 합계가 100%가 아님 (80.0%)" in reason


def test_numeric_consistency_allows_rounding_tolerance_on_weight_sum():
    portfolio = [
        {"asset_class": "domestic_equity", "value_krw": 500, "weight": 0.334},
        {"asset_class": "cash", "value_krw": 500, "weight": 0.333},
        {"asset_class": "bond", "value_krw": 333, "weight": 0.333},
    ]
    explanations = _explanations(DISCLAIMER_TEXT)

    assert numeric_consistency(
        explanations, METRICS, {AS_OF_DATE}, None, portfolio
    )[0] is True


def test_numeric_consistency_accepts_cited_evidence_fact_outside_metrics():
    topic = "거시환경·스트레스 개연성"
    text = "한국은행은 2026-05-29 기준금리를 2.50%로 유지했습니다."
    explanations = [{"topic": topic, "text": text, "revision": 0}]
    citations = [
        {
            "claim": topic,
            "quote": text,
            "source": "bok_mpd_202605.pdf",
            "chunk_id": "bok_mpd_202605.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(
        explanations,
        METRICS,
        {AS_OF_DATE},
        citations,
    )

    assert passed is True
    assert "evidence_fact=2" in reason


def test_numeric_consistency_rejects_uncited_or_cross_topic_evidence_fact():
    topic = "거시환경·스트레스 개연성"
    text = "한국은행은 기준금리를 2.50%로 유지했습니다."
    explanations = [{"topic": topic, "text": text, "revision": 0}]
    citations = [
        {
            "claim": "세무 참고",
            "quote": text,
            "source": "bok_mpd_202605.pdf",
            "chunk_id": "bok_mpd_202605.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(
        explanations,
        METRICS,
        {AS_OF_DATE},
        citations,
    )

    assert passed is False
    assert "같은 topic의 검증 인용에 없음" in reason


def test_numeric_consistency_rejects_number_that_is_only_substring_of_cited_fact():
    topic = "거시환경·스트레스 개연성"
    explanations = [{"topic": topic, "text": "시장 참고 금액은 50,000원입니다.", "revision": 0}]
    citations = [
        {
            "claim": topic,
            "quote": "시장 참고 금액은 150,000원입니다.",
            "source": "macro.pdf",
            "chunk_id": "macro.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(explanations, METRICS, {AS_OF_DATE}, citations)

    assert passed is False
    assert "50,000원가 같은 topic의 검증 인용에 없음" in reason


def test_numeric_consistency_accepts_equivalent_cited_currency_units():
    topic = "거시환경·스트레스 개연성"
    explanations = [{"topic": topic, "text": "시장 참고 금액은 0.5억원입니다.", "revision": 0}]
    citations = [
        {
            "claim": topic,
            "quote": "시장 참고 금액은 5,000만원입니다.",
            "source": "macro.pdf",
            "chunk_id": "macro.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(explanations, METRICS, {AS_OF_DATE}, citations)

    assert passed is True
    assert "evidence_fact=1" in reason


def test_numeric_consistency_accepts_equivalent_cited_bp_and_percent():
    topic = "거시환경·스트레스 개연성"
    explanations = [{"topic": topic, "text": "정책금리 충격은 250bp입니다.", "revision": 0}]
    citations = [
        {
            "claim": topic,
            "quote": "정책금리 충격은 2.5%입니다.",
            "source": "macro.pdf",
            "chunk_id": "macro.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(explanations, METRICS, {AS_OF_DATE}, citations)

    assert passed is True
    assert "evidence_fact=1" in reason


def test_numeric_consistency_rejects_same_number_with_different_unit_dimension():
    topic = "거시환경·스트레스 개연성"
    explanations = [{"topic": topic, "text": "참고 금액은 100원입니다.", "revision": 0}]
    citations = [
        {
            "claim": topic,
            "quote": "참고 비율은 100%입니다.",
            "source": "macro.pdf",
            "chunk_id": "macro.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(explanations, METRICS, {AS_OF_DATE}, citations)

    assert passed is False
    assert "100원가 같은 topic의 검증 인용에 없음" in reason


def test_numeric_consistency_does_not_accept_uncited_fact_that_matches_metric_value():
    topic = "거시환경·스트레스 개연성"
    explanations = [
        {
            "topic": topic,
            "text": "참고자료의 정책금리는 1.00%입니다.",
            "revision": 0,
        }
    ]

    passed, reason = numeric_consistency(
        explanations,
        {"confidence": 0.99},
        {AS_OF_DATE},
        [],
    )

    assert passed is False
    assert "1.00%가 같은 topic의 검증 인용에 없음" in reason


def test_numeric_consistency_does_not_accept_uncited_publication_date_matching_as_of_date():
    topic = "거시환경·스트레스 개연성"
    explanations = [
        {
            "topic": topic,
            "text": f"한국은행은 {AS_OF_DATE} 회의에서 정책 방향을 발표했습니다.",
            "revision": 0,
        }
    ]

    passed, reason = numeric_consistency(
        explanations,
        METRICS,
        {AS_OF_DATE},
        [],
    )

    assert passed is False
    assert f"날짜 {AS_OF_DATE}가 같은 topic의 검증 인용에 없음" in reason


def test_numeric_consistency_does_not_reclassify_wrong_var_as_evidence_fact():
    text = f"기준일 {AS_OF_DATE}, 99% 신뢰수준에서 1일 VaR은 4,000만원입니다."
    explanations = [{"topic": "VaR 해석", "text": text, "revision": 0}]
    citations = [
        {
            "claim": "VaR 해석",
            "quote": text,
            "source": "methodology_var_cvar_2026.pdf",
            "chunk_id": "methodology_var_cvar_2026.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(
        explanations,
        METRICS,
        {AS_OF_DATE},
        citations,
    )

    assert passed is False
    assert "4,000만원가 metrics에 없음" in reason


def test_numeric_consistency_does_not_reclassify_wrong_as_of_date_as_evidence_fact():
    wrong_date = "2026-05-29"
    text = f"리포트 기준일은 {wrong_date}입니다."
    explanations = [{"topic": "기준일 및 유의사항", "text": text, "revision": 0}]
    citations = [
        {
            "claim": "기준일 및 유의사항",
            "quote": text,
            "source": "methodology_var_cvar_2026.pdf",
            "chunk_id": "methodology_var_cvar_2026.pdf::0001",
            "verified": True,
        }
    ]

    passed, reason = numeric_consistency(
        explanations,
        METRICS,
        {AS_OF_DATE},
        citations,
    )

    assert passed is False
    assert f"기준 데이터에 없는 날짜 {wrong_date}" in reason


def test_hallucination_pass_and_fail_with_chunk_text():
    passing_llm = _AxisLLM(hallucination_passed=True)
    assert hallucination(
        _explanations("VaR 설명"),
        [VERIFIED_CITATION],
        passing_llm,
        {AS_OF_DATE},
    )[0] is True
    assert VERIFIED_CITATION["extra"]["chunk_text"] in passing_llm.prompts[0]
    assert AS_OF_DATE in passing_llm.prompts[0]

    failing_llm = _AxisLLM(hallucination_passed=False)
    passed, reason = hallucination(
        _explanations("근거 없는 확정적 주장"),
        [VERIFIED_CITATION],
        failing_llm,
    )
    assert passed is False
    assert "hallucination 실패" in reason


def test_hallucination_ignores_non_dict_extra_without_crashing():
    for malformed_extra in ("not-a-dict", None):
        citation = {**VERIFIED_CITATION, "extra": malformed_extra}
        llm = _AxisLLM(hallucination_passed=True)

        passed, _reason = hallucination(
            _explanations("VaR 설명"),
            [citation],
            llm,
        )

        assert passed is True
        assert '"chunk_text": ""' in llm.prompts[0]


def test_false_precision_pass_and_fail():
    passing_llm = _AxisLLM(precision_passed=True)
    assert false_precision(
        _explanations("99% 신뢰수준에서 1일 VaR은 약 3,000만원입니다."),
        passing_llm,
    )[0] is True

    failing_llm = _AxisLLM(precision_passed=False)
    passed, reason = false_precision(
        _explanations("손실 확률은 2.3%입니다."),
        failing_llm,
    )
    assert passed is False
    assert "false_precision 실패" in reason


def test_disclaimer_pass_and_fail():
    assert disclaimer(_explanations(DISCLAIMER_TEXT), {AS_OF_DATE})[0] is True
    passed, reason = disclaimer(_explanations("VaR 설명입니다."), {AS_OF_DATE})
    assert passed is False
    assert "기준일" in reason
    assert "E1" in reason
    assert "E3" in reason


def test_disclaimer_requires_both_e1_and_e3():
    """E1(비권유)만 있거나 E3(책임 소재)만 있으면 fail한다 — 라벨링 가이드
    §2⑤ B2·B3. 불확실성 고지("실제 결과와 다를 수 있다")만으로는 어느 쪽도
    충족하지 못한다(B4, 위조정밀도 P2가 담당). 기준일은 세 경우 모두 채워
    E1·E3 여부만 갈리게 한다."""
    prefix = f"기준일 {AS_OF_DATE} 기준 "

    e1_only = prefix + "투자 권유가 아니며 원금 또는 수익을 보장하지 않습니다."
    passed, reason = disclaimer(_explanations(e1_only), {AS_OF_DATE})
    assert passed is False
    assert "E3" in reason
    assert "E1" not in reason

    e3_only = prefix + "최종 의사결정 책임은 고객과 담당 PB에게 있습니다."
    passed, reason = disclaimer(_explanations(e3_only), {AS_OF_DATE})
    assert passed is False
    assert "E1" in reason
    assert "E3" not in reason

    uncertainty_only = prefix + "실제 결과와 다를 수 있습니다."
    passed, reason = disclaimer(_explanations(uncertainty_only), {AS_OF_DATE})
    assert passed is False
    assert "E1" in reason
    assert "E3" in reason

    both = prefix + (
        "투자 권유가 아니며 원금 또는 수익을 보장하지 않습니다. "
        "최종 의사결정 책임은 고객과 담당 PB에게 있습니다."
    )
    assert disclaimer(_explanations(both), {AS_OF_DATE})[0] is True


def test_disclaimer_e3_accepts_alternate_wordings_and_order():
    """PR #178 리뷰(다경) — E3 정규식이 "의사결정|판단 → 책임 → 주체 → 있|귀속"
    어순만 받아들여 정당한 면책문을 놓치는 문제를 재현·검증한다."""
    prefix = f"기준일 {AS_OF_DATE} 기준 "
    e1 = "투자 권유가 아니며 원금 또는 수익을 보장하지 않습니다. "

    subject_after_responsibility = prefix + e1 + "투자의 최종 책임은 고객에게 있습니다."
    assert disclaimer(_explanations(subject_after_responsibility), {AS_OF_DATE})[0] is True

    responsibility_attribution = (
        prefix + e1 + "본 자료에 따른 책임은 투자자 본인에게 귀속됩니다."
    )
    assert disclaimer(_explanations(responsibility_attribution), {AS_OF_DATE})[0] is True

    subject_first_reversed_order = (
        prefix + e1 + "고객님의 책임 하에 판단하시기 바랍니다."
    )
    assert disclaimer(_explanations(subject_first_reversed_order), {AS_OF_DATE})[0] is True


def test_prohibited_expression_negated_pass_and_positive_fail():
    assert prohibited_expression(_explanations("원금은 보장되지 않습니다."))[0] is True
    assert prohibited_expression(_explanations("원금은 보장 안 됨을 명시합니다."))[0] is True

    passed, reason = prohibited_expression(_explanations("수익률을 보장합니다."))
    assert passed is False
    assert "보장" in reason

    passed, _ = prohibited_expression(
        _explanations("수익이 보장됩니다. 투자 권유가 아니며 실제 결과와 다를 수 있습니다.")
    )
    assert passed is False

    passed, _ = prohibited_expression(_explanations("수익률을 보장 안정적으로 제공합니다."))
    assert passed is False


def test_prohibited_expression_ambiguous_negations_request_manual_review():
    explanations = _explanations("수익을 보장하지 않거나 못 한다고 봅니다.")
    passed, reason = prohibited_expression(explanations)
    assert passed is True
    assert "수동검토" in reason
    assert prohibited_manual_flags(explanations)


def test_prohibited_expression_clear_double_negation_fails():
    texts = (
        "수익률을 보장하지 않는다고 오해해서는 안 됩니다.",
        "수익률을 보장하지 않는다고, 오해해서는 안 됩니다.",
        "수익을 보장하지 않을 수 없습니다.",
        "수익 보장이 아니라고 할 수 없습니다.",
        "수익을 보장하지 않는다고 착각하지 마십시오.",
    )
    for text in texts:
        explanations = _explanations(text)
        passed, reason = prohibited_expression(explanations)

        assert passed is False
        assert "명시적 이중부정" in reason
        assert prohibited_manual_flags(explanations) == []


def test_judge_eval_normal_e2e_passes_with_fake_llm():
    out = judge_eval(_normal_state(), llm=_AxisLLM())

    assert out["judge"]["passed"] is True
    assert out["judge_feedback"] == ""
    assert set(out["judge"]["rubric"]) == {
        "source_validity",
        "numeric_consistency",
        "hallucination",
        "false_precision",
        "disclaimer",
        "prohibited_expression",
    }
    assert all(axis["passed"] for axis in out["judge"]["rubric"].values())


def test_old_house_view_adds_non_blocking_freshness_warning():
    state = _normal_state()
    route = {
        "topic": "VaR 설명",
        "category": "house_view",
        "evidence_role": "interpretation_reference",
        "routing_reason": "CVaR 기여도 1위 자산군: 국내주식(domestic_equity)",
    }
    state["run_config"]["audit"] = {
        "llm": {
            "rag_cite": {
                "latest": {
                    "routing_contract": "rag-routing-v1",
                    "routes": [route],
                }
            }
        }
    }
    state["citations"] = [
        {
            **VERIFIED_CITATION,
            "extra": {
                **VERIFIED_CITATION["extra"],
                "category": "house_view",
                "evidence_role": "interpretation_reference",
                "routing_reason": route["routing_reason"],
                "published_at": "2025-05-01",
            },
        }
    ]

    out = judge_eval(state, llm=_AxisLLM())

    freshness = next(
        check
        for check in out["judge"]["checks"]
        if check["name"] == "citation_publication_freshness"
    )
    assert out["judge"]["passed"] is True
    assert freshness["passed"] is False
    assert freshness["required"] is False
    assert any("최신성 중대 경고" in flag for flag in out["judge"]["manual_review_flags"])


def test_judge_retry_limit_exits_with_manual_review_warning():
    state = _normal_state()
    failing_llm = _AxisLLM(hallucination_passed=False)

    current_state = state
    last_out = {}
    for attempt in range(1, JUDGE_MAX_RETRIES + 1):
        last_out = judge_eval(current_state, llm=failing_llm)
        current_state = {**current_state, **last_out}
        expected = (
            "manual_review_gate"
            if attempt == JUDGE_MAX_RETRIES
            else "rag_cite"
        )
        assert route_after_judge(current_state) == expected

    assert current_state["judge_retries"] == JUDGE_MAX_RETRIES
    assert MANUAL_REVIEW_WARNING in last_out["judge"]["manual_review_flags"]

    # 재시도를 소진해도 리포트는 확정되지 않는다.
    report = manual_review_gate(current_state)["report"]
    assert MANUAL_REVIEW_WARNING in report["warnings"]
    assert report["finalized"] is False
    assert report["status"] == "pending_manual_review"
    assert report["governance"]["manual_review_gate"]["status"] == "blocked"
