import { test } from "node:test";
import assert from "node:assert/strict";
import { calculateHomeGoal, calculateRequiredSavings, calculateTargetDate, calculateAffordableHousePrice } from "./calculateHomeGoal";
import { compareHomeGoalPortfolios, readHomeGoalDraft, describeHomeGoalComparison } from "./portfolioAdapter";
import { EXAMPLE_HOME_GOAL, EMPTY_HOME_GOAL, type HomeGoalInput } from "./types";
import type { Portfolio } from "../mockData";
import { formatWon } from "../format";

const example: HomeGoalInput = {
  currentAssets: 80_000_000, monthlySavings: 1_500_000, portfolioExpectedReturn: 0.045,
  targetHousePrice: 600_000_000, targetYears: 3, expectedHousePriceGrowth: 0.02,
  expectedMortgageAmount: 400_000_000, purchaseCostRate: 0.03,
};
const close = (actual: number, expected: number, tolerance = 0.01) => assert.ok(Math.abs(actual - expected) < tolerance, `${actual} != ${expected}`);

test("요청 입력의 회귀값: 예시 UI 숫자 대신 실제 공식을 적용", () => {
  const result = calculateHomeGoal(example);
  close(result.futureHousePrice, 636_724_800);
  close(result.purchaseCosts, 19_101_744);
  close(result.requiredEquity, 255_826_544);
  close(result.futureHomeFund, 148_992_422.881956);
  close(result.gap, 106_834_121.118044);
  close(result.achievementRate, 58.239626);
  close(result.requiredMonthlySavings!, 4_277_358.578419);
  assert.equal(result.expectedAchievementMonths, 122);
  assert.equal(result.additionalMonths, 86);
  close(result.affordableHousePrice, 502_260_020.950255);
});

test("독립적인 월말 적립 루프와 미래가치 일치 (양수·0·음수·매우 작은 수익률)", () => {
  for (const rate of [0.045, 0, -0.08, 1e-12]) {
    let savings = 0;
    for (let month = 0; month < 36; month++) savings = savings * (1 + rate / 12) + example.monthlySavings;
    const result = calculateHomeGoal({ ...example, portfolioExpectedReturn: rate });
    close(result.futureValueOfMonthlySavings, savings);
  }
});

test("필요 저축액 역산 후 목표 Gap이 0이 된다", () => {
  const monthlySavings = calculateRequiredSavings(example)!;
  close(calculateHomeGoal({ ...example, monthlySavings }).gap, 0);
});

test("구매 가능 현재 가격을 다시 입력하면 목표 Gap이 0이 된다", () => {
  const targetHousePrice = calculateAffordableHousePrice(example);
  close(calculateHomeGoal({ ...example, targetHousePrice }).gap, 0);
});

test("달성 시점 직전에는 부족하고, 달성 월에는 집값 상승까지 충족", () => {
  const month = calculateTargetDate(example)!;
  assert.ok(calculateHomeGoal({ ...example, targetYears: (month - 1) / 12 }).gap > 0);
  assert.ok(calculateHomeGoal({ ...example, targetYears: month / 12 }).gap <= 0);
});

test("0% 수익률은 원금 + 저축액 × 월수", () => {
  const result = calculateHomeGoal({ ...example, portfolioExpectedReturn: 0 });
  assert.equal(result.futureHomeFund, 134_000_000);
});

test("즉시 매수: 부족한 자금은 월 저축으로 역산하지 않는다", () => {
  const result = calculateHomeGoal({ ...example, targetYears: 0 });
  assert.equal(result.requiredMonthlySavings, null);
  assert.equal(result.futureHomeFund, example.currentAssets);
});

test("이미 달성: 음수 Gap과 100% 초과 원본 보존, 추가 기간은 0", () => {
  const result = calculateHomeGoal({ ...example, currentAssets: 800_000_000 });
  assert.equal(result.status, "achieved");
  assert.ok(result.gap < 0);
  assert.ok(result.achievementRate > 100);
  assert.equal(result.requiredMonthlySavings, 0);
  assert.equal(result.additionalMonths, 0);
});

test("대출이 총비용 이상: 필요자기자본 0, 달성률 유한", () => {
  const result = calculateHomeGoal({ ...example, expectedMortgageAmount: 900_000_000 });
  assert.equal(result.requiredEquity, 0);
  assert.equal(result.achievementRate, 100);
});

test("저축·자산이 없으면 탐색 상한 내 미달성", () => {
  const result = calculateHomeGoal({ ...example, currentAssets: 0, monthlySavings: 0 });
  assert.equal(result.expectedAchievementMonths, null);
  assert.equal(result.projectionStatus, "not_found_within_limit");
});

test("계산 지문은 입력 순서에 무관하며 입력 변화는 반영", () => {
  const reversed = Object.fromEntries(Object.entries(example).reverse()) as unknown as HomeGoalInput;
  assert.deepEqual(calculateHomeGoal(example), calculateHomeGoal(reversed));
  assert.notEqual(calculateHomeGoal(example).computation_hash, calculateHomeGoal({ ...example, monthlySavings: 1_500_001 }).computation_hash);
});

test("비정상 입력·기간·오버플로 방어", () => {
  for (const patch of [
    { currentAssets: NaN }, { monthlySavings: Infinity }, { targetYears: -1 },
    { targetYears: 51 }, { targetYears: 0.01 }, { portfolioExpectedReturn: -1 },
    { expectedHousePriceGrowth: -1 }, { targetHousePrice: 0 }, { purchaseCostRate: -0.1 },
    { expectedMortgageAmount: -1 }, { currentAssets: -1 }, { purchaseCostRate: 1.1 },
    { portfolioExpectedReturn: 1e100, targetYears: 50 },
  ]) assert.throws(() => calculateHomeGoal({ ...example, ...patch }));
});

test("빈 입력과 실제 0 구분, 만원·퍼센트 단위 변환", () => {
  assert.throws(() => readHomeGoalDraft(EMPTY_HOME_GOAL));
  assert.deepEqual(readHomeGoalDraft(EXAMPLE_HOME_GOAL), {
    currentAssets: 80e6, monthlySavings: 1.5e6, targetHousePrice: 600e6,
    targetYears: 3, expectedHousePriceGrowth: 0.02, expectedMortgageAmount: 400e6, purchaseCostRate: 0.03,
  });
  assert.equal(readHomeGoalDraft({ ...EXAMPLE_HOME_GOAL, monthlySavings: "0" }).monthlySavings, 0);
});

function portfolio(id: Portfolio["id"], returnPct: number): Portfolio {
  // 단위·연결 검증용 fixture. 실제 UI의 금융지표로 사용하지 않는다.
  return { id, name: id, metrics: { expectedReturnPct: returnPct } } as Portfolio;
}

test("장기계산은 기준 수익률, 스트레스는 별도 %p로 연결", () => {
  const rows = compareHomeGoalPortfolios(EXAMPLE_HOME_GOAL, [portfolio("a", 4.5)], [portfolio("a", -1)], "live", true);
  close(rows[0].result!.futureHomeFund, 148_992_422.881956);
  assert.equal(rows[0].input!.portfolioExpectedReturn, 0.045);
  assert.equal(rows[0].stressDeltaPct, -5.5);
  assert.match(describeHomeGoalComparison(rows), /적합성 판단은 보류/);
});

test("fallback·빈 결과·누락된 수익률로 실자금 추정하지 않는다", () => {
  for (const source of ["fallback", "empty"] as const) {
    const rows = compareHomeGoalPortfolios(EXAMPLE_HOME_GOAL, [portfolio("a", 4.5)], [], source, false);
    assert.equal(rows[0].result, null);
    assert.equal(rows[0].returnPct, null);
  }
  const unavailable = portfolio("a", 0);
  unavailable.metrics.expectedReturnAvailable = false;
  assert.equal(compareHomeGoalPortfolios(EXAMPLE_HOME_GOAL, [unavailable], [], "live", false)[0].result, null);
  assert.ok(compareHomeGoalPortfolios(EXAMPLE_HOME_GOAL, [portfolio("a", 0)], [], "live", false)[0].result);
});

test("금액 포맷은 억·만원·부호·비정상값을 처리", () => {
  assert.equal(formatWon(600_000_000), "6억원");
  assert.equal(formatWon(80_000_000), "8,000만원");
  assert.equal(formatWon(-1_000_000), "-100만원");
  assert.equal(formatWon(Infinity), "—");
});

test("전략 금액은 만원 단위까지 보존하여 구매 상한을 올려 표시하지 않는다", () => {
  assert.equal(formatWon(505_678_901, { rounding: "floor" }), "5억 567만원");
  assert.equal(formatWon(4_277_358, { rounding: "ceil" }), "428만원");
  assert.equal(formatWon(100_000_000, { rounding: "floor" }), "1억원");
});

test("시연 Stress는 실제 계산을 하지 않으므로 0%p로 오인시키지 않는다", () => {
  const portfolios = [portfolio("a", 4.5)];
  const rows = compareHomeGoalPortfolios(EXAMPLE_HOME_GOAL, portfolios, portfolios, "demo", true);
  assert.ok(rows[0].result);
  assert.equal(rows[0].stressDeltaPct, null);
});
