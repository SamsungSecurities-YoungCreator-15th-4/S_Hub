/**
 * S.ymphony 리포트가 진단하는 대상 — 화면·PDF 가 같이 읽는다.
 *
 * 리포트는 원래 상담 전 보유 비중만 보고 있었다. 상수로 적힌 값이라 그럴 수밖에
 * 없었고, 그 결과 "제안대로 옮기면 이 위험이 어떻게 되는가" 에 리포트가 답하지
 * 못했다. 지금은 확정 대상 안(제안 A/B 또는 제안 조정)을 진단한다.
 *
 * 상담 전 비중은 `baseline` 으로 함께 넘긴다 — 없어진 것이 아니라 비교 대상이
 * 되었다. IPS 충돌 검사가 "상한을 넘었었고 이 안에서 풀렸다" 를 말할 수 있는 것도
 * 두 비중을 같이 들고 있기 때문이다.
 */

import { useDashboardStore } from "./store";
import { useViewedPortfolio } from "./viewedPortfolio";
import type { CalcUnitWeights } from "./assetMapping";
import type { Customer, Portfolio } from "./mockData";

export interface SymphonySubject {
  /** 진단 대상 안. */
  portfolio: Portfolio | undefined;
  /** 화면에 적을 대상 이름 ("안정 추구" / "제안 조정"). */
  label: string;
  /** 상담 전 보유 비중. 비교용이며 대상이 아니다. */
  baselineWeights: CalcUnitWeights | undefined;
  /** 총 평가금액(원). 고객 레코드의 운용자산에서 읽는다. */
  totalKrw: number;
  customer: Customer | undefined;
}

export function useSymphonySubject(): SymphonySubject {
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  const portfolios = useDashboardStore((s) => s.portfolios);
  const { viewed } = useViewedPortfolio();

  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];

  return {
    portfolio: viewed,
    label: viewed?.name ?? "제안",
    baselineWeights: portfolios.find((p) => p.id === "current")?.weights,
    totalKrw: (customer?.aumEokwon ?? 0) * 100_000_000,
    customer,
  };
}
