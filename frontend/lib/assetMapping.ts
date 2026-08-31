/**
 * 자산 분류 매핑 단일 소스 (Single Source of Truth)
 *
 * - 백엔드/데이터 구조: 11종 계산 단위 (주식 4 · 채권 3 · 대체 4)
 * - 화면 표시: 6분류로 묶어서 노출 (정본 디자인 기준)
 *
 * 6↔11 매핑을 바꿀 일이 생기면 이 파일만 수정하면 된다.
 *
 * TODO(팀 확정 필요): 11종 계산 단위의 정확한 명칭·구성은 백엔드 팀과
 * 아직 확정 전. 아래는 "주식4·채권3·대체4" 합의만 반영한 가안이다.
 */

// ── 11종 계산 단위 ──────────────────────────────────────────────
export const CALC_UNITS = [
  // 주식 4
  { id: "domesticEquity", label: "국내주식", group: "주식" },
  { id: "overseasDividendEquity", label: "해외배당주", group: "주식" },
  { id: "overseasGrowthEquity", label: "해외성장주", group: "주식" },
  { id: "emergingEquity", label: "신흥국주식", group: "주식" },
  // 채권 3
  { id: "domesticBond", label: "국내일반채권", group: "채권" },
  { id: "overseasBond", label: "해외채권", group: "채권" },
  { id: "lowCouponBond", label: "저쿠폰·장기채", group: "채권" },
  // 대체 4
  { id: "separateTaxBond", label: "분리과세채권", group: "대체" },
  { id: "reits", label: "리츠", group: "대체" },
  { id: "gold", label: "금", group: "대체" },
  { id: "infraFund", label: "인프라펀드", group: "대체" },
] as const;

export type CalcUnitId = (typeof CALC_UNITS)[number]["id"];

/** 11종 비중(%) 묶음. 합계 100을 가정한다. */
export type CalcUnitWeights = Record<CalcUnitId, number>;

/** 고객 현재 보유 자산 비중 입력값(%) — 11종 계산단위 + 현금. 미입력 항목은 키 자체가 없다. */
export type CurrentWeightsInput = Partial<Record<CalcUnitId | "cash", number>>;

/** 입력된 비중 합계(%). 미입력 항목은 0으로 취급. */
export function sumCurrentWeightsInput(input: CurrentWeightsInput): number {
  return Object.values(input).reduce(
    (acc, v) => acc + (typeof v === "number" && Number.isFinite(v) ? v : 0),
    0,
  );
}

/**
 * 입력값이 계산에 써도 되는 상태인지 검증한다.
 *
 * 백엔드는 합계가 100이 아니어도 normalize_weights로 조용히 100%로 재조정해버려서,
 * "화면에 보이는 합계 ≠ 실제 계산에 쓰인 비중"이 될 수 있다(추적성 위반). 아무것도
 * 입력하지 않은 상태(합계 0)는 유효로 본다 — 그건 "아직 입력 안 함"이라 백엔드
 * 기본값(현금 100%)으로 정직하게 폴백하는 정상 경로이기 때문이다. 값을 하나라도
 * 입력했다면 합계가 100(오차 0.5%p 이내)이어야 유효하다.
 */
export function isCurrentWeightsInputValid(input: CurrentWeightsInput): boolean {
  const total = sumCurrentWeightsInput(input);
  if (total === 0) return true;
  return Math.abs(total - 100) < 0.5;
}

// ── 6분류 화면 표시 그룹 (정본 디자인의 범례 순서) ─────────────
export const DISPLAY_GROUPS = [
  "국내주식",
  "해외배당주",
  "해외성장주",
  "일반채권",
  "저쿠폰채",
  "분리과세",
] as const;

export type DisplayGroup = (typeof DISPLAY_GROUPS)[number];

/** 도넛·히트맵에서 쓰는 6분류 색상 램프 (메인컬러 #0064FF 계열) */
export const DISPLAY_GROUP_COLORS: Record<DisplayGroup, string> = {
  국내주식: "#0064FF",
  해외배당주: "#2C7BFF",
  해외성장주: "#5C9CFF",
  일반채권: "#8FBCFF",
  저쿠폰채: "#B8D4FF",
  분리과세: "#DCE9FF",
};

/** 백엔드 8개 자산군 색상 맵 (PR #162 이후 allocation에서 직접 사용) */
export const BACKEND_ASSET_COLORS: Record<string, string> = {
  domestic_equity: "#0064FF",
  overseas_equity: "#2C7BFF",
  reit:            "#5C9CFF",
  gold:            "#74A9FF",
  bond:            "#8FBCFF",
  commodity:       "#B8D4FF",
  dollar:          "#DCE9FF",
  cash:            "#E2E8F0",
};

// ── 11종 → 6분류 매핑 ──────────────────────────────────────────
// TODO(팀 확정 필요): 특히 대체자산 4종을 "분리과세"로 묶는 부분은 가안.
export const CALC_TO_DISPLAY: Record<CalcUnitId, DisplayGroup> = {
  domesticEquity: "국내주식",
  overseasDividendEquity: "해외배당주",
  overseasGrowthEquity: "해외성장주",
  emergingEquity: "해외성장주",
  domesticBond: "일반채권",
  overseasBond: "일반채권",
  lowCouponBond: "저쿠폰채",
  separateTaxBond: "분리과세",
  reits: "분리과세",
  gold: "분리과세",
  infraFund: "분리과세",
};

/** 11종 비중을 화면 표시용 6분류 비중으로 합산한다. */
export function toDisplayAllocation(
  weights: CalcUnitWeights,
): { group: DisplayGroup; weight: number }[] {
  const acc = Object.fromEntries(DISPLAY_GROUPS.map((g) => [g, 0])) as Record<
    DisplayGroup,
    number
  >;
  for (const unit of CALC_UNITS) {
    // 백엔드 응답에 일부 자산군이 빠져도 NaN이 되지 않도록 0 처리
    acc[CALC_TO_DISPLAY[unit.id]] += weights[unit.id] ?? 0;
  }
  return DISPLAY_GROUPS.map((group) => ({ group, weight: acc[group] }));
}
