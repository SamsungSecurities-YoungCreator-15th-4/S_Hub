/**
 * 화면 골격용 더미 데이터 모음.
 *
 * ⚠️ 모든 수치는 HTML 시안·정본 디자인에서 그대로 옮긴 자리표시자다.
 *    실제 지표(샤프지수·MDD·세금 등)는 백엔드(yfinance + 세법 로직) 연동 후
 *    이 파일을 API 응답으로 대체한다. 임의 수치를 실데이터처럼 쓰지 말 것.
 */

import type { CalcUnitWeights } from "./assetMapping";
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
    // 시연 기준 고객. 33세 직장인 6년차 — 은퇴자산을 쌓으면서 3년 뒤 전세
    // 보증금 인상분도 마련해야 하는, 절세계좌 lock-up 과 정면으로 부딪히는 사례다.
    id: "cust-001",
    name: "김성삼",
    grade: "일반",
    pbCode: "PB-100482",
    aumLabel: "운용자산 1억원",
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
  },
  {
    id: "cust-002",
    name: "이사조",
    grade: "VVIP",
    pbCode: "PB-100483",
    aumLabel: "운용자산 52억원",
    aumEokwon: 52,
    isaUsedManwon: 800, // ISA 여유 있음
    pensionUsedManwon: 600,
    realizedLossManwon: 3200,
    marginalRatePct: 49.5,
    age: 33,
    horizonYears: 3, // 변경: 1년 → 3년
    nearTermNeedManwon: 0, // 창업 대금(금액 미상) — 추후 입력
    nearTermNeedYears: null,
    isaOpened: true,
  },
  {
    id: "cust-003",
    name: "박기업",
    grade: "VVIP",
    pbCode: "PB-100484",
    aumLabel: "운용자산 31억원",
    aumEokwon: 31,
    isaUsedManwon: 0, // ISA 미납입
    pensionUsedManwon: 300,
    realizedLossManwon: 0,
    marginalRatePct: 38.5,
    age: 62,
    horizonYears: 10, // 초장기(10년 이상)
    nearTermNeedManwon: 0, // 법인 운전자금은 별도 관리
    nearTermNeedYears: null,
    isaOpened: true,
  },
];

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
  baseLabel: "기준 : 포트폴리오 A · 18억",
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
};
