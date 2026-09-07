/**
 * 스트레스 시나리오 — 엔진(S.ymphony) 정의를 화면에서 재현한다.
 *
 * SSOT는 `engine/engine/stress.py`다. 이 파일은 그 상수를 옮겨 적은 사본이며,
 * 프론트엔드에서 파이썬을 import할 수 없어 불가피하게 중복된다.
 * 엔진 쪽 값이 바뀌면 여기도 함께 고쳐야 한다.
 *
 * 엔진 주석(stress.py:6)이 규정하는 성격을 그대로 따른다.
 *   - 시나리오는 사전 정의·문서화되며 실행 시점에 임의로 생성되지 않는다.
 *   - 충격 크기는 역사적 국면으로 방향·크기를 검증한 정형화된 대표 낙폭이며,
 *     특정 사건의 정밀 재현이 아니다(그래서 화면 문구도 "참조"라고 적는다).
 *
 * 계산식도 engine/engine/stress.py 의 run_stress 와 동일하다.
 *   loss      = Σ -(value × shock)
 *   loss_low  = Σ min(-(value × shock × (1-band)), -(value × shock × (1+band)))
 *   loss_high = Σ max(...)
 * 부호 규약도 같다 — 양수 = 손실.
 */

import { CALC_UNITS, type CalcUnitId, type CalcUnitWeights } from "./assetMapping";

/** 엔진 자산군(6종). engine/engine/stress.py 의 shocks 키와 동일. */
type EngineAssetClass =
  | "domestic_equity"
  | "global_equity"
  | "domestic_bond"
  | "global_bond"
  | "alternatives"
  | "cash";

/**
 * 11종 계산단위 → 엔진 6종 자산군.
 *
 * 분리과세채권은 실질이 채권이라 domestic_bond 로 보낸다. CALC_UNITS 의
 * group 표기가 "대체"인 것은 DISPLAY_GROUPS 와 같은 세제 분류 기준이고
 * 리스크 분류가 아니다(2026-09-07 팀 확인).
 */
export const CALC_UNIT_TO_ENGINE_CLASS: Record<CalcUnitId, EngineAssetClass> = {
  domesticEquity: "domestic_equity",
  overseasDividendEquity: "global_equity",
  overseasGrowthEquity: "global_equity",
  emergingEquity: "global_equity",
  domesticBond: "domestic_bond",
  overseasBond: "global_bond",
  lowCouponBond: "domestic_bond",
  separateTaxBond: "domestic_bond",
  reits: "alternatives",
  gold: "alternatives",
  infraFund: "alternatives",
};

/** 카드 시나리오 키. STRESS_SCENARIOS 의 key 와 1:1 대응한다. */
export type StressScenarioKey = "covid" | "high_rate" | "strong_usd";

export interface StressScenario {
  key: StressScenarioKey;
  /** 카드 제목 — 사람이 기억하는 사건 이름. */
  label: string;
  /** 국면을 한마디로. */
  blurb: string;
  /**
   * 카드에 표기할 자산군별 충격 요약.
   * 아래 shocks 값을 그대로 옮긴 것이라 화면 문구와 계산 근거가 같다.
   */
  shockSummary: string;
  /** 엔진 reference 원문 — 근거 표기용. */
  reference: string;
  shocks: Record<EngineAssetClass, number>;
}

/**
 * 기본 시나리오 3종. 발생 시점 순(2020 → 2022)으로 나열한다.
 * shocks 값은 engine/engine/stress.py 의 SCENARIO_C_COVID ·
 * SCENARIO_A_HIGH_RATE · SCENARIO_B_STRONG_USD 를 그대로 옮긴 것이다.
 */
export const STRESS_SCENARIOS: StressScenario[] = [
  {
    key: "covid",
    label: "2020 코로나",
    blurb: "위험자산 투매",
    shockSummary: "국내주식 −30% · 해외주식 −25% · 채권 −1~3%",
    reference: "2020-02~03 코로나 급락 국면 참조 — 핵심 특징을 반영한 가상 시나리오(방향·크기 정합)",
    shocks: {
      domestic_equity: -0.3,
      global_equity: -0.25,
      domestic_bond: -0.03,
      global_bond: -0.01,
      alternatives: -0.02,
      cash: 0.0,
    },
  },
  {
    key: "high_rate",
    label: "2022 고금리",
    blurb: "금리 급등",
    shockSummary: "주식 −25% · 국내채권 −15% · 해외채권 −12%",
    reference: "2022 고금리 국면(한·미 정책금리 급등) 참조 — 핵심 특징을 반영한 가상 시나리오(방향·크기 정합)",
    shocks: {
      domestic_equity: -0.25,
      global_equity: -0.25,
      domestic_bond: -0.15,
      global_bond: -0.12,
      alternatives: -0.1,
      cash: 0.0,
    },
  },
  {
    key: "strong_usd",
    label: "2022 강달러",
    blurb: "원화 약세",
    shockSummary: "국내주식 −12% · 국내채권 −5% · 해외주식 −3%",
    reference: "2022 강달러 국면(원/달러 1,440원대) 참조 — 핵심 특징을 반영한 가상 시나리오(방향·크기 정합)",
    shocks: {
      domestic_equity: -0.12,
      global_equity: -0.03,
      domestic_bond: -0.05,
      global_bond: -0.01,
      alternatives: -0.02,
      cash: 0.0,
    },
  },
];

/** 자산군별 상대 충격 밴드 — 표시용. engine/engine/stress.py 의 SHOCK_BAND 와 동일. */
const SHOCK_BAND: Record<EngineAssetClass, number> = {
  domestic_equity: 0.25,
  global_equity: 0.25,
  domestic_bond: 0.15,
  global_bond: 0.15,
  alternatives: 0.2,
  cash: 0.0,
};

export interface StressLoss {
  /** 손실액(원). 양수 = 손실 — 엔진 부호 규약과 동일. */
  lossKrw: number;
  lossKrwLow: number;
  lossKrwHigh: number;
  /** 총자산 대비 손실률(0~1). */
  lossPct: number;
}

/**
 * 비중(%)과 총자산으로 시나리오 손실을 계산한다.
 * weights 합계가 100이 아니면 그 합계를 분모로 쓴다(엔진의 total_value 와 같은 취급).
 */
export function runStress(
  weights: CalcUnitWeights,
  totalKrw: number,
  scenario: StressScenario,
): StressLoss {
  let loss = 0;
  let lossLow = 0;
  let lossHigh = 0;
  let totalWeight = 0;

  for (const unit of CALC_UNITS) {
    const weightPct = weights[unit.id] ?? 0;
    if (!Number.isFinite(weightPct) || weightPct === 0) continue;
    totalWeight += weightPct;

    const assetClass = CALC_UNIT_TO_ENGINE_CLASS[unit.id];
    const shock = scenario.shocks[assetClass];
    const band = SHOCK_BAND[assetClass];
    const valueKrw = (weightPct / 100) * totalKrw;

    loss += -(valueKrw * shock);
    const bound1 = -(valueKrw * shock * (1 - band));
    const bound2 = -(valueKrw * shock * (1 + band));
    lossLow += Math.min(bound1, bound2);
    lossHigh += Math.max(bound1, bound2);
  }

  const denominator = (totalWeight / 100) * totalKrw;
  return {
    lossKrw: loss,
    lossKrwLow: lossLow,
    lossKrwHigh: lossHigh,
    lossPct: denominator > 0 ? loss / denominator : 0,
  };
}

/** 손실액 표기. 표기 규칙은 lib/formatKrw.ts 하나로 모은다. */
export { formatKrwCompact as formatKrwLoss } from "./formatKrw";
