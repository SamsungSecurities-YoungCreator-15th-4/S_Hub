"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatWon } from "@/lib/format";
import { CALCULATION_ASSUMPTIONS } from "@/lib/home-goal/calculateHomeGoal";
import { HOME_GOAL_FIELDS, EXAMPLE_HOME_GOAL, type HomeGoalDraft } from "@/lib/home-goal/types";
import { describeHomeGoalComparison, formatHomeGoalMonths, type HomeGoalComparison } from "@/lib/home-goal/portfolioAdapter";
import HomeGoalStrategyCard from "./HomeGoalStrategyCard";

export default function HomeGoalDetailModal({ open, onOpenChange, onReturnFocus, draft, onDraftChange, rows, selectedId, onSelect, sourceLabel, riskLabel, analyzing }: {
  open: boolean; onOpenChange: (value: boolean) => void;
  onReturnFocus: () => void;
  draft: HomeGoalDraft; onDraftChange: (value: HomeGoalDraft) => void;
  rows: HomeGoalComparison[]; selectedId: string; onSelect: (value: string) => void;
  sourceLabel: string; riskLabel: string; analyzing: boolean;
}) {
  const selected = rows.find((row) => row.id === selectedId);
  const result = analyzing ? null : selected?.result;
  const input = selected?.input;
  const progress = result ? Math.min(100, Math.max(0, result.achievementRate)) : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="block max-h-[90dvh] overflow-y-auto rounded-2xl p-5 sm:max-w-4xl sm:p-6" overlayClassName="bg-black/40 backdrop-blur-sm"
        onCloseAutoFocus={(event) => { event.preventDefault(); onReturnFocus(); }}>
        <DialogHeader className="pr-6 text-left">
          <DialogTitle className="text-xl font-extrabold">내 집 마련 전략 분석</DialogTitle>
          <DialogDescription>같은 주택 목표에서 저축·매수 시점·주택가격을 조정해 보세요.</DialogDescription>
        </DialogHeader>

        <section className="mt-5 rounded-xl bg-muted/50 p-4" aria-labelledby="home-goal-input-title">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 id="home-goal-input-title" className="font-bold">나의 주택 목표</h3>
            <Button size="sm" variant="outline" onClick={() => onDraftChange({ ...EXAMPLE_HOME_GOAL })}>예시 입력 불러오기</Button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {HOME_GOAL_FIELDS.map(({ key, label, unit, step }) => (
              <label key={key} htmlFor={`home-goal-${key}`} className="block text-xs font-semibold text-muted-foreground">
                {label}
                <div className="relative mt-1.5">
                  <Input id={`home-goal-${key}`} type="number" inputMode="decimal" step={step}
                    min={key === "expectedHousePriceGrowth" ? undefined : 0}
                    value={draft[key]} onChange={(event) => onDraftChange({ ...draft, [key]: event.target.value })}
                    className="bg-card pr-16 text-sm text-foreground tabular-nums" placeholder="입력" />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[11px]">{unit}</span>
                </div>
              </label>
            ))}
            <label className="block text-xs font-semibold text-muted-foreground" htmlFor="home-goal-portfolio">
              기준 포트폴리오 · 세전 기대수익률
              <select id="home-goal-portfolio" value={selectedId} onChange={(event) => onSelect(event.target.value)}
                className="mt-1.5 h-9 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-brand">
                {rows.map((row) => <option key={row.id} value={row.id}>{row.name} · {row.returnPct === null ? "분석 대기" : `${row.returnPct.toFixed(2)}%`}</option>)}
              </select>
            </label>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">주택 마련 자금은 전체 운용자산과 별도입니다. 입력값은 이 브라우저 세션에서 고객별로 보관되며 새로고침 시 초기화됩니다.</p>
          <p className="mt-1 text-xs text-muted-foreground">{sourceLabel} · 대출액·부대비용률·집값 상승률은 입력 가정</p>
        </section>

        {analyzing ? (
          <p role="status" className="py-6 text-center text-sm text-muted-foreground">포트폴리오 분석 중입니다. 완료 후 다시 계산합니다.</p>
        ) : !result || !input ? (
          <p role="status" className="py-6 text-center text-sm text-muted-foreground">{selected?.error ?? "포트폴리오 분석과 목표 입력을 완료해 주세요."}</p>
        ) : (
          <>
            <section className="mt-5 grid gap-3 sm:grid-cols-2" aria-label="현재 목표와 계획">
              <div className="rounded-xl border p-4">
                <h3 className="mb-3 font-bold">현재 목표</h3>
                <dl className="space-y-2 text-sm">
                  <Amount label="현재 주택 마련 자금" value={formatWon(input.currentAssets)} />
                  <Amount label="목표 주택가격 · 현재" value={formatWon(input.targetHousePrice)} />
                  <Amount label="목표 매수 시점" value={input.targetYears === 0 ? "지금" : `${formatHomeGoalMonths(Math.round(input.targetYears * 12))} 후`} />
                  <Amount label="매수 시점 예상 주택가격" value={formatWon(result.futureHousePrice)} />
                  <Amount label="예상 대출액" value={formatWon(input.expectedMortgageAmount)} />
                  <Amount label="취득 부대비용" value={formatWon(result.purchaseCosts)} />
                  <Amount label="필요 자기자본" value={formatWon(result.requiredEquity)} />
                </dl>
              </div>
              <div className="rounded-xl bg-brand/5 p-4">
                <h3 className="mb-3 font-bold">현재 계획 · {selected?.name}</h3>
                <dl className="space-y-2 text-sm">
                  <Amount label="기준 기대수익률 · 연" value={`${(input.portfolioExpectedReturn * 100).toFixed(2)}%`} />
                  <Amount label="월 저축" value={formatWon(input.monthlySavings)} />
                  <Amount label="매수 시점 예상자금" value={formatWon(result.futureHomeFund)} />
                  <Amount label={result.gap > 0 ? "부족자금" : "여유자금"} value={formatWon(Math.abs(result.gap))} />
                  <Amount label="목표 달성률" value={`${progress.toFixed(1)}%`} />
                </dl>
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">{result.status === "achieved" ? "입력한 가정에서는 목표 시점의 필요 자기자본을 충족합니다." : "예상자금이 필요 자기자본보다 부족합니다. 아래 세 가지 조정안을 확인해 보세요."}</p>
                {result.requiredEquity === 0 && <p className="mt-2 text-xs text-muted-foreground">대출 가정이 주택가격과 비용의 합 이상이므로 필요 자기자본을 0원으로 표시합니다. 대출 가능 여부를 별도로 확인해 주세요.</p>}
              </div>
            </section>

            <section className="mt-5" aria-labelledby="home-goal-strategies">
              <h3 id="home-goal-strategies" className="mb-3 font-bold">Gap을 줄이는 세 가지 방법</h3>
              <div className="grid gap-3 lg:grid-cols-3">
                <HomeGoalStrategyCard number={1} title="월 저축액 조정">
                  {result.requiredMonthlySavings === null ? <p className="text-sm">지금 매수하려면 추가 목돈 {formatWon(Math.max(0, result.gap))}이 필요합니다.</p> : <>
                    <p className="text-xs text-muted-foreground">목표 시점 유지 시 필요 저축</p>
                    <p className="text-xl font-extrabold tabular-nums">{formatWon(result.requiredMonthlySavings, { rounding: "ceil" })}<span className="ml-1 text-xs font-medium text-muted-foreground">/ 월</span></p>
                    <p className="text-xs text-muted-foreground">현재 {formatWon(input.monthlySavings)} · 추가 {formatWon(Math.max(0, result.requiredMonthlySavings - input.monthlySavings), { rounding: "ceil" })} / 월</p>
                    <p className="text-[11px] text-muted-foreground">목표 충족을 위해 만원 단위 올림</p>
                  </>}
                </HomeGoalStrategyCard>
                <HomeGoalStrategyCard number={2} title="매수 시점 연장">
                  <p className="text-xs text-muted-foreground">현재 자금·저축·포트폴리오 유지</p>
                  <p className="text-xl font-extrabold">{result.additionalMonths === 0 ? "연장 필요 없음" : result.expectedAchievementMonths === null ? "50년 내 미달성" : `${formatHomeGoalMonths(result.expectedAchievementMonths)} 후`}</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">{result.additionalMonths === null ? "탐색 범위 내에서 목표에 도달하지 못합니다." : result.additionalMonths > 0 ? `기존 목표보다 ${formatHomeGoalMonths(result.additionalMonths)} 추가 필요합니다.` : "계산상 목표 시점의 자기자본을 충족합니다."} 집값 상승과 부대비용도 함께 반영합니다.</p>
                </HomeGoalStrategyCard>
                <HomeGoalStrategyCard number={3} title="주택가격 조정">
                  <p className="text-xs text-muted-foreground">구매 가능한 주택 · 현재 가격 기준</p>
                  <p className="text-xl font-extrabold tabular-nums">{formatWon(result.affordableHousePrice, { rounding: "floor" })}</p>
                  <p className="text-xs text-muted-foreground">매수 시점 가격 {formatWon(result.affordableHousePriceAtPurchase)} · 대출 가정 유지</p>
                  <p className="text-[11px] text-muted-foreground">구매 가능 상한은 만원 단위 내림</p>
                </HomeGoalStrategyCard>
              </div>
            </section>

            <section className="mt-5" aria-labelledby="home-goal-comparison">
              <h3 id="home-goal-comparison" className="mb-3 font-bold">현재·A·B 비교</h3>
              <div className="overflow-x-auto rounded-xl border">
                <table className="w-full min-w-[530px] text-right text-xs tabular-nums">
                  <caption className="sr-only">같은 주택 목표에서 포트폴리오별 예상자금과 Gap 비교</caption>
                  <thead className="bg-muted/70"><tr><th scope="col" className="p-3 text-left">구분</th>{rows.map((row) => <th scope="col" key={row.id} className={`p-3 ${row.id === selectedId ? "text-brand-dark" : ""}`}>{row.name}</th>)}</tr></thead>
                  <tbody>
                    <CompareRow label="기준 기대수익률" rows={rows} render={(row) => row.returnPct === null ? "미확보" : `${row.returnPct.toFixed(2)}%`} />
                    <CompareRow label="목표 시점 예상자금" rows={rows} render={(row) => row.result ? formatWon(row.result.futureHomeFund) : "계산 대기"} />
                    <CompareRow label="Gap · 음수는 여유자금" rows={rows} render={(row) => row.result ? formatWon(row.result.gap) : "계산 대기"} />
                    <CompareRow label="최근 Stress · 수익률 변화" rows={rows} render={(row) => row.stressDeltaPct === null ? "미분석" : `${row.stressDeltaPct > 0 ? "+" : ""}${row.stressDeltaPct.toFixed(2)}%p`} />
                    <CompareRow label="손실허용한도 적합성" rows={rows} render={() => "판단 보류"} />
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">고객 위험성향: {riskLabel || "미입력"}. Stress는 기준 대비 연 기대수익률 변화이며 원금 손실률과 다릅니다. 기존 API의 근사값이 포함될 수 있어 손실한도 판정에 사용하지 않습니다.</p>
              <p className="mt-3 rounded-xl bg-muted/60 p-3 text-sm leading-relaxed">{describeHomeGoalComparison(rows)}</p>
            </section>

            <details className="mt-5 rounded-xl border p-3 text-xs text-muted-foreground">
              <summary className="cursor-pointer font-bold">계산 근거와 가정 확인</summary>
              <ul className="mt-3 list-disc space-y-1.5 pl-4">{CALCULATION_ASSUMPTIONS.map((text) => <li key={text}>{text}</li>)}</ul>
              <p className="mt-3">필요 자기자본 = 예상 주택가격 × (1 + 부대비용률) − 예상 대출액 (최소 0원)</p>
              <p className="mt-1">Gap = 필요 자기자본 − (현재 자금의 미래가치 + 월 저축의 미래가치)</p>
              <p className="mt-1">금액 표시는 반올림하되 계산에는 반올림 전 값을 사용합니다. 100% 초과 달성률은 화면에서만 제한합니다.</p>
              <p className="mt-3 break-all">계산 지문: {result.computation_hash}</p>
              <p className="mt-1">{sourceLabel} · 나머지 입력은 위 목표 설정값 · 최종 판단은 PB 검토</p>
            </details>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Amount({ label, value }: { label: string; value: string }) {
  return <div className="flex flex-wrap justify-between gap-x-3 gap-y-1"><dt className="text-muted-foreground">{label}</dt><dd className="font-bold tabular-nums">{value}</dd></div>;
}

function CompareRow({ label, rows, render }: { label: string; rows: HomeGoalComparison[]; render: (row: HomeGoalComparison) => string }) {
  return <tr className="border-t"><th scope="row" className="p-3 text-left font-medium text-muted-foreground">{label}</th>{rows.map((row) => <td key={row.id} className="p-3 font-semibold">{render(row)}</td>)}</tr>;
}
