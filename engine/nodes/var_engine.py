"""결정론 리스크 엔진 호출 노드 — app.engine.metrics.compute_metrics() 위임.

7자산군 일별 수익률은 run_config["data_source"]에 따라 두 경로 중 하나로 받는다.
  - "dummy": app.engine.returns.load_returns() — 고정 수식 + parquet 캐시(네트워크 불요).
  - "real" (기본값): app.engine.returns.load_real_returns() — yfinance 조회 +
    parquet 캐시(로컬 전용, git 미커밋 — Yahoo Finance 재배포 제약). 발표 전 1회
    실행해 로컬 캐시를 미리 만들어두면 이후 오프라인에서도 동작한다.
  - 그 외 값은 조용히 dummy로 처리하지 않고 즉시 실패한다 — 실데이터 사용 여부는
    리스크 수치의 핵심 전제이므로 오타를 방치하면 설명가능성이 깨진다.
동일 config·동일 데이터 하에서 computation_hash가 항상 동일함을 보장한다.

이 노드는 approval_gate를 통과한 뒤에만 실행되므로 승인 여부를 다시 검사하지 않는다.
"""
from engine.context import CalcContext
from engine.deterministic.metrics import compute_metrics
from engine.deterministic.compare import compare_metrics, derive_defensive_variant
from engine.deterministic.tax import TaxPolicy, after_tax_projection
from engine.deterministic.returns import (
    DEFAULT_N,
    DEFAULT_REAL_N,
    DEFAULT_RF_ANNUAL,
    FX_TICKER,
    REAL_ASSET_TICKERS,
    data_period,
    load_real_returns,
    load_returns,
)
from engine.state import RiskState

VALID_DATA_SOURCES = ("real", "dummy")


def var_engine(state: RiskState) -> dict:
    run_config = state.get("run_config") or {}
    as_of_date = run_config.get("as_of_date")
    data_source = run_config.get("data_source", "real")

    if data_source not in VALID_DATA_SOURCES:
        raise ValueError(
            f"지원하지 않는 data_source입니다: {data_source!r} "
            f"(허용값: {VALID_DATA_SOURCES}). 오타가 조용히 dummy로 처리되면 "
            "리포트 수치의 출처가 왜곡되므로 즉시 실패시킵니다."
        )

    if data_source == "real":
        n = run_config.get("var_lookback_days")
        n = n if n is not None else DEFAULT_REAL_N
        rf_rate = run_config.get("rf_rate")
        rf_annual = rf_rate if rf_rate is not None else DEFAULT_RF_ANNUAL
        returns_df = load_real_returns(n=n, as_of_date=as_of_date, rf_annual=rf_annual)
        fx_applied = True  # 해외자산은 USD/KRW 환율변동을 명시적으로 결합했다.
        tickers = dict(REAL_ASSET_TICKERS)
        fx_ticker = FX_TICKER
        # 공식(r_KRW = (1+r_USD)*(1+r_FX)-1)에 실제로 쓰인 기준일 환율값 —
        # load_real_returns가 returns_df.attrs에 실어 보낸다(캐시 히트여도 보존).
        fx_rate_asof = returns_df.attrs.get("fx_rate_asof")
    else:
        n = run_config.get("var_lookback_days") or DEFAULT_N
        returns_df = load_returns(n=n, as_of_date=as_of_date)
        # 더미 경로는 cash 도 _DUMMY_VOL 로 만들므로 **수익률 생성에는** rf 가
        # 개입하지 않는다. 다만 Sharpe 의 무위험수익률은 그것과 별개 용도이므로
        # 설정값을 그대로 쓴다. 두 쓰임을 rf_applied 로 구분해 기록한다.
        rf_rate = run_config.get("rf_rate")
        rf_annual = rf_rate if rf_rate is not None else DEFAULT_RF_ANNUAL
        fx_applied = False  # 더미 단계 — 환율 미적용.
        tickers = None
        fx_ticker = None
        fx_rate_asof = None  # 더미 경로는 환율 자체를 쓰지 않는다.

    seed = run_config.get("seed")
    seed = seed if seed is not None else 42

    # 두 배분안이 **같은 컨텍스트**를 쓰도록 먼저 만들어 둔다.
    # rf_applied 는 "수익률 시계열 생성에 rf 가 쓰였나"다(실데이터 경로의 cash).
    # rf_annual 은 Sharpe 의 무위험수익률로도 쓰이므로 두 경로 모두 기록한다.
    calc_context = CalcContext.from_run_config(
        run_config, rf_annual=rf_annual, rf_applied=(data_source == "real")
    ).with_rag_index()

    metrics = compute_metrics(
        returns_df=returns_df,
        portfolio=state.get("portfolio", []),
        confidence=run_config.get("var_confidence", 0.99),
        horizons=run_config.get("horizons", [1, 10]),
        base_currency=run_config.get("base_currency", "KRW"),
        data_period_meta=data_period(returns_df),
        fx_applied=fx_applied,
        methodology_ref="methodology_var_cvar_2026",
        data_source=data_source,
        tickers=tickers,
        fx_ticker=fx_ticker,
        fx_rate_asof=fx_rate_asof,
        seed=seed,  # VaR/CVaR 신뢰구간(bootstrap)의 재현성 고정 — config.yaml의 seed
        # 계산 조건을 한 곳에 묶어 결과에 기록한다. meta 전용이라 해시는 그대로다.
        context=calc_context,
    )

    # 세전 → 세금 → 비용 → 세후. 결정론 계층이며 LLM 이 관여하지 않는다.
    # 기대수익은 엔진이 이미 낸 값을 그대로 받는다 — 여기서 새로 만들지 않는다.
    gross = (metrics.get("risk_adjusted") or {}).get("annualized_return")
    if gross is not None:
        metrics["after_tax"] = after_tax_projection(
            portfolio=state.get("portfolio", []),
            gross_return_annual=gross,
            policy=TaxPolicy.from_run_config(run_config),
        )
    # ── A/B 비교안 ────────────────────────────────────────────────────
    #
    #  같은 returns_df·같은 컨텍스트로 **엔진을 한 번 더** 호출한다.
    #  state 스키마(portfolio: list 단수)를 건드리지 않으므로 기존 계약이
    #  그대로 유지된다. 비교안은 state["portfolio_b"] 로 받거나, 없으면
    #  규칙으로 파생한다(권유가 아니라 파생임을 산출물에 적는다).
    portfolio_a = state.get("portfolio", [])
    comparison_cfg = run_config.get("comparison") or {}
    if portfolio_a and comparison_cfg.get("enabled", True):
        portfolio_b = state.get("portfolio_b")
        derived = portfolio_b is None
        if derived:
            portfolio_b = derive_defensive_variant(
                portfolio_a, shift=float(comparison_cfg.get("defensive_shift", 0.10))
            )
        metrics_b = compute_metrics(
            returns_df=returns_df,          # 같은 데이터
            portfolio=portfolio_b,
            confidence=run_config.get("var_confidence", 0.99),
            horizons=run_config.get("horizons", [1, 10]),
            base_currency=run_config.get("base_currency", "KRW"),
            data_period_meta=data_period(returns_df),
            fx_applied=fx_applied,
            methodology_ref="methodology_var_cvar_2026",
            data_source=data_source,
            tickers=tickers,
            fx_ticker=fx_ticker,
            fx_rate_asof=fx_rate_asof,
            seed=seed,
            context=calc_context,           # 같은 컨텍스트 — 이게 비교의 전제다
        )
        comparison = compare_metrics(metrics, metrics_b)
        comparison["portfolio_b"] = portfolio_b
        comparison["b_is_derived"] = derived
        if derived:
            comparison["derivation_note"] = (
                f"B안은 위험자산 비중을 {comparison_cfg.get('defensive_shift', 0.10):.0%} "
                "덜어 방어자산으로 옮긴 **규칙 기반 파생안**입니다. 이 비율이 "
                "적정하다는 근거는 없으며, 권고안이 아닙니다."
            )
        metrics["comparison"] = comparison

    return {"metrics": metrics}
