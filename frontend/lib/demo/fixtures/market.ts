/**
 * 시연 고정 데이터 — lib/api.ts 의 market 계열 5개 함수용.
 *
 * ⚠️ 값의 출처: 새로 만든 숫자가 아니라 `lib/mockData.ts` 의 MACRO_INDICATORS 를
 * 그대로 옮긴 것이다. 화면(MacroTicker)이 백엔드 실패 시 이미 쓰던 값과 같다.
 * 시연 시나리오 수치가 확정되면 mockData.ts 를 고치면 여기도 따라간다.
 *
 * fetchPortfolios · fetchStressScenarios · fetchHistoricalCrises ·
 * fetchStressedPortfolios 는 현재 호출부가 없다(미사용 API). 빈 배열을 돌려
 * "데모 모드에서 네트워크를 타지 않는다"만 보장한다. 쓰이기 시작하면 값을 채운다.
 */
import type {
  HistoricalCrisis,
  MacroIndicators,
  PortfolioProposal,
  StressScenario,
  StressedPortfolio,
} from "../../types";

/** mockData 의 MACRO_INDICATORS 문자열 값을 백엔드 응답 형태로 옮긴 것. */
export const DEMO_MACRO_INDICATORS: MacroIndicators = {
  baseRate: { price: 3.5, change: -0.25, changePct: -6.67, isStatic: true },
  treasuryYield: { price: 4.38, change: -0.05, changePct: -1.13 },
  krwUsd: { price: 1220, change: -20, changePct: -1.61 },
  cpi: { price: 3.2, change: -0.25, changePct: -7.25, isStatic: true },
  kospi: { price: 2790, change: 31, changePct: 1.12 },
  sp500: { price: 5640, change: 18, changePct: 0.32 },
  fetchedAt: "2026-07-03T17:20:00+09:00",
};

export const DEMO_PORTFOLIO_PROPOSALS: PortfolioProposal[] = [];
export const DEMO_STRESS_SCENARIOS: StressScenario[] = [];
export const DEMO_HISTORICAL_CRISES: HistoricalCrisis[] = [];
export const DEMO_STRESSED_PORTFOLIOS: StressedPortfolio[] = [];
