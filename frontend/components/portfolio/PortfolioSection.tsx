"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import ReportDetailModal from "@/components/dashboard/ReportDetailModal";
import AssetDonut from "@/components/portfolio/AssetDonut";
import {
  BACKEND_ASSET_COLORS,
  toCalcUnitAllocation,
} from "@/lib/assetMapping";
import { type Portfolio, type PortfolioMetrics } from "@/lib/mockData";
import { pctOfAumLabel } from "@/lib/formatKrw";
import { formatSharpe } from "@/lib/sharpe";
import { useDashboardStore } from "@/lib/store";
import HelpTooltip from "@/components/common/HelpTooltip";

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

/** 중앙 상단: 현재 / 포트폴리오 A / 포트폴리오 B — 카드 클릭으로 선택 */
export default function PortfolioSection() {
  const {
    selectedPortfolioId,
    selectPortfolio,
    portfolios,
    portfolioSource,
    portfolioNote,
    analyzing,
  } = useDashboardStore();
  const [detailOpen, setDetailOpen] = useState(false);

  // 분석 전(=빈 상태)에는 볼 리포트가 없으므로 자세히도 내보내지 않는다.
  const isEmpty =
    portfolioSource === "fallback" && portfolioNote === undefined && !analyzing;

  const asOf = new Date()
    .toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replace(/\. /g, ".")
    .replace(/\.$/, "");

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
        <div className="flex items-center gap-2">
          {portfolioSource !== "fallback" && (
            <span
              className="text-[11px] font-semibold text-muted-foreground"
              suppressHydrationWarning
            >
              {asOf} 기준
            </span>
          )}
          {!isEmpty && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDetailOpen(true)}
              className="h-7 text-[12px] font-bold"
            >
              자세히
            </Button>
          )}
        </div>
      </div>

      {isEmpty ? (
        <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[14px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
          {portfolios.map((pf) => (
            <PortfolioCard
              key={pf.id}
              pf={pf}
              isSelected={pf.id !== "current" && selectedPortfolioId === pf.id}
              onSelect={() => selectPortfolio(pf.id)}
              selectable={pf.id !== "current"}
            />
          ))}
        </div>
      )}

      {detailOpen && <ReportDetailModal onClose={() => setDetailOpen(false)} />}
    </section>
  );
}

function PortfolioCard({
  pf,
  isSelected,
  onSelect,
  selectable,
}: {
  pf: Portfolio;
  isSelected: boolean;
  onSelect: () => void;
  selectable: boolean;
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

  const portfolioType =
    pf.id === "a" ? "안정추구형" : pf.id === "b" ? "수익추구형" : null;

  return (
    <Card
      tabIndex={selectable ? 0 : undefined}
      className={`gap-0 p-3 transition-shadow focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand ${
        selectable ? "cursor-pointer" : "cursor-default"
      } ${
        isSelected && selectable
          ? "border-2 border-brand shadow-[0_6px_20px_rgba(0,100,255,0.14)]"
          : selectable
            ? "hover:shadow-md"
            : ""
      }`}
      onClick={selectable ? onSelect : undefined}
      onKeyDown={
        selectable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect();
              }
            }
          : undefined
      }
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[13px] font-extrabold">
          {pf.name}
          {portfolioType && (
            <span className="rounded-md bg-[#DCE9FF] px-1.5 py-0.5 text-[9px] font-extrabold text-brand-dark">
              {portfolioType}
            </span>
          )}
        </div>
      </div>

      <div className="flex min-h-72 items-stretch gap-2.5">
        <div className="flex flex-1 flex-col items-center">
          <AssetDonut allocation={allocation} />
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
      <div className="mt-2.5 grid grid-cols-3 gap-px overflow-hidden rounded-lg bg-muted">
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
        <Metric k="샤프지수" v={formatSharpe(m.sharpe)} />
      </div>
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
          className={`mt-1 text-[14px] font-extrabold leading-none tabular-nums ${toneCls}`}
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
          <div className={`mt-0.5 text-[12px] font-bold tabular-nums ${toneCls}`}>
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
