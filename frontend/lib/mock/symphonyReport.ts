/**
 * S.ymphony 리스크 리포트 — 화면 상수.
 *
 * 이 파일은 "자세히" 리포트 화면(components/dashboard/ReportDetailModal.tsx)이
 * 그대로 표시하는 값만 담는다. 계산은 하지 않는다 — 6지표 산출의 SSOT 는 엔진의
 * `calculate_metrics` 하나뿐이고, 화면에서 다시 계산하면 같은 숫자가 두 곳에서
 * 나오게 된다. 여기 있는 값은 엔진 산출물을 옮겨 적은 것이며, 화면은 표시만 한다.
 *
 * 백엔드 연동 시 교체 대상은 이 파일 하나다(화면 컴포넌트는 형태만 읽는다).
 */

/** 리포트 기준일. 확정 승인 표기도 같은 값을 쓴다. */
export const REPORT_AS_OF = "2026-09-10";

/** 리포트 산출 조건 — 헤더·재현성 블록이 함께 읽는다. */
export const REPORT_META = {
  totalValuationKrw: 100_000_000,
  seed: 20260910,
  engineVersion: "v0.9.3",
  confidenceLevelPct: 99,
} as const;

/** 라벨 + 비중(%) 한 줄. 배분 집계·기여도 표가 공유한다. */
interface AllocationRow {
  label: string;
  weightPct: number;
}

// ── ② IPS 충돌 검사 ──────────────────────────────────────────────

interface ConflictRow {
  rule: string;
  message: string;
  observed: string;
  threshold: string;
  severity: "review" | "block";
  basis: string;
}

export const IPS_CONFLICTS: ConflictRow[] = [
  {
    rule: "liquidity_cash_shortfall",
    message: "현금성 자산이 근시일 필요자금에 미달합니다",
    observed: "현금성 자산 0원",
    threshold: "필요자금 20,000,000원 (3년 내)",
    severity: "review",
    basis:
      "근거: IPS Liquidity(중간), IPS Unique(3년 내 전세 보증금 인상분 2,000만원)",
  },
  {
    rule: "single_risky_asset_concentration",
    message: "단일 위험자산 비중이 상한을 초과했습니다",
    observed: "국내주식 42.0%",
    threshold: "상한 40.0%",
    severity: "review",
    basis: "근거: ips_policy.yaml · single_risky_asset_max 0.40",
  },
];

export const IPS_CONFLICT_NOTE =
  "두 건 모두 review 등급입니다. 차단 대상이 아니며 PB 판단으로 예외 승인할 수 있습니다.";

// ── ③ VaR / CVaR ────────────────────────────────────────────────

interface RiskMetricRow {
  label: string;
  ratioPct: number;
  amountKrw: number;
  /** 90% 신뢰구간(비율 하한·상한). */
  ciPct: [number, number];
}

export const RISK_METRICS: RiskMetricRow[] = [
  { label: "1일 VaR", ratioPct: 2.21, amountKrw: 2_210_000, ciPct: [2.03, 2.41] },
  { label: "1일 CVaR", ratioPct: 2.53, amountKrw: 2_530_000, ciPct: [2.32, 2.76] },
  { label: "10일 VaR", ratioPct: 6.99, amountKrw: 6_990_000, ciPct: [6.42, 7.62] },
  { label: "10일 CVaR", ratioPct: 8.0, amountKrw: 8_000_000, ciPct: [7.34, 8.73] },
];

// ── ④ CVaR 자산군 기여도 (6자산군 · 합계 100.0%) ─────────────────

export const CVAR_CONTRIBUTIONS: AllocationRow[] = [
  { label: "국내주식", weightPct: 55.4 },
  { label: "해외성장주", weightPct: 26.3 },
  { label: "금", weightPct: 8.0 },
  { label: "해외배당주", weightPct: 6.5 },
  { label: "국내채권", weightPct: 3.8 },
  { label: "현금", weightPct: 0.0 },
];

export const CVAR_CONTRIBUTION_NOTE =
  "국내주식은 보유 비중 42.0%보다 손실 기여도가 높습니다.";

// ── ⑤ 스트레스 시나리오 ─────────────────────────────────────────

interface StressRow {
  key: string;
  label: string;
  lossPct: number;
  lossKrw: number;
}

/** 손실은 음수로 둔다 — 화면에서 부호를 붙이지 않고 값 그대로 읽게 한다. */
export const STRESS_SCENARIOS: StressRow[] = [
  { key: "gfc_2008", label: "2008 글로벌 금융위기", lossPct: -32.4, lossKrw: -32_400_000 },
  { key: "covid_2020", label: "2020 팬데믹 급락", lossPct: -21.7, lossKrw: -21_700_000 },
  { key: "rates_2022", label: "2022 금리 급등", lossPct: -16.8, lossKrw: -16_800_000 },
];

/** 최악 시나리오 키 — 화면이 강조할 행. */
export const WORST_STRESS_KEY = "gfc_2008";

export const STRESS_NOTE =
  "2020 시나리오 기준 손실액이 근시일 필요자금 2,000만원을 상회합니다.";

// ── ⑥ 인용·출처 ─────────────────────────────────────────────────

interface CitationRow {
  no: number;
  source: string;
  locator: string;
  usedIn: string;
}

export const CITATIONS: CitationRow[] = [
  {
    no: 1,
    source: "한국은행 통화정책방향 결정문 (2026-08)",
    locator: "기준금리 3.00%",
    usedIn: "VaR/CVaR · 스트레스",
  },
  {
    no: 2,
    source: "사내 House View 2026 3Q",
    locator: "자산배분 가이드 · 위험자산 상한",
    usedIn: "IPS 충돌 · 손실 기여도",
  },
  {
    no: 3,
    source: "국세청 2026년 세금가이드 1권",
    locator: "ISA 과세특례",
    usedIn: "절세",
  },
  {
    no: 4,
    source: "국세청 2026년 세금가이드 2권",
    locator: "연금계좌 세액공제",
    usedIn: "절세",
  },
];

// ── ⑦ 검증 항목 ─────────────────────────────────────────────────

interface VerificationRow {
  label: string;
  /** 분수 표기가 필요한 항목만 채운다(퍼센트로 바꾸지 않는다). */
  ratio?: string;
  passed: boolean;
}

export const VERIFICATIONS: VerificationRow[] = [
  { label: "입력 스키마 검증", passed: true },
  { label: "자산 비중 합계 100.0%", passed: true },
  { label: "인용 근거 존재", ratio: "4/4", passed: true },
  { label: "본문·표 수치 일관성", passed: true },
  { label: "금지 표현 검사", passed: true },
  { label: "개별 종목 권유 문구 부재", passed: true },
  { label: "난수 시드 고정", passed: true },
];

export const VERIFICATION_NOTE =
  "검증 항목 중 하나라도 실패하면 이 지점에서 산출이 중단되며 승인 단계로 넘어가지 않습니다.";

// ── ⑧ 재현성 해시 ───────────────────────────────────────────────

interface HashRow {
  label: string;
  value: string;
}

export const REPRODUCIBILITY_HASHES: HashRow[] = [
  { label: "입력 스냅샷", value: "sha256:4f2a9c1d7b03" },
  { label: "정책 파일 (ips_policy.yaml)", value: "sha256:8e11b4a6d59f" },
  { label: "엔진 상수", value: "sha256:c07d3f82ae61" },
  { label: "리포트 페이로드", value: "sha256:a95c60e4128b" },
];

export const REPRODUCIBILITY_NOTE = `동일한 입력·정책·시드에서 동일한 해시가 재생성됩니다. 시드 ${REPORT_META.seed} 고정.`;

// ── ⑨ 면책 ──────────────────────────────────────────────────────

export const DISCLAIMERS: { code: string; text: string }[] = [
  {
    code: "E1",
    text: "본 리포트는 정보 제공을 목적으로 하며 특정 상품의 매매를 권유하지 않습니다.",
  },
  {
    code: "E3",
    text: "과거 데이터에 기반한 추정치이며 미래 성과를 보장하지 않습니다.",
  },
];

/** 원 단위 금액 표기. 부호를 그대로 살린다(손실은 음수로 들어온다). */
export function formatWon(krw: number): string {
  return `${krw.toLocaleString("ko-KR")}원`;
}
