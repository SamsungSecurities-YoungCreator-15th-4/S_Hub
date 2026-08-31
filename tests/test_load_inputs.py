"""load_inputs 노드 — market_data_ref가 실제 data_source와 일치하는지 검증.

[리뷰 반영] market_data_ref["source"]가 항상 "dummy"로 하드코딩돼 있어,
var_engine이 실제로는 data_source="real"을 쓰는데 state에는 "dummy"로
남는 출처 모순이 있었다. config.yaml의 data_source를 그대로 반영하도록
고친 뒤, 그 회귀를 여기서 검증한다.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.nodes.load_inputs import load_inputs


def test_market_data_ref_matches_config_data_source():
    """config.yaml의 data_source(현재 "real")가 market_data_ref.source에 그대로 반영된다."""
    result = load_inputs({})
    assert result["market_data_ref"]["source"] == "real"
    assert "yfinance" in result["market_data_ref"]["note"]


def test_market_data_ref_reflects_dummy_source(monkeypatch, tmp_path):
    """data_source="dummy"인 config에서는 market_data_ref도 dummy로 일관되게 남는다."""
    import engine.nodes.load_inputs as load_inputs_mod

    dummy_config_path = tmp_path / "config.yaml"
    dummy_config_path.write_text(
        'seed: 42\nas_of_date: "2026-07-03"\nbase_currency: KRW\n'
        "rf_rate: 0.0325\nvar_confidence: 0.99\nhorizons: [1, 10]\n"
        "data_source: dummy\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(load_inputs_mod, "CONFIG_PATH", dummy_config_path)

    result = load_inputs({})
    assert result["market_data_ref"]["source"] == "dummy"
    assert "더미" in result["market_data_ref"]["note"]


def test_load_inputs_validates_hard_stop_policy_before_graph(monkeypatch):
    """정책 파일 오류는 terminal gate가 아니라 그래프 첫 노드에서 드러나야 한다."""
    import engine.nodes.load_inputs as load_inputs_mod

    def invalid_policy() -> str:
        raise ValueError("Hard Stop 정책 설정 오류")

    monkeypatch.setattr(
        load_inputs_mod,
        "resolve_hard_stop_policy_version",
        invalid_policy,
    )

    with pytest.raises(ValueError, match="Hard Stop 정책 설정 오류"):
        load_inputs({})


def test_graph_stops_at_first_node_for_invalid_hard_stop_policy(
    monkeypatch,
    tmp_path,
):
    """실제 정책 파일 오류면 downstream·terminal gate 전에 그래프가 실패해야 한다."""
    import engine.graph as graph_module
    import engine.hard_stop_policy as policy_module

    invalid_policy = tmp_path / "hard_stop_policy.yaml"
    invalid_policy.write_text('version: ""\n', encoding="utf-8")
    monkeypatch.setattr(policy_module, "HARD_STOP_POLICY_PATH", invalid_policy)
    policy_module.resolve_hard_stop_policy_version.cache_clear()

    downstream_calls: list[str] = []

    def should_not_run(state):
        downstream_calls.append("downstream")
        return {}

    monkeypatch.setattr(graph_module, "extract_ips", should_not_run)
    monkeypatch.setattr(graph_module, "manual_review_gate", should_not_run)
    graph = graph_module.build_graph()

    try:
        with pytest.raises(ValueError, match="version"):
            graph.invoke(
                {},
                {"configurable": {"thread_id": "invalid-hard-stop-policy"}},
            )
        assert downstream_calls == []
    finally:
        policy_module.resolve_hard_stop_policy_version.cache_clear()
