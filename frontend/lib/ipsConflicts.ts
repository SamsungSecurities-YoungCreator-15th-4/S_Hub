/**
 * IPS 충돌 검사 — 비중에서 직접 판정한다.
 *
 * 예전에는 `lib/mock/symphonyReport.ts` 에 두 줄을 상수로 적어 두었다. 그 두 줄은
 * 김성삼의 상담 전 비중("국내주식 42.0%")에만 맞는 문장이라, 리포트가 제안안을
 * 가리키게 되면 본문과 어긋났다. 여기서 판정하면 어느 안을 보든 문장이 따라온다.
 *
 * 기준의 SSOT 는 `config/ips_policy.yaml` 이다. 아래 임계값은 그 파일의 값을 옮겨
 * 적은 사본이며, 프론트엔드에서 YAML 을 읽을 수 없어 불가피하게 중복된다.
 * 정책 파일이 바뀌면 여기도 함께 고친다.
 *
 * 판정 등급은 전부 `review` 다 — 정책 파일 주석이 규정하듯 이 숫자들은 법정 한도가
 * 아니라 공식 적합성·분산 원칙을 사전 red flag 로 바꾼 내부 기준이고, 상품 위험등급
 * 확정 전에는 PB 의 근거 있는 예외 승인을 허용한다.
 */

import { CALC_UNITS, type CalcUnitId, type CalcUnitWeights } from "./assetMapping";

/** config/ips_policy.yaml · thresholds.max_single_risky_asset_ratio */
const MAX_SINGLE_RISKY_ASSET_RATIO = 0.4;

/** 정책 파일 버전. 근거 문구에 그대로 적는다. */
export const IPS_POLICY_VERSION = "2026-07-13.v1";

/**
 * 위험자산으로 보는 계산단위.
 *
 * 채권 3종과 분리과세채권은 제외한다 — 분리과세채권은 CALC_UNITS 의 group 표기가
 * "대체" 지만 그건 세제 분류이고 실질은 채권이다(lib/stressScenarios.ts 의
 * 엔진 자산군 매핑과 같은 취급).
 */
const RISKY_UNITS: CalcUnitId[] = [
  "domesticEquity",
  "overseasDividendEquity",
  "overseasGrowthEquity",
  "emergingEquity",
  "reits",
  "gold",
  "infraFund",
];

export interface ConflictRow {
  rule: string;
  message: string;
  observed: string;
  threshold: string;
  severity: "review" | "block";
  basis: string;
  /** 판정 결과. resolved 는 상담 전 비중에서는 걸렸으나 이 안에서는 풀린 항목이다. */
  status: "violation" | "resolved";
  /** 상담 전 비중에서의 관측값. 해소된 항목에만 채운다. */
  previousObserved?: string;
}

export interface ConflictInput {
  /** 판정 대상 비중 — 리포트가 보고 있는 안. */
  weights: CalcUnitWeights;
  /** 상담 전 보유 비중. 해소 여부 비교용이며, 없으면 비교를 만들지 않는다. */
  baselineWeights?: CalcUnitWeights;
  /** 근시일 필요자금(만원)과 시점(년). IPS Unique 에서 온다. */
  nearTermNeedManwon: number;
  nearTermNeedYears: number | null;
  /** 근시일 필요자금의 목적 표기. 없으면 목적 없이 금액만 적는다. */
  nearTermNeedLabel?: string;
  /** 총 평가금액(원). 필요자금을 비중으로 환산할 때 쓴다. */
  totalKrw: number;
  /**
   * 현금성 자산 비중(%). 포트폴리오 비중 11종에는 현금 항목이 없어 호출부가 넘긴다.
   * 미지정이면 0으로 본다 — 제안안들은 현금을 두지 않는다.
   */
  cashPct?: number;
}

/** 위험자산 중 비중이 가장 큰 하나. */
function largestRiskyUnit(weights: CalcUnitWeights) {
  let top: { label: string; pct: number } | null = null;
  for (const id of RISKY_UNITS) {
    const pct = weights[id] ?? 0;
    if (top === null || pct > top.pct) {
      top = { label: CALC_UNITS.find((u) => u.id === id)?.label ?? id, pct };
    }
  }
  return top;
}

const fmtPct = (v: number) => `${v.toFixed(1)}%`;
const fmtManwon = (v: number) => `${v.toLocaleString("ko-KR")}만원`;

export function evaluateIpsConflicts(input: ConflictInput): ConflictRow[] {
  const rows: ConflictRow[] = [];

  // ── 단일 위험자산 집중도 ────────────────────────────────────
  const top = largestRiskyUnit(input.weights);
  const limitPct = MAX_SINGLE_RISKY_ASSET_RATIO * 100;
  if (top) {
    const over = top.pct > limitPct;
    const prev = input.baselineWeights
      ? largestRiskyUnit(input.baselineWeights)
      : null;
    const wasOver = prev !== null && prev.pct > limitPct;
    if (over || wasOver) {
      rows.push({
        rule: "single_risky_asset_concentration",
        message: over
          ? "단일 위험자산 비중이 상한을 초과했습니다"
          : "단일 위험자산 집중도가 상한 아래로 내려왔습니다",
        observed: `${top.label} ${fmtPct(top.pct)}`,
        threshold: `상한 ${fmtPct(limitPct)}`,
        severity: "review",
        basis: `근거: ips_policy.yaml(${IPS_POLICY_VERSION}) · max_single_risky_asset_ratio ${MAX_SINGLE_RISKY_ASSET_RATIO.toFixed(2)}`,
        status: over ? "violation" : "resolved",
        previousObserved:
          !over && prev ? `${prev.label} ${fmtPct(prev.pct)}` : undefined,
      });
    }
  }

  // ── 유동성: 현금성 자산이 근시일 필요자금에 미달 ────────────
  const needManwon = input.nearTermNeedManwon;
  if (needManwon > 0 && input.nearTermNeedYears !== null) {
    const cashPct = input.cashPct ?? 0;
    const cashManwon = (cashPct / 100) * (input.totalKrw / 10_000);
    const short = cashManwon < needManwon;
    const purpose = input.nearTermNeedLabel
      ? `${input.nearTermNeedYears}년 내 ${input.nearTermNeedLabel} ${fmtManwon(needManwon)}`
      : `${input.nearTermNeedYears}년 내 ${fmtManwon(needManwon)}`;
    rows.push({
      rule: "liquidity_cash_shortfall",
      message: short
        ? "현금성 자산이 근시일 필요자금에 미달합니다"
        : "현금성 자산이 근시일 필요자금을 덮습니다",
      observed: `현금성 자산 ${fmtManwon(Math.round(cashManwon))}`,
      threshold: `필요자금 ${fmtManwon(needManwon)} (${input.nearTermNeedYears}년 내)`,
      severity: "review",
      basis: `근거: IPS Liquidity · IPS Unique(${purpose})`,
      status: short ? "violation" : "resolved",
    });
  }

  return rows;
}

/** 블록 부제·요약 문장. 위반 건수와 해소 건수를 함께 말한다. */
export function conflictSummary(rows: ConflictRow[]): {
  sub: string;
  note: string;
} {
  const violations = rows.filter((r) => r.status === "violation");
  const resolved = rows.filter((r) => r.status === "resolved");
  const sub =
    resolved.length > 0
      ? `${violations.length}건 · 해소 ${resolved.length}건`
      : `${violations.length}건`;

  if (violations.length === 0) {
    return {
      sub,
      note: "이 구성에서는 사전 검토 기준을 넘는 항목이 없습니다.",
    };
  }
  return {
    sub,
    note: `${violations.length}건 모두 review 등급입니다. 차단 대상이 아니며 PB 판단으로 예외 승인할 수 있습니다.`,
  };
}
