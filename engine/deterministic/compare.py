"""결정론 계층 — 목적·리스크가 다른 두 배분안을 나란히 놓는다.

주의: 이 패키지(engine.deterministic)에서는 langchain/llm 관련 import 금지.

9월 과제 요구:

    포트폴리오는 목적·리스크가 다른 **비교안(A/B 등)**이 있고,
    대체자산(금·리츠·원자재·달러 등)을 하나 이상 넣을 것

이 모듈이 **하지 않는 것** — 여기가 더 중요하다
------------------------------------------------
핸드아웃 금지 항목에 **'최적 포트폴리오'** 가 있다. 그래서 이 모듈은

  * 두 안에 **순위를 매기지 않는다.** `better`·`recommended`·`score` 같은
    키를 만들지 않는다.
  * "어느 쪽이 낫다"를 판단하지 않는다. **차이만** 낸다.
  * 고르는 주체는 사람이다. 그 선택의 근거는 승인 기록에 남는다.

중간발표에서 리뷰어가 말한 그림이 이것이다 — AI 는 결과를 나란히 놓고,
PB 가 고르고, 그 판단 근거가 기록된다.

같은 조건에서 쟀는가
--------------------
두 안을 비교하려면 **같은 기준일·같은 데이터·같은 시드**로 계산돼야 한다.
한쪽만 다른 조건이면 비교 자체가 거짓이 된다. `compare_metrics()` 는 두
결과의 계산 컨텍스트가 다르면 **예외를 던진다** — 조용히 비교하지 않는다.
계산 컨텍스트(engine/context.py)를 만든 이유 중 하나가 정확히 이것이다.
"""
from __future__ import annotations


class ComparisonContextMismatch(ValueError):
    """두 배분안이 다른 조건에서 계산됐다. 비교하면 안 된다."""


#: 비교에 실을 지표. 여기 없는 값은 표에 넣지 않는다 — 화면에 뜨는 값은
#: 전부 엔진이 산출한 것이어야 한다(case_022 의 교훈).
COMPARED_KEYS = (
    ("var_1d_krw", "1일 VaR"),
    ("var_10d_krw", "10일 VaR"),
    ("cvar_1d_krw", "1일 CVaR"),
    ("annualized_return", "연율화 기대수익"),
    ("annualized_volatility", "연율화 변동성"),
    ("sharpe_ratio", "Sharpe"),
    ("max_drawdown", "최대낙폭"),
    ("worst_stress_loss_krw", "최악 스트레스 손실"),
)


def derive_defensive_variant(
    portfolio: list[dict],
    *,
    shift: float = 0.10,
    from_classes: tuple[str, ...] = ("domestic_equity", "global_equity", "reits"),
    to_classes: tuple[str, ...] = ("domestic_bond", "global_bond", "cash"),
) -> list[dict]:
    """위험자산 비중을 규칙대로 옮겨 **방어적 성격의 비교안**을 만든다.

    ⚠️ 이건 **권유가 아니라 규칙 기반 파생**이다. `shift` 만큼을 위험자산에서
    덜어 방어자산으로 옮길 뿐이며, 이 비율이 적정하다는 근거는 없다.
    산출물에 그 사실을 실어 보낸다.

    총 평가액은 보존한다 — 두 안의 규모가 다르면 비교가 성립하지 않는다.
    """
    if not portfolio:
        raise ValueError("포트폴리오가 비어 있어 비교안을 만들 수 없습니다.")
    total = sum(float(p.get("value_krw") or 0.0) for p in portfolio)
    if total <= 0:
        raise ValueError("포트폴리오 평가액이 0 이하입니다.")

    by_class = {str(p.get("asset_class")): dict(p) for p in portfolio}
    movable = sum(
        float(by_class[c]["value_krw"]) for c in from_classes if c in by_class
    )
    moved = min(movable, total * float(shift))
    if moved <= 0:
        # 옮길 위험자산이 없으면 원안을 그대로 돌려준다(빈 비교안을 만들지 않는다).
        return [dict(p) for p in portfolio]

    # 출처: 위험자산에서 보유 비중에 비례해 덜어낸다.
    for c in from_classes:
        if c in by_class:
            share = float(by_class[c]["value_krw"]) / movable
            by_class[c]["value_krw"] = float(by_class[c]["value_krw"]) - moved * share
    # 목적지: 방어자산에 균등 배분한다.
    targets = [c for c in to_classes if c in by_class]
    if not targets:
        raise ValueError(f"옮겨 담을 자산군이 없습니다: {to_classes}")
    for c in targets:
        by_class[c]["value_krw"] = float(by_class[c]["value_krw"]) + moved / len(targets)

    out = []
    for p in portfolio:
        item = by_class[str(p.get("asset_class"))]
        item["weight"] = float(item["value_krw"]) / total
        out.append(item)
    return out


def _extract(metrics: dict) -> dict:
    """비교에 쓸 값만 뽑는다. 없는 값은 None 으로 둔다(0으로 채우지 않는다)."""
    m = metrics or {}
    horizons = m.get("horizons") or {}
    ra = m.get("risk_adjusted") or {}
    stress = m.get("stress") or {}

    losses = [
        float(v.get("loss_krw"))
        for v in stress.values()
        if isinstance(v, dict) and isinstance(v.get("loss_krw"), (int, float))
    ]
    return {
        "var_1d_krw": (horizons.get("1d") or {}).get("var_krw"),
        "var_10d_krw": (horizons.get("10d") or {}).get("var_krw"),
        "cvar_1d_krw": (horizons.get("1d") or {}).get("cvar_krw"),
        "annualized_return": ra.get("annualized_return"),
        "annualized_volatility": ra.get("annualized_volatility"),
        "sharpe_ratio": ra.get("sharpe_ratio"),
        "max_drawdown": ra.get("max_drawdown"),
        "worst_stress_loss_krw": max(losses) if losses else None,
    }


def _context_of(metrics: dict) -> dict:
    meta = (metrics or {}).get("meta") or {}
    ctx = meta.get("calc_context") or {}
    # 컨텍스트가 없는 구버전 결과도 최소한 이 셋으로는 대조한다.
    return {
        "as_of": ctx.get("as_of"),
        "currency": ctx.get("currency") or meta.get("base_currency"),
        "data_source": ctx.get("data_source") or meta.get("data_source"),
        "seed": ctx.get("seed") if ctx else meta.get("seed"),
        "n_observations": meta.get("n_observations"),
    }


def compare_metrics(metrics_a: dict, metrics_b: dict, *, label_a: str = "A안",
                    label_b: str = "B안") -> dict:
    """두 배분안의 지표를 나란히 놓는다. **우열은 판단하지 않는다.**

    같은 조건에서 계산되지 않았으면 `ComparisonContextMismatch` 를 던진다 —
    조건이 다른 두 값을 나란히 놓는 것 자체가 오해를 만든다.
    """
    ctx_a, ctx_b = _context_of(metrics_a), _context_of(metrics_b)
    if ctx_a != ctx_b:
        differing = {k: (ctx_a.get(k), ctx_b.get(k)) for k in ctx_a if ctx_a.get(k) != ctx_b.get(k)}
        raise ComparisonContextMismatch(
            f"두 배분안이 다른 조건에서 계산됐습니다: {differing}. "
            "같은 기준일·데이터·시드로 다시 계산해야 비교할 수 있습니다."
        )

    a, b = _extract(metrics_a), _extract(metrics_b)
    rows = []
    for key, ko in COMPARED_KEYS:
        va, vb = a.get(key), b.get(key)
        delta = (vb - va) if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None
        rows.append({"key": key, "label": ko, "a": va, "b": vb, "delta": delta})

    return {
        "labels": {"a": label_a, "b": label_b},
        "context": ctx_a,          # 두 안이 공유하는 조건. 화면에 함께 적는다.
        "rows": rows,
        # ⚠️ 순위·추천을 담지 않는다. 이 dict 에 'better'·'recommended' 키가
        #    생기면 '최적 포트폴리오' 금지 항목에 걸린다.
        "selection": {
            "decided_by": "human",
            "note": (
                "본 비교는 두 배분안의 산출 결과를 나란히 제시할 뿐이며 "
                "어느 쪽을 권고하지 않습니다. 선택과 그 근거는 담당 PB가 "
                "승인 기록에 남깁니다."
            ),
        },
    }
