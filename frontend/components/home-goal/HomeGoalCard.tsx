"use client";

import { useMemo, useRef, useState } from "react";
import { ArrowRight, House } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDashboardStore } from "@/lib/store";
import { IS_DEMO } from "@/lib/demo/flag";
import { formatWon } from "@/lib/format";
import { EMPTY_HOME_GOAL, EXAMPLE_HOME_GOAL } from "@/lib/home-goal/types";
import { compareHomeGoalPortfolios, formatHomeGoalMonths } from "@/lib/home-goal/portfolioAdapter";
import HomeGoalDetailModal from "./HomeGoalDetailModal";

/** 고객·대시보드 선택 변경 시 모달과 로컬 비교 선택을 초기화한다. */
export default function HomeGoalCard() {
  const customerId = useDashboardStore((state) => state.selectedCustomerId);
  const selectedPortfolioId = useDashboardStore((state) => state.selectedPortfolioId);
  return <CustomerHomeGoal key={`${customerId}:${selectedPortfolioId}`} customerId={customerId} />;
}

function CustomerHomeGoal({ customerId }: { customerId: string }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [localPortfolioId, setLocalPortfolioId] = useState<string | null>(null);
  const { homeGoalDrafts, setHomeGoalDraft, selectedPortfolioId, basePortfolios, portfolios, portfolioSource, isStressMode, analyzing, ips } = useDashboardStore();
  const draft = homeGoalDrafts[customerId] ?? (IS_DEMO ? EXAMPLE_HOME_GOAL : EMPTY_HOME_GOAL);
  const selectedId = localPortfolioId ?? selectedPortfolioId;
  const rows = useMemo(() => compareHomeGoalPortfolios(draft, basePortfolios, portfolios, portfolioSource, isStressMode), [draft, basePortfolios, portfolios, portfolioSource, isStressMode]);
  const selected = rows.find((row) => row.id === selectedId) ?? rows[0];
  const result = analyzing ? null : selected?.result;
  const input = selected?.input;
  const progress = result ? Math.min(100, Math.max(0, result.achievementRate)) : 0;
  const sourceLabel = portfolioSource === "live" ? "기대수익률: 기존 포트폴리오 분석" : portfolioSource === "demo" ? "기대수익률: 시연 고정 데이터" : "기대수익률: 분석 대기";

  return (
    <Card className="gap-0 p-4" aria-label="내 집 마련 Gap">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded-xl bg-brand/10 p-2 text-brand-dark"><House className="size-4" aria-hidden="true" /></span>
          <h2 className="text-base font-extrabold">내 집 마련 Gap</h2>
        </div>
        <span className="text-[11px] font-semibold text-muted-foreground">{selected?.name ?? "포트폴리오"} 기준 · {IS_DEMO ? "시연·입력 가정" : "입력 가정"}</span>
      </div>
      {result && input ? (
        <>
          <p className="mt-3 text-sm font-semibold">{input.targetYears === 0 ? "지금" : `${formatHomeGoalMonths(Math.round(input.targetYears * 12))} 후`} · {formatWon(input.targetHousePrice)} 주택 <span className="text-xs font-normal text-muted-foreground">(현재 가격)</span></p>
          <dl className="mt-3 grid grid-cols-1 gap-3 min-[520px]:grid-cols-3">
            <Headline label="필요 자기자본" value={formatWon(result.requiredEquity)} />
            <Headline label="목표 시점 예상 주택자금" value={formatWon(result.futureHomeFund)} />
            <Headline label={result.status === "achieved" ? "여유자금" : "부족자금"} value={formatWon(Math.abs(result.gap))} accent />
          </dl>
          <div className="mt-4">
            <div className="mb-1.5 flex justify-between text-xs font-bold"><span className="text-muted-foreground">목표 달성률</span><span className="text-brand-dark tabular-nums">{progress.toFixed(1)}%</span></div>
            <div role="progressbar" aria-label="내 집 마련 목표 달성률" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(progress.toFixed(1))} className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-brand transition-[width]" style={{ width: `${progress}%` }} />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">{result.status === "achieved" ? "현재 계획 유지 시 계산상 목표 달성" : result.additionalMonths === null ? "현재 계획 유지 시 50년 내 미달성" : `현재 계획 유지 시 약 ${result.additionalMonths}개월 추가 필요`}</p>
            <Button ref={triggerRef} size="sm" variant="outline" onClick={() => setOpen(true)} className="text-brand-dark">내 집 마련 전략 분석 <ArrowRight className="size-3.5" /></Button>
          </div>
          <p className="mt-2 text-[10px] text-muted-foreground">{sourceLabel} · 대출·취득비용은 가정 · 세전 추정</p>
        </>
      ) : (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted/40 p-3">
          <p role="status" className="text-sm text-muted-foreground">{analyzing ? "포트폴리오 분석 후 예상자금을 계산합니다." : selected?.error ?? "주택 목표와 마련 자금을 입력해 주세요."}</p>
          <Button ref={triggerRef} size="sm" variant="outline" onClick={() => setOpen(true)}>주택 목표 설정 <ArrowRight className="size-3.5" /></Button>
        </div>
      )}
      <HomeGoalDetailModal open={open} onOpenChange={setOpen} draft={draft} onDraftChange={(value) => setHomeGoalDraft(customerId, value)}
        onReturnFocus={() => triggerRef.current?.focus()}
        rows={rows} selectedId={selected?.id ?? "current"} onSelect={setLocalPortfolioId} sourceLabel={sourceLabel} riskLabel={ips.risk} analyzing={analyzing} />
    </Card>
  );
}

function Headline({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return <div className={`min-w-0 rounded-xl p-3 ${accent ? "bg-brand/5" : "bg-muted/40"}`}><dt className="text-[11px] font-semibold text-muted-foreground">{label}</dt><dd className={`mt-1 text-xl font-extrabold tabular-nums ${accent ? "text-brand-dark" : ""}`}>{value}</dd></div>;
}
