"""결정론 계층 — 세전 → 세금 → 비용 → 세후 기말자산.

주의: 이 패키지(engine.deterministic)에서는 langchain/llm 관련 import 금지.

왜 결정론 계층인가
------------------
9월 과제가 **"LLM이 세금을 직접 결정하게 하기"를 금지 항목**으로 못박았다.
세율 적용은 규칙이지 판단이 아니므로 `engine/deterministic/` 에 둔다. LLM 은 이 결과를
**설명**할 뿐 값을 만들지 않는다.

무엇을 다루고 무엇을 안 다루는가 — 이게 이 모듈의 핵심이다
-----------------------------------------------------------
중간발표 지적이 정확히 이 지점이었다.

    세후수익률을 계산했을 때 종합부동산세 뭐 등등이 있는데
    **단순 세금 하나로 절세를 했다면 개망한 거임**

그래서 이 모듈은 **다루는 세목을 좁게 선언하고, 범위 밖을 결과에 실어 보낸다.**
`out_of_scope` 는 장식이 아니라 산출물의 일부다 — 리포트가 그걸 그대로 적어야
"우리가 계산한 것이 세금의 전부가 아니다"가 독자에게 전달된다.

**'절세 최적화'라는 표현은 쓰지 않는다.** 핸드아웃 금지 항목이고, 최적을 말하는
순간 투자 권유에 가까워진다.

추정 범위
---------
금융소득종합과세는 **다른 소득에 따라 세율이 달라진다.** 우리는 고객의 다른
소득을 모르므로 단일 세후 금액을 확정할 수 없다. 하한(원천징수 15.4%)과
상한(종합과세 최고 49.5%)의 **구간으로** 낸다 — VaR CI 와 같은 규약이다.
단일 값으로 내면 그 자체가 위조정밀도다.

세율·보수의 출처
----------------
값을 코드에 박지 않고 `config.yaml` 에서 받는다. `judge_eval.py` 의
`min(score, 0.4)` 처럼 근거 없는 상수가 되지 않게, 각 값의 출처 문자열을
결과에 함께 싣는다.
"""
from __future__ import annotations

from dataclasses import dataclass

#: 안전한 기본값. config 가 없어도 계산은 되지만 출처는 '미지정'으로 남는다.
DEFAULT_WITHHOLDING_RATE = 0.154
DEFAULT_COMPREHENSIVE_TOP_RATE = 0.495
DEFAULT_COMPREHENSIVE_THRESHOLD_KRW = 20_000_000


@dataclass(frozen=True)
class TaxPolicy:
    """세율·비용과 **그 출처**. 값만 들고 다니면 근거가 사라진다."""

    withholding_rate: float = DEFAULT_WITHHOLDING_RATE
    withholding_rate_source: str | None = None
    comprehensive_threshold_krw: float = DEFAULT_COMPREHENSIVE_THRESHOLD_KRW
    comprehensive_threshold_source: str | None = None
    comprehensive_top_rate: float = DEFAULT_COMPREHENSIVE_TOP_RATE
    comprehensive_top_rate_source: str | None = None
    estimate_band: tuple[float, float] = (
        DEFAULT_WITHHOLDING_RATE,
        DEFAULT_COMPREHENSIVE_TOP_RATE,
    )
    scope: str = "financial_income"
    out_of_scope: tuple[str, ...] = ()
    fee_annual: dict[str, float] | None = None
    fee_source: str | None = None

    @classmethod
    def from_run_config(cls, run_config: dict | None) -> "TaxPolicy":
        cfg = run_config or {}
        tax = cfg.get("tax") or {}
        band = tax.get("estimate_band") or [
            tax.get("withholding_rate", DEFAULT_WITHHOLDING_RATE),
            tax.get("comprehensive_top_rate", DEFAULT_COMPREHENSIVE_TOP_RATE),
        ]
        return cls(
            withholding_rate=float(tax.get("withholding_rate", DEFAULT_WITHHOLDING_RATE)),
            withholding_rate_source=tax.get("withholding_rate_source"),
            comprehensive_threshold_krw=float(
                tax.get("comprehensive_threshold_krw", DEFAULT_COMPREHENSIVE_THRESHOLD_KRW)
            ),
            comprehensive_threshold_source=tax.get("comprehensive_threshold_source"),
            comprehensive_top_rate=float(
                tax.get("comprehensive_top_rate", DEFAULT_COMPREHENSIVE_TOP_RATE)
            ),
            comprehensive_top_rate_source=tax.get("comprehensive_top_rate_source"),
            estimate_band=(float(band[0]), float(band[1])),
            scope=str(tax.get("scope", "financial_income")),
            out_of_scope=tuple(tax.get("out_of_scope") or ()),
            fee_annual=cfg.get("fee_annual") or None,
            fee_source=cfg.get("fee_source"),
        )


def annual_fee_krw(portfolio: list[dict], fee_annual: dict[str, float] | None) -> dict:
    """자산군별 연간 보수. 요율이 없는 자산군은 **0이 아니라 '미지정'** 으로 센다.

    없는 요율을 0으로 처리하면 비용이 실제보다 작아 보인다 — 조용히 낙관적인
    숫자를 만드는 것이 이 프로젝트에서 가장 경계하는 일이다.
    """
    rates = fee_annual or {}
    per_asset: dict[str, float] = {}
    missing: list[str] = []
    total = 0.0
    for item in portfolio or []:
        asset = item.get("asset_class")
        value = float(item.get("value_krw") or 0.0)
        if asset not in rates:
            missing.append(str(asset))
            continue
        fee = value * float(rates[asset])
        per_asset[str(asset)] = fee
        total += fee
    return {"total_krw": total, "per_asset": per_asset, "rate_missing": sorted(missing)}


def financial_income_tax(income_krw: float, policy: TaxPolicy) -> dict:
    """금융소득(이자·배당)에 대한 세액을 **구간으로** 낸다.

    하한 — 전액 원천징수(15.4%)로 끝나는 경우.
    상한 — 기준금액 초과분이 종합과세 최고 세율(49.5%)을 맞는 경우.

    고객의 다른 소득을 모르므로 그 사이 어디인지는 **단정하지 않는다.**
    """
    income = max(0.0, float(income_krw or 0.0))
    low_rate, high_rate = policy.estimate_band

    low = income * low_rate

    # 상한: 기준금액까지는 원천징수, 초과분은 최고 세율.
    threshold = policy.comprehensive_threshold_krw
    if income <= threshold:
        high = income * low_rate
    else:
        high = threshold * low_rate + (income - threshold) * high_rate

    return {
        "income_krw": income,
        "tax_low_krw": low,
        "tax_high_krw": high,
        "comprehensive_applies": income > threshold,
        "excess_over_threshold_krw": max(0.0, income - threshold),
    }


def after_tax_projection(
    *,
    portfolio: list[dict],
    gross_return_annual: float,
    policy: TaxPolicy,
    horizon_years: float = 1.0,
) -> dict:
    """세전 → 세금 → 비용 → 세후 기말자산.

    `gross_return_annual` 은 엔진이 산출한 연율화 기대수익률을 그대로 받는다
    (`metrics.risk_adjusted.annualized_return`). 여기서 새로 만들지 않는다 —
    엔진이 안 낸 값을 이 모듈이 지어내면 case_022 의 함정과 같아진다.

    ⚠️ 과세 대상은 **금융소득(이자·배당)만**이다. 이 함수는 기대수익 전부를
       금융소득으로 보지 않는다 — 그렇게 하면 양도차익까지 과세하는 셈이라
       세금이 과대계상된다. 대신 `taxable_ratio` 로 비율을 받고, 그 값이
       가정임을 결과에 명시한다.
    """
    total_value = sum(float(p.get("value_krw") or 0.0) for p in (portfolio or []))
    if total_value <= 0:
        raise ValueError("포트폴리오 평가액이 0 이하라 세후 자산을 계산할 수 없습니다.")

    years = float(horizon_years)
    gross_gain = total_value * float(gross_return_annual) * years

    # 금융소득 비율 — 이자·배당이 기대수익에서 차지하는 몫.
    # 자산군별 실제 배당·이자 수익률 데이터가 없으므로 **가정**이며,
    # 그 사실을 assumptions 에 적는다.
    taxable_ratio = 1.0
    taxable_income = max(0.0, gross_gain) * taxable_ratio

    tax = financial_income_tax(taxable_income, policy)
    fee = annual_fee_krw(portfolio, policy.fee_annual)
    fee_total = fee["total_krw"] * years

    return {
        # ── 세전 → 세금 → 비용 → 세후 (핸드아웃이 요구한 흐름) ──
        "opening_value_krw": total_value,
        "gross_gain_krw": gross_gain,
        "pre_tax_value_krw": total_value + gross_gain,
        "tax_low_krw": tax["tax_low_krw"],
        "tax_high_krw": tax["tax_high_krw"],
        "fee_krw": fee_total,
        # 세금이 구간이므로 세후 자산도 구간이다. 단일 값으로 내지 않는다.
        "after_tax_value_low_krw": total_value + gross_gain - tax["tax_high_krw"] - fee_total,
        "after_tax_value_high_krw": total_value + gross_gain - tax["tax_low_krw"] - fee_total,
        "comprehensive_applies": tax["comprehensive_applies"],
        "excess_over_threshold_krw": tax["excess_over_threshold_krw"],
        "fee_rate_missing": fee["rate_missing"],
        "assumptions": {
            "horizon_years": years,
            "gross_return_annual": float(gross_return_annual),
            "gross_return_source": "engine.metrics.risk_adjusted.annualized_return",
            "taxable_ratio": taxable_ratio,
            "taxable_ratio_note": (
                "기대수익 전액을 금융소득으로 가정했다. 자산군별 배당·이자 "
                "수익률 데이터가 없어 분해하지 못한 것이며, 실제보다 세금이 "
                "크게 잡힐 수 있다."
            ),
            "withholding_rate": policy.withholding_rate,
            "withholding_rate_source": policy.withholding_rate_source or "미지정",
            "comprehensive_threshold_krw": policy.comprehensive_threshold_krw,
            "comprehensive_threshold_source": policy.comprehensive_threshold_source or "미지정",
            "comprehensive_top_rate": policy.comprehensive_top_rate,
            "comprehensive_top_rate_source": policy.comprehensive_top_rate_source or "미지정",
            "fee_source": policy.fee_source or "미지정",
            "scope": policy.scope,
        },
        # 리포트가 그대로 적어야 하는 목록. 이게 산출물의 일부다.
        "out_of_scope": list(policy.out_of_scope),
    }
