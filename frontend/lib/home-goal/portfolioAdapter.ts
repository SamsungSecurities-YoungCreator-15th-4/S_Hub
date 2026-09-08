import type { Portfolio } from "../mockData";
import type { DataSource } from "../api/result";
import { calculateHomeGoal } from "./calculateHomeGoal";
import { HOME_GOAL_FIELDS, type HomeGoalDraft, type HomeGoalInput, type HomeGoalResult } from "./types";

export interface HomeGoalComparison {
  id: Portfolio["id"];
  name: string;
  input: HomeGoalInput | null;
  result: HomeGoalResult | null;
  error: string | null;
  returnPct: number | null;
  stressDeltaPct: number | null;
}

export function readHomeGoalDraft(draft: HomeGoalDraft): Omit<HomeGoalInput, "portfolioExpectedReturn"> {
  const values = {} as Omit<HomeGoalInput, "portfolioExpectedReturn">;
  for (const { key, label, scale } of HOME_GOAL_FIELDS) {
    if (!draft[key].trim()) throw new Error(`${label}을 입력해 주세요.`);
    const value = Number(draft[key]);
    if (!Number.isFinite(value)) throw new Error(`${label}에 유효한 숫자를 입력해 주세요.`);
    values[key] = value * scale;
  }
  return values;
}

export function compareHomeGoalPortfolios(
  draft: HomeGoalDraft, basePortfolios: Portfolio[], stressedPortfolios: Portfolio[],
  source: DataSource, isStressMode: boolean,
): HomeGoalComparison[] {
  return basePortfolios.map((portfolio) => {
    const available = (source === "live" || source === "demo") &&
      portfolio.metrics.expectedReturnAvailable !== false && Number.isFinite(portfolio.metrics.expectedReturnPct);
    const stressed = stressedPortfolios.find((p) => p.id === portfolio.id);
    // 현재 시연 fixture는 충격을 계산하지 않고 기준 포트폴리오를 그대로 반환한다.
    const stressAvailable = source === "live" && available && isStressMode && stressed?.metrics.expectedReturnAvailable !== false &&
      stressed != null && Number.isFinite(stressed.metrics.expectedReturnPct);
    const row: HomeGoalComparison = {
      id: portfolio.id, name: portfolio.id === "current" ? "현재" : `포트폴리오 ${portfolio.id.toUpperCase()}`,
      input: null, result: null, error: null,
      returnPct: available ? portfolio.metrics.expectedReturnPct : null,
      stressDeltaPct: stressAvailable ? stressed.metrics.expectedReturnPct - portfolio.metrics.expectedReturnPct : null,
    };
    try {
      const values = readHomeGoalDraft(draft);
      if (!available) throw new Error("포트폴리오 분석 완료 후 기대수익률을 연결합니다.");
      row.input = { ...values, portfolioExpectedReturn: portfolio.metrics.expectedReturnPct / 100 };
      row.result = calculateHomeGoal(row.input);
    } catch (error) {
      row.error = error instanceof Error ? error.message : "계산 입력을 확인해 주세요.";
    }
    return row;
  });
}

/** 수익률 변화(%p)는 원금 손실률이 아니다. 수치형 한도 계약이 없으므로 추천하지 않는다. */
export function describeHomeGoalComparison(rows: HomeGoalComparison[]): string {
  const valid = rows.filter((row) => row.result);
  if (!valid.length) return "목표 입력과 포트폴리오 분석을 완료하면 현재·A·B의 목표 자금을 비교할 수 있습니다.";
  const lowestGap = Math.min(...valid.map((row) => row.result!.gap));
  const best = valid.filter((row) => Math.abs(row.result!.gap - lowestGap) < 1).map((row) => row.name).join("·");
  return `${best}의 계산상 Gap이 가장 작습니다. 고객별 수치형 손실허용한도와 동일 기준의 스트레스 손실률이 없어 적합성 판단은 보류합니다. PB가 위험과 목표를 함께 검토해 주세요.`;
}

export function formatHomeGoalMonths(months: number): string {
  if (months === 0) return "지금";
  const years = Math.floor(months / 12);
  const rest = months % 12;
  return [years ? `${years}년` : "", rest ? `${rest}개월` : ""].filter(Boolean).join(" ");
}
