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

/** 흐름 막대 한 줄 — 세후 수익 / 금융소득세 / 세액공제 환급(만원). */
export interface TaxFlowRow {
  name: string;
  afterTax: number;
  tax: number;
  refund: number;
}

/** 총액을 세목으로 쪼갠 값. 세 항이 그대로 더해져 금융소득이 된다. */
export interface TaxFlowBreakdown {
  financialManwon: number;
  pretaxGainManwon: number;
  /** 전환으로 늘어난 금융소득세 — 금융소득에서 빠지는 몫이라 부호가 뒤집힌다. */
  switchTaxManwon: number;
  /** ISA 가 도로 깎은 금융소득세. switchTax − isaCut 이 실제 세금 증가분이다. */
  isaCutManwon: number;
  refundManwon: number;
}

export interface TaxFlowRows {
  rows: TaxFlowRow[];
  breakdown: TaxFlowBreakdown;
  /** 현재 대비 1년치 차이(만원) = 금융소득 + 근로소득세 환급. */
  totalSavingManwon: number;
  pretaxLabel: string;
  totalLabel: string;
}

/**
 * 흐름 막대 세 줄과 세목 분해.
 *
 * 화면(TaxWaterfall)과 리포트가 같은 함수를 부른다. 막대와 분해 줄이 서로 다른
 * 식으로 구해지면 "세전 = 세후 + 세금" 이 화면 안에서 어긋난다.
 */
export function deriveTaxFlowRows(flow: TaxFlowInput): TaxFlowRows {
  const { aumManwon: aum, current, selected } = flow;
  const pct = (v: number) => Math.round((aum * v) / 100);

  const curAfter = pct(current.afterTaxReturnPct);
  const curTax = pct(current.expectedReturnPct) - curAfter;
  const selAfter = pct(selected.afterTaxReturnPct);
  const selTax = pct(selected.expectedReturnPct) - selAfter;

  const isaSaving = Math.round(flow.financialTaxSavingManwon);
  const refund = Math.round(flow.creditRefundManwon);

  const rows: TaxFlowRow[] = [
    { name: "현재", afterTax: curAfter, tax: curTax, refund: 0 },
    { name: selected.name, afterTax: selAfter, tax: selTax, refund: 0 },
    {
      // ISA 절감은 금융소득세를 직접 깎으므로 세후 수익으로 넘어간다.
      name: "+ 절세 제안",
      afterTax: selAfter + isaSaving,
      tax: Math.max(selTax - isaSaving, 0),
      refund,
    },
  ];

  /*
   * 세 값을 막대에서 직접 뺀다. 전환 이익과 ISA 절감을 따로 더하면 세금 조각에
   * 걸린 하한(Math.max(selTax - isaSaving, 0))을 지나쳐 화면과 어긋날 수 있다.
   * 이렇게 두면 세전 = 세후 + 세금 이 막대와 항상 같은 값으로 맞는다.
   */
  const financialManwon = rows[2].afterTax - rows[0].afterTax;
  const taxDeltaManwon = rows[2].tax - rows[0].tax;
  const switchTaxManwon = rows[1].tax - rows[0].tax;

  return {
    rows,
    breakdown: {
      financialManwon,
      pretaxGainManwon: financialManwon + taxDeltaManwon,
      switchTaxManwon,
      // 차액으로 구한다. 이렇게 두면 세전 − 전환세금 + ISA 가 늘 금융소득과 맞는다.
      isaCutManwon: switchTaxManwon - taxDeltaManwon,
      refundManwon: refund,
    },
    totalSavingManwon: financialManwon + refund,
    pretaxLabel: `${selected.name} 기준 · 자산 ${(aum / 10000).toFixed(1)}억`,
    /*
     * "손에 남는 돈" 은 세후 수익 전체로 읽혀 총액처럼 보였다. 이 값은 현재
     * 포트폴리오를 그대로 뒀을 때와 견준 1년치 차이다.
     *
     * 고객 앞에서 그대로 읽는 화면이라 다른 라벨과 같은 명사구·존대 어투로
     * 맞춘다("연간 절세 효과", "3대 절세계좌 활용 시 예상 추가 절감").
     * "따지면" 은 따져 묻는 말로 들리고 "남는 돈"·"순증" 은 총액으로 읽히거나
     * 어려웠다. "세후 기준" 이 이 카드의 핵심을, "기대" 가 추정치임을 말한다 —
     * 위 지표 카드가 이미 "세후 수익률" 이라 용어도 이어진다.
     *
     * "연간" 은 빼지 않는다 — 금융소득도 세액공제도 매년 되풀이되는 금액인데
     * 기간이 없으면 한 번 받는 돈으로 읽힌다.
     */
    totalLabel: "세후 기준 연간 기대 효과",
  };
}
