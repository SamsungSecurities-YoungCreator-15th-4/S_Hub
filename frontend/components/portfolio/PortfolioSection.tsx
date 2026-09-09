"use client";

import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import AssetDonut from "@/components/portfolio/AssetDonut";
import {
  BACKEND_ASSET_COLORS,
  CALC_UNITS,
  toCalcUnitAllocation,
} from "@/lib/assetMapping";
import { type Portfolio, type PortfolioMetrics } from "@/lib/mockData";
import { pctOfAumLabel } from "@/lib/formatKrw";
import { formatSharpe } from "@/lib/sharpe";
import { useDashboardStore } from "@/lib/store";
import HelpTooltip from "@/components/common/HelpTooltip";
import AsOfNote from "@/components/common/AsOfNote";

const METRIC_HELP: Record<string, string> = {
  기대수익률:
    "연간 기대 수익률입니다. 과거 수익률과 자산별 위험 프리미엄을 바탕으로 추정한 값으로, 실제 수익을 보장하지 않습니다.",
  샤프지수:
    "위험 1단위당 초과 수익을 나타냅니다. 값이 클수록 위험 대비 수익이 높으며, 1.0 이상이면 우수한 수준으로 평가합니다.",
  소르티노:
    "하락 위험(손실 변동성)만을 고려한 위험 조정 수익률입니다. 샤프지수보다 손실 가능성을 더 엄밀하게 반영합니다.",
  세후수익률:
    "세금 효과를 반영한 실질 수익률입니다. ISA·연금 계좌 활용 등 절세 전략 적용 시 수치가 높아집니다.",
  변동성:
    "포트폴리오 수익률의 표준편차로 측정한 위험 수준입니다. 값이 낮을수록 수익이 안정적입니다.",
  MDD: "분석 기간 중 고점 대비 최대 하락폭(Maximum Drawdown)입니다. 최악의 시나리오에서의 손실 규모를 나타냅니다.",
};

/**
 * 카드가 그릴 수 있는 포트폴리오.
 *
 * Portfolio.id 는 "current"|"a"|"b" 로 고정돼 있고 세금·PDF·인사이트가 그 전제로
 * 읽는다. 화면에만 존재하는 "custom" 을 그 유니온에 넣으면 그쪽들이 오류 없이
 * 조용히 폴백하므로, 카드 쪽에서만 id 를 넓혀 받는다.
 */
type CardPortfolio = Omit<Portfolio, "id"> & { id: string };

/** 제안 카드 세그먼트 라벨. 두 안은 같은 축의 양끝이라 성향 이름으로 부른다. */
const PROPOSAL_LABEL: Record<string, string> = {
  a: "안정추구",
  b: "수익추구",
};

/** 중앙 상단: 현재(1/3) + 제안(2/3, 세그먼트 전환) */
export default function PortfolioSection() {
  const {
    selectedPortfolioId,
    selectPortfolio,
    customWeightsInput,
    weightsEditTarget,
    setWeightsEditTarget,
    portfolios,
    portfolioSource,
    portfolioNote,
    analyzing,
  } = useDashboardStore();

  const current = portfolios.find((pf) => pf.id === "current");
  const proposals = portfolios.filter((pf) => pf.id !== "current");
  const selectedProposal =
    proposals.find((pf) => pf.id === selectedPortfolioId) ?? proposals[0];
  const isCustom = weightsEditTarget === "custom";

  /**
   * 사용자 정의 안. 비중은 사람이 직접 조정한 값을 그대로 쓴다.
   * 지표는 비워 둔다 — 임의 비중의 기대수익률·변동성·MDD 를 산출하려면 자산군별
   * 수익률·공분산이 필요한데 프론트에 그 데이터가 없다. 근거 없는 숫자를 지어
   * 넣지 않는다(lib/sharpe.ts 가 같은 이유로 샤프만 계산으로 승격했다).
   */
  const customBase = selectedProposal ?? proposals[0];
  const customPortfolio: CardPortfolio | undefined = isCustom && customBase
    ? {
        ...customBase,
        // 백엔드 원본 allocation 을 지운다 — 도넛이 사람이 조정한 weights 를 쓰게 한다.
        allocation: undefined,
        id: "custom",
        name: "사용자 정의",
        weights: CALC_UNITS.reduce(
          (acc, unit) => ({ ...acc, [unit.id]: customWeightsInput[unit.id] ?? 0 }),
          {} as Portfolio["weights"],
        ),
      }
    : undefined;

  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">포트폴리오 대시보드</h2>
          {analyzing ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              분석중...
            </div>
          ) : portfolioSource === "live" ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
              <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
              연동 완료
            </div>
          ) : null}
        </div>
        {portfolioSource !== "fallback" && <AsOfNote />}
      </div>

      {portfolioSource === "fallback" &&
      portfolioNote === undefined &&
      !analyzing ? (
        <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[14px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
          {current && (
            <PortfolioCard
              pf={current}
              header={
                <span className="text-[13px] font-extrabold">
                  {current.name}
                </span>
              }
            />
          )}
          {/*
            제안 A·B 를 한 카드로 합치고 세그먼트로 전환한다. 두 안은 같은 축
            (안정 ↔ 수익)의 양끝이라 나란히 두는 것보다 하나를 바꿔 보는 편이
            비교가 된다. 폭은 두 카드가 쓰던 만큼(2/3)을 그대로 쓴다.
          */}
          {(customPortfolio ?? selectedProposal) && (
            <PortfolioCard
              pf={(customPortfolio ?? selectedProposal)!}
              className="xl:col-span-2"
              legendCols={3}
              metricsUnavailableNote={
                isCustom
                  ? "직접 조정한 비중의 지표는 자산군별 수익률·변동성 데이터가 연결되면 계산됩니다."
                  : undefined
              }
              header={
                <div className="flex rounded-lg bg-muted p-0.5">
                  {proposals.map((pf) => {
                    const active = !isCustom && selectedProposal?.id === pf.id;
                    return (
                      <button
                        key={pf.id}
                        type="button"
                        onClick={() => {
                          setWeightsEditTarget("current");
                          selectPortfolio(pf.id);
                        }}
                        aria-pressed={active}
                        className={`rounded-md px-3 py-1 text-[11px] font-bold transition-colors ${
                          active
                            ? "bg-white text-brand-dark shadow-sm"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {PROPOSAL_LABEL[pf.id] ?? pf.name}
                      </button>
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => setWeightsEditTarget("custom")}
                    aria-pressed={isCustom}
                    className={`rounded-md px-3 py-1 text-[11px] font-bold transition-colors ${
                      isCustom
                        ? "bg-white text-brand-dark shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    사용자 정의
                  </button>
                </div>
              }
            />
          )}
        </div>
      )}
    </section>
  );
}

function PortfolioCard({
  pf,
  header,
  className,
  metricsUnavailableNote,
  legendCols,
}: {
  pf: CardPortfolio;
  /** 카드 상단 — 현재 카드는 이름, 제안 카드는 세그먼트 컨트롤이 온다. */
  header: React.ReactNode;
  className?: string;
  /** 지표를 계산할 근거가 없을 때의 안내. 있으면 지표 격자 대신 이 문장을 보여준다. */
  metricsUnavailableNote?: string;
  legendCols?: 2 | 3;
}) {
  // 지표의 원화 병기 기준. 고객 총자산이 없으면 pctOfAumLabel 이 병기를 생략한다.
  const aumEokwon = useDashboardStore(
    (s) =>
      (s.customers.find((c) => c.id === s.selectedCustomerId) ?? s.customers[0])
        ?.aumEokwon ?? 0,
  );

  // 백엔드 8개 자산군이 있으면 직접 사용, 없으면 구형 6분류 변환으로 폴백
  const allocation = pf.allocation
    ? pf.allocation
        .filter((a) => a.weight > 0)
        .map((a) => ({
          label: a.name,
          weight: a.weight,
          color: BACKEND_ASSET_COLORS[a.asset_class] ?? "#8899AA",
        }))
    : toCalcUnitAllocation(pf.weights);
  const m = pf.metrics as PortfolioMetrics & {
    afterTaxReturnRangeLabel?: string;
    mddRangeLabel?: string;
  };

  return (
    <Card className={`gap-0 p-3 ${className ?? ""}`}>
      <div className="mb-2 flex min-h-7 items-center justify-between">
        {header}
      </div>

      <div className="flex min-h-72 items-stretch gap-2.5">
        <div className="flex flex-1 flex-col items-center">
          <AssetDonut allocation={allocation} legendCols={legendCols} />
        </div>
      </div>

      {/*
        지표 순서는 "얼마나 잃을 수 있나"(윗줄) → "얼마나 벌 수 있나"(아랫줄)다.
        쓸 날이 정해진 자금을 다루는 상담에서는 기대수익보다 낙폭이 먼저 읽혀야 한다.
        소르티노는 하락 위험만으로 계산하는 지표라 윗줄에 둔다.

        원화 병기는 백엔드 실계산 값이 있으면 그것을 쓰고, 없으면
        pctOfAumLabel(비율 × 고객 총자산)로 만든다. 어느 경로든 값의 출처가
        코드에서 하나로 추적된다.
      */}
      {metricsUnavailableNote ? (
        <div className="mt-2.5 rounded-lg border border-dashed border-muted-foreground/25 bg-muted/30 px-3 py-5">
          <p className="text-center text-[12px] font-semibold leading-relaxed text-muted-foreground">
            {metricsUnavailableNote}
          </p>
        </div>
      ) : (
        <div className="mt-2.5 grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-muted">
        {/*
          2열 3행이다. 3열로 두면 좁은 "현재" 카드에서 타일이 100px 남짓이라
          "-2억 6,280만원" 같은 원화 병기가 줄바꿈으로 깨지고, 그 바람에 두 카드의
          같은 지표가 서로 다른 높이에 놓여 비교가 되지 않았다.

          행마다 성격을 맞춰 묶는다 — 얼마나 잃을 수 있나 / 위험 대비 수익 /
          얼마나 벌 수 있나. 쓸 날이 정해진 자금을 다루는 상담이라 손실이 맨 위다.
        */}
        <Metric
          k="MDD"
          v={`${m.mddPct.toFixed(1)}%`}
          rangeSub={m.mddRangeLabel}
          sub={m.mddAmountLabel ?? pctOfAumLabel(m.mddPct, aumEokwon, "-")}
          tone={m.mddPct > 0 ? "down" : undefined}
          value={m.mddPct}
        />
        <Metric
          k="변동성"
          v={`${m.volatilityPct.toFixed(2)}%`}
          sub={m.volatilityAmountLabel ?? pctOfAumLabel(m.volatilityPct, aumEokwon, "±")}
          value={m.volatilityPct}
        />
        <Metric
          k="소르티노"
          v={m.sortino != null ? m.sortino.toFixed(2) : "-"}
        />
        <Metric k="샤프지수" v={formatSharpe(m.sharpe)} />
        <Metric k="기대수익률" v={`${m.expectedReturnPct.toFixed(2)}%`} />
        <Metric
          k="세후수익률"
          v={`${Math.abs(m.afterTaxReturnPct).toFixed(1)}%`}
          rangeSub={m.afterTaxReturnRangeLabel}
          sub={
            m.afterTaxAmountLabel ??
            pctOfAumLabel(
              m.afterTaxReturnPct,
              aumEokwon,
              m.afterTaxReturnPct < 0 ? "-" : "+",
            )
          }
          tone={
            m.afterTaxReturnPct > 0
              ? "up"
              : m.afterTaxReturnPct < 0
                ? "down"
                : undefined
          }
          value={m.afterTaxReturnPct}
        />
        </div>
      )}
    </Card>
  );
}

function Metric({
  k,
  v,
  rangeSub,
  sub,
  tone,
  value,
}: {
  k: string;
  v: string;
  rangeSub?: string;
  sub?: string;
  tone?: "up" | "down";
  value?: number;
}) {
  const helpMode = useDashboardStore((s) => s.helpMode);
  const effectiveTone = value === 0 ? undefined : tone;
  const toneCls =
    effectiveTone === "up"
      ? "text-up"
      : effectiveTone === "down"
        ? "text-down"
        : "";
  const arrow =
    effectiveTone === "up" ? "▲" : effectiveTone === "down" ? "▼" : null;
  return (
    <HelpTooltip text={METRIC_HELP[k] ?? ""}>
      <div className="h-full bg-card px-2 py-1.5">
        <div
          className={`w-fit text-[12px] font-bold text-muted-foreground ${
            helpMode
              ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
              : ""
          }`}
        >
          {k}
        </div>
        {/*
          원화 금액을 먼저 읽히게 한다 — 매스 고객은 비율보다 금액으로 이해한다.
          원화 병기가 없는 지표(샤프·소르티노 등)는 비율·수치가 그대로 큰 값이 된다.
        */}
        <div
          className={`mt-1 whitespace-nowrap text-[14px] font-extrabold leading-none tabular-nums ${toneCls}`}
        >
          {/* 금액은 부호(+ · - · ±)만 달고 삼각형은 아래 비율이 가져간다. */}
          {sub ? (
            value === 0 ? (
              sub.replace(/^[+\-±]/, "")
            ) : (
              sub
            )
          ) : (
            <>
              {arrow && <span className="mr-0.5 text-[14px]">{arrow}</span>}
              {v}
            </>
          )}
        </div>
        {sub && (
          <div className={`mt-0.5 whitespace-nowrap text-[12px] font-bold tabular-nums ${toneCls}`}>
            {arrow && <span className="mr-0.5">{arrow}</span>}
            {v}
          </div>
        )}
        {rangeSub && (
          <div className="mt-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
            {rangeSub}
          </div>
        )}
      </div>
    </HelpTooltip>
  );
}
