"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/card";
import { BACKTEST_SERIES, type Portfolio } from "@/lib/mockData";
import { CALC_UNITS } from "@/lib/assetMapping";
import { adjustmentRatio } from "@/lib/viewedPortfolio";
import HelpTooltip from "@/components/common/HelpTooltip";
import { selectViewedPlanKey, useDashboardStore } from "@/lib/store";

const BACKTEST_HELP = [
  "5년 전 이 비중으로 투자했다면의 결과",
  "실제 운용 실적이 아닌 과거 시장 데이터 계산값",
];

const BENCHMARKS = ["KOSPI", "S&P500", "MSCI ACWI"] as const;
type Benchmark = (typeof BENCHMARKS)[number];

const BENCHMARK_KEY: Record<Benchmark, string> = {
  KOSPI: "kospi",
  "S&P500": "sp500",
  "MSCI ACWI": "msciAcwi",
};

/**
 * 그릴 선 — 현재와 "지금 고른 제안" 둘이다.
 *
 * 제안 카드가 세그먼트 한 장으로 합쳐져 화면에 제안이 하나씩만 보이므로,
 * 백테스트도 A·B 를 동시에 긋지 않는다. 선택한 안만 따라간다.
 */
function linesFor(proposalKey: "a" | "b", adjusted: boolean) {
  return [
    { key: "current", name: "현재", color: "#8B95A1", width: 2 },
    adjusted
      ? { key: ADJUSTED_SERIES_KEY, name: "제안 조정", color: "#003FA8", width: 2.6 }
      : { key: proposalKey, name: "제안", color: "#0064FF", width: 2.6 },
  ];
}

/** 조정안 곡선의 데이터 키. 실데이터 경로의 포트폴리오 id 와 겹치지 않는 이름이다. */
const ADJUSTED_SERIES_KEY = "adjusted";

const BENCHMARK_COLOR = "#DC2626";

const pctFmt = (v: number) => {
  if (Number.isNaN(v)) return "";
  const ret = v - 100;
  return `${ret >= 0 ? "+" : ""}${ret.toFixed(1)}%`;
};

/** 중앙 중단: 현재·제안 백테스트 선그래프 (최근 5년, 누적 수익률 표시) */
export default function BacktestChart() {
  const [benchmark, setBenchmark] = useState<Benchmark>("KOSPI");
  const helpMode = useDashboardStore((s) => s.helpMode);
  const portfolios = useDashboardStore((s) => s.portfolios);
  const portfolioSource = useDashboardStore((s) => s.portfolioSource);
  const portfolioNote = useDashboardStore((s) => s.portfolioNote);
  const analyzing = useDashboardStore((s) => s.analyzing);
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const proposedWeightsInput = useDashboardStore((s) => s.proposedWeightsInput);
  const viewedPlanKey = useDashboardStore(selectViewedPlanKey);

  const proposalKey: "a" | "b" = selectedPortfolioId === "b" ? "b" : "a";
  const isAdjusted = viewedPlanKey === "proposed";
  // 제안 카드의 선택과 같은 값을 본다 — 카드와 곡선이 다른 안을 가리키면 안 된다.
  const lines = linesFor(proposalKey, isAdjusted);

  const displayPortfolios = portfolios;

  const benchKey = BENCHMARK_KEY[benchmark];
  const hasRealData =
    portfolioSource === "live" &&
    displayPortfolios.some((p) => (p.backtest?.length ?? 0) > 0);

  // 실데이터: 포트폴리오별 date → value 맵 구성 후 날짜 기준으로 병합
  const pfByDate = new Map<string, Record<string, number>>();
  if (hasRealData) {
    for (const pf of displayPortfolios) {
      for (const pt of pf.backtest ?? []) {
        const row = pfByDate.get(pt.date) ?? {};
        row[pf.id] = pt.value;
        pfByDate.set(pt.date, row);
      }
    }
    // 벤치마크: 포트폴리오 A 기준 (세 포트폴리오 모두 동일 벤치마크 사용)
    const benchSource = displayPortfolios.find((p) => p.id === "a")?.benchmarks;
    if (benchSource) {
      const allBenchSeries: Record<string, typeof benchSource.kospi> = {
        kospi: benchSource.kospi,
        sp500: benchSource.sp500,
        msciAcwi: benchSource.msciAcwi,
      };
      for (const [key, series] of Object.entries(allBenchSeries)) {
        for (const pt of series ?? []) {
          const row = pfByDate.get(pt.date) ?? {};
          row[key] = pt.value;
          pfByDate.set(pt.date, row);
        }
      }
    }
  }

  const baseChartData: Record<string, number | string>[] = hasRealData
    ? Array.from(pfByDate.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, vals]) => ({ date, ...vals }))
    : BACKTEST_SERIES;

  /*
    조정안에는 자체 시계열이 없다. 지표와 같은 축(주식 비중으로 잰 조정 강도 t)
    으로 현재 곡선과 제안 곡선 사이를 보간해 한 줄을 만든다 — 비중을 제안보다
    공격적으로 잡으면 곡선도 제안 바깥으로 나가고, 되돌리면 현재 쪽으로 붙는다.
    실데이터가 붙으면 조정 비중으로 실제 시계열을 다시 돌려 이 보간을 걷어낸다.
  */
  const adjustBase = portfolios.find((p) => p.id === "current");
  const adjustProposal = portfolios.find((p) => p.id === proposalKey);
  const t =
    isAdjusted && adjustBase && adjustProposal
      ? adjustmentRatio(
          adjustBase,
          adjustProposal,
          CALC_UNITS.reduce(
            (acc, u) => ({ ...acc, [u.id]: proposedWeightsInput[u.id] ?? 0 }),
            {} as Portfolio["weights"],
          ),
        )
      : null;

  const chartData =
    t === null
      ? baseChartData
      : baseChartData.map((row) => {
          const cur = row.current;
          const prop = row[proposalKey];
          if (typeof cur !== "number" || typeof prop !== "number") return row;
          return { ...row, [ADJUSTED_SERIES_KEY]: cur + (prop - cur) * t };
        });

  const xKey = hasRealData ? "date" : "year";
  const xTicks = hasRealData
    ? (() => {
        // 연도가 바뀌는 첫 데이터 포인트만 틱으로 선택 — 1월 영업일 전체를 잡으면
        // 라벨이 겹치므로 연도당 정확히 하나만 표시한다.
        const ticks: string[] = [];
        let lastYear = "";
        for (const d of chartData as { date: string }[]) {
          const year = d.date.slice(0, 4);
          if (year !== lastYear) {
            ticks.push(d.date);
            lastYear = year;
          }
        }
        return ticks;
      })()
    : ["2021", "2022", "2023", "2024", "2025", "2026"];

  if (
    portfolioSource === "fallback" &&
    portfolioNote === undefined &&
    !analyzing
  ) {
    return (
      <Card className="flex min-h-[200px] items-center justify-center gap-0 p-3">
        <p className="text-[14px] font-semibold text-muted-foreground">
          분석 결과가 존재하지 않습니다
        </p>
      </Card>
    );
  }

  return (
    <Card className="gap-0 p-3">
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HelpTooltip text={BACKTEST_HELP}>
            <p className="cursor-default text-[14px] font-bold">
              <span
                className={
                  helpMode
                    ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                    : ""
                }
              >
                백테스트
              </span>{" "}
              <span className="text-[12px] font-semibold text-muted-foreground">
                최근 5년
              </span>
              <span className="ml-1.5 text-[11px] font-semibold text-muted-foreground/60">
                (누적 수익률, 2021년 기준)
              </span>
            </p>
          </HelpTooltip>
          {analyzing ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              분석중...
            </div>
          ) : hasRealData ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
              <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
              연동 완료
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          {/* 현재·제안 범례 */}
          {lines.map((l) => (
            <span
              key={l.key}
              className="flex items-center gap-1.5 text-[12px] font-bold text-muted-foreground"
            >
              <span
                className="h-0.75 w-3.5 rounded-sm"
                style={{ backgroundColor: l.color }}
              />
              {l.name}
            </span>
          ))}

          {/* 벤치마크 세그먼트 컨트롤 */}
          <div className="flex items-center gap-1.5">
            <span
              className="h-0.75 w-3.5 rounded-sm"
              style={{ backgroundColor: BENCHMARK_COLOR }}
            />
            <div className="flex rounded-lg bg-muted p-0.5">
              {BENCHMARKS.map((b) => (
                <button
                  key={b}
                  type="button"
                  onClick={() => setBenchmark(b)}
                  className={`rounded-md px-2 py-0.5 text-[11px] font-bold transition-colors ${
                    benchmark === b
                      ? "bg-white text-brand-dark shadow-sm"
                      : "text-muted-foreground"
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 0, left: 16 }}
          >
            <CartesianGrid vertical={false} stroke="#F1F3F5" />
            <XAxis
              dataKey={xKey}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "#B0B8C1", fontWeight: 600 }}
              ticks={xTicks}
              tickFormatter={
                hasRealData ? (v: string) => v.slice(0, 4) : undefined
              }
            />
            <YAxis hide domain={["dataMin - 6", "dataMax + 6"]} />
            <Tooltip
              formatter={(value, name) => {
                const label =
                  name === benchKey
                    ? benchmark
                    : (lines.find((l) => l.key === name)?.name ?? String(name));
                return [
                  value != null ? `${pctFmt(Number(value))} (${value})` : "-",
                  label,
                ];
              }}
              itemSorter={(item) => {
                const order: Record<string, number> = {
                  current: 0,
                  a: 1,
                  b: 2,
                  [benchKey]: 3,
                };
                return order[String(item.dataKey)] ?? 99;
              }}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            {/* 벤치마크 라인 */}
            <Line
              key={benchKey}
              type="monotone"
              dataKey={benchKey}
              stroke={BENCHMARK_COLOR}
              strokeWidth={1.8}
              strokeDasharray="4 3"
              dot={false}
              isAnimationActive={false}
            />
            {lines.map((l) => (
              <Line
                key={l.key}
                type="monotone"
                dataKey={l.key}
                stroke={l.color}
                strokeWidth={l.width}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
