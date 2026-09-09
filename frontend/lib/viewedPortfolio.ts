import { CALC_UNITS } from "@/lib/assetMapping";
import type { Portfolio } from "@/lib/mockData";
import { selectViewedPlanKey, useDashboardStore } from "@/lib/store";
import { withSharpe } from "@/lib/sharpe";

/** 위험자산 비중(%) — 주식 4종 합계. 조정 강도를 재는 축이다. */
function equityShare(weights: Portfolio["weights"]): number {
  return CALC_UNITS.filter((u) => u.group === "주식").reduce(
    (sum, u) => sum + (weights[u.id] ?? 0),
    0,
  );
}

/**
 * 조정안의 지표를 현재↔제안 사이 보간으로 유도한다.
 *
 * 자산군별 수익률·변동성 계열이 아직 없어 실제 재계산은 불가능하다. 그렇다고
 * 임의의 숫자를 박으면 화면 숫자의 출처를 코드에서 따라갈 수 없게 되므로,
 * 대신 **위험자산(주식) 비중을 축으로 한 선형 보간**이라는 규칙 하나를 둔다.
 * t=0 이면 현재 포트폴리오의 지표, t=1 이면 제안의 지표이고, 조정으로 주식
 * 비중이 그 사이 어디에 놓이는지가 t 다. 같은 입력이면 같은 값이 나온다.
 *
 * 시연용 근사이며, 백엔드 지표 산출이 붙으면 이 함수는 통째로 걷어낸다.
 * 샤프만은 보간하지 않고 `withSharpe` 로 다시 유도한다 — 기대수익률·변동성과
 * 어긋난 샤프가 나오는 것을 막기 위해서다.
 */
export function deriveAdjustedMetrics(
  current: Portfolio,
  base: Portfolio,
  adjustedWeights: Portfolio["weights"],
): Portfolio["metrics"] {
  const curEq = equityShare(current.weights);
  const baseEq = equityShare(base.weights);
  const adjEq = equityShare(adjustedWeights);
  const span = baseEq - curEq;
  // 두 안의 주식 비중이 같으면 축이 서지 않는다. 이때는 제안 지표를 그대로 둔다.
  const rawT = Math.abs(span) < 0.01 ? 1 : (adjEq - curEq) / span;
  // 관측 구간 밖으로 멀리 나간 외삽은 신뢰할 수 없어 양끝을 조금만 열어 둔다.
  const t = Math.min(1.5, Math.max(-0.5, rawT));

  const lerp = (a: number, b: number) => a + (b - a) * t;
  const c = current.metrics;
  const b = base.metrics;

  return withSharpe({
    ...b,
    expectedReturnPct: Number(lerp(c.expectedReturnPct, b.expectedReturnPct).toFixed(1)),
    volatilityPct: Number(lerp(c.volatilityPct, b.volatilityPct).toFixed(1)),
    sortino: Number(lerp(c.sortino, b.sortino).toFixed(2)),
    mddPct: Number(lerp(c.mddPct, b.mddPct).toFixed(1)),
    afterTaxReturnPct: Number(lerp(c.afterTaxReturnPct, b.afterTaxReturnPct).toFixed(1)),
    // 백엔드가 준 원화 병기는 조정 전 비중의 값이라 버린다. 화면이 비율×총자산으로 다시 만든다.
    volatilityAmountLabel: undefined,
    mddAmountLabel: undefined,
    afterTaxAmountLabel: undefined,
  });
}

/**
 * 지금 확정 대상인 안을 돌려준다.
 *
 * PB 가 제안 조정으로 비중을 손보면 화면·확정 스냅샷은 그 안을 기준으로 움직인다
 * (`selectViewedPlanKey`). 리포트가 조정 전 제안을 그대로 내보내면 승인한 것과
 * 다른 문서가 나가므로, PDF 도 같은 식을 쓴다.
 *
 * 비중은 PB 가 손본 값이고, 지표는 `deriveAdjustedMetrics` 가 현재↔제안 사이
 * 보간으로 유도한다(백테스트 곡선은 제안의 것을 그대로 쓴다).
 */
export function useViewedPortfolio(): {
  base: Portfolio | undefined;
  viewed: Portfolio | undefined;
  isAdjusted: boolean;
} {
  const portfolios = useDashboardStore((s) => s.portfolios);
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const proposedWeightsInput = useDashboardStore((s) => s.proposedWeightsInput);
  const viewedPlanKey = useDashboardStore(selectViewedPlanKey);

  const selId: "a" | "b" = selectedPortfolioId === "b" ? "b" : "a";
  const base = portfolios.find((p) => p.id === selId);
  const isAdjusted = viewedPlanKey === "proposed" && !!base;

  const current = portfolios.find((p) => p.id === "current");

  let viewed: Portfolio | undefined = base;
  if (isAdjusted && base) {
    const weights = CALC_UNITS.reduce(
      (acc, u) => ({ ...acc, [u.id]: proposedWeightsInput[u.id] ?? 0 }),
      {} as Portfolio["weights"],
    );
    viewed = {
      ...base,
      name: "제안 조정",
      // 도넛용 8자산군 원본은 조정 비중과 맞지 않으므로 버리고 11종 비중만 쓴다.
      allocation: undefined,
      weights,
      metrics: current
        ? deriveAdjustedMetrics(current, base, weights)
        : base.metrics,
    };
  }

  return { base, viewed, isAdjusted };
}
