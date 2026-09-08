import {
  BACKTEST_SERIES,
  PORTFOLIOS,
  TAX_ADVICE,
  TAX_EFFECT,
  TAX_THRESHOLD,
  type Customer,
} from "@/lib/mockData";
import { pctOfAumLabel } from "@/lib/formatKrw";
import type { IpsState } from "@/lib/store";

type ScenarioState = { ratePct: number; fxKrw: number };

export interface DashboardInsightContextInput {
  selectedCustomer?: Customer;
  selectedPortfolioId: string;
  ips: IpsState;
  scenario: ScenarioState;
  liveBase: ScenarioState;
  otherIncomeManwon: number;
}

export type DashboardInsightContext = Record<string, unknown>;

function pctToRatio(value: number): number {
  return value / 100;
}

function parseNumber(label: string | undefined | null): number | null {
  if (typeof label !== "string") return null;
  const value = Number.parseFloat(label.replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(value) ? value : null;
}

function parsePercentToRatio(label: string | undefined | null): number | null {
  const value = parseNumber(label);
  return value == null ? null : value / 100;
}

function parseManwonLabelToWon(label: string | undefined | null): number | null {
  const value = parseNumber(label);
  return value == null ? null : value * 10_000;
}

/**
 * AI 인사이트에 넘길 포트폴리오 요약.
 *
 * 원화 병기 라벨은 화면(PortfolioSection)과 같은 규칙으로 만든다 — 백엔드
 * 실계산 값이 있으면 그것을, 없으면 비율 × 고객 총자산으로 계산한다.
 * 폴백이 없으면 화면에는 금액이 보이는데 AI 에게는 undefined 가 가서,
 * 답변이 금액을 쓰지 못한다.
 */
function toPortfolioSummary(
  portfolio: (typeof PORTFOLIOS)[number],
  aumEokwon: number,
) {
  const metrics = portfolio.metrics;
  return {
    api_key: portfolio.id,
    name: portfolio.name,
    badge: portfolio.badge,
    weights: portfolio.weights,
    metrics: {
      expected_return: pctToRatio(metrics.expectedReturnPct),
      volatility: pctToRatio(metrics.volatilityPct),
      sharpe_ratio: metrics.sharpe,
      sortino_ratio: metrics.sortino,
      mdd: -pctToRatio(metrics.mddPct),
      after_tax_return: pctToRatio(metrics.afterTaxReturnPct),
      volatility_amount_label:
        metrics.volatilityAmountLabel ??
        pctOfAumLabel(metrics.volatilityPct, aumEokwon, "±"),
      mdd_amount_label:
        metrics.mddAmountLabel ??
        pctOfAumLabel(metrics.mddPct, aumEokwon, "-"),
      after_tax_amount_label:
        metrics.afterTaxAmountLabel ??
        pctOfAumLabel(
          metrics.afterTaxReturnPct,
          aumEokwon,
          metrics.afterTaxReturnPct < 0 ? "-" : "+",
        ),
    },
  };
}

function portfolioContextKey(id: string): "current" | "portfolio_a" | "portfolio_b" {
  if (id === "current") return "current";
  if (id === "b") return "portfolio_b";
  return "portfolio_a";
}

export function buildDashboardInsightContext({
  selectedCustomer,
  selectedPortfolioId,
  ips,
  scenario,
  liveBase,
  otherIncomeManwon,
}: DashboardInsightContextInput): DashboardInsightContext {
  const selectedPortfolio =
    PORTFOLIOS.find((portfolio) => portfolio.id === selectedPortfolioId) ??
    PORTFOLIOS.find((portfolio) => portfolio.id === "a") ??
    PORTFOLIOS[0];
  const current = PORTFOLIOS.find((portfolio) => portfolio.id === "current");
  const portfolioA = PORTFOLIOS.find((portfolio) => portfolio.id === "a");
  const portfolioB = PORTFOLIOS.find((portfolio) => portfolio.id === "b");
  const selectedPortfolioKey = selectedPortfolio?.id ?? "a";
  // 원화 병기 폴백의 기준. 고객이 없으면 0 이라 pctOfAumLabel 이 undefined 를 돌려준다.
  const aumEokwon = selectedCustomer?.aumEokwon ?? 0;

  return {
    schema_version: "dashboard_context_v1",
    selected_customer: selectedCustomer
      ? {
          id: selectedCustomer.id,
          client_id: selectedCustomer.clientId ?? null,
          name: selectedCustomer.name,
          aum_eokwon: selectedCustomer.aumEokwon,
          marginal_rate_pct: selectedCustomer.marginalRatePct,
          age: selectedCustomer.age,
          horizon_years: selectedCustomer.horizonYears,
          near_term_need_manwon: selectedCustomer.nearTermNeedManwon,
          near_term_need_years: selectedCustomer.nearTermNeedYears,
        }
      : null,
    selected_portfolio: {
      id: selectedPortfolio?.id ?? "",
      name: selectedPortfolio?.name ?? "",
    },
    ips: {
      goal: ips.goal,
      target_return_pct: ips.returnPct,
      risk_profile: ips.risk,
      time_years: ips.timeYears,
      liquidity: ips.liquidity,
      tax: ips.tax,
      legal: ips.legal,
      unique: ips.unique,
    },
    benchmark_choice: "all",
    current: current ? toPortfolioSummary(current, aumEokwon) : null,
    portfolio_a: portfolioA ? toPortfolioSummary(portfolioA, aumEokwon) : null,
    portfolio_b: portfolioB ? toPortfolioSummary(portfolioB, aumEokwon) : null,
    backtest: {
      period: "최근 5년",
      index_base: 100,
      series: BACKTEST_SERIES,
    },
    stress: {
      live_base: liveBase,
      selected_scenario: scenario,
      deltas: {
        rate_pct: scenario.ratePct - liveBase.ratePct,
        fx_krw: scenario.fxKrw - liveBase.fxKrw,
      },
    },
    tax_optimizer: {
      selected_portfolio_key: portfolioContextKey(selectedPortfolioKey),
      current: {
        headline: {
          annual_tax_saving: TAX_EFFECT.annualSavingManwon * 10_000,
          after_tax_return_before: parsePercentToRatio(
            TAX_EFFECT.afterTaxReturn.from,
          ),
          after_tax_return_after: parsePercentToRatio(
            TAX_EFFECT.afterTaxReturn.to,
          ),
          tax_amount_before: parseManwonLabelToWon(TAX_EFFECT.effectiveTax.from),
          tax_amount_after: parseManwonLabelToWon(TAX_EFFECT.effectiveTax.to),
        },
      },
      effect: TAX_EFFECT,
      threshold: {
        ...TAX_THRESHOLD,
        other_income_manwon: otherIncomeManwon,
      },
      advice_cards: TAX_ADVICE.cards,
      total_label: TAX_ADVICE.totalLabel,
      total_saving: TAX_ADVICE.totalSaving,
    },
  };
}
