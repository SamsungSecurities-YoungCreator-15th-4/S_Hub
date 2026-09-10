/**
 * 시연 고정 데이터 — lib/api/ 의 백엔드 호출 함수용.
 *
 * ⚠️ 값의 출처: 새로 만든 숫자가 하나도 없다. 전부 `lib/mockData.ts` 에서 가져온다.
 * 이 파일은 "mockData 를 각 API 함수의 반환 타입에 맞춰 조립하는" 어댑터일 뿐이다.
 * 시연 시나리오 수치가 확정되면 `mockData.ts` 만 고치면 여기도 자동으로 따라간다.
 *
 * 각 모듈의 기존 폴백 빌더(mockConsultation 등)도 이 파일을 재사용하도록 바꿨다.
 * 값이 두 벌로 갈라지면 "데모 모드에서 본 화면"과 "백엔드 죽었을 때 화면"이
 * 달라져 시연 중 원인 판별이 불가능해진다.
 *
 * import 방향은 항상 fixtures → mockData 다. 반대로 두면 순환 참조가 된다.
 */
import {
  CONSULT_LOG,
  INSIGHT,
  IPS_DEFAULT,
  PAST_CONSULTATIONS,
  PORTFOLIOS,
  TAX_EFFECT,
  withCurrentWeights,
} from "../../mockData";
import type { CreatedClient, CreateClientResult, ListedClient } from "../../api/clients";
import type { ConsultationSummaryItem } from "../../api/consultations";
import type { InsightData } from "../../api/rag";
import type { PortfolioCalcData, StressMetricsResult } from "../../api/portfolio";
import type { SttConsultationData } from "../../api/stt";
import type { TaxInsightData } from "../../api/tax";
import type { NearTermNeedKind, Portfolio } from "../../mockData";
import type { CurrentWeightsInput } from "../../assetMapping";

/** 상담 1건(전사 + IPS). stt.ts 의 업로드·상세조회 양쪽이 쓴다. */
export function demoConsultation(): SttConsultationData {
  return {
    consultationId: "",
    transcript: CONSULT_LOG,
    ips: {
      goal: IPS_DEFAULT.goal,
      returnPct: IPS_DEFAULT.returnPct,
      risk: IPS_DEFAULT.risk,
      timeYears: IPS_DEFAULT.timeYears,
      tax: IPS_DEFAULT.tax,
      liquidity: IPS_DEFAULT.liquidity,
      legal: IPS_DEFAULT.legal,
      unique: IPS_DEFAULT.unique,
    },
    transcriptTitle: "상담 기록",
    consultationDate: "",
  };
}

/** RAG·DART 인사이트. question 은 호출부가 채운다. */
/**
 * 질문 성격에 맞는 응답을 고른다. 맞는 것이 없으면 기본(현재 포트폴리오 분석).
 * `key` 를 주면 그 응답을 직접 고른다 — 호출부가 질문의 성격을 이미 아는 경우다.
 *
 * 질문을 무시하고 늘 같은 답을 내면 화면에서 RAG 가 질문을 읽는지 확인할 수 없다.
 * 응답·인용은 전부 `mockData.INSIGHT` 에 있다 — 여기서 만들지 않는다.
 */
export function demoInsight(query?: string, key?: string): InsightData {
  const q = (query ?? "").toLowerCase();
  const hit = key
    ? INSIGHT.scenarios.find((sc) => sc.key === key)
    : q
      ? INSIGHT.scenarios.find((sc) => sc.keywords.some((k) => q.includes(k)))
      : undefined;

  const answer = hit?.answer ?? INSIGHT.defaultAnswer;
  const sources = hit?.sources ?? INSIGHT.sources;
  return {
    answer,
    summary: answer.split("\n\n")[0] ?? answer,
    citations: sources.map((s) => ({ title: s.title, date: s.date })),
  };
}

/** 절세 요약 문구. 폴백 문구와 달리 "연결 실패" 를 말하지 않는다 — 실패가 아니라 선택이므로. */
export function demoTaxSummary(portfolioName: string): TaxInsightData {
  return {
    summary: [
      `[절세 요약 · ${portfolioName}]`,
      `- 전략 적용 시 연간 약 ${TAX_EFFECT.annualSavingManwon.toLocaleString()}만원의 세금 절감이 추정됩니다.`,
      `- 세후수익률(추정): ${TAX_EFFECT.afterTaxReturn.from} → ${TAX_EFFECT.afterTaxReturn.to}`,
    ].join("\n"),
  };
}

/**
 * 납입 배분 화면의 근거 문장 — **LLM 자리의 시연 대역**이다.
 *
 * 목표 모양: 상담 전사와 IPS 를 읽어 "왜 이 시점에 이 금액이 필요한지"와 "그래서
 * 무엇을 양보할 수 없는지"를 문장으로 만든다. 지금은 그 호출을 붙일 수 없어 고정
 * 문구로 대신하며, demoTaxSummary·demoInsight 와 같은 자리다.
 *
 * **목적에 따라 문장이 갈린다.** 금액과 시점만으로는 "못 미루는 돈"이라고 말할 수
 * 없다 — 전세 보증금은 계약일에 묶이지만 창업 자금은 시점을 조절할 여지가 있어서,
 * 같은 2,000만원이라도 조언이 달라진다. 실제 LLM 이 그렇게 답할 것이므로 대역도
 * 하나로 뭉뚱그리지 않는다. 목적을 모르면 시점 경직성을 단정하지 않는다.
 *
 * 배분 슬라이더를 따라 바뀌지 않는다. 이 문장이 설명하는 것은 지금의 배분이 아니라
 * **바꿀 수 없는 제약**이고, 실제 LLM 도 슬라이더를 움직일 때마다 다시 부르지 않는다.
 *
 * 엔드포인트가 생기면 이 함수를 fetch 로 갈아 끼우고 호출부는 그대로 둔다.
 */
export function demoContributionRationale(
  need: {
    manwon: number;
    years: number;
    kind?: NearTermNeedKind;
    label?: string;
  },
  pensionLockupYears: number,
): string {
  const { manwon, years, kind, label } = need;
  if (manwon <= 0 || years <= 0) return "";

  const amount = `${manwon.toLocaleString()}만원`;
  const locked = `연금에 넣어 ${pensionLockupYears}년 묶으면 그 시점에 손댈 수 없습니다.`;

  switch (kind) {
    case "lease":
      return (
        `${years}년 뒤 전세 재계약은 날짜가 정해진 지출이라 ${amount}은 미루거나 줄일 수 ` +
        `있는 돈이 아닙니다. 은퇴자산은 시점을 넓게 두고 쌓을 수 있지만 이 돈은 그렇지 ` +
        `않습니다: ${locked}`
      );
    case "homePurchase":
      return (
        `주택 계약금은 계약일과 대출 실행일에 함께 묶여, ${years}년 뒤 ${amount}이 ` +
        `현금으로 있어야 합니다. 하루 늦으면 계약 자체가 흔들립니다: ${locked}`
      );
    case "startup":
      return (
        `창업 자금은 시점을 다소 조절할 수 있어 전세나 계약금만큼 경직되지는 않습니다. ` +
        `다만 ${years}년을 크게 넘기면 준비해 온 기회를 놓치는 비용이 생깁니다: ${locked}`
      );
    case "education":
      return (
        `학자금은 학기 일정에 묶여 ${years}년 뒤 ${amount}이 필요한 시점을 미룰 수 ` +
        `없습니다. 한 학기를 건너뛰는 선택지가 사실상 없기 때문입니다: ${locked}`
      );
    default:
      // 목적을 모르면 "못 미루는 돈"이라고 단정하지 않는다. 금액과 시점만 말한다.
      return (
        `${years}년 뒤 ${label ? `${label} ` : ""}${amount}이 필요합니다. 시점을 미룰 수 ` +
        `있는 지출인지 상담에서 확인해야 합니다: ${locked}`
      );
  }
}

/** 포트폴리오 계산 결과. 기존 폴백과 같은 형태 — 상관행렬·세금 맵은 백엔드 산출물이라 null. */
export function demoPortfolioCalc(
  currentWeights?: CurrentWeightsInput,
): PortfolioCalcData {
  return {
    portfolios: withCurrentWeights(PORTFOLIOS, currentWeights),
    calculationSessionId: "",
    correlationHeatmap: null,
    portfolioTax: null,
    taxOptimizer: null,
  };
}

/** 스트레스 지표. 충격 적용 전 포트폴리오를 그대로 돌려준다(백엔드 재계산 없음). */
export function demoStressMetrics(currentPortfolios: Portfolio[]): StressMetricsResult {
  return {
    portfolios: currentPortfolios.length > 0 ? currentPortfolios : PORTFOLIOS,
    stressTax: null,
    correlationHeatmap: null,
    portfolioTax: null,
    taxOptimizer: null,
  };
}

export function demoStressTestPortfolios(): Portfolio[] {
  return PORTFOLIOS;
}

/**
 * 신규 고객 등록. DB 미저장이므로 status 는 "fallback" 이다 —
 * 호출부(Sidebar)가 `status === "live"` 로 영속 여부를 판단하는데,
 * 데모에서 저장됐다고 말하면 거짓이 된다. clientId 는 빈 문자열이고
 * 호출부가 로컬 id 를 만들어 붙인다.
 */
export function demoCreatedClient(name: string, aumEokwon: number): CreateClientResult {
  const data: CreatedClient = { clientId: "", name, aumEokwon };
  return { status: "fallback", data, note: "시연 고정 데이터: DB에 저장되지 않습니다." };
}

/**
 * 고객 목록. 빈 배열을 돌려 화면이 mockData 의 CUSTOMERS 초기값을 그대로 쓰게 한다.
 * (Sidebar 는 목록이 비면 hydrate 를 건너뛴다.)
 */
export function demoClientList(): ListedClient[] {
  return [];
}

/**
 * 지난 상담 목록. mockData 의 PAST_CONSULTATIONS 를 목록 타입으로 옮긴다.
 *
 * 고객 이름으로 거른다 — 거르지 않으면 다른 고객의 상담 기록이 목록에 뜨고,
 * 상담 전 고객 화면에도 이름이 남는다.
 */
export function demoConsultationList(
  customerName?: string,
): ConsultationSummaryItem[] {
  const rows = customerName
    ? PAST_CONSULTATIONS.filter((c) => c.title.includes(customerName))
    : PAST_CONSULTATIONS;
  return rows.map((c) => ({
    consultationId: c.id,
    transcriptTitle: c.title,
    consultationDate: "",
  }));
}
