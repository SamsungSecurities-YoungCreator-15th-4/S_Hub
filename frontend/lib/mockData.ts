/**
 * 화면 골격용 더미 데이터 모음.
 *
 * ⚠️ 모든 수치는 HTML 시안·정본 디자인에서 그대로 옮긴 자리표시자다.
 *    실제 지표(샤프지수·MDD·세금 등)는 백엔드(yfinance + 세법 로직) 연동 후
 *    이 파일을 API 응답으로 대체한다. 임의 수치를 실데이터처럼 쓰지 말 것.
 */

import {
  CALC_UNITS,
  isCurrentWeightsInputValid,
  sumCurrentWeightsInput,
  type CalcUnitWeights,
  type CurrentWeightsInput,
} from "./assetMapping";
import { withSharpe } from "./sharpe";

// ── 헤더: 거시지표 ──────────────────────────────────────────────
export interface MacroIndicator {
  label: string;
  value: string;
  change: string;
  direction: "up" | "down" | "neutral";
}

/**
 * 헤더 거시지표 폴백 — `/api/macro` 조회가 **최초 마운트에서** 실패했을 때만 보인다.
 * (한 번이라도 성공한 뒤의 실패는 MacroTicker 가 직전 실데이터를 그대로 유지한다.)
 *
 * ⚠️ 실제 시세와 너무 벌어지면 폴백이 떴을 때 화면이 티가 난다. 실제로 한 번
 *    KOSPI 2,790 / S&P 5,640 짜리 낡은 값이 남아 있어 실데이터(6,954 / 7,686)와
 *    두 배 이상 벌어졌었다. 가끔 아래 스냅샷을 갱신할 것.
 *
 * 스냅샷 기준: 2026-09-08 종가 (`/api/macro` 실측)
 * 표기 형식은 MacroTicker 의 실시간 경로와 같게 맞춘다 — 지수는 소수점 없이,
 * 등락은 지수 소수 2자리 · 금리 %p · 환율 원.
 */
export const MACRO_INDICATORS: MacroIndicator[] = [
  { label: "미국 기준금리", value: "3.75%", change: "0.25%p", direction: "down" },
  { label: "미 10Y", value: "4.80%", change: "0.01%p", direction: "up" },
  { label: "미국 CPI", value: "3.4%", change: "0.10%p", direction: "down" },
  { label: "원/달러", value: "1,341", change: "4원", direction: "down" },
  { label: "KOSPI", value: "6,955", change: "40.87", direction: "down" },
  { label: "S&P 500", value: "7,686", change: "32.28", direction: "down" },
];

export const BASE_TIME = "17:20";

// ── 고객 ───────────────────────────────────────────────────────
export interface Customer {
  id: string;
  name: string;
  /** 자산 규모 구분. 1억원대 직장인 고객이 들어오면서 VVIP 단일 값에서 넓혔다. */
  grade: "VVIP" | "일반";
  pbCode: string;
  aumLabel: string; // 표시용
  aumEokwon: number; // 계산용 (억원)
  /**
   * 연간 총급여(만원). 연금계좌 세액공제율이 총급여 5,500만원(종합소득금액
   * 4,500만원) 경계에서 16.5% / 13.2% 로 갈리므로 판정에 반드시 필요하다.
   * 한계세율만으로는 이 경계를 알 수 없다 — 둘은 다른 기준(과세표준 vs 총급여)이다.
   */
  salaryManwon?: number;
  /** 연간 신규 납입 여력(만원) — 절세계좌에 배분할 수 있는 금액 (IPS Unique). */
  annualContributionManwon?: number;
  // 절세계좌 기납입액·세부담 입력값(만원/%) — 절세 제안 실계산용 고객 데이터.
  // 실서비스에서는 PB가 입력/연동(준호님 DB 반영 예정). 여기선 현실적 자리표시자.
  // ISA **누적** 납입금액(만원). 조특법 산식이 누적 기준이라 당해 납입액이 아니다.
  isaUsedManwon: number;
  /** ISA 가입 후 경과연수 — 한도는 1월 1일에 새로 쌓인다. 미지정이면 가입 첫해로 본다. */
  isaYearsSinceOpen?: number;
  pensionUsedManwon: number; // 연금저축+IRP 당해 납입액 (세액공제 한도 900만)
  realizedLossManwon: number; // 확정 가능 평가손실 (Tax-loss harvesting용)
  marginalRatePct: number; // 한계세율(지방세 포함, %) — 종합과세 추가과세 비교용
  // 적합성(lock-up) 게이팅 입력 — 임시 수기 입력(추후 DB/IPS 연동).
  age: number; // 나이 — 연금 55세 수령요건 게이팅
  horizonYears: number; // 투자기간(년) — ISA 3년·연금 lock-up 게이팅 (IPS Time)
  nearTermNeedManwon: number; // 단기 필요자금(만원) — 묶이는 금액에서 제외 (IPS Unique)
  nearTermNeedYears: number | null; // 단기 필요자금 필요 시점(년)
  isaOpened: boolean; // ISA 기존 개설 여부(시나리오: 다들 옛날 개설=true)
  /**
   * ISA 의무보유 3년 중 남은 기간(년). 의무보유는 납입분별이 아니라 계좌 단위라
   * 개설 시점이 정한다. 미지정이면 미개설=3년, 개설=0년으로 본다.
   */
  isaYearsUntilLiquid?: number;
  /**
   * 마지막 상담일(YYYY-MM-DD). 없으면 상담 이력이 없는 고객이다.
   * `isNew` 와 같은 사실의 두 표현이라 함께 움직인다 — isNew 는 분기용,
   * 이쪽은 화면 표기용이다.
   */
  lastConsultedAt?: string;
  /**
   * 상담 이력이 있는 고객이 화면에 열릴 때 복원할 IPS. 없으면 IPS_DEFAULT 를 쓴다.
   * 신규 고객은 이 값을 두지 않는다 — 상담 전에 IPS 가 있을 수 없다.
   */
  ips?: typeof IPS_DEFAULT;
  /** 상담 이력이 있는 고객의 현재 보유 비중(%). 합계 100. */
  currentWeights?: CurrentWeightsInput;
  /** DB(client 테이블) UUID. 초기 mock 3명·미저장(데모) 고객은 없음. */
  clientId?: string;
  /** DB 저장 성공 여부. false = 데모(로컬에만 추가). undefined = mock 초기 고객. */
  persisted?: boolean;
  /**
   * 갓 생성돼 아직 상담(STT/지난 상담 불러오기)이 한 번도 없는 신규 고객.
   * true면 더미 IPS로 자동 분석하지 않고 IPS·중앙 대시보드를 빈 상태로 둔다.
   * STT 완료 또는 과거 상담 불러오기 시 false 로 해제된다.
   */
  isNew?: boolean;
}

export const CUSTOMERS: Customer[] = [
  {
    // 상담 이력이 있는 고객. 화면을 열면 지난 회차의 IPS·비중·확정 상태가 복원된다.
    // 목록 첫 번째라 초기 선택 고객이기도 하다 — 처음 열었을 때 채워진 화면을 본다.
    id: "cust-002",
    name: "이사조",
    grade: "일반",
    pbCode: "PB-100483",
    aumLabel: "운용자산 3억원",
    aumEokwon: 3,
    salaryManwon: 8000,
    // 총급여 8,000만원 기준 연 2,400만원(월 200만원)을 절세계좌 납입여력으로 잡는다.
    // 법정 수치가 아니라 이 고객의 설정값이다 — 실서비스에서는 PB 가 입력한다.
    annualContributionManwon: 2400,
    isaUsedManwon: 2000, // 누적 납입액
    // 3년 전 개설. 이 값이 없으면 "올해 가입"으로 계산돼(조특법 누적 산식의
    // 경과연수 0) 상담 이력이 있는 고객인데 올해 한도만 남은 것으로 잡힌다.
    isaYearsSinceOpen: 3,
    pensionUsedManwon: 900, // 연금 세액공제 한도 소진
    realizedLossManwon: 0,
    marginalRatePct: 26.4,
    age: 47,
    horizonYears: 13,
    nearTermNeedManwon: 0,
    nearTermNeedYears: 0,
    isaOpened: true,
    lastConsultedAt: "2026-08-21",
    ips: {
      goal: "은퇴 후 현금흐름 확보",
      assetLabel: "3억원",
      returnPct: 5,
      // 브리프의 "중립형"은 IpsState.risk 유니온(안정형·균형형·공격형)에 없는 값이라
      // 같은 자리의 균형형으로 적는다. 유니온은 팀 데이터 계약이라 넓히지 않는다.
      risk: "균형형" as "안정형" | "균형형" | "공격형",
      timeYears: 13,
      tax: "배당소득 원천징수",
      liquidity: "낮음" as "낮음" | "중간" | "높음",
      legal: "특이사항 없음",
      unique: "배당 중심 선호 · 연금 세액공제 한도 소진",
    },
    currentWeights: {
      domesticEquity: 18,
      overseasGrowthEquity: 14,
      overseasDividendEquity: 16,
      domesticBond: 22,
      overseasBond: 10,
      reits: 8,
      gold: 6,
      cash: 6,
    },
  },
  {
    // 상담 이력이 있는 고객. 위와 같은 성격, 값만 다르다.
    id: "cust-003",
    name: "박기업",
    grade: "일반",
    pbCode: "PB-100484",
    aumLabel: "운용자산 5억원",
    aumEokwon: 5,
    salaryManwon: 6000,
    // 총급여 6,000만원 기준 연 1,800만원(월 150만원). 이사조와 같은 기준이다.
    annualContributionManwon: 1800,
    isaUsedManwon: 2000, // 누적 납입액
    // 개설 4년 이상 — 누적 산식의 경과연수 상한이라 총한도 1억이 그대로 쌓인다.
    isaYearsSinceOpen: 4,
    // 연금저축·IRP 당해 납입액. 세액공제 한도(900만)를 넘겨 납입한 상태라
    // 추가 납입에 대한 공제 여력은 없다.
    pensionUsedManwon: 1800,
    realizedLossManwon: 0,
    marginalRatePct: 26.4,
    age: 58,
    horizonYears: 7,
    // IPS Unique 의 "3년 내 인출 계획" 을 금액·시점으로 옮긴 값. 운용자산 5억의
    // 10%를 3년 내 인출한다고 본다. 0 으로 두면 Unique 와 어긋난다.
    nearTermNeedManwon: 5000,
    nearTermNeedYears: 3,
    isaOpened: true,
    lastConsultedAt: "2026-07-30",
    ips: {
      goal: "원금 보전 우선 · 정기 인출",
      assetLabel: "5억원",
      returnPct: 4,
      // 브리프의 "안정추구형" → 유니온의 안정형. 위와 같은 이유다.
      risk: "안정형" as "안정형" | "균형형" | "공격형",
      timeYears: 7,
      tax: "금융소득 종합과세 대상",
      liquidity: "높음" as "낮음" | "중간" | "높음",
      legal: "특이사항 없음",
      unique: "3년 내 인출 계획 · 채권 비중 선호",
    },
    currentWeights: {
      domesticEquity: 8,
      overseasGrowthEquity: 6,
      overseasDividendEquity: 10,
      domesticBond: 30,
      separateTaxBond: 12,
      overseasBond: 12,
      gold: 4,
      cash: 18,
    },
  },
  {
    // 상담 전 고객. 좌·중·우가 전부 비어 있고 확정도 없다 — IPS·비중·분석 결과는
    // 상담을 거쳐 사람이 채운다. isNew 가 그 분기를 담당한다(store.selectCustomer).
    // 33세 직장인 6년차 — 은퇴자산을 쌓으면서 3년 뒤 전세 보증금 인상분도
    // 마련해야 하는, 절세계좌 lock-up 과 정면으로 부딪히는 사례다.
    id: "cust-001",
    name: "김성삼",
    grade: "일반",
    pbCode: "PB-100482",
    // 분석 전이라 운용자산을 단정하지 않는다. 목록에는 이 자리에 상담 이력을 적는다.
    aumLabel: "상담 이력 없음",
    aumEokwon: 1,
    salaryManwon: 5200, // 총급여 5,500만원 이하 → 연금 세액공제율 16.5%
    annualContributionManwon: 1500, // 연 납입여력
    isaUsedManwon: 800, // 작년 개설 후 누적 납입액
    isaYearsSinceOpen: 1, // 올해 한도 = 2,000×2 − 800 = 3,200만원 (미납분이 쌓인다)
    pensionUsedManwon: 0, // 연금계좌 미개설 — 900만 한도가 통째로 남아 있다
    realizedLossManwon: 0,
    marginalRatePct: 16.5, // 과세표준 1,400~5,000만 구간(15%) + 지방소득세
    age: 33,
    horizonYears: 22, // 만 55세 연금 수령까지 남은 기간과 같다 — 적합성 경계
    nearTermNeedManwon: 2000, // 3년 내 전세 보증금 인상분
    nearTermNeedYears: 3,
    isaOpened: true,
    isaYearsUntilLiquid: 2, // 작년 개설 — 2년 뒤 해제, 전세 시점(3년)보다 이르다
    isNew: true,
  },
];

/**
 * PB가 입력한 현재 보유 비중을 "현재" 포트폴리오의 weights 에 얹는다.
 *
 * 도넛(PortfolioSection 의 toCalcUnitAllocation)과 스트레스 손실
 * (StressTestSection → runStress)이 같은 weights 를 읽으므로, 입력이 화면까지
 * 그대로 도달한다. 스트레스 손실은 엔진 상수·수식으로 실제 계산되는 값이다
 * (`lib/stressScenarios.ts` — SSOT 는 engine/engine/stress.py).
 *
 * 지표(기대수익률·변동성·MDD·소르티노)는 바꾸지 않는다. 임의 비중으로 다시
 * 계산하려면 자산별 수익률 시계열이 있어야 하는데 프론트 경로에는 없다
 * (`lib/sharpe.ts` 가 같은 이유로 샤프 외의 지표 계산을 두지 않았다).
 * 없는 값을 지어내지 않고 픽스처 값을 유지하며, 출처는 DataSourceBadge 가
 * "시연 고정 데이터"로 표시한다.
 *
 * 입력이 없거나 합계가 100%가 아니면 손대지 않는다 — 라이브 경로도
 * `isCurrentWeightsInputValid` 로 같은 입력을 막는다.
 */
export function withCurrentWeights(
  portfolios: Portfolio[],
  input?: CurrentWeightsInput,
): Portfolio[] {
  if (!input || sumCurrentWeightsInput(input) === 0) return portfolios;
  if (!isCurrentWeightsInputValid(input)) return portfolios;

  const weights = Object.fromEntries(
    CALC_UNITS.map((u) => [u.id, input[u.id] ?? 0]),
  ) as CalcUnitWeights;

  return portfolios.map((pf) =>
    pf.id === "current" ? { ...pf, weights, allocation: undefined } : pf,
  );
}

// ── 지난 상담 기록 목록 (더미) ─────────────────────────────────
export interface PastConsultation {
  id: string;
  title: string;
}

export const PAST_CONSULTATIONS: PastConsultation[] = [
  { id: "pc-1", title: "20260628_김성삼_상담기록" },
  { id: "pc-2", title: "20260615_김성삼_상담기록" },
  { id: "pc-3", title: "20260601_김성삼_상담기록" },
  { id: "pc-4", title: "20260528_이사조_상담기록" },
  { id: "pc-5", title: "20260510_박기업_상담기록" },
];

// ── 상담 내역 ──────────────────────────────────────────────────
export interface ConsultMessage {
  speaker: "PB" | "고객";
  text: string;
  time: string;
}

export const CONSULT_DURATION = "02:14";

export const CONSULT_LOG: ConsultMessage[] = [
  // 이 전사가 IPS 의 근거다. IPS Unique 를 바꾸면 여기도 같이 바꿔야 앞뒤가 맞는다.
  // (store 의 transcript 초기값이라 사이드바 상담 내역에 그대로 찍힌다.)
  {
    speaker: "PB",
    text: "은퇴자산을 길게 가져가고 싶다고 하셨는데, 중간에 목돈 나갈 일이 있으실까요?",
    time: "00:07",
  },
  {
    speaker: "고객",
    text: "3년 뒤에 전세 재계약이 있어요. 보증금 인상분이 2,000만원쯤 될 것 같습니다.",
    time: "00:15",
  },
  {
    speaker: "PB",
    text: "그 자금은 따로 확보해 두고 나머지를 굴리는 쪽으로 잡겠습니다. 현재 계좌는 어떻게 운용 중이신가요?",
    time: "00:28",
  },
  {
    speaker: "고객",
    text: "국내 반도체주 비중이 좀 큽니다. ISA는 작년에 만들어서 800만원 정도 넣었고요.",
    time: "00:40",
  },
  {
    speaker: "PB",
    text: "ISA 한도는 미사용분이 다음 해로 쌓입니다. 작년 미납분까지 하면 올해는 3,200만원까지 가능합니다.",
    time: "00:52",
  },
  {
    speaker: "고객",
    text: "연금저축은 아직 안 만들었어요. 세액공제가 크다고는 들었는데 55세까지 못 뺀다고 해서요.",
    time: "01:08",
  },
  {
    speaker: "PB",
    text: "연 900만원까지 세액공제 대상이고 총급여 5,500만원 이하면 공제율이 16.5%입니다. 다만 말씀대로 만 55세까지 묶입니다.",
    time: "01:20",
  },
  {
    speaker: "고객",
    text: "매년 1,500만원 정도는 넣을 수 있는데, 3년 뒤 전세금까지 생각하면 얼마씩 나눠야 할지 모르겠네요.",
    time: "01:42",
  },
  {
    speaker: "PB",
    text: "절세와 유동성이 반대로 움직이는 구간이라 배분을 같이 보면서 정하겠습니다.",
    time: "01:55",
  },
];

// ── IPS 조율기 초기값 ──────────────────────────────────────────
export const IPS_DEFAULT = {
  goal: "은퇴자산 형성 + 3년 내 전세 재계약 대비",
  assetLabel: "1억원",
  returnPct: 7,
  risk: "공격형" as "안정형" | "균형형" | "공격형",
  // 만 55세까지 22년. 연금 수령 요건과 정확히 같은 값이라 적합성 판정이 경계에 선다.
  timeYears: 22,
  tax: "해외주식 양도세 · 배당소득 원천징수",
  liquidity: "중간" as "낮음" | "중간" | "높음",
  legal: "특이사항 없음",
  unique:
    "국내 반도체주 비중이 큼 · 3년 내 전세 보증금 인상분 약 2,000만원 필요 · " +
    "연 납입여력 1,500만원 · ISA 운용 중이나 한도 미소진, 연금계좌 미개설",
};

// ── 포트폴리오 3종 (현재 / A 베스트 / B 추천) ──────────────────
export interface PortfolioMetrics {
  expectedReturnPct: number;
  volatilityPct: number;
  /** (기대수익률 − 무위험수익률) / 변동성. lib/sharpe.ts 가 단일 정의다.
   *  변동성이 0 이하면 정의되지 않아 undefined 다. */
  sharpe?: number;
  sortino: number;
  /** 백엔드 실계산 원화 병기. 없으면 화면이 비율×총자산으로 계산한다. */
  volatilityAmountLabel?: string;
  mddPct: number; // 양수로 보관, 표시 시 ▼ 접두
  mddAmountLabel?: string;
  afterTaxReturnPct: number;
  afterTaxAmountLabel?: string;
}

export interface BacktestPoint {
  date: string; // YYYY-MM
  value: number; // 누적 인덱스 (base = 100)
}

export interface Portfolio {
  id: "current" | "a" | "b";
  name: string;
  badge: "현재" | "베스트" | "추천";
  /** 백엔드 8개 자산군 원본 allocation (도넛 차트에 직접 사용) */
  allocation?: { asset_class: string; name: string; weight: number }[];
  /** 11종 계산 단위 비중(%). PDF 상관관계 히트맵 필터링용 — 도넛 표시는 allocation 우선 */
  weights: CalcUnitWeights;
  metrics: PortfolioMetrics;
  backtest?: BacktestPoint[];
  benchmarks?: {
    kospi?: BacktestPoint[];
    sp500?: BacktestPoint[];
    msciAcwi?: BacktestPoint[];
  };
}

// 11종 비중은 시안의 6분류 값(예: 현재 25/18/12/22/12/11)이 나오도록 가배분한 것.
// TODO(팀 확정 필요): 백엔드 11종 실데이터 연동 시 교체.
export const PORTFOLIOS: Portfolio[] = [
  {
    id: "current",
    name: "현재",
    badge: "현재",
    weights: {
      domesticEquity: 25,
      overseasDividendEquity: 18,
      overseasGrowthEquity: 9,
      emergingEquity: 3,
      domesticBond: 14,
      overseasBond: 8,
      lowCouponBond: 12,
      separateTaxBond: 5,
      reits: 3,
      gold: 2,
      infraFund: 1,
    },
    metrics: withSharpe({
      expectedReturnPct: 4.8,
      volatilityPct: 11.2,
      sortino: 0.3,
      mddPct: 14.6,
      afterTaxReturnPct: 4.0,
    }),
  },
  {
    id: "a",
    name: "포트폴리오 A",
    badge: "베스트",
    weights: {
      domesticEquity: 20,
      overseasDividendEquity: 22,
      overseasGrowthEquity: 9,
      emergingEquity: 3,
      domesticBond: 11,
      overseasBond: 7,
      lowCouponBond: 14,
      separateTaxBond: 6,
      reits: 4,
      gold: 2,
      infraFund: 2,
    },
    metrics: withSharpe({
      expectedReturnPct: 6.4,
      volatilityPct: 12.5,
      sortino: 0.48,
      mddPct: 11.2,
      afterTaxReturnPct: 5.5,
    }),
  },
  {
    id: "b",
    name: "포트폴리오 B",
    badge: "추천",
    weights: {
      domesticEquity: 28,
      overseasDividendEquity: 26,
      overseasGrowthEquity: 17,
      emergingEquity: 5,
      domesticBond: 8,
      overseasBond: 4,
      lowCouponBond: 8,
      separateTaxBond: 2,
      reits: 1,
      gold: 1,
      infraFund: 0,
    },
    metrics: withSharpe({
      expectedReturnPct: 8.7,
      volatilityPct: 20.3,
      sortino: 0.43,
      mddPct: 23.3,
      afterTaxReturnPct: 7.2,
    }),
  },
];

// ── 백테스트 (최근 5년, 100 기준 지수화 더미) ──────────────────
// 벤치마크(kospi·sp500·msciAcwi)는 실제 시장 흐름의 근사치 — 실 API 연동 전 UI 시안용.
export const BACKTEST_SERIES = [
  {
    year: "2021",
    current: 100,
    a: 100,
    b: 100,
    kospi: 100,
    sp500: 100,
    msciAcwi: 100,
  },
  {
    year: "2022",
    current: 96,
    a: 103,
    b: 92,
    kospi: 76,
    sp500: 81,
    msciAcwi: 80,
  },
  {
    year: "2023",
    current: 108,
    a: 116,
    b: 118,
    kospi: 90,
    sp500: 104,
    msciAcwi: 100,
  },
  {
    year: "2024",
    current: 118,
    a: 131,
    b: 128,
    kospi: 97,
    sp500: 134,
    msciAcwi: 123,
  },
  {
    year: "2025",
    current: 128,
    a: 150,
    b: 156,
    kospi: 101,
    sp500: 165,
    msciAcwi: 148,
  },
  {
    year: "2026",
    current: 140,
    a: 176,
    b: 200,
    kospi: 108,
    sp500: 190,
    msciAcwi: 168,
  },
];

// ── 절세 최적화 시뮬레이터 ─────────────────────────────────────
export const TAX_EFFECT = {
  baseLabel: "기준 : 포트폴리오 A",
  annualSavingManwon: 1080,
  subNote:
    "일반과세 대비 · 세후 수익률 +0.6%p · 해외주식 양도세 22%·공제 250만 반영",
  afterTaxReturn: { from: "5.5%", to: "6.1%", delta: "+0.6%p" },
  effectiveTax: { from: "1,620", to: "540만", delta: "-66.7%" },
  // 세금 흐름 비교 (세전 기대수익 2.59억 기준, afterTaxManwon=만원)
  flow: {
    pretaxLabel: "세전 기대수익 2.59억 기준",
    rows: [
      { label: "현재", afterTaxManwon: 25100, taxManwon: 795 },
      { label: "포트폴리오 전환", afterTaxManwon: 25600, taxManwon: 363 },
      { label: "+ 절세 제안", afterTaxManwon: 25900, taxManwon: 0 },
    ],
    totalLabel: "총 절세 효과 (전환 432만 + 제안 363만)",
    totalSavingManwon: 795,
  },
  // 절세 계좌 배치 활용도
  accounts: [
    {
      name: "ISA",
      tag: "비과세·분리과세",
      used: 2000,
      limit: 2000,
      caption: "납입 한도 100% 활용 · 비과세 200만 + 초과분 9.9% 분리과세",
    },
    {
      name: "연금저축 + IRP",
      tag: "세액공제",
      used: 900,
      limit: 900,
      caption: "세액공제 한도 소진 · 공제율 16.5% → 환급 148만",
    },
    {
      name: "일반계좌",
      tag: "분리과세 ETF",
      used: null,
      limit: null,
      caption: "국내·해외 ETF 중심으로 금융소득종합과세 구간 회피",
    },
  ],
};

/**
 * 절세 제안 카드에 연계할 상품 목록의 원소 타입.
 * 개별 상품·펀드 제시는 백엔드에 근거가 없어(계산 대상은 ISA·연금 등 계좌 제도뿐)
 * 목록을 비워 두었다. 근거 있는 상품 소스가 생기면 여기에 채운다.
 */
export interface TaxAdviceProduct {
  name: string;
  desc: string;
}

/**
 * Mass 고객용 절세 제안 카드가 참조하는 기존 계산 전략.
 * 연금저축과 IRP는 백엔드의 연금계좌 합산 계산(pension_credit)을 공유한다.
 */
export type TaxAdviceSourceKey = "isa" | "pension_credit";

export interface TaxAdviceDisplayCard {
  key: "brokerage_isa" | "pension_savings" | "irp";
  sourceKey: TaxAdviceSourceKey;
  /** 같은 연금계좌 계산값을 두 번 합산하지 않기 위한 표시 역할. */
  savingRole: "primary" | "included";
  icon: string;
  title: string;
  /**
   * 고객용 PDF 가 쓰는 산문. 문단으로 읽히는 매체라 문장 형태를 유지한다.
   * 화면 카드는 아래 helpLines 를 쓴다 — 같은 내용이므로 한쪽만 고치지 말 것.
   */
  body: string;
  /**
   * 화면 가이드 툴팁용 개조식 목록. 마우스를 올린 잠깐 읽는 글이라 한 줄에
   * 한 사실만 둔다.
   */
  helpLines: string[];
  tag: string;
  saving: string;
  products: TaxAdviceProduct[];
}

export const TAX_ADVICE: {
  cards: TaxAdviceDisplayCard[];
  totalLabel: string;
  totalSaving: string;
} = {
  cards: [
    {
      key: "brokerage_isa",
      sourceKey: "isa",
      savingRole: "primary",
      icon: "ISA",
      title: "중개형 ISA",
      // 출처: 삼성증권 ISA 안내
      // https://www.samsungpop.com/ux/kor/finance/isa/isainfo/intro.do
      body: "계좌 안의 손익을 통산한 순소득 중 일반형 200만원·서민형 400만원까지 비과세되고, 초과분은 9.9%로 분리과세됩니다.",
      helpLines: [
        "계좌 내 손익을 통산한 순소득에 과세",
        "비과세 한도 일반형 200만원 · 서민형 400만원",
        "초과분은 9.9% 분리과세",
      ],
      tag: "연 2,000만원 · 의무보유 3년",
      saving: "",
      products: [
        {
          name: "삼성증권 중개형 ISA",
          desc: "중개형 ISA 제도와 가입 조건 확인",
        },
      ],
    },
    {
      key: "pension_savings",
      sourceKey: "pension_credit",
      savingRole: "primary",
      icon: "연",
      title: "개인연금 (연금저축)",
      // 출처: 국세청 연금계좌 세액공제·삼성증권 개인연금 거래안내
      // https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7875&mi=6449
      // https://www.samsungpop.com/ux/kor/customer/guide/workproductguide/personalAnnuity.do
      body: "연금저축 납입액은 연 600만원까지 세액공제 대상이며, IRP·DC를 더하면 연금계좌 합산 연 900만원까지 적용됩니다.",
      helpLines: [
        "연 600만원까지 세액공제 대상",
        "IRP·DC 합산 시 연 900만원까지 적용",
      ],
      tag: "연금계좌 합산 절감액",
      saving: "",
      products: [
        {
          name: "삼성증권 연금저축계좌",
          desc: "연금저축 세액공제와 거래 조건 확인",
        },
      ],
    },
    {
      key: "irp",
      sourceKey: "pension_credit",
      savingRole: "included",
      icon: "IRP",
      title: "개인형 IRP",
      // 출처: 삼성증권 연금가이드(가입대상·세액공제 한도)
      // https://www.samsungpop.com/mbw/finance/pensionAccount.do?cmd=guide&tab=DIRP
      body: "소득이 있는 취업자가 가입할 수 있으며, 연금저축·DC와 합산해 연 900만원까지 세액공제 대상이 됩니다.",
      helpLines: [
        "소득이 있는 취업자가 가입 가능",
        "연금저축·DC와 합산해 연 900만원까지 세액공제",
        // 연금저축을 먼저 채우는 배분 순서의 근거. 디폴트옵션이면 100% 투자가
        // 가능하므로 "IRP 가 불리하다"고 단정하지 않고 한도가 있다는 사실만 적는다.
        "위험자산 투자한도 70% (디폴트옵션 운용 시 예외)",
        "중도인출은 무주택 주택구입·요양 등 법정 사유만 가능",
      ],
      tag: "연금저축과 900만원 한도 공유",
      saving: "합산 절감액에 포함",
      products: [
        {
          name: "삼성증권 개인형 IRP",
          desc: "개인형 IRP 가입 조건과 세제 혜택 확인",
        },
      ],
    },
  ],
  totalLabel: "3대 절세계좌 활용 시 예상 추가 절감",
  totalSaving: "분석 후 계산",
};

// ── 시나리오 Test (스트레스 테스트) ─────────────────────────────
export const SCENARIO_BASE = {
  ratePct: 3.75, // 현재 기준금리 (시안 기준)
  rateMin: 0,
  rateMax: 6,
  rateStep: 0.25,
  fxKrw: 1530, // 현재 원/달러 (시안 기준)
  fxMin: 1000,
  fxMax: 2000,
  fxStep: 10,
};

/**
 * AI 인사이트 하단의 출처/인용 목록 원소 타입.
 * 실제 출처는 백엔드 RAG(`/rag/insight`)의 citations 로 채운다.
 * 아래 INSIGHT.sources 는 백엔드 미연결(시연·폴백) 시에만 쓰이는 대체값이다.
 */
export interface InsightSource {
  title: string;
  date: string;
}

// ── AI 인사이트 ────────────────────────────────────────────────
export const INSIGHT = {
  placeholder: "예: 재무제표, RAG 문서, 분석 결과 요약",
  query:
    "현재 고객 포트폴리오의 시장 환경 대응 전략 및 최적 자산 배분 방향을 분석해 주세요.",
  defaultAnswer:
    "현재 고객 포트폴리오는 국내주식 20%, 해외배당주 22% 비중으로 선진국 배당 자산에 상대적으로 집중되어 있습니다. 최근 미 연준의 금리 동결 기조 장기화 가능성을 고려할 때, 단기 채권 듀레이션을 1~2년 이내로 유지하면서 투자등급 회사채 비중을 소폭 확대하는 전략이 유효합니다.\n\n환율 측면에서는 원/달러 환율이 1,380~1,420원 구간에서 등락하는 현 상황에서, 해외자산 중 비헤지 비중이 44%에 달해 환손실 리스크가 잠재합니다. 달러 익스포저의 30% 수준까지 환헤지 전환을 단계적으로 검토하시기 바랍니다.\n\n세후 수익률 기준으로는 포트폴리오 A(세후 5.5%)가 현재 포트폴리오(세후 4.0%) 대비 약 1.5%p 우위에 있으며, ISA 계좌 편입과 연금저축 한도 추가 납입을 통해 절세 여력이 연간 최대 1,080만원 추가로 확보 가능합니다.\n\n리스크 관리 측면에서 MDD -11.2% 수준은 고객 손실 허용 범위(통상 -15% 이내) 내에 있으나, 글로벌 경기 둔화 시나리오 하에서 해외성장주 비중(12%)이 변동성 확대의 주요 원인이 될 수 있습니다. 포트폴리오 B의 해외성장주 22% 비중 확대안은 고수익 추구 성향 고객에 한해 선별 제안을 권고합니다.",
  /**
   * 시연·폴백용 인용 목록. 새로 지어낸 출처가 아니라 **실제 RAG 코퍼스 문서**다.
   *
   * 값의 출처: `backend/data/<category>/*.pdf` (= `corpus/manifest.md` 21건).
   * title·date 는 운영 인제스천 스크립트가 생성하는 문자열을 그대로 옮긴 것이라
   * 백엔드 연결 시 `/rag/insight` 가 돌려주는 값과 형식·내용이 일치한다.
   *   · title : `backend/scripts/ingest_documents.py` humanize_title()
   *             = "<파일명 stem, _ → 공백> (<source_type>)"
   *             source_type 폴더명 매핑 house_view→house_view / tax→tax_law / macro→macro
   *   · date  : 같은 파일 parse_published_date() = 파일명의 YYYYMM→YYYY-MM-01,
   *             YYYY→YYYY-01-01
   *
   * 코퍼스에 없는 문서명을 여기 추가하지 않는다 — 화면의 출처는 추적 가능해야 한다.
   */
  sources: [
    { title: "bok mpd 202601 (macro)", date: "2026-01-01" },
    { title: "fed fomc 202601 (macro)", date: "2026-01-01" },
    { title: "samsung equity 202511 (house_view)", date: "2025-11-01" },
    { title: "nts taxguide 2026 vol1 (tax_law)", date: "2026-01-01" },
  ] as InsightSource[],
  /**
   * 질문 성격별 응답. 백엔드 미연결 시 `demoInsight(query)` 가 keywords 로 고른다.
   *
   * 하나뿐이면 무엇을 물어도 같은 답이 나와, RAG 가 질문을 읽는다는 사실 자체가
   * 화면에서 확인되지 않는다. 질문의 성격(거시·하우스뷰·세제)에 따라 인용하는
   * 코퍼스 카테고리가 갈리는 것이 이 기능의 핵심이라 그 갈림을 보이게 한다.
   *
   * sources 는 위 주석과 같은 규칙이다 — 코퍼스에 실제로 있는 문서만 적는다
   * (`corpus/manifest.md` 21건). 없는 문서명을 지어내면 화면의 출처가 추적 불가가 된다.
   *
   * 첫 항목부터 순서대로 검사하므로, 좁은 질문을 위에 둔다.
   */
  scenarios: [
    {
      key: "individual_security",
      // 개별 종목은 이 화면의 범위가 아니다. 답을 지어내지 않고 범위를 밝힌다 —
      // 실재하는 회사의 시세·지표를 근거 없이 만들어 내는 것이 가장 나쁜 실패다.
      keywords: ["종목", "주가", "시세", "티커", "몇 주", "매수", "매도"],
      answer:
        "이 화면은 자산군 단위로만 분석합니다. 개별 종목의 시세·재무 지표는 여기서 다루지 않습니다.\n\n" +
        "이유는 두 가지입니다. 하나는 근거입니다 — 리스크 계량과 스트레스 시나리오는 자산군별 수익률·상관관계 위에서 계산되고, 개별 종목 단위의 시세·재무 데이터는 이 경로에 연결돼 있지 않습니다. 다른 하나는 성격입니다 — 개별 종목 매매 권유는 이 도구가 내는 판단이 아닙니다.\n\n" +
        "보유 종목을 반영하려면 좌측 자산 비중 조절기에서 해당 자산군 비중으로 넣어 주십시오. 국내주식·해외성장주 같은 자산군 단위로 들어가면 VaR·스트레스 손실에 그대로 반영됩니다.",
      sources: [] as InsightSource[],
    },
    {
      key: "tax_account",
      keywords: ["isa", "연금", "irp", "절세", "세금", "세액공제", "한도", "과세"],
      answer:
        "절세계좌는 납입 한도와 잠기는 기간을 함께 봐야 합니다. 한도만 보고 채우면 정작 필요한 시점에 꺼내지 못합니다.\n\n" +
        "ISA는 연 2,000만원·총 1억원 한도이고 의무보유는 3년입니다. 채우지 못한 한도가 다음 해로 넘어가는 구조라, 개설 후 몇 해가 지났는지에 따라 올해 넣을 수 있는 금액이 달라집니다. 순소득 200만원(서민형 400만원)까지 비과세이고 초과분은 9.9% 분리과세입니다.\n\n" +
        "연금계좌는 연금저축·IRP 합산 900만원까지 세액공제 대상이며, 연금저축 단독으로는 600만원이 상한입니다. 900만원을 전부 연금저축에 넣으면 600만원까지만 공제되므로 나머지는 IRP로 보내야 합니다. 공제율은 총급여 5,500만원(종합소득금액 4,500만원)을 경계로 16.5%와 13.2%로 갈립니다.\n\n" +
        "연금계좌는 만 55세까지 잠깁니다. 근시일에 쓸 자금이 있으면 한도를 채우는 것이 답이 아닙니다 — 좌측 절세 최적화의 납입 배분에서 두 값이 어떻게 맞물리는지 확인하십시오.",
      sources: [
        { title: "nts taxguide 2026 vol1 (tax_law)", date: "2026-01-01" },
        { title: "nts taxguide 2026 vol2 (tax_law)", date: "2026-01-01" },
      ] as InsightSource[],
    },
    {
      key: "house_view",
      // "전망" 은 넣지 않는다 — "기준금리 전망" 이 거시 대신 여기로 잡힌다.
      keywords: ["업종", "반도체", "하우스뷰", "섹터", "주식 비중", "자산배분"],
      answer:
        "하우스뷰 기준으로는 위험자산 비중 상한과 단일 자산 집중도를 먼저 봅니다.\n\n" +
        "국내주식 비중이 큰 포트폴리오는 업종 사이클과 지수 변동이 같은 방향으로 겹칩니다. 특정 업종 전망이 좋더라도 그 노출이 이미 단일 위험자산 상한을 넘고 있으면, 전망의 방향과 무관하게 비중 자체가 리스크 요인이 됩니다. 좌측 리포트의 IPS 충돌 검사가 이 조건을 확인합니다.\n\n" +
        "분산 측면에서는 해외배당주·채권·대체자산이 국내주식과 다른 방향으로 움직이는 구간을 확보하는 것이 우선입니다. 업종 판단으로 비중을 키우는 것보다, 그 판단이 틀렸을 때의 낙폭을 IPS 허용 범위 안에 두는 것이 먼저입니다.\n\n" +
        "구체적인 업종 의견은 인용된 하우스뷰 원문을 확인하십시오. 이 화면은 그 의견을 자산군 비중으로 옮겼을 때의 리스크만 계산합니다.",
      sources: [
        { title: "samsung equity 202511 (house_view)", date: "2025-11-01" },
        { title: "samsung equity 202510 (house_view)", date: "2025-10-01" },
      ] as InsightSource[],
    },
    {
      key: "macro",
      keywords: ["금리", "환율", "연준", "fomc", "한국은행", "통화정책", "인플레", "달러"],
      answer:
        "금리와 환율은 포트폴리오의 서로 다른 자리에 닿습니다.\n\n" +
        "금리는 채권 듀레이션에 먼저 반영됩니다. 인하 기대가 뒤로 밀리는 구간에서는 장기채의 가격 변동이 커지므로, 만기가 정해진 자금은 듀레이션을 짧게 유지하는 편이 목표 시점의 불확실성을 줄입니다.\n\n" +
        "환율은 해외자산의 비헤지 비중에 걸립니다. 원화 강세 구간에서는 해외자산의 원화 환산 수익이 깎이므로, 비헤지 비중이 클수록 기초자산이 올라도 손에 남는 금액이 줄어듭니다. 헤지 전환은 비용이 붙으므로 목표 시점과 비중을 함께 보고 정해야 합니다.\n\n" +
        "두 충격이 동시에 온 경우의 손실은 자세히 리포트의 스트레스 시나리오에서 확인할 수 있습니다. 시나리오별 손실액은 엔진 상수와 같은 수식으로 계산됩니다.",
      sources: [
        { title: "bok mpd 202605 (macro)", date: "2026-05-01" },
        { title: "fed fomc 202604 (macro)", date: "2026-04-01" },
      ] as InsightSource[],
    },
  ],
};
