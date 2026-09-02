"""세금 엔진(app.engine.tax) 계약 테스트.

중간발표 지적이 이 파일의 존재 이유다.

    세후수익률을 계산했을 때 종합부동산세 뭐 등등이 있는데
    **단순 세금 하나로 절세를 했다면 개망한 거임**

그래서 값이 맞는지보다 **범위를 밝혔는지**를 더 세게 검사한다.
"""
import pytest
import yaml

from engine.deterministic.tax import (
    TaxPolicy,
    after_tax_projection,
    annual_fee_krw,
    financial_income_tax,
)
from engine.nodes.load_inputs import CONFIG_PATH, DUMMY_PORTFOLIO


def _policy() -> TaxPolicy:
    return TaxPolicy.from_run_config(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))


# ── 1. 범위를 반드시 밝힌다 ───────────────────────────────────────────────

def test_out_of_scope_is_not_empty():
    """다루지 않는 세목이 비어 있으면 '이게 세금의 전부'로 읽힌다."""
    assert _policy().out_of_scope, "범위 밖 세목 선언이 비어 있으면 안 된다"


def test_out_of_scope_names_the_big_ones():
    """중간발표에서 이름이 나온 세목들이 실제로 적혀 있어야 한다."""
    joined = " ".join(_policy().out_of_scope)
    assert "양도소득세" in joined
    assert "종합부동산세" in joined
    assert "상속" in joined


def test_projection_carries_out_of_scope_to_the_report():
    """산출물이 범위 밖 목록을 들고 나가야 리포트가 적을 수 있다."""
    out = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.05, policy=_policy()
    )
    assert out["out_of_scope"], "범위 밖 목록이 산출물에 실려야 한다"


def test_scope_is_declared():
    assert _policy().scope == "financial_income"


# ── 2. 단일 값으로 확정하지 않는다 ────────────────────────────────────────

def test_tax_is_a_range_not_a_point():
    """다른 소득을 모르므로 세액을 하나로 확정할 수 없다."""
    out = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.10, policy=_policy()
    )
    assert out["tax_low_krw"] < out["tax_high_krw"]
    assert out["after_tax_value_low_krw"] < out["after_tax_value_high_krw"]


def test_after_tax_low_uses_high_tax():
    """세후 하한은 세금 상한에서 나와야 한다 — 뒤집히면 낙관적으로 보인다."""
    out = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.10, policy=_policy()
    )
    expected_low = (
        out["pre_tax_value_krw"] - out["tax_high_krw"] - out["fee_krw"]
    )
    assert out["after_tax_value_low_krw"] == pytest.approx(expected_low)


# ── 3. 손으로 검증 가능한 세액 ────────────────────────────────────────────

def test_below_threshold_is_withholding_only():
    """기준금액 이하면 하한·상한이 같다 — 종합과세가 적용되지 않는다."""
    p = TaxPolicy(withholding_rate=0.154, comprehensive_threshold_krw=20_000_000,
                  comprehensive_top_rate=0.495, estimate_band=(0.154, 0.495))
    out = financial_income_tax(10_000_000, p)
    assert out["tax_low_krw"] == pytest.approx(10_000_000 * 0.154)
    assert out["tax_high_krw"] == pytest.approx(10_000_000 * 0.154)
    assert out["comprehensive_applies"] is False


def test_above_threshold_splits_at_the_line():
    """3,000만원이면 2,000만원까지 15.4%, 초과 1,000만원이 49.5%."""
    p = TaxPolicy(withholding_rate=0.154, comprehensive_threshold_krw=20_000_000,
                  comprehensive_top_rate=0.495, estimate_band=(0.154, 0.495))
    out = financial_income_tax(30_000_000, p)
    assert out["tax_low_krw"] == pytest.approx(30_000_000 * 0.154)
    assert out["tax_high_krw"] == pytest.approx(20_000_000 * 0.154 + 10_000_000 * 0.495)
    assert out["comprehensive_applies"] is True
    assert out["excess_over_threshold_krw"] == pytest.approx(10_000_000)


def test_negative_income_is_not_taxed():
    out = financial_income_tax(-5_000_000, _policy())
    assert out["tax_low_krw"] == 0.0 and out["tax_high_krw"] == 0.0


# ── 4. 비용 — 없는 요율을 0으로 만들지 않는다 ─────────────────────────────

def test_missing_fee_rate_is_reported_not_zeroed():
    """요율이 없는 자산군을 0으로 세면 비용이 실제보다 작아 보인다."""
    out = annual_fee_krw(
        [{"asset_class": "gold", "value_krw": 1_000_000_000},
         {"asset_class": "무엇인가", "value_krw": 1_000_000_000}],
        {"gold": 0.004},
    )
    assert out["total_krw"] == pytest.approx(4_000_000)
    assert out["rate_missing"] == ["무엇인가"]


def test_config_covers_every_asset_class():
    """자산군을 늘리면 보수 요율도 같이 늘려야 한다 — 안 그러면 조용히 빠진다."""
    out = annual_fee_krw(DUMMY_PORTFOLIO, _policy().fee_annual)
    assert out["rate_missing"] == []


# ── 5. 가정을 항상 함께 낸다 ──────────────────────────────────────────────

def test_assumptions_record_every_source():
    out = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.05, policy=_policy()
    )
    a = out["assumptions"]
    for key in ("withholding_rate_source", "comprehensive_threshold_source",
                "comprehensive_top_rate_source", "fee_source", "gross_return_source"):
        assert a[key], f"{key} 가 비어 있으면 근거 없는 값이 된다"


def test_unconfirmed_sources_say_so():
    """근거를 아직 못 찾은 값은 '가정'이라고 적혀 있어야 한다."""
    a = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.05, policy=_policy()
    )["assumptions"]
    assert "가정" in a["comprehensive_threshold_source"]
    assert "가정" in a["fee_source"]


def test_taxable_ratio_limitation_is_stated():
    """기대수익 전액을 금융소득으로 본 것은 과대계상이다 — 그 사실을 적는다."""
    a = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.05, policy=_policy()
    )["assumptions"]
    assert "크게 잡힐 수 있다" in a["taxable_ratio_note"]


def test_gross_return_is_not_invented_here():
    """기대수익은 엔진 산출값을 받아야 한다 — 이 모듈이 만들면 case_022 함정이다."""
    a = after_tax_projection(
        portfolio=DUMMY_PORTFOLIO, gross_return_annual=0.05, policy=_policy()
    )["assumptions"]
    assert a["gross_return_source"] == "engine.metrics.risk_adjusted.annualized_return"


# ── 6. 금지 표현 ──────────────────────────────────────────────────────────

def test_no_optimization_language_in_config():
    """'절세 최적화'는 핸드아웃 금지 항목이다."""
    raw = CONFIG_PATH.read_text(encoding="utf-8")
    assert "절세 최적화" not in raw.replace("'절세 최적화' 라는 표현은 쓰지 않는다", "")


# ── 7. 엔진 연결 ──────────────────────────────────────────────────────────

def test_var_engine_attaches_after_tax():
    from engine.nodes.var_engine import var_engine

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["data_source"] = "dummy"
    m = var_engine({"run_config": cfg, "portfolio": DUMMY_PORTFOLIO})["metrics"]
    assert "after_tax" in m
    assert m["after_tax"]["out_of_scope"]


def test_empty_portfolio_raises():
    with pytest.raises(ValueError):
        after_tax_projection(portfolio=[], gross_return_annual=0.05, policy=_policy())
