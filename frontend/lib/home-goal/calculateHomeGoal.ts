import type { HomeGoalInput, HomeGoalResult } from "./types";

export const FORMULA_VERSION = "home-goal-v1";
/** 달성 불가능을 단정하지 않고 이 범위 내 미달성으로 표시한다. */
export const MAX_PROJECTION_MONTHS = 600;

export const CALCULATION_ASSUMPTIONS = [
  "현재 자금은 연복리 (1+r)^t, 월 저축은 월말 납입·월복리 r/12로 계산합니다.",
  "연장 기간에도 집값과 취득 부대비용은 상승하며, 예상 대출액은 고정합니다.",
  "기대수익률이 일정하다고 가정한 세전 추정입니다. 투자세금·수수료·대출 상환액은 포함하지 않습니다.",
  "대출액·집값 상승률·부대비용률은 사용자 가정이며 대출 승인액이나 법정 세율이 아닙니다.",
  "구매 가능 주택가격은 현재 가격 기준입니다. 달성 시점은 최대 50년까지 월 단위로 탐색합니다.",
] as const;

export function validateHomeGoal(input: HomeGoalInput): void {
  for (const [key, value] of Object.entries(input)) {
    if (!Number.isFinite(value)) throw new Error(`${key}: 유효한 숫자를 입력해 주세요.`);
  }
  for (const key of ["currentAssets", "monthlySavings", "expectedMortgageAmount"] as const) {
    if (input[key] < 0 || input[key] > 1e14) throw new Error("자금·저축·대출액은 0원 이상 100조원 이하로 입력해 주세요.");
  }
  if (input.targetHousePrice <= 0 || input.targetHousePrice > 1e14) throw new Error("주택가격은 0원 초과 100조원 이하로 입력해 주세요.");
  const months = input.targetYears * 12;
  if (months < 0 || months > MAX_PROJECTION_MONTHS || Math.abs(months - Math.round(months)) > 1e-8) {
    throw new Error("매수 시점은 0~50년 범위에서 월 단위로 입력해 주세요. (예: 0.5년 = 6개월)");
  }
  if (input.portfolioExpectedReturn <= -1 || input.expectedHousePriceGrowth <= -1) throw new Error("연 수익률·집값 상승률은 -100%보다 커야 합니다.");
  if (input.purchaseCostRate < 0 || input.purchaseCostRate > 1) throw new Error("부대비용률은 0~100%로 입력해 주세요.");
}

/** 사용자 제공 공식: 월말 적립식 미래가치 S × ((1+i)^n - 1) / i.
 * expm1/log1p는 0에 가까운 수익률에서 소수점 상쇄 오차를 줄인다. */
function savingsFactor(annualReturn: number, months: number): number {
  const rate = annualReturn / 12;
  return rate === 0 ? months : Math.expm1(months * Math.log1p(rate)) / rate;
}

function project(input: HomeGoalInput, months: number) {
  const years = months / 12;
  const futureHousePrice = input.targetHousePrice * (1 + input.expectedHousePriceGrowth) ** years;
  const purchaseCosts = futureHousePrice * input.purchaseCostRate;
  // 대출 가정이 비용을 초과해도 음의 자기자본·달성률을 표시하지 않는다.
  const requiredEquity = Math.max(0, futureHousePrice + purchaseCosts - input.expectedMortgageAmount);
  const futureCurrentAssets = input.currentAssets * (1 + input.portfolioExpectedReturn) ** years;
  const futureValueOfMonthlySavings = input.monthlySavings * savingsFactor(input.portfolioExpectedReturn, months);
  const futureHomeFund = futureCurrentAssets + futureValueOfMonthlySavings;
  const values = { futureHousePrice, purchaseCosts, requiredEquity, futureCurrentAssets, futureValueOfMonthlySavings, futureHomeFund };
  if (Object.values(values).some((value) => !Number.isFinite(value))) throw new Error("입력한 상승률·기간으로 계산 가능한 숫자 범위를 초과했습니다.");
  return values;
}

/** 목표 시점을 유지하는 데 필요한 월말 저축액. 즉시 매수인데 부족하면 null. */
export function calculateRequiredSavings(input: HomeGoalInput): number | null {
  validateHomeGoal(input);
  const months = Math.round(input.targetYears * 12);
  const { requiredEquity, futureCurrentAssets } = project(input, months);
  const need = Math.max(0, requiredEquity - futureCurrentAssets);
  if (need === 0) return 0;
  if (months === 0) return null;
  const result = need / savingsFactor(input.portfolioExpectedReturn, months);
  if (!Number.isFinite(result)) throw new Error("필요 저축액이 계산 범위를 초과했습니다.");
  return result;
}

/** 목표 시점부터 탐색한다. 일찍 충족했다가 집값 상승으로 다시 부족해지는 경우도 방어. */
export function calculateTargetDate(input: HomeGoalInput): number | null {
  validateHomeGoal(input);
  for (let months = Math.round(input.targetYears * 12); months <= MAX_PROJECTION_MONTHS; months++) {
    const result = project(input, months);
    if (result.futureHomeFund >= result.requiredEquity) return months;
  }
  return null;
}

/** (미래자금 + 대출) / (1 + 비용률), 이후 집값 상승률로 현재 가격으로 환산. */
export function calculateAffordableHousePrice(input: HomeGoalInput): number {
  validateHomeGoal(input);
  const { futureHomeFund } = project(input, Math.round(input.targetYears * 12));
  const price = (futureHomeFund + input.expectedMortgageAmount) / (1 + input.purchaseCostRate) / (1 + input.expectedHousePriceGrowth) ** input.targetYears;
  if (!Number.isFinite(price)) throw new Error("구매 가능 가격이 계산 범위를 초과했습니다.");
  return price;
}

/** 정렬된 입력+공식 버전의 FNV-1a 재현성 지문. 보안 서명·승인 증명으로 사용하지 않는다. */
function computationHash(input: HomeGoalInput): string {
  const canonical = JSON.stringify([FORMULA_VERSION, MAX_PROJECTION_MONTHS, Object.entries(input).sort(([a], [b]) => a.localeCompare(b, "en"))]);
  let hash = 0x811c9dc5;
  for (let i = 0; i < canonical.length; i++) hash = Math.imul(hash ^ canonical.charCodeAt(i), 0x01000193) >>> 0;
  return `${FORMULA_VERSION}-fnv1a-${hash.toString(16).padStart(8, "0")}`;
}

export function calculateHomeGoal(input: HomeGoalInput): HomeGoalResult {
  validateHomeGoal(input);
  const months = Math.round(input.targetYears * 12);
  const projection = project(input, months);
  const gap = projection.requiredEquity - projection.futureHomeFund;
  const expectedAchievementMonths = calculateTargetDate(input);
  const achievementRate = projection.requiredEquity === 0 ? 100 : projection.futureHomeFund / projection.requiredEquity * 100;
  const affordableHousePriceAtPurchase = (projection.futureHomeFund + input.expectedMortgageAmount) / (1 + input.purchaseCostRate);
  if (![gap, achievementRate, affordableHousePriceAtPurchase].every(Number.isFinite)) throw new Error("계산 범위를 초과했습니다.");
  return {
    ...projection, gap, achievementRate,
    requiredMonthlySavings: calculateRequiredSavings(input),
    expectedAchievementMonths,
    additionalMonths: expectedAchievementMonths === null ? null : expectedAchievementMonths - months,
    affordableHousePrice: calculateAffordableHousePrice(input),
    affordableHousePriceAtPurchase,
    status: gap <= 0 ? "achieved" : "gap",
    projectionStatus: expectedAchievementMonths === null ? "not_found_within_limit" : "found",
    computation_hash: computationHash(input), formulaVersion: FORMULA_VERSION,
  };
}
