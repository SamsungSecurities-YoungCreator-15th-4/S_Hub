/**
 * VaR / CVaR · 손실 기여도 — 비중에서 직접 계산한다.
 *
 * 예전에는 `lib/mock/symphonyReport.ts` 에 숫자를 적어 두었다. 그 값들은 고객
 * 김성삼의 **상담 전 보유 비중** 하나에만 맞는 상수여서, 리포트가 제안안을
 * 가리키게 되면 같이 움직이지 못했다. 여기서 계산하면 어느 안을 보든 숫자가
 * 따라온다.
 *
 * ── 산식 ────────────────────────────────────────────────────────
 * 모수적(정규분포) VaR 이다. 기존 공표값을 역산하면 정확히 이 산식이 나온다
 * (일간 σ 0.950% → 1일 VaR 2.21% · CVaR 2.53% · 10일 VaR 6.99% · CVaR 8.00%).
 * 산식을 바꾸지 않고 입력 비중만 바꾸는 것이라 앞서 배포한 수치와 방법론이 같다.
 *
 *   σ_daily = σ_annual / √252            (연 250~252 영업일 관행 중 252)
 *   VaR_1d  = z_(99%) × σ_daily          z = 2.32635
 *   CVaR_1d = φ(z)/(1−0.99) × σ_daily    배수 = 2.66521
 *   10일    = 1일 × √10                  (바젤 square-root-of-time)
 *
 * φ 는 표준정규 확률밀도. CVaR 배수 φ(z)/(1−α) 는 정규분포 조건부기대손실의
 * 닫힌 해다 — 여기서 임의로 정한 상수가 아니다.
 *
 * ── σ_annual 을 어디서 읽는가 ───────────────────────────────────
 * 포트폴리오의 `metrics.volatilityPct` 를 그대로 쓴다. 화면·PDF 가 이미 같은
 * 값을 "변동성" 으로 보여주고 있어서, 여기서 따로 계산하면 한 문서 안에서
 * 변동성과 VaR 이 서로 다른 σ 를 말하게 된다.
 *
 * ── 손실 기여도 ─────────────────────────────────────────────────
 * 한계기여도(component VaR)를 쓴다. 자산 i 의 기여율은
 *
 *   contrib_i = w_i × (Σw)_i / σ_p²      (합계 100%)
 *
 * 로, 분산의 오일러 분해다. VaR·CVaR 이 σ 의 상수배라 비율은 셋이 같다.
 * Σ 는 아래 연 변동성 × 상관계수로 만든다.
 */

import {
  CALC_UNITS,
  type CalcUnitId,
  type CalcUnitWeights,
} from "./assetMapping";

/** 99% 신뢰수준. 리포트 헤더 표기와 같은 값이다. */
export const CONFIDENCE_LEVEL_PCT = 99;

/** z_(99%). 표준정규 상위 1% 분위수. */
const Z_99 = 2.3263478740408408;

/** CVaR 배수 φ(z)/(1−α). 정규분포 조건부기대손실의 닫힌 해. */
const CVAR_MULTIPLIER =
  Math.exp((-Z_99 * Z_99) / 2) / Math.sqrt(2 * Math.PI) / 0.01;

/** 연간 영업일. σ 연율 → 일간 환산에 쓴다. */
const TRADING_DAYS = 252;

/**
 * 계산단위별 연 변동성(%).
 *
 * 자산군 대표치이며 개별 종목값이 아니다. 국내주식은 KOSPI, 해외성장주는
 * 나스닥100, 해외배당주는 배당귀족형 지수, 채권은 듀레이션대별 국고채 수준의
 * 통상 범위를 따른다. 이 표와 아래 상관계수로 김성삼 상담 전 비중
 * (국내주식 42 · 해외성장주 26 · 금 12 · 국내채권 12 · 해외배당주 8)을 계산하면
 * 연 σ 15.6% · 1일 VaR 2.29% · 국내주식 기여도 56.2% 가 나와, 이전에 공표한
 * 15.1% · 2.21% · 55.4% 와 오차 1%p 안에서 맞는다.
 *
 * TODO(실데이터): 백엔드가 자산군 수익률 시계열을 내려주면 표본 공분산으로 교체한다.
 */
const ANNUAL_VOL_PCT: Record<CalcUnitId, number> = {
  domesticEquity: 22,
  overseasDividendEquity: 14,
  overseasGrowthEquity: 24,
  emergingEquity: 26,
  domesticBond: 4,
  overseasBond: 6,
  lowCouponBond: 3.5,
  separateTaxBond: 3.5,
  reits: 18,
  gold: 15,
  infraFund: 12,
};

/** 상관 블록. 계산단위를 성격이 같은 묶음으로 줄여 상관계수를 준다. */
type CorrBlock = "eq" | "bd" | "re" | "gd" | "in";

const CORR_BLOCK: Record<CalcUnitId, CorrBlock> = {
  domesticEquity: "eq",
  overseasDividendEquity: "eq",
  overseasGrowthEquity: "eq",
  emergingEquity: "eq",
  domesticBond: "bd",
  overseasBond: "bd",
  lowCouponBond: "bd",
  separateTaxBond: "bd",
  reits: "re",
  gold: "gd",
  infraFund: "in",
};

/**
 * 블록 간 상관계수. 대각은 1이고 표기는 한 방향만 둔다(대칭이라 조회 시 뒤집어 찾는다).
 * 금이 주식과 0.0 인 것은 위기 국면의 안전자산 성격을 반영한 것이고,
 * 스트레스 시나리오에서 금 충격을 작게 잡은 것과 같은 취급이다.
 */
const CORRELATION: Record<string, number> = {
  "eq|eq": 0.75,
  "eq|bd": 0.1,
  "eq|re": 0.6,
  "eq|gd": 0.0,
  "eq|in": 0.4,
  "bd|bd": 0.85,
  "bd|re": 0.25,
  "bd|gd": 0.15,
  "bd|in": 0.3,
  "re|gd": 0.2,
  "re|in": 0.45,
  "gd|in": 0.1,
};

function correlation(a: CalcUnitId, b: CalcUnitId): number {
  if (a === b) return 1;
  const x = CORR_BLOCK[a];
  const y = CORR_BLOCK[b];
  if (x === y) return CORRELATION[`${x}|${y}`] ?? 1;
  return CORRELATION[`${x}|${y}`] ?? CORRELATION[`${y}|${x}`] ?? 0;
}

/** (Σw)_i — 자산 i 와 포트폴리오의 공분산. 비중은 %, 결과는 %² 단위. */
function covarianceWithPortfolio(
  unit: CalcUnitId,
  weights: CalcUnitWeights,
): number {
  let acc = 0;
  for (const other of CALC_UNITS) {
    const w = (weights[other.id] ?? 0) / 100;
    acc += w * ANNUAL_VOL_PCT[unit] * ANNUAL_VOL_PCT[other.id] * correlation(unit, other.id);
  }
  return acc;
}

/**
 * σ 추정오차에서 오는 90% 신뢰구간 배수.
 *
 * VaR 은 σ 의 상수배라, 구간은 표본표준편차 σ̂ 의 구간을 그대로 물려받는다.
 * 정규 표본에서 (n−1)σ̂²/σ² 가 자유도 n−1 의 χ² 를 따르므로
 *
 *   [ σ̂·√((n−1)/χ²_{0.95}) ,  σ̂·√((n−1)/χ²_{0.05}) ]
 *
 * 이며, 위쪽이 더 넓은 비대칭 구간이 된다. χ² 분위수는 Wilson–Hilferty 근사
 * χ²_p(k) ≈ k(1 − 2/9k + z_p√(2/9k))³ 로 구한다. 관측기간은 1년(252영업일)이다.
 * 이 배수로 계산하면 이전에 공표한 구간(2.21% → 2.03~2.41%)이 2.06~2.39% 로
 * 재현된다.
 */
const CI_MULTIPLIER = (() => {
  const k = TRADING_DAYS - 1;
  const z = 1.6448536269514722;
  const chi2 = (zp: number) =>
    k * Math.pow(1 - 2 / (9 * k) + zp * Math.sqrt(2 / (9 * k)), 3);
  return [Math.sqrt(k / chi2(z)), Math.sqrt(k / chi2(-z))] as const;
})();

export interface RiskMetricRow {
  label: string;
  /** 손실률(%). 양수로 둔다 — 화면에서 부호를 붙인다. */
  ratioPct: number;
  /** 손실액(원). */
  amountKrw: number;
  /** 90% 신뢰구간(비율 하한·상한, %). */
  ciPct: [number, number];
}

/**
 * 1일·10일 VaR/CVaR 네 줄.
 *
 * `volatilityPct` 는 포트폴리오 지표의 연 변동성(%)이고, `totalKrw` 는 고객
 * 총 평가금액이다. 둘 다 호출부가 실제 값에서 읽어 넘긴다.
 */
export function riskMetricRows(
  volatilityPct: number,
  totalKrw: number,
): RiskMetricRow[] {
  const daily = volatilityPct / Math.sqrt(TRADING_DAYS);
  const rows: [string, number][] = [
    ["1일 VaR", daily * Z_99],
    ["1일 CVaR", daily * CVAR_MULTIPLIER],
    ["10일 VaR", daily * Z_99 * Math.sqrt(10)],
    ["10일 CVaR", daily * CVAR_MULTIPLIER * Math.sqrt(10)],
  ];
  return rows.map(([label, ratioPct]) => ({
    label,
    ratioPct,
    amountKrw: (ratioPct / 100) * totalKrw,
    ciPct: [ratioPct * CI_MULTIPLIER[0], ratioPct * CI_MULTIPLIER[1]] as [
      number,
      number,
    ],
  }));
}

export interface ContributionRow {
  label: string;
  weightPct: number;
}

/**
 * 손실 기여도(%). 합계 100. 큰 것부터 정렬하고, `limit` 을 넘는 꼬리는 "기타" 로 묶는다.
 *
 * 6분류(CALC_TO_DISPLAY)를 쓰지 않는다 — 그 묶음은 세제 기준이라 리츠·금·인프라펀드가
 * 전부 "분리과세" 한 줄이 되고, "분리과세가 손실의 6.9%" 같은 읽을 수 없는 문장이 된다
 * (같은 이유가 `lib/assetMapping.ts` 의 toCalcUnitAllocation 주석에도 적혀 있다).
 * 리스크를 말하는 자리에서는 계산단위 이름을 그대로 쓴다.
 */
export function cvarContributions(
  weights: CalcUnitWeights,
  limit = 6,
): ContributionRow[] {
  let variance = 0;
  for (const unit of CALC_UNITS) {
    variance +=
      ((weights[unit.id] ?? 0) / 100) * covarianceWithPortfolio(unit.id, weights);
  }
  if (variance <= 0) return [];

  const rows = CALC_UNITS.map((unit) => ({
    label: unit.label as string,
    weightPct:
      ((((weights[unit.id] ?? 0) / 100) *
        covarianceWithPortfolio(unit.id, weights)) /
        variance) *
      100,
  }))
    .filter((r) => r.weightPct > 0.05)
    .sort((a, b) => b.weightPct - a.weightPct);

  if (rows.length <= limit) return rows;
  const head = rows.slice(0, limit - 1);
  const tail = rows.slice(limit - 1);
  return [
    ...head,
    {
      label: "기타",
      weightPct: tail.reduce((acc, r) => acc + r.weightPct, 0),
    },
  ];
}

/** 연 변동성(%) — 비중만으로 구한다. 지표가 없는 조정안 등에서 쓴다. */
export function portfolioVolatilityPct(weights: CalcUnitWeights): number {
  let variance = 0;
  for (const unit of CALC_UNITS) {
    variance +=
      ((weights[unit.id] ?? 0) / 100) * covarianceWithPortfolio(unit.id, weights);
  }
  return Math.sqrt(Math.max(variance, 0));
}
