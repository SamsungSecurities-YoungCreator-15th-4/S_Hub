"use client";

import { useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxGauge from "@/components/tax/TaxGauge";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import AsOfNote from "@/components/common/AsOfNote";
import { TAX_ADVICE } from "@/lib/mockData";
import { PRODUCT_LINKS } from "@/lib/productLinks";
import { useDashboardStore } from "@/lib/store";
import type { StressTaxStrategyCard } from "@/lib/api";

// portfolio id → backend kind key
const ID_TO_KIND: Record<string, string> = {
  current: "current",
  a: "A",
  b: "B",
};

const MASS_TAX_SOURCE_KEYS = ["isa", "pension_credit"] as const;

/** 중앙 하단: 절세 최적화 시뮬레이터 */
// 백엔드 값이 문자열로 와도 산술 더하기가 문자열 연결로 변질되지 않도록 숫자로 강제
// 변환한다. number 거나 비어있지 않은 string 만 인정하고(빈문자열·boolean·배열이
// Number()로 0/1 둔갑하는 것 차단), 변환 불가(NaN)·그 외는 null 로 떨궈 폴백을 타게 한다.
function toFiniteNumber(v: unknown): number | null {
  if (typeof v !== "number" && (typeof v !== "string" || v.trim() === ""))
    return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function TaxSection() {
  const {
    selectedPortfolioId,
    portfolios,
    portfolioSource,
    portfolioNote,
    portfolioTax,
    stressTax,
    taxOptimizer,
    customers,
    selectedCustomerId,
    analyzing,
    isStressMode,
  } = useDashboardStore();

  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  const selectedPortfolio = portfolios.find(
    (p) => p.id === selectedPortfolioId,
  );
  const currentPortfolio = portfolios.find((p) => p.id === "current");

  // 선택된 포트폴리오의 tax 데이터 (calculate 응답)
  const selectedKind = ID_TO_KIND[selectedPortfolioId] ?? "current";
  const selectedTax = portfolioTax?.[selectedKind] ?? null;

  // selectedPortfolioId → tax_optimizer 맵 키 (백엔드: current / portfolio_a / portfolio_b)
  const TAX_OPT_KEY: Record<string, string> = {
    current: "current",
    a: "portfolio_a",
    b: "portfolio_b",
  };
  const taxOptEntry = taxOptimizer
    ? (taxOptimizer[TAX_OPT_KEY[selectedPortfolioId] ?? "current"] ??
      taxOptimizer["portfolio_a"] ??
      Object.values(taxOptimizer)[0] ??
      null)
    : null;

  // 절세 화면 소스: 스트레스 모드면 taxOptimizer(포트폴리오별 stressed) 우선, 아니면 calculate 결과
  const taxSource = isStressMode
    ? (taxOptEntry ?? stressTax?.stressed ?? null)
    : taxOptEntry;

  const isLive =
    portfolioSource === "live" && selectedTax != null && taxSource != null;

  // 세후수익률 비교 — 현재 vs 선택 포트폴리오
  const currentAfterTax = currentPortfolio?.metrics.afterTaxReturnPct ?? null;
  const selectedAfterTax = selectedPortfolio?.metrics.afterTaxReturnPct ?? null;

  // 절세 효과 헤드라인: 스트레스 모드면 taxSource(stressed) headline, 아니면 calculate saved_vs_current
  const annualSavingManwon = isStressMode
    ? taxSource?.headline.annual_tax_saving != null
      ? Math.round(taxSource.headline.annual_tax_saving / 10000)
      : null
    : selectedTax
      ? Math.round(selectedTax.saved_vs_current / 10000)
      : null;

  // 실효세 절감: taxSource.headline의 세전→세후 실효세 (만원)
  const effectiveTaxBeforeMan =
    taxSource?.headline.tax_amount_before != null
      ? Math.round(taxSource.headline.tax_amount_before / 10000)
      : null;
  const effectiveTaxAfterMan =
    taxSource?.headline.tax_amount_after != null
      ? Math.round(taxSource.headline.tax_amount_after / 10000)
      : null;
  const effectiveTaxDeltaPct =
    effectiveTaxBeforeMan != null &&
    effectiveTaxAfterMan != null &&
    effectiveTaxBeforeMan > 0
      ? ((effectiveTaxAfterMan - effectiveTaxBeforeMan) /
          effectiveTaxBeforeMan) *
        100
      : null;

  // TaxWaterfall에 넘길 waterfallData
  const waterfallData = selectedTax
    ? {
        waterfall: selectedTax.waterfall,
        savingManwon: annualSavingManwon ?? 0,
      }
    : null;

  // 종합과세 게이지: 스트레스 모드면 포트폴리오별 taxOptEntry gauge 우선, 아니면 calculate gauge
  const gaugeData =
    (isStressMode
      ? (taxOptEntry?.financial_income_tax_gauge ??
        stressTax?.stressed?.financial_income_tax_gauge)
      : null) ??
    selectedTax?.gauge ??
    null;

  // 실시간 추출/계산된 계좌 잔여 한도 및 사용액 반영 (IPS 실시간 연동)
  const isaLiveUsed = toFiniteNumber(taxSource?.account_cards?.isa?.used_capacity);
  const isaLiveRemaining = toFiniteNumber(taxSource?.account_cards?.isa?.remaining_capacity);
  const isaUsedManwon = isaLiveUsed != null ? Math.round(isaLiveUsed / 10000) : (customer?.isaUsedManwon ?? null);
  const isaLimitManwon = (isaLiveUsed != null && isaLiveRemaining != null)
    ? Math.round((isaLiveUsed + isaLiveRemaining) / 10000)
    : 2000;

  const irpLiveUsed = toFiniteNumber(taxSource?.account_cards?.irp?.used_capacity);
  // 백엔드 IRP 카드는 ISA와 달리 remaining_capacity가 아니라 remaining_tax_credit_capacity로 내려온다.
  const irpLiveRemaining = toFiniteNumber(taxSource?.account_cards?.irp?.remaining_tax_credit_capacity);
  const pensionUsedManwon = irpLiveUsed != null ? Math.round(irpLiveUsed / 10000) : (customer?.pensionUsedManwon ?? null);
  const pensionLimitManwon = (irpLiveUsed != null && irpLiveRemaining != null)
    ? Math.round((irpLiveUsed + irpLiveRemaining) / 10000)
    : 900;

  // 절세 제안 카드: 소스가 있으면 strategy_cards, 없으면 mock
  const liveStrategyCards = taxSource?.strategy_cards ?? null;

  const baseLabel = selectedPortfolio?.name ?? "포트폴리오";

  if (
    portfolioSource === "fallback" &&
    portfolioNote === undefined &&
    !analyzing
  ) {
    return (
      <section>
        <div className="mb-2 px-0.5">
          <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
        </div>
        <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[14px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      </section>
    );
  }

  return (
    <Tabs defaultValue="effect">
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">절세 최적화 시뮬레이터</h2>
          {analyzing ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              분석중...
            </div>
          ) : isLive ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
              <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
              연동 완료
            </div>
          ) : null}
          {/* 절세 수치는 백엔드 계산값이라 인용할 외부 출처가 없어 기준일만 적는다. */}
          <AsOfNote source="KRW" />
        </div>
        <TabsList className="h-auto rounded-lg bg-muted p-0.5">
          <TabsTrigger
            value="effect"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            절세 효과
          </TabsTrigger>
          <TabsTrigger
            value="threshold"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            종합과세 임계선
          </TabsTrigger>
          <TabsTrigger
            value="advice"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            절세 제안
          </TabsTrigger>
        </TabsList>
      </div>

      <Card className="gap-0 p-3">
        {/* 탭 1: 절세 효과 */}
        <TabsContent value="effect" className="flex flex-col gap-2">
          <div className="flex items-center gap-4 rounded-xl border border-brand/20 bg-brand/5 px-3.5 py-3">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-brand/20 bg-white px-2 py-0.5 text-[13px] font-bold text-muted-foreground">
                  {baseLabel}
                </span>
              </div>
              {annualSavingManwon != null ? (
                <p
                  className={`mt-1.5 flex items-baseline gap-1.5 text-[13px] font-bold ${annualSavingManwon > 0 ? "text-up" : "text-foreground"}`}
                >
                  연간 절세 효과
                  <b className="text-3xl font-extrabold tabular-nums tracking-tight">
                    {annualSavingManwon > 0 ? "+" : ""}
                    {annualSavingManwon.toLocaleString()}
                  </b>
                  <span className="text-[12px] font-extrabold">만원</span>
                </p>
              ) : (
                <p className="mt-1.5 text-[13px] font-bold text-muted-foreground">
                  분석하기를 실행하면 실제 절세 효과를 계산합니다
                </p>
              )}
              {selectedTax?.summary && (
                <p className="mt-1 text-[13px] font-semibold text-muted-foreground">
                  {selectedTax.summary}
                </p>
              )}
            </div>
            {currentAfterTax != null && selectedAfterTax != null && (
              <>
                <SummaryStat
                  k="세후 수익률"
                  v={`${currentAfterTax.toFixed(1)}% → ${selectedAfterTax.toFixed(1)}%`}
                  d={`${selectedAfterTax - currentAfterTax > 0 ? "+" : ""}${(selectedAfterTax - currentAfterTax).toFixed(1)}%p`}
                  delta={selectedAfterTax - currentAfterTax}
                />
                {effectiveTaxBeforeMan != null &&
                effectiveTaxAfterMan != null ? (
                  <SummaryStat
                    k="실효세 절감"
                    v={`${effectiveTaxBeforeMan.toLocaleString()} → ${effectiveTaxAfterMan.toLocaleString()}만`}
                    d={
                      effectiveTaxDeltaPct != null
                        ? `${effectiveTaxDeltaPct >= 0 ? "+" : ""}${effectiveTaxDeltaPct.toFixed(1)}%`
                        : ""
                    }
                    delta={effectiveTaxDeltaPct ?? undefined}
                  />
                ) : annualSavingManwon != null ? (
                  <SummaryStat
                    k="절세 효과"
                    v={`${annualSavingManwon.toLocaleString()}만원`}
                    d="vs 현재 포트폴리오"
                  />
                ) : null}
              </>
            )}
          </div>

          <div className="grid grid-cols-2 items-start gap-4">
            <TaxWaterfall
              waterfallData={isStressMode ? null : waterfallData}
              liveHeadline={isStressMode ? (taxSource?.headline ?? null) : null}
              liveAumEokwon={customer?.aumEokwon}
            />
            <AccountAllocation
              accounts={[
                {
                  key: "isa",
                  usedManwon: isaUsedManwon,
                  limitManwon: isaLimitManwon,
                },
                {
                  key: "pension",
                  usedManwon: pensionUsedManwon,
                  limitManwon: pensionLimitManwon,
                },
              ]}
            />
          </div>
        </TabsContent>

        {/* 탭 2: 종합과세 임계선 */}
        <TabsContent value="threshold">
          <TaxGauge gaugeData={gaugeData} portfolioLabel={baseLabel} />
        </TabsContent>

        {/* 탭 3: 절세 제안 */}
        <TabsContent value="advice">
          <AdviceCards liveCards={liveStrategyCards?.cards ?? null} />
        </TabsContent>
      </Card>
    </Tabs>
  );
}

type AdviceTab = "제안설명" | "상품추천";

interface AdviceCardsProps {
  liveCards: StressTaxStrategyCard[] | null;
}

function AdviceCards({ liveCards }: AdviceCardsProps) {
  const [tabs, setTabs] = useState<Record<string, AdviceTab>>({});

  const liveByKey = new Map(liveCards?.map((card) => [card.key, card]) ?? []);

  // 화면은 Mass 고객의 3대 절세계좌만 보여 준다. 연금저축·IRP는 현재 백엔드의
  // pension_credit 합산 계산을 공유하므로 연금저축 카드에만 금액을 표시한다.
  const cards = TAX_ADVICE.cards.map((copy) => {
    const live = liveByKey.get(copy.sourceKey);
    const transferManwon = live?.transferableManwon ?? null;
    const reason = live?.reason ?? live?.ineligibleReason ?? null;
    const applicable = live?.applicable ?? true;
    let body = copy.body;

    if (live && !applicable && reason) {
      body = reason;
    } else if (transferManwon != null) {
      const capacityLabel = transferManwon.toLocaleString();
      body =
        copy.sourceKey === "isa"
          ? `${copy.body} 현재 계산상 이전 가능액은 ${capacityLabel}만원입니다.`
          : `${copy.body} 현재 계산상 합산 잔여 활용 가능액은 ${capacityLabel}만원입니다.`;
    }

    const saving =
      copy.savingRole === "included"
        ? applicable && (live?.combined_contribution_manwon ?? 0) > 0
          ? copy.saving
          : ""
        : live?.applicable && live.combined_contribution_manwon > 0
          ? `+${live.combined_contribution_manwon.toLocaleString()}만원`
          : live
            ? ""
            : copy.saving;

    return { ...copy, body, saving, applicable };
  });

  // 기존 6종 combined_total에는 화면에서 제외한 전략도 들어 있다. 표시 총액은
  // ISA와 pension_credit을 각각 한 번만 합산해 3개 카드와 계산 범위를 맞춘다.
  const massTotalManwon = liveCards?.length
    ? MASS_TAX_SOURCE_KEYS.reduce(
        (sum, key) =>
          sum + (liveByKey.get(key)?.combined_contribution_manwon ?? 0),
        0,
      )
    : null;
  const totalSaving =
    massTotalManwon != null
      ? `+${massTotalManwon.toLocaleString()}만원`
      : TAX_ADVICE.totalSaving;

  return (
    <>
      <div className="max-h-[520px] overflow-y-auto">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {cards.map((card) => {
            // 연계 상품 목록이 비면 "상품추천" 탭 자체를 감춘다 — 빈 탭·빈 박스를 남기지 않는다.
            const hasProducts = card.products.length > 0;
            const active = hasProducts
              ? (tabs[card.title] ?? "제안설명")
              : "제안설명";
            return (
              <div
                key={card.title}
                className={`flex flex-col rounded-xl border p-2.5 ${!card.applicable ? "opacity-50" : ""}`}
              >
                <div className="mb-1.5 flex items-center gap-1.5">
                  <span className="flex-1 text-[13px] font-extrabold leading-tight">
                    {card.title}
                  </span>
                  {hasProducts && (
                    <div className="flex shrink-0 rounded-md bg-muted p-0.5">
                      {(["제안설명", "상품추천"] as AdviceTab[]).map((t) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() =>
                            setTabs((prev) => ({ ...prev, [card.title]: t }))
                          }
                          className={`rounded-sm px-1.5 py-0.5 text-[10px] font-bold transition-colors ${
                            active === t
                              ? "bg-white text-brand-dark shadow-sm"
                              : "text-muted-foreground"
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {active === "제안설명" ? (
                  <div className="flex h-[132px] flex-col overflow-y-auto pr-0.5">
                    <p className="pt-1.5 text-[13px] font-semibold leading-snug text-muted-foreground">
                      {card.body}
                    </p>
                    <div className="mt-auto pt-1">
                      <p className="text-[13px] font-bold text-muted-foreground/60">
                        {card.tag}
                      </p>
                      {card.saving && (
                        <p
                          className={`text-[13px] font-extrabold tabular-nums ${
                            card.savingRole === "included"
                              ? "text-muted-foreground"
                              : "text-up"
                          }`}
                        >
                          {card.saving}
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="h-[132px] overflow-y-auto pr-0.5">
                    <div className="flex flex-col gap-1.5">
                      {card.products.map((p) => {
                        const url = PRODUCT_LINKS[p.name] ?? "";
                        return (
                          <button
                            key={p.name}
                            type="button"
                            disabled={!url}
                            onClick={() =>
                              url &&
                              window.open(url, "_blank", "noopener,noreferrer")
                            }
                            className={`flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-1.5 text-left transition-colors ${
                              url
                                ? "cursor-pointer hover:bg-brand/10"
                                : "cursor-default opacity-50"
                            }`}
                          >
                            <ExternalLink className="size-3 shrink-0 text-brand" />
                            <span className="flex flex-col">
                              <span className="text-[12px] font-extrabold text-brand-dark">
                                {p.name}
                              </span>
                              <span className="text-[10px] font-semibold leading-snug text-muted-foreground">
                                {p.desc}
                              </span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between rounded-xl bg-brand/10 px-3 py-2">
        <span className="text-[13px] font-bold text-brand-dark">
          {TAX_ADVICE.totalLabel}
        </span>
        <span className="text-[13px] font-extrabold tabular-nums text-brand-dark">
          {totalSaving}
        </span>
      </div>
    </>
  );
}

function SummaryStat({
  k,
  v,
  d,
  delta,
}: {
  k: string;
  v: string;
  d: string;
  delta?: number;
}) {
  const dCls =
    delta === undefined || delta > 0
      ? "text-up"
      : delta < 0
        ? "text-down"
        : "text-foreground";
  return (
    <div className="min-w-29.5 rounded-xl border bg-white px-3 py-2">
      <p className="text-[13px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-1 text-[13px] font-extrabold tabular-nums">{v}</p>
      <p className={`mt-0.5 text-[13px] font-extrabold tabular-nums ${dCls}`}>
        {d}
      </p>
    </div>
  );
}
