import { useDashboardStore } from "@/lib/store";
import { useViewedPortfolio } from "@/lib/viewedPortfolio";
import {
  allocationPlan,
  maxPensionKeepingNeed as calcMaxPensionKeepingNeed,
  pensionAccount,
  type TaxAccountInput,
  type AllocationPlan,
} from "@/lib/taxAccounts";
import type { Customer } from "@/lib/mockData";

/**
 * 절세계좌 배분을 화면과 리포트가 같은 값으로 보게 하는 한 곳.
 *
 * 배분은 백엔드 없이 프론트에서 계산한다(`lib/taxAccounts.ts`) — 한도·세액공제율·
 * 의무보유기간이 전부 법정 상수라 조회할 외부 소스가 없다. 그런데 그 계산이
 * TaxSection 안에 있고 슬라이더 값도 그 컴포넌트의 useState 였다. PDF 는 store 만
 * 읽으므로 리포트에는 그 숫자가 하나도 닿지 않았다 — 화면이 "약 +97만원" 을
 * 말할 때 리포트는 "분석 후 계산" 이라는 문구를 그대로 인쇄했다.
 *
 * 확정 대상 안을 store 에 두고 훅 하나로 읽게 한 것(`useViewedPortfolio`)과 같은
 * 방식으로 옮긴다. 읽는 쪽이 늘어나도 계산은 여기 한 번만 있다.
 */

/** 세금 흐름 막대(TaxWaterfall)와 리포트 비교표가 함께 쓰는 입력. */
export interface TaxFlowInput {
  /** 운용자산(만원) */
  aumManwon: number;
  current: { expectedReturnPct: number; afterTaxReturnPct: number };
  selected: {
    name: string;
    expectedReturnPct: number;
    afterTaxReturnPct: number;
  };
  /**
   * 금융소득세를 직접 줄이는 절감액(만원) — ISA.
   *
   * ⚠️ 전제: 위 afterTaxReturnPct 가 **일반계좌 원천징수 기준**이라고 본다. 그래야
   *    ISA 절감을 그 위에 얹는 것이 맞다. 만약 그 세후수익률이 이미 ISA 활용을
   *    가정한 값이라면 같은 절감을 두 번 세게 된다.
   *
   *    지금 mockData 의 포트폴리오 지표에는 그 값이 무슨 기준인지 적혀 있지 않고,
   *    원래 백엔드가 계산하던 값이라 확인할 방법이 없다. 금액이 작아(이 고객 18만원)
   *    결론을 흔들지는 않지만, 포트폴리오 지표를 실계산으로 붙일 때 세후수익률의
   *    정의를 먼저 못박아야 한다.
   */
  financialTaxSavingManwon: number;
  /** 근로소득세에서 돌려받는 환급액(만원) — 연금 세액공제 */
  creditRefundManwon: number;
}

export interface TaxPlanState {
  customer: Customer | undefined;
  /** 배분 결과. 고객 정보가 없으면 null. */
  plan: AllocationPlan | null;
  /** 연 납입여력(만원) */
  budgetManwon: number;
  /** 슬라이더가 놓인 자리(만원) — 손대지 않았으면 연금 잔여한도. */
  pensionRequestManwon: number;
  setPensionRequestManwon: (v: number) => void;
  /**
   * 근시일 필요자금을 지키면서 연금에 넣을 수 있는 최대 납입액(만원).
   * 유동액과 같은 규칙이어야 해서 계산 모듈에 맡긴다 — 화면에서 따로 유도하면
   * ISA 의무보유가 목표 시점 뒤에 풀리는 고객에서 두 값이 갈린다.
   */
  pensionCeilingForNeed: number | null;
}

function accountInputOf(customer: Customer | undefined): TaxAccountInput | null {
  if (!customer) return null;
  return {
    salaryManwon: customer.salaryManwon,
    isaUsedManwon: customer.isaUsedManwon,
    isaYearsSinceOpen: customer.isaYearsSinceOpen,
    pensionUsedManwon: customer.pensionUsedManwon,
    age: customer.age,
    horizonYears: customer.horizonYears,
    isaOpened: customer.isaOpened,
    isaYearsUntilLiquid: customer.isaYearsUntilLiquid,
  };
}

export function useTaxPlan(): TaxPlanState {
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  const stored = useDashboardStore((s) => s.pensionRequestManwon);
  const setStored = useDashboardStore((s) => s.setPensionRequestManwon);

  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const input = accountInputOf(customer);

  /*
   * 기본값은 연금 한도를 꽉 채운 상태다. "한도부터 채운다" 는 통념이 이 고객에게는
   * 왜 틀리는지가 슬라이더를 건드리기 전에 바로 보여야 하기 때문이다.
   */
  const defaultPension = input ? pensionAccount(input).headroomManwon : 0;
  const pensionRequestManwon = stored ?? defaultPension;

  const budgetManwon = customer?.annualContributionManwon ?? 0;
  const needYears = customer?.nearTermNeedYears ?? 0;

  const plan =
    input && customer
      ? allocationPlan(input, budgetManwon, pensionRequestManwon, needYears)
      : null;

  const pensionCeilingForNeed =
    input && customer
      ? calcMaxPensionKeepingNeed(
          input,
          budgetManwon,
          customer.nearTermNeedManwon,
          needYears,
        )
      : null;

  return {
    customer,
    plan,
    budgetManwon,
    pensionRequestManwon,
    setPensionRequestManwon: setStored,
    pensionCeilingForNeed,
  };
}

/**
 * 세금 흐름 막대의 입력.
 *
 * 기준이 되는 안은 **확정 대상 안**이다(`useViewedPortfolio`). PB 가 제안 조정으로
 * 비중을 손봤는데 이 막대만 조정 전 제안을 그리면, 같은 화면의 계좌 배치 막대·
 * 리포트 비교표와 다른 안을 말하게 된다.
 */
export function useTaxFlow(): TaxFlowInput | null {
  const portfolios = useDashboardStore((s) => s.portfolios);
  const { viewed } = useViewedPortfolio();
  const { customer, plan } = useTaxPlan();

  const current = portfolios.find((p) => p.id === "current");
  if (!customer || !plan || !viewed || !current) return null;

  return {
    aumManwon: customer.aumEokwon * 10000,
    current: {
      expectedReturnPct: current.metrics.expectedReturnPct,
      afterTaxReturnPct: current.metrics.afterTaxReturnPct,
    },
    selected: {
      name: viewed.name,
      expectedReturnPct: viewed.metrics.expectedReturnPct,
      afterTaxReturnPct: viewed.metrics.afterTaxReturnPct,
    },
    // ISA 는 금융소득세를 직접 깎지만 연금 세액공제는 근로소득세에서 돌려받는
    // 돈이라 같은 막대에 못 쌓는다. 두 갈래로 나눠 넘긴다.
    financialTaxSavingManwon: plan.isaSavingManwon,
    creditRefundManwon: plan.pensionSavingManwon,
  };
}
