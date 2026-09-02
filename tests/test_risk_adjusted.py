"""위험조정 성과 지표(Sharpe·MDD) 계약 테스트.

9월 과제가 요구한 것은 값이 아니라 **값 + 가정**이다.

    기대수익·변동성·Sharpe·MDD와 함께 VaR/CVaR, 스트레스 시나리오 2개 이상을
    보여 주고, **가정을 적을 것**

가정 없이 숫자만 내면 case_022 의 함정(엔진 미산출 지표를 근거 없이 표시)과
같은 것이 된다. 그래서 assumptions 블록의 존재를 테스트로 고정한다.
"""
import numpy as np
import pandas as pd
import pytest
import yaml

from engine.context import CalcContext
from engine.deterministic.metrics import (
    TRADING_DAYS_PER_YEAR,
    annualized_return,
    annualized_volatility,
    compute_metrics,
    max_drawdown,
    risk_adjusted_metrics,
    sharpe_ratio,
)
from engine.deterministic.returns import DEFAULT_RF_ANNUAL, data_period, load_returns
from engine.nodes.load_inputs import CONFIG_PATH, DUMMY_PORTFOLIO


# ── 1. 손으로 검증 가능한 값 ──────────────────────────────────────────────

def test_max_drawdown_hand_checkable():
    """+10% → -20% → +5% 곡선의 최대낙폭.

    자산곡선 1.0 → 1.10 → 0.88 → 0.924
    고점 1.10 대비 저점 0.88 → 낙폭 (1.10-0.88)/1.10 = 0.20
    """
    ret = np.array([0.10, -0.20, 0.05])
    dd = max_drawdown(ret)
    assert dd["mdd"] == pytest.approx(0.20)
    assert dd["peak"] == 0      # 곡선 1.10 지점(인덱스 0)
    assert dd["trough"] == 1    # 곡선 0.88 지점
    assert dd["recovered"] is None      # 0.924 는 1.10 을 못 넘었다


def test_max_drawdown_records_recovery():
    """저점 이후 고점을 되찾으면 회복 시점을 남긴다."""
    ret = np.array([0.10, -0.20, 0.30])   # 1.10 → 0.88 → 1.144 (고점 회복)
    dd = max_drawdown(ret)
    assert dd["recovered"] == 2
    assert dd["recovery_days"] == 1


def test_max_drawdown_is_zero_for_monotonic_rise():
    dd = max_drawdown(np.array([0.01, 0.01, 0.01]))
    assert dd["mdd"] == 0.0
    assert dd["peak"] is None and dd["trough"] is None


def test_max_drawdown_sign_is_positive_for_loss():
    """부호 규약: 양수 = 낙폭. historical_var·run_stress 와 통일한다."""
    dd = max_drawdown(np.array([-0.5, 0.0]))
    assert dd["mdd"] == pytest.approx(0.5)
    # 고점은 관측 시작 직전(초기 자본)이다 — 대응하는 날짜가 없다.
    assert dd["peak"] == "구간_시작"
    assert dd["trough"] == 0


def test_max_drawdown_labels_dates_when_index_given():
    idx = pd.bdate_range("2026-01-01", periods=3)
    dd = max_drawdown(np.array([0.10, -0.20, 0.05]), index=idx)
    assert dd["peak"] == str(idx[0].date())
    assert dd["trough"] == str(idx[1].date())


def test_annualization_uses_252():
    """연율화 계수는 가정이므로 값이 바뀌면 테스트가 잡아야 한다."""
    assert TRADING_DAYS_PER_YEAR == 252
    ret = np.full(100, 0.001)
    assert annualized_return(ret) == pytest.approx(0.001 * 252)


def test_sharpe_matches_formula():
    rng = np.random.default_rng(7)
    ret = rng.normal(0.0004, 0.008, 500)
    expected = (annualized_return(ret) - 0.0325) / annualized_volatility(ret)
    assert sharpe_ratio(ret, 0.0325) == pytest.approx(expected)


# ── 2. 근거 없는 수치를 만들지 않는다 ─────────────────────────────────────

def test_sharpe_is_none_when_volatility_is_zero():
    """0으로 나눈 값이나 임의 상수를 내지 않는다 — 그게 위조정밀도다."""
    assert sharpe_ratio(np.full(50, 0.001), 0.0325) is None


def test_metrics_are_none_on_insufficient_data():
    assert annualized_return(np.array([])) is None
    assert annualized_volatility(np.array([0.01])) is None


# ── 3. 가정을 항상 함께 낸다 ──────────────────────────────────────────────

def test_assumptions_block_is_always_present():
    ra = risk_adjusted_metrics(
        np.array([0.01, -0.02, 0.03]), rf_annual=0.0325, rf_source="config.yaml:rf_rate"
    )
    a = ra["assumptions"]
    assert a["trading_days_per_year"] == 252
    assert a["rf_annual"] == 0.0325
    assert a["rf_source"] == "config.yaml:rf_rate"
    assert a["volatility_ddof"] == 1
    assert a["drawdown_sign"] == "positive_is_loss"


def test_rf_source_is_recorded_when_context_missing():
    """컨텍스트 없이 계산해도 '무엇을 썼는지'는 남아야 한다."""
    df = load_returns(n=250)
    m = compute_metrics(
        returns_df=df, portfolio=DUMMY_PORTFOLIO, confidence=0.99, horizons=[1, 10],
        data_period_meta=data_period(df), data_source="dummy", seed=42,
    )
    a = m["risk_adjusted"]["assumptions"]
    assert a["rf_annual"] == 0.0
    assert "미지정" in a["rf_source"]


def test_rf_comes_from_context_when_given():
    df = load_returns(n=250)
    ctx = CalcContext.from_run_config(
        {"as_of_date": "2026-08-28", "data_source": "real"},
        rf_annual=DEFAULT_RF_ANNUAL, rf_applied=True,
    )
    m = compute_metrics(
        returns_df=df, portfolio=DUMMY_PORTFOLIO, confidence=0.99, horizons=[1, 10],
        data_period_meta=data_period(df), data_source="dummy", seed=42, context=ctx,
    )
    a = m["risk_adjusted"]["assumptions"]
    assert a["rf_annual"] == DEFAULT_RF_ANNUAL
    assert a["rf_source"] == "config.yaml:rf_rate"


# ── 4. 해시 계약 ──────────────────────────────────────────────────────────

def test_risk_adjusted_is_covered_by_computation_hash():
    """지표가 달라지면 해시도 달라져야 한다 — 안 그러면 재현 대조가 무의미하다."""
    df = load_returns(n=250)
    args = dict(
        returns_df=df, portfolio=DUMMY_PORTFOLIO, confidence=0.99, horizons=[1, 10],
        data_period_meta=data_period(df), data_source="dummy", seed=42,
    )
    ctx_a = CalcContext(as_of="2026-08-28", rf_annual=0.0325, rf_source="a")
    ctx_b = CalcContext(as_of="2026-08-28", rf_annual=0.0500, rf_source="a")
    ha = compute_metrics(**args, context=ctx_a)["meta"]["computation_hash"]
    hb = compute_metrics(**args, context=ctx_b)["meta"]["computation_hash"]
    assert ha != hb, "무위험수익률이 바뀌면 Sharpe 가 바뀌고 해시도 바뀌어야 한다"


# ── 5. 설정 정합 ──────────────────────────────────────────────────────────

def test_sharpe_rf_default_matches_config():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["rf_rate"] == DEFAULT_RF_ANNUAL
