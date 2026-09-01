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
} from "../../mockData";
import type { CreatedClient, CreateClientResult, ListedClient } from "../../api/clients";
import type { ConsultationSummaryItem } from "../../api/consultations";
import type { InsightData } from "../../api/rag";
import type { PortfolioCalcData, StressMetricsResult } from "../../api/portfolio";
import type { SttConsultationData } from "../../api/stt";
import type { TaxInsightData } from "../../api/tax";
import type { Portfolio } from "../../mockData";

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
export function demoInsight(): InsightData {
  return {
    answer: INSIGHT.defaultAnswer,
    summary: INSIGHT.defaultAnswer.split("\n\n")[0] ?? INSIGHT.defaultAnswer,
    citations: INSIGHT.sources.map((s) => ({ title: s.title, date: s.date })),
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

/** 포트폴리오 계산 결과. 기존 폴백과 같은 형태 — 상관행렬·세금 맵은 백엔드 산출물이라 null. */
export function demoPortfolioCalc(): PortfolioCalcData {
  return {
    portfolios: PORTFOLIOS,
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
  return { status: "fallback", data, note: "시연 고정 데이터 — DB에 저장되지 않습니다." };
}

/**
 * 고객 목록. 빈 배열을 돌려 화면이 mockData 의 CUSTOMERS 초기값을 그대로 쓰게 한다.
 * (Sidebar 는 목록이 비면 hydrate 를 건너뛴다.)
 */
export function demoClientList(): ListedClient[] {
  return [];
}

/** 지난 상담 목록. mockData 의 PAST_CONSULTATIONS 를 목록 타입으로 옮긴다. */
export function demoConsultationList(): ConsultationSummaryItem[] {
  return PAST_CONSULTATIONS.map((c) => ({
    consultationId: c.id,
    transcriptTitle: c.title,
    consultationDate: "",
  }));
}
