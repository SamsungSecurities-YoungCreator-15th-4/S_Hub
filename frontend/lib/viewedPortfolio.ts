import { CALC_UNITS } from "@/lib/assetMapping";
import type { Portfolio } from "@/lib/mockData";
import { selectViewedPlanKey, useDashboardStore } from "@/lib/store";

/**
 * 지금 확정 대상인 안을 돌려준다.
 *
 * PB 가 제안 조정으로 비중을 손보면 화면·확정 스냅샷은 그 안을 기준으로 움직인다
 * (`selectViewedPlanKey`). 리포트가 조정 전 제안을 그대로 내보내면 승인한 것과
 * 다른 문서가 나가므로, PDF 도 같은 식을 쓴다.
 *
 * 반환하는 조정안은 비중만 PB 가 손본 값이고 지표·백테스트는 원래 제안의 것이다 —
 * 자산군별 수익률·변동성 계열이 없어 다시 계산할 수 없기 때문이다. 지표를 표시하는
 * 쪽은 `isAdjusted` 로 걸러 조정안 지표를 그대로 믿지 않게 한다.
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

  const viewed: Portfolio | undefined =
    isAdjusted && base
      ? {
          ...base,
          name: "제안 조정",
          // 도넛용 8자산군 원본은 조정 비중과 맞지 않으므로 버리고 11종 비중만 쓴다.
          allocation: undefined,
          weights: CALC_UNITS.reduce(
            (acc, u) => ({ ...acc, [u.id]: proposedWeightsInput[u.id] ?? 0 }),
            {} as Portfolio["weights"],
          ),
        }
      : base;

  return { base, viewed, isAdjusted };
}
