/** 금액은 원, 수익률·비용률은 소수(4.5% = 0.045). */
export interface HomeGoalInput {
  currentAssets: number;
  monthlySavings: number;
  portfolioExpectedReturn: number;
  targetHousePrice: number;
  targetYears: number;
  expectedHousePriceGrowth: number;
  expectedMortgageAmount: number;
  purchaseCostRate: number;
}

export interface HomeGoalResult {
  futureHousePrice: number;
  purchaseCosts: number;
  requiredEquity: number;
  futureCurrentAssets: number;
  futureValueOfMonthlySavings: number;
  futureHomeFund: number;
  gap: number;
  /** 계산값은 100%를 초과할 수 있으며 UI에서만 제한한다. */
  achievementRate: number;
  requiredMonthlySavings: number | null;
  expectedAchievementMonths: number | null;
  additionalMonths: number | null;
  /** 현재 가격 기준. */
  affordableHousePrice: number;
  affordableHousePriceAtPurchase: number;
  status: "achieved" | "gap";
  projectionStatus: "found" | "not_found_within_limit";
  computation_hash: string;
  formulaVersion: string;
}

export type HomeGoalField = Exclude<keyof HomeGoalInput, "portfolioExpectedReturn">;
/** 입력 도중의 빈 문자열을 0으로 계산하지 않는다. 금액 입력 단위는 만원. */
export type HomeGoalDraft = Record<HomeGoalField, string>;

export const EMPTY_HOME_GOAL: HomeGoalDraft = {
  currentAssets: "", monthlySavings: "", targetHousePrice: "",
  targetYears: "", expectedHousePriceGrowth: "",
  expectedMortgageAmount: "", purchaseCostRate: "",
};

/** 사용자 요청의 시뮬레이션 입력 예시. 실제 고객 자산·정책 데이터가 아니다. */
export const EXAMPLE_HOME_GOAL: HomeGoalDraft = {
  currentAssets: "8000", monthlySavings: "150", targetHousePrice: "60000",
  targetYears: "3", expectedHousePriceGrowth: "2",
  expectedMortgageAmount: "40000", purchaseCostRate: "3",
};

export const HOME_GOAL_FIELDS: {
  key: HomeGoalField; label: string; unit: string; scale: number; step: string;
}[] = [
  { key: "currentAssets", label: "현재 주택 마련 자금", unit: "만원", scale: 10000, step: "1" },
  { key: "monthlySavings", label: "월 추가 저축액", unit: "만원", scale: 10000, step: "1" },
  { key: "targetHousePrice", label: "목표 주택가격 · 현재 기준", unit: "만원", scale: 10000, step: "1" },
  { key: "targetYears", label: "목표 매수 시점", unit: "년 후", scale: 1, step: "0.5" },
  { key: "expectedHousePriceGrowth", label: "예상 주택가격 상승률", unit: "% / 년", scale: 0.01, step: "0.1" },
  { key: "expectedMortgageAmount", label: "예상 대출액 · 가정", unit: "만원", scale: 10000, step: "1" },
  { key: "purchaseCostRate", label: "취득 부대비용률 · 가정", unit: "%", scale: 0.01, step: "0.1" },
];
