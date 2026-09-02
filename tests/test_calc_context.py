"""계산 컨텍스트(engine.context.CalcContext) 계약 테스트.

가장 중요한 성질은 **해시 불변**이다. 컨텍스트는 '무엇으로 계산했나'를 기록할 뿐이고
계산 입력을 바꾸지 않는다. 이게 깨지면 기존 실행과의 대조가 전부 끊긴다.
"""
import yaml

from engine.context import CalcContext, rag_index_fingerprint
from engine.deterministic.metrics import compute_metrics
from engine.deterministic.returns import DEFAULT_RF_ANNUAL, data_period, load_returns
from engine.nodes.load_inputs import CONFIG_PATH, DUMMY_PORTFOLIO
from engine.nodes.var_engine import var_engine


def _common_args():
    df = load_returns(n=250, as_of_date="2026-07-03")
    return dict(
        returns_df=df,
        portfolio=DUMMY_PORTFOLIO,
        confidence=0.99,
        horizons=[1, 10],
        base_currency="KRW",
        data_period_meta=data_period(df),
        fx_applied=False,
        methodology_ref="methodology_var_cvar_2026",
        data_source="dummy",
        seed=42,
    )


# ── 1. 해시 불변 ──────────────────────────────────────────────────────────

def test_context_does_not_change_computation_hash():
    """컨텍스트를 붙여도 computation_hash 가 바뀌면 안 된다.

    바뀌면 8월·9월 산출물 대조가 끊기고, 컨텍스트 도입이 '안전한 변경'이 아니게 된다.
    """
    args = _common_args()
    without = compute_metrics(**args)
    with_ctx = compute_metrics(**args, context=CalcContext(as_of="2026-07-03"))
    assert without["meta"]["computation_hash"] == with_ctx["meta"]["computation_hash"]


def test_context_does_not_change_any_number():
    args = _common_args()
    without = compute_metrics(**args)
    with_ctx = compute_metrics(**args, context=CalcContext(as_of="2026-07-03"))
    assert without["horizons"] == with_ctx["horizons"]
    assert without["stress"] == with_ctx["stress"]


# ── 2. 빠졌던 값이 실제로 기록되는가 ──────────────────────────────────────

def test_rf_annual_is_recorded_when_applied():
    """rf_annual 이 meta 에 없던 것이 컨텍스트 도입의 직접 동기다."""
    ctx = CalcContext.from_run_config(
        {"as_of_date": "2026-07-03", "data_source": "real"},
        rf_annual=DEFAULT_RF_ANNUAL,
        rf_applied=True,
    )
    meta = ctx.as_meta()
    assert meta["rf_annual"] == DEFAULT_RF_ANNUAL
    assert meta["rf_applied"] is True
    assert meta["rf_source"] == "config.yaml:rf_rate"


def test_rf_is_marked_unapplied_on_dummy_path():
    """더미 경로는 cash 도 합성이라 rf 가 개입하지 않는다.

    설정에 rf_rate 가 있다고 '썼다'고 기록하면 그 자체가 위조정밀도다.
    """
    state = {
        "run_config": {
            "as_of_date": "2026-07-03", "data_source": "dummy", "base_currency": "KRW",
            "seed": 42, "rf_rate": 0.0325, "var_confidence": 0.99,
            "horizons": [1, 10], "var_lookback_days": 250,
        },
        "portfolio": DUMMY_PORTFOLIO,
    }
    out = var_engine(state)["metrics"]
    ctx = out["meta"]["calc_context"]
    # 수익률 생성에는 안 쓰였다 → rf_applied False
    assert ctx["rf_applied"] is False
    assert ctx["data_source"] == "dummy"
    # 그러나 Sharpe 의 무위험수익률은 별개 용도이므로 설정값이 그대로 실린다.
    # 두 쓰임을 다시 섞으면(rf_annual=None) Sharpe 가 rf=0 으로 계산돼 왜곡된다.
    assert ctx["rf_annual"] == 0.0325
    assert out["risk_adjusted"]["assumptions"]["rf_annual"] == 0.0325


def test_var_engine_records_context_fields():
    state = {
        "run_config": {
            "as_of_date": "2026-07-03", "data_source": "dummy", "base_currency": "KRW",
            "seed": 42, "var_confidence": 0.99, "horizons": [1, 10],
            "var_lookback_days": 250,
        },
        "portfolio": DUMMY_PORTFOLIO,
    }
    ctx = var_engine(state)["metrics"]["meta"]["calc_context"]
    assert ctx["as_of"] == "2026-07-03"
    assert ctx["currency"] == "KRW"
    assert ctx["seed"] == 42


# ── 3. 설정과의 정합 ──────────────────────────────────────────────────────

def test_default_as_of_matches_config_yaml():
    """returns.DEFAULT_AS_OF 와 config.yaml 의 as_of_date 가 갈리면 실패한다.

    갈리면 as_of_date 인자를 생략한 호출이 **조용히 다른 구간**을 쓴다.
    기준일은 숫자의 일부라 이런 불일치는 리포트 전체를 오염시킨다.
    """
    from engine.deterministic.returns import DEFAULT_AS_OF

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["as_of_date"] == DEFAULT_AS_OF


def test_default_rf_matches_config_yaml():
    """returns.DEFAULT_RF_ANNUAL 과 config.yaml 의 rf_rate 가 갈라지면 실패한다.

    context.py 가 순환 import 를 피하려 상수를 참조하지 않으므로 여기서 묶어 둔다.
    """
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["rf_rate"] == DEFAULT_RF_ANNUAL


# ── 4. 불변성·안전성 ──────────────────────────────────────────────────────

def test_context_is_immutable():
    """실행 중에 계산 조건이 바뀌면 같은 실행이 아니다."""
    import dataclasses

    ctx = CalcContext(as_of="2026-07-03")
    try:
        ctx.as_of = "2026-01-01"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("CalcContext 는 frozen 이어야 한다")


def test_rag_fingerprint_is_tolerant_of_missing_index(tmp_path):
    """인덱스를 못 읽는 것이 계산을 막을 이유는 아니다 — 기록만 비운다."""
    assert rag_index_fingerprint(tmp_path / "없는파일.sqlite3") is None


def test_describe_is_human_readable():
    ctx = CalcContext(
        as_of="2026-07-03", data_source="real",
        rf_annual=0.0325, rf_applied=True, rag_index="ccbccf5b44be5b84",
    )
    line = ctx.describe()
    assert "2026-07-03" in line and "KRW" in line
    assert "3.2500%" in line
    assert "ccbccf5b44be5b84" in line
