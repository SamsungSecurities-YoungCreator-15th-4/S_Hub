/**
 * 대시보드 전역 상태 (Zustand).
 * 선택 고객 · IPS 조율기 값 · 시나리오 슬라이더만 담는 최소 골격.
 */

import { create } from "zustand";
import {
  type ConsultMessage,
  type Customer,
  type MacroIndicator,
  type Portfolio,
  CUSTOMERS,
  IPS_DEFAULT,
  MACRO_INDICATORS,
  PORTFOLIOS,
  SCENARIO_BASE,
  withCurrentWeights,
} from "./mockData";
import type {
  ApiResult,
  DataSource,
  InsightData,
  CorrelationHeatmapResponse,
  PortfolioTaxResponse,
  StressTaxData,
} from "./api";
import { CALC_UNITS, type CurrentWeightsInput } from "./assetMapping";
import {
  INITIAL_RUN_STATUS,
  RUN_STATUS,
  RUN_STATUS_EXPORT_ALLOWED,
  canTransition,
  type RunStatus,
} from "./runStatus";

export type { CurrentWeightsInput };

/**
 * 확정 스냅샷 — PB가 확정 승인한 시점에 화면이 보여 주던 안을 한 줄로 적은 것.
 *
 * 승인은 "그 안, 그 비중으로 계산한 리포트"에 대한 것이라, 확정 이후 보는 안이
 * 바뀌면 확정본과 다른 내용이 PDF로 나간다. 그래서 지금 보는 안을 이 스냅샷과
 * 대조해 다르면 추출을 잠근다(runStatus 는 locked 그대로 둔다 — 확정한 사실
 * 자체는 남아 있고, 확정한 안으로 돌아오면 재승인 없이 다시 열린다).
 *
 * 안의 키 · 그 안의 비중 · 확정 당시의 현재 보유 비중을 이어 붙인다. 세 조각을
 * 따로 들고 필드마다 비교하는 대신 문자열 하나로 두면 대조가 === 하나로 끝난다.
 */
type LockedSnapshot = string;

/** 비중 비교의 축. 순서를 고정해야 문자열 비교가 성립한다. */
const SNAPSHOT_KEYS: string[] = [...CALC_UNITS.map((u) => u.id), "cash"];

/** 미입력을 0으로 채워 고정 길이로 적는다. 소수 2자리에서 끊어 부동소수 오차를 없앤다. */
function normalizeWeights(w: Record<string, number | undefined>): string {
  return SNAPSHOT_KEYS.map((k) => Math.round((w[k] ?? 0) * 100) / 100).join(",");
}

export interface IpsState {
  returnPct: number;
  risk: "안정형" | "균형형" | "공격형";
  timeYears: number;
  liquidity: "낮음" | "중간" | "높음";
  goal: string;
  tax: string;
  legal: string;
  unique: string;
}

/**
 * 신규 고객(상담 전) 전용 빈 IPS — 더미 값을 쓰지 않고 조율기를 비운 채로 시작한다.
 * Segment(risk/liquidity)는 "" 일 때 아무 항목도 선택되지 않은 상태로 렌더된다.
 */
export const EMPTY_IPS: IpsState = {
  returnPct: 0,
  risk: "" as IpsState["risk"],
  timeYears: 0,
  liquidity: "" as IpsState["liquidity"],
  goal: "",
  tax: "",
  legal: "",
  unique: "",
};

/** STT 상담 연동 상태(비동기 흐름·출처 표시용). */
export type SttStatus = "idle" | "uploading" | "done" | "error";

export interface DashboardState {
  customers: Customer[];
  selectedCustomerId: string;
  selectedPortfolioId: string;
  ips: IpsState;
  scenario: { ratePct: number; fxKrw: number };
  /** 실시간 현재값 (금리·환율) — 슬라이더 기준점·델타 계산의 기준.
   *  백엔드 /api/macro-indicators 로드 전엔 목 기준값으로 시작한다. */
  liveBase: { ratePct: number; fxKrw: number };
  liveBaseLoaded: boolean;
  /** 고객이 지금 실제로 들고 있는 자산 비중(%) — calculate·stress-metrics의 "현재 포트폴리오"
   *  기준선으로 그대로 전송된다. 미입력 시 백엔드가 현금 100%로 폴백한다. */
  currentWeightsInput: CurrentWeightsInput;
  setCurrentWeightsInput: (patch: CurrentWeightsInput) => void;
  /** 제안 포트폴리오를 PB가 손본 비중(%) — 분석 결과가 있을 때만 입력할 수 있다.
   *  현재 보유 비중과 달리 계산 요청에 실리지 않는다(표시·검토용). */
  proposedWeightsInput: CurrentWeightsInput;
  setProposedWeightsInput: (patch: CurrentWeightsInput) => void;
  /** 제안 조정 입력을 지금 선택된 제안의 비중으로 되돌린다. */
  resetProposedToSelected: () => void;
  /**
   * 비중 입력 폼이 지금 어느 쪽을 편집하는가.
   * 중앙 제안 카드의 세그먼트가 같은 값을 보므로 좌·우가 함께 움직인다 —
   * 왼쪽에서 조정하는데 가운데가 다른 안을 보여주면 무엇을 만지는지 알 수 없다.
   */
  weightsTab: "current" | "proposed";
  setWeightsTab: (tab: "current" | "proposed") => void;
  /**
   * 직전 분석 게이트에서 거절했는가.
   *
   * runStatusReason 으로 대신할 수 없다 — 거절 시점이 draft 면 draft → blocked
   * 전이가 전이표에 없어(lib/runStatus.ts) setRunStatus 가 조용히 무시되고
   * 사유도 남지 않는다. 그래서 표시용 플래그를 따로 둔다.
   */
  analyzeRejected: boolean;
  setAnalyzeRejected: (v: boolean) => void;
  /**
   * 제안 조정 비중을 손댔는가 — 화면 안내 전용 플래그.
   *
   * 현재 보유 비중에는 두지 않는다. 그쪽은 분석 전에 처음 채워 넣는 입력이라
   * 0에서 값이 들어가는 것이 정상 경로인데, 거기에 "재분석 필요"를 띄우면
   * 아직 한 번도 분석하지 않은 화면에서 재분석을 요구하게 된다.
   * 제안 조정은 분석 결과가 나온 뒤에만 만질 수 있어(isTrusted 게이트) 다르다.
   */
  proposedWeightsDirty: boolean;

  // ── STT/상담 연동 상태 ──
  /** 화면에 표시하는 상담 전사. 녹음·업로드 전에는 빈 배열이다. */
  transcript: ConsultMessage[];
  /** 전사 데이터 출처(상담 입력 전 = empty, 시연 전사 = fallback). */
  transcriptSource: DataSource;
  /** STT 로 확보한 실 consultation_id(RAG·tax 재사용). 없으면 빈 문자열. */
  consultationId: string;
  sttStatus: SttStatus;
  sttNote?: string;

  // ── 포트폴리오 계산 결과 ──
  /** 항상 화면에 표시되는 단일 포트폴리오 배열 (base·stress 모드 모두 여기서 읽는다) */
  portfolios: Portfolio[];
  /** 마지막 /portfolio/calculate 결과 — stress PnL 델타 계산의 기준선 */
  basePortfolios: Portfolio[];
  portfolioSource: DataSource;
  portfolioNote?: string;
  /** calculate 결과로 portfolios·basePortfolios 동시 갱신, isStressMode: false */
  setPortfolios: (
    portfolios: Portfolio[],
    source: DataSource,
    note?: string,
  ) => void;
  /** stress-metrics 결과를 portfolios에 반영 (basePortfolios는 유지), isStressMode: true */
  setStressPortfolios: (portfolios: Portfolio[]) => void;

  // ── 스트레스 모드 상태 ──
  isStressMode: boolean;
  stressPreset: "current" | "crisis" | "war" | null;
  setStressPreset: (preset: "current" | "crisis" | "war" | null) => void;
  /** portfolios를 basePortfolios로 복원, isStressMode: false */
  clearStressMode: () => void;

  // ── 히트맵·절세 데이터 ──
  correlationHeatmap: CorrelationHeatmapResponse | null;
  setCorrelationHeatmap: (h: CorrelationHeatmapResponse | null) => void;
  /** 포트폴리오 kind("current" | "A" | "B") 별 절세 데이터 */
  portfolioTax: Record<string, PortfolioTaxResponse> | null;
  setPortfolioTax: (tax: Record<string, PortfolioTaxResponse>) => void;
  /** stress-metrics 응답의 base_tax/stressed_tax 쌍 — TaxSection 연동용 */
  stressTax: { base: StressTaxData; stressed: StressTaxData } | null;
  setStressTax: (
    tax: { base: StressTaxData; stressed: StressTaxData } | null,
  ) => void;
  /** calculate 응답의 tax_optimizer — 스트레스 미진입 시 절세 제안·종합과세 게이지 소스 */
  taxOptimizer: Record<string, StressTaxData> | null;
  setTaxOptimizer: (tax: Record<string, StressTaxData> | null) => void;

  // ── 분석하기 버튼 상태 ──
  analyzing: boolean;
  setAnalyzing: (v: boolean) => void;
  /** IPS·시나리오 기준선 — 마지막 분석 시점을 기록해 다음 분석 시 변화 여부 판단에 사용 */
  lastAnalyzedIps: IpsState | null;
  lastAnalyzedScenario: { ratePct: number; fxKrw: number } | null;
  setAnalysisBaseline: (
    ips: IpsState,
    scenario: { ratePct: number; fxKrw: number },
  ) => void;

  // ── 실행 상태(확정 수명주기) ──
  // 값·전이 규칙의 출처는 lib/runStatus.ts 하나뿐이다(엔진 계약을 그대로 옮긴 것).
  // 읽는 곳: 헤더 상태 칩·PDF 추출 잠금. 쓰는 곳: 분석 승인 게이트(Sidebar)·
  // IPS 반영 승인(RightPanel)·확정 승인(ReportDetailModal)뿐이다.
  /** 현재 상담의 실행 상태. 초기값 draft. */
  runStatus: RunStatus;
  /** blocked 사유(엔진 governance.confirmation_blocked_reason에 대응). 없으면 빈 문자열. */
  runStatusReason: string;
  /** 전이표에 있는 전이만 반영한다. 규칙에 없는 전이는 상태를 바꾸지 않는다. */
  setRunStatus: (next: RunStatus, reason?: string) => void;
  /** 초기 상태(draft)로 되돌린다. 재실행·상담 전환 시 사용. */
  resetRunStatus: () => void;
  /** 확정 승인 시점의 안. 승인 전·초기화 후에는 null. */
  lockedSnapshot: LockedSnapshot | null;
  /**
   * 확정 승인 — locked 전이와 스냅샷 기록을 한 번에 한다.
   * 전이가 거부되면(전이표에 없는 경로) 스냅샷도 남기지 않는다.
   */
  lockReport: () => void;

  // ── 상단바 실시간 시장 지표 ──
  // MacroTicker 가 /api/macro-indicators 로 받은 실데이터를 여기에 올려, PDF 등
  // 다른 화면이 같은 값을 읽게 한다(미로드·실패 시엔 목 기준값으로 시작).
  macroIndicators: MacroIndicator[];
  setMacroIndicators: (rows: MacroIndicator[]) => void;

  // ── AI 인사이트 결과 ──
  insightResult: ApiResult<InsightData> | null;
  setInsightResult: (result: ApiResult<InsightData>) => void;

  helpMode: boolean;
  toggleHelpMode: () => void;

  addCustomer: (c: Customer) => void;
  setCustomers: (customers: Customer[]) => void;
  selectCustomer: (id: string) => void;
  /** 신규 고객의 isNew 플래그 해제(STT/과거 상담 불러오기 등 실제 데이터 확보 시). */
  clearCustomerNew: (id: string) => void;
  selectPortfolio: (id: string) => void;
  setIps: (patch: Partial<IpsState>) => void;
  setScenario: (patch: Partial<DashboardState["scenario"]>) => void;
  resetScenario: () => void;
  /** 실시간 현재값 주입 — 최초 1회는 슬라이더(scenario)도 실시간 값으로 맞춘다. */
  setLiveBase: (base: { ratePct: number; fxKrw: number }) => void;

  setTranscript: (transcript: ConsultMessage[], source: DataSource) => void;
  setConsultationId: (id: string) => void;
  setSttStatus: (status: SttStatus, note?: string) => void;
}

/**
 * 중앙 카드가 지금 보여 주는 안의 키.
 *
 * 사이드바의 입력 탭(weightsTab)이 아니라 "손을 댔는가"로 정한다. 분석 직후
 * 제안 조정 탭에는 선택한 제안의 값이 그대로 들어가 있어서, 그 시점의 조정안은
 * 안정추구·수익추구와 같은 안이다. 실제로 값을 고쳐야 비로소 별개의 안이 된다.
 *
 * `components/portfolio/PortfolioSection.tsx` 의 세그먼트가 같은 식을 읽는다 —
 * 화면에서 활성인 칸과 확정 대조의 기준이 갈라지면 안 된다.
 */
export function selectViewedPlanKey(s: DashboardState): string {
  return s.proposedWeightsDirty ? "proposed" : s.selectedPortfolioId;
}

/** 지금 보여 주는 안 — 확정 스냅샷과 같은 형태로 뽑는다. */
function viewedPlan(s: DashboardState): LockedSnapshot {
  const planKey = selectViewedPlanKey(s);
  const weights =
    planKey === "proposed"
      ? s.proposedWeightsInput
      : (s.portfolios.find((pf) => pf.id === planKey)?.weights ?? {});
  return [
    planKey,
    normalizeWeights(weights),
    normalizeWeights(s.currentWeightsInput),
  ].join("|");
}

/**
 * 제안 안의 비중을 입력 폼 형태로 옮긴다. 없는 안이면 빈 값.
 *
 * 제안 조정은 "빈 칸에서 새로 짜는 것"이 아니라 "이 제안에서 출발해 손보는 것"이다.
 * 그래서 제안을 고르는 순간 그 값이 입력 폼에 들어가 있어야 한다.
 */
function seedFromProposal(
  portfolios: Portfolio[],
  id: string,
): CurrentWeightsInput {
  const weights = portfolios.find((pf) => pf.id === id)?.weights;
  if (!weights) return {};
  return Object.fromEntries(
    CALC_UNITS.map((u) => [u.id, weights[u.id] ?? 0]),
  ) as CurrentWeightsInput;
}

/**
 * 상담 이력이 있는 고객의 복원값. 상담 전(isNew)이면 null.
 *
 * 첫 로드와 고객 전환이 같은 식을 쓴다 — 예전에는 전환에만 복원이 걸려 있어,
 * 사이트를 처음 열었을 때와 같은 고객을 다시 고른 뒤의 화면이 달랐다.
 *
 * 자산 배분만 이 고객의 비중으로 갈아 끼운다. 6지표·백테스트는 비중에서
 * 산출할 경로가 프론트에 없어 픽스처 값을 그대로 쓴다
 * (`lib/mockData.ts` withCurrentWeights 주석과 같은 이유).
 */
function restoredForCustomer(c: Customer | undefined) {
  return !c?.isNew && c?.currentWeights
    ? {
        ips: { ...(c.ips ?? IPS_DEFAULT) },
        currentWeightsInput: { ...c.currentWeights },
        portfolios: withCurrentWeights(PORTFOLIOS, c.currentWeights),
        portfolioSource: "fallback" as DataSource,
        portfolioNote: "지난 상담 회차의 결과입니다.",
      }
    : null;
}

/** 첫 화면의 복원값 — 목록 첫 고객 기준. */
const INITIAL_RESTORED = restoredForCustomer(CUSTOMERS[0]);

export const useDashboardStore = create<DashboardState>((set) => ({
  customers: [...CUSTOMERS],
  selectedCustomerId: CUSTOMERS[0].id,
  selectedPortfolioId: "a",
  ips: {
    returnPct: IPS_DEFAULT.returnPct,
    risk: IPS_DEFAULT.risk,
    timeYears: IPS_DEFAULT.timeYears,
    liquidity: IPS_DEFAULT.liquidity,
    goal: IPS_DEFAULT.goal,
    tax: IPS_DEFAULT.tax,
    legal: IPS_DEFAULT.legal,
    unique: IPS_DEFAULT.unique,
  },
  scenario: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
  liveBase: { ratePct: SCENARIO_BASE.ratePct, fxKrw: SCENARIO_BASE.fxKrw },
  liveBaseLoaded: false,
  currentWeightsInput: {},
  setCurrentWeightsInput: (patch) =>
    set((s) => ({
      currentWeightsInput: { ...s.currentWeightsInput, ...patch },
      analyzeRejected: false,
    })),
  analyzeRejected: false,
  setAnalyzeRejected: (v) => set({ analyzeRejected: v }),
  proposedWeightsDirty: false,
  weightsTab: "current",
  setWeightsTab: (tab) => set({ weightsTab: tab }),
  proposedWeightsInput: {},
  setProposedWeightsInput: (patch) =>
    set((s) => ({
      proposedWeightsInput: { ...s.proposedWeightsInput, ...patch },
      // 비중을 새로 손댔으면 직전 거절은 지나간 이야기다 — 안내를 한 줄만
      // 띄우려면 지금 유효한 사실만 남아야 한다.
      analyzeRejected: false,
      proposedWeightsDirty: true,
    })),

  // 초기 포트폴리오는 mock(데모) — 출처를 fallback 으로 둬 배지로 명시한다.
  portfolios: PORTFOLIOS,
  basePortfolios: PORTFOLIOS,
  portfolioSource: "fallback" as DataSource,
  portfolioNote: "포트폴리오를 계산 중입니다.",
  /**
   * 분석 결과 반영.
   *
   * 결과가 나오면 사이드바 입력을 제안 조정 탭으로 넘기고 선택된 제안의 비중을
   * 심는다 — 이 시점부터 PB 가 만지는 것은 "고객이 지금 들고 있는 비중"이 아니라
   * "고객에게 내놓을 안"이기 때문이다. 현재 보유 탭은 그대로 남아 있어 언제든
   * 돌아갈 수 있다.
   */
  setPortfolios: (portfolios, source, note) =>
    set((s) => ({
      portfolios,
      basePortfolios: portfolios,
      portfolioSource: source,
      portfolioNote: note,
      isStressMode: false,
      weightsTab: "proposed",
      /*
        이미 손본 조정안은 그대로 둔다.

        전에는 분석 결과가 올 때마다 선택한 제안의 값으로 다시 심고 dirty 를
        내렸다. 그러면 조정 → 승인 → 조정값 소멸이 되어, 조정한 안을 확정하려고
        승인했는데 그 안이 사라졌다. 조정을 할 이유가 없어지는 동작이었다.

        손대지 않은 상태에서는 종전대로 선택한 제안을 심는다 — 그때의 조정안은
        선택한 제안과 같은 안이라 심어 둬야 출발점이 생긴다.
      */
      ...(s.proposedWeightsDirty
        ? {}
        : {
            proposedWeightsInput: seedFromProposal(
              portfolios,
              s.selectedPortfolioId,
            ),
            proposedWeightsDirty: false,
          }),
    })),
  setStressPortfolios: (portfolios) => set({ portfolios, isStressMode: true }),

  isStressMode: false,
  stressPreset: "current",
  setStressPreset: (preset) => set({ stressPreset: preset }),
  clearStressMode: () =>
    set((s) => ({ portfolios: s.basePortfolios, isStressMode: false })),

  correlationHeatmap: null,
  setCorrelationHeatmap: (h) => set({ correlationHeatmap: h }),
  portfolioTax: null,
  setPortfolioTax: (tax) => set({ portfolioTax: tax }),
  stressTax: null,
  setStressTax: (tax) => set({ stressTax: tax }),
  taxOptimizer: null,
  setTaxOptimizer: (tax) => set({ taxOptimizer: tax }),

  analyzing: false,
  setAnalyzing: (v) => set({ analyzing: v }),
  lastAnalyzedIps: null,
  lastAnalyzedScenario: null,
  setAnalysisBaseline: (ips, scenario) =>
    set({ lastAnalyzedIps: ips, lastAnalyzedScenario: scenario }),

  runStatus: INITIAL_RUN_STATUS,
  runStatusReason: "",
  setRunStatus: (next, reason) =>
    set((s) => {
      // 실패 폐쇄: 규칙에 없는 전이는 조용히 무시하고 현재 상태를 유지한다.
      // 잘못된 전이로 확정(locked)이나 차단 해제가 일어나는 것을 막는 것이 목적이다.
      if (!canTransition(s.runStatus, next)) return s;
      // 확정에서 벗어나면 스냅샷도 함께 버린다 — 남겨 두면 나중에 locked 로
      // 돌아왔을 때 승인한 적 없는 안이 확정본으로 취급된다.
      return {
        runStatus: next,
        runStatusReason: reason ?? "",
        lockedSnapshot: next === RUN_STATUS.LOCKED ? s.lockedSnapshot : null,
      };
    }),
  resetRunStatus: () =>
    set({
      runStatus: INITIAL_RUN_STATUS,
      runStatusReason: "",
      lockedSnapshot: null,
    }),
  lockedSnapshot: null,
  lockReport: () =>
    set((s) => {
      if (!canTransition(s.runStatus, RUN_STATUS.LOCKED)) return s;
      return {
        runStatus: RUN_STATUS.LOCKED,
        runStatusReason: "",
        lockedSnapshot: viewedPlan(s),
      };
    }),

  macroIndicators: MACRO_INDICATORS,
  setMacroIndicators: (rows) => set({ macroIndicators: rows }),

  insightResult: null,
  setInsightResult: (result) => set({ insightResult: result }),

  // 상담 입력 전에는 내역을 비워 둔다. 고정 전사는 녹음 종료 또는 데모 업로드 후에만 반영한다.
  transcript: [],
  transcriptSource: "empty",
  consultationId: "",
  sttStatus: "idle",
  sttNote: undefined,
  helpMode: false,

  toggleHelpMode: () => set((s) => ({ helpMode: !s.helpMode })),
  addCustomer: (c) => set((s) => ({ customers: [...s.customers, c] })),
  setCustomers: (customers) =>
    set((s) => ({
      customers,
      selectedCustomerId: customers.some((c) => c.id === s.selectedCustomerId)
        ? s.selectedCustomerId
        : (customers[0]?.id ?? s.selectedCustomerId),
    })),
  selectCustomer: (id) =>
    set((s) => {
      const target = s.customers.find((c) => c.id === id);
      /*
        고객은 두 부류다.

          상담 이력 있음 : 지난 회차의 IPS·보유 비중·분석 결과가 복원되고 확정도
                          그대로 살아 있다. PB 가 이어서 보는 화면이다.
          상담 전(isNew) : 좌·중·우가 전부 비어 있고 확정도 없다. IPS·비중·분석
                          결과는 상담을 거쳐 사람이 채운다.

        복원값의 출처는 고객 레코드 하나뿐이다(`lib/mockData.ts` CUSTOMERS).
        여기서 숫자를 만들지 않는다.
      */
      const restored = restoredForCustomer(target);

      const next: Partial<DashboardState> = {
        selectedCustomerId: id,
        // 고객 전환 시 이전 고객의 분석 결과·스트레스 상태 전체 초기화
        portfolioSource: "fallback" as DataSource,
        portfolios: PORTFOLIOS,
        basePortfolios: PORTFOLIOS,
        portfolioNote: undefined,
        currentWeightsInput: {},
        correlationHeatmap: null,
        portfolioTax: null,
        stressTax: null,
        taxOptimizer: null,
        insightResult: null,
        analyzeRejected: false,
        weightsTab: "current",
        proposedWeightsInput: {},
        proposedWeightsDirty: false,
        isStressMode: false,
        stressPreset: "current",
        scenario: { ...s.liveBase }, // 슬라이더도 live 기준으로 초기화 → 자동분석는 항상 calculate
        // 실행 상태도 초기화 — 이전 고객의 상태 칩이 새 고객 화면에 남지 않게 한다.
        // 승인은 "이 고객의 이 리포트"에 대한 것이라 고객과 함께 폐기한다. 분석 결과·
        // IPS·비중을 전부 지우는데 확정만 남으면, 아무도 승인하지 않은 새 고객의
        // 리포트가 곧바로 추출 가능해진다.
        runStatus: INITIAL_RUN_STATUS,
        runStatusReason: "",
        lockedSnapshot: null,
        // 고객 전환 시 이전 고객의 상담 내역·상담 ID·STT 상태는 신규/기존 구분 없이 항상 초기화한다.
        // (이전 고객의 transcript·consultationId가 새 고객 화면에 노출되거나, 새 고객 clientId와
        //  이전 consultationId 조합으로 스냅샷이 잘못 저장되는 것을 방지)
        transcript: [] as ConsultMessage[],
        transcriptSource: "empty" as DataSource,
        consultationId: "",
        sttStatus: "idle" as SttStatus,
        sttNote: undefined,
        // 상담 전 고객은 IPS도 빈 상태로 시작 — 없는 값을 보여주지 않는다.
        ...(target?.isNew ? { ips: EMPTY_IPS } : {}),
        ...(restored ?? {}),
      };

      if (!restored) return next;

      /*
        지난 회차는 그때 PB 가 확정한 상태로 열린다 — 확정을 여기서 새로 받는 것이
        아니라 남아 있던 것을 되살리는 것이라, 전이표를 거치지 않고 결과 상태를
        그대로 쓴다. 스냅샷은 지금 복원한 안 그대로 만든다. 그래야 추출 조건
        (locked AND 보는 안 === 확정 스냅샷)이 성립해 PDF 가 열린 채로 시작한다.
      */
      const seeded = { ...s, ...next } as DashboardState;
      return {
        ...next,
        runStatus: RUN_STATUS.LOCKED,
        lockedSnapshot: viewedPlan(seeded),
      };
    }),
  clearCustomerNew: (id) =>
    set((s) => ({
      customers: s.customers.map((c) =>
        c.id === id ? { ...c, isNew: false } : c,
      ),
    })),
  /**
   * 제안 선택 — 고른 안의 비중을 제안 조정 입력에 그대로 심는다.
   *
   * 심을 때 dirty 를 내린다. 방금 심은 값은 아직 조정이 아니라 그 제안 자체이고,
   * 그 상태에서 중앙 세그먼트가 "제안 조정"으로 넘어가면 같은 안이 두 이름으로
   * 보인다. 손대지 않은 제안은 제 이름으로 남는다.
   *
   * 조정 중에 다른 제안을 고르면 조정값은 덮인다 — 기준선을 갈아 끼우는 동작이라
   * 그 위에 남은 조정을 얹을 자리가 없다.
   */
  selectPortfolio: (id) =>
    set((s) => ({
      selectedPortfolioId: id,
      proposedWeightsInput: seedFromProposal(s.portfolios, id),
      proposedWeightsDirty: false,
    })),
  /** 제안 조정을 고른 제안의 값으로 되돌린다(제안 조정 탭의 초기화). */
  resetProposedToSelected: () =>
    set((s) => ({
      proposedWeightsInput: seedFromProposal(s.portfolios, s.selectedPortfolioId),
      proposedWeightsDirty: false,
    })),
  setIps: (patch) => set((s) => ({ ips: { ...s.ips, ...patch } })),
  setScenario: (patch) =>
    set((s) => ({ scenario: { ...s.scenario, ...patch } })),
  resetScenario: () => set((s) => ({ scenario: { ...s.liveBase } })),
  setLiveBase: (base) =>
    set((s) => {
      // 사용자가 슬라이더를 직접 건드리지 않았으면(=scenario가 직전 liveBase와 동일)
      // 거시지표 새로고침 시 scenario도 새 live 기준으로 재동기화한다.
      // 그렇지 않으면(스트레스 값을 직접 넣어둔 경우) 사용자 조작을 보존한다.
      // 이 재동기화가 없으면 새로고침 후 scenario≠liveBase 가 되어, 일반 분석이
      // 스트레스 분기로 잘못 라우팅되고 대시보드 스냅샷 저장이 누락된다.
      const untouched =
        s.scenario.ratePct === s.liveBase.ratePct &&
        s.scenario.fxKrw === s.liveBase.fxKrw;
      return {
        liveBase: base,
        scenario: !s.liveBaseLoaded || untouched ? { ...base } : s.scenario,
        liveBaseLoaded: true,
      };
    }),
  setTranscript: (transcript, source) =>
    set({ transcript, transcriptSource: source }),
  setConsultationId: (id) => set({ consultationId: id }),
  setSttStatus: (status, note) => set({ sttStatus: status, sttNote: note }),
  /*
    첫 화면도 고객 전환과 같은 복원을 태운다. 예전에는 전환에만 걸려 있어,
    사이트를 처음 열었을 때와 그 고객을 다시 고른 뒤의 화면이 달랐다.
    데이터 키만 덮으므로 위의 액션 함수들은 그대로다.
  */
  ...(INITIAL_RESTORED ?? {}),
}));

// ── 실행 상태 셀렉터 ──
// 스토어에 셀렉터 관례가 없어 컴포넌트가 각자 s.runStatus 를 적으면 키 이름이
// 흩어진다. 읽는 경로를 여기 하나로 모아 둔다.

/** 현재 실행 상태. */
export const selectRunStatus = (s: DashboardState): RunStatus => s.runStatus;

/**
 * 아직 분석 결과가 없는가 — 중앙 빈 화면·우측 인사이트·자세히 버튼이 함께 읽는다.
 *
 * 판정 식이 화면마다 흩어져 있으면 한 곳만 고쳐도 다른 곳이 따라오지 않아,
 * 중앙은 비어 있는데 우측은 조회가 열려 있는 상태가 생긴다.
 */
export const selectAnalysisEmpty = (s: DashboardState): boolean =>
  s.portfolioSource === "fallback" &&
  s.portfolioNote === undefined &&
  !s.analyzing;

/** 컴포넌트용 구독 훅 — `const status = useRunStatus();` */
export const useRunStatus = (): RunStatus =>
  useDashboardStore(selectRunStatus);

/**
 * 고객 제공(PDF 추출) 허용 여부.
 *
 *   추출 가능 = runStatus === locked  AND  지금 보는 안 === 확정 스냅샷
 *
 * 앞 절의 출처는 lib/runStatus.ts 의 RUN_STATUS_EXPORT_ALLOWED 이고, 뒤 절은
 * 확정 승인 때 기록한 스냅샷과의 대조다. 탭을 바꾸거나 비중을 손대면 뒤 절이
 * 깨져 잠기고, 확정한 안으로 돌아오면 재승인 없이 다시 열린다.
 */
export const selectExportAllowed = (s: DashboardState): boolean => {
  if (!RUN_STATUS_EXPORT_ALLOWED[s.runStatus]) return false;
  const snap = s.lockedSnapshot;
  if (!snap) return false;
  return viewedPlan(s) === snap;
};

/** 추출이 막힌 이유. 허용 상태면 빈 문자열. */
export const selectExportBlockReason = (s: DashboardState): string => {
  if (selectExportAllowed(s)) return "";
  if (!RUN_STATUS_EXPORT_ALLOWED[s.runStatus]) return "PB 승인 후 추출";
  return "확정한 안과 달라 다시 잠겼습니다";
};
