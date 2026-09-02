"""A/B 비교안(app.engine.compare) 계약 테스트.

이 모듈에서 가장 중요한 건 **하지 않는 것**이다.

  * 핸드아웃 금지 항목에 '최적 포트폴리오'가 있다 → 순위를 매기지 않는다
  * 조건이 다른 두 값을 나란히 놓으면 비교 자체가 거짓이다 → 거부한다

그래서 값이 맞는지보다 이 두 성질을 더 세게 검사한다.
"""
import json

import pytest
import yaml

from engine.context import CalcContext
from engine.deterministic.compare import (
    ComparisonContextMismatch,
    compare_metrics,
    derive_defensive_variant,
)
from engine.deterministic.metrics import compute_metrics
from engine.deterministic.returns import data_period, load_returns
from engine.nodes.load_inputs import CONFIG_PATH, DUMMY_PORTFOLIO


def _metrics(portfolio, *, ctx=None, seed=42):
    df = load_returns(n=250)
    return compute_metrics(
        returns_df=df, portfolio=portfolio, confidence=0.99, horizons=[1, 10],
        data_period_meta=data_period(df), data_source="dummy", seed=seed,
        context=ctx or CalcContext(as_of="2026-08-28", data_source="dummy", seed=42),
    )


# ── 1. 우열을 판단하지 않는다 ─────────────────────────────────────────────

def test_no_ranking_keys_anywhere():
    """'better'·'recommended'·'score' 같은 키가 생기면 권유에 가까워진다."""
    out = compare_metrics(_metrics(DUMMY_PORTFOLIO),
                          _metrics(derive_defensive_variant(DUMMY_PORTFOLIO)))
    blob = json.dumps(out, ensure_ascii=False).lower()
    for banned in ("better", "recommended", "recommend", "optimal", "best", "rank"):
        assert banned not in blob, f"비교 결과에 '{banned}' 가 들어가면 안 된다"


def test_selection_is_attributed_to_human():
    out = compare_metrics(_metrics(DUMMY_PORTFOLIO),
                          _metrics(derive_defensive_variant(DUMMY_PORTFOLIO)))
    assert out["selection"]["decided_by"] == "human"
    assert "권고하지 않습니다" in out["selection"]["note"]


def test_no_optimization_language_in_source():
    """'최적'이라는 표현이 산출물에 실리지 않는다."""
    out = compare_metrics(_metrics(DUMMY_PORTFOLIO),
                          _metrics(derive_defensive_variant(DUMMY_PORTFOLIO)))
    assert "최적" not in json.dumps(out, ensure_ascii=False)


# ── 2. 같은 조건에서 쟀는가 ───────────────────────────────────────────────

def test_different_context_is_rejected():
    """기준일이 다르면 비교 자체가 거짓이다 — 조용히 넘기지 않는다."""
    a = _metrics(DUMMY_PORTFOLIO, ctx=CalcContext(as_of="2026-08-28", data_source="dummy"))
    b = _metrics(DUMMY_PORTFOLIO, ctx=CalcContext(as_of="2026-07-03", data_source="dummy"))
    with pytest.raises(ComparisonContextMismatch) as e:
        compare_metrics(a, b)
    assert "as_of" in str(e.value)


def test_different_seed_is_rejected():
    a = _metrics(DUMMY_PORTFOLIO, ctx=CalcContext(as_of="2026-08-28", seed=42))
    b = _metrics(DUMMY_PORTFOLIO, ctx=CalcContext(as_of="2026-08-28", seed=7))
    with pytest.raises(ComparisonContextMismatch):
        compare_metrics(a, b)


def test_shared_context_is_reported():
    """두 안이 공유하는 조건을 화면에 함께 적을 수 있어야 한다."""
    out = compare_metrics(_metrics(DUMMY_PORTFOLIO),
                          _metrics(derive_defensive_variant(DUMMY_PORTFOLIO)))
    assert out["context"]["as_of"] == "2026-08-28"
    assert out["context"]["n_observations"] == 250


# ── 3. 파생 규칙 ──────────────────────────────────────────────────────────

def test_derived_variant_preserves_total_value():
    """규모가 다르면 비교가 성립하지 않는다."""
    b = derive_defensive_variant(DUMMY_PORTFOLIO, shift=0.10)
    assert sum(p["value_krw"] for p in b) == pytest.approx(
        sum(p["value_krw"] for p in DUMMY_PORTFOLIO)
    )
    assert sum(p["weight"] for p in b) == pytest.approx(1.0)


def test_derived_variant_reduces_risky_assets():
    a = {p["asset_class"]: p["weight"] for p in DUMMY_PORTFOLIO}
    b = {p["asset_class"]: p["weight"] for p in derive_defensive_variant(DUMMY_PORTFOLIO)}
    for risky in ("domestic_equity", "global_equity", "reits"):
        assert b[risky] < a[risky], f"{risky} 비중이 줄어야 한다"
    for safe in ("domestic_bond", "global_bond", "cash"):
        assert b[safe] > a[safe], f"{safe} 비중이 늘어야 한다"


def test_gold_is_not_treated_as_risky_here():
    """금은 방어 성격이라 위험자산 이전 대상이 아니다(conflict_check 와 같은 판단)."""
    a = {p["asset_class"]: p["weight"] for p in DUMMY_PORTFOLIO}
    b = {p["asset_class"]: p["weight"] for p in derive_defensive_variant(DUMMY_PORTFOLIO)}
    assert b["gold"] == pytest.approx(a["gold"])


def test_empty_portfolio_raises():
    with pytest.raises(ValueError):
        derive_defensive_variant([])


# ── 4. 값을 지어내지 않는다 ───────────────────────────────────────────────

def test_missing_metric_stays_none_not_zero():
    """엔진이 안 낸 값은 0이 아니라 None 이어야 한다."""
    bare = {"meta": {"calc_context": {"as_of": "x", "currency": "KRW",
                                      "data_source": "dummy", "seed": 42}}}
    out = compare_metrics(bare, bare)
    assert all(r["a"] is None and r["b"] is None and r["delta"] is None
               for r in out["rows"])


def test_rows_cover_the_declared_metrics():
    out = compare_metrics(_metrics(DUMMY_PORTFOLIO),
                          _metrics(derive_defensive_variant(DUMMY_PORTFOLIO)))
    labels = [r["label"] for r in out["rows"]]
    assert "Sharpe" in labels and "최대낙폭" in labels and "1일 VaR" in labels


# ── 5. 노드 연결 ──────────────────────────────────────────────────────────

def test_var_engine_produces_comparison_with_shared_context():
    from engine.nodes.var_engine import var_engine

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["data_source"] = "dummy"
    m = var_engine({"run_config": cfg, "portfolio": DUMMY_PORTFOLIO})["metrics"]
    c = m["comparison"]
    assert c["b_is_derived"] is True
    assert "권고안이 아닙니다" in c["derivation_note"]
    # 두 안이 같은 조건이었으므로 예외 없이 여기까지 왔다는 것이 곧 검증이다.
    assert c["context"]["as_of"] == cfg["as_of_date"]


def test_explicit_portfolio_b_is_used_as_is():
    from engine.nodes.var_engine import var_engine

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["data_source"] = "dummy"
    custom = derive_defensive_variant(DUMMY_PORTFOLIO, shift=0.20)
    m = var_engine({"run_config": cfg, "portfolio": DUMMY_PORTFOLIO,
                    "portfolio_b": custom})["metrics"]
    assert m["comparison"]["b_is_derived"] is False
    assert "derivation_note" not in m["comparison"]


def test_comparison_can_be_disabled():
    from engine.nodes.var_engine import var_engine

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["data_source"] = "dummy"
    cfg["comparison"] = {"enabled": False}
    m = var_engine({"run_config": cfg, "portfolio": DUMMY_PORTFOLIO})["metrics"]
    assert "comparison" not in m
