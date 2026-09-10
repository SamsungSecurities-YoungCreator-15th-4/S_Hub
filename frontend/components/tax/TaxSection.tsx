"use client";

import { ExternalLink, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import HelpTooltip from "@/components/common/HelpTooltip";
// 계좌별 활용도 막대(AccountAllocation)와 이름이 헷갈리지 않도록 "납입 배분"으로 둔다.
import ContributionSplit from "@/components/tax/ContributionSplit";
import { TAX_ADVICE } from "@/lib/mockData";
import { PRODUCT_LINKS } from "@/lib/productLinks";
import { useDashboardStore } from "@/lib/store";
// LLM 자리의 시연 대역. 엔드포인트가 생기면 이 import 만 fetch 로 바뀐다.
import { demoContributionRationale } from "@/lib/demo/fixtures/api";
import { useState } from "react";
import { useTaxFlow, useTaxPlan } from "@/lib/taxPlan";
import { deriveAdviceCards } from "@/lib/taxAdviceCards";
import type { AllocationPlan } from "@/lib/taxAccounts";
import type { StressTaxStrategyCard } from "@/lib/api";

// portfolio id → backend kind key
const ID_TO_KIND: Record<string, string> = {
  current: "current",
  a: "A",
  b: "B",
};

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
    ips,
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
  // 지표 카드도 흐름 막대와 같은 안을 봐야 한다(아래 baseLabel 주석 참고).
  // waterfallFlow 는 이 줄 아래에서 만들어지므로 실제 대입은 그쪽에서 한다.
  const selectedAfterTaxBase =
    selectedPortfolio?.metrics.afterTaxReturnPct ?? null;

  // 절세 효과 헤드라인: 스트레스 모드면 taxSource(stressed) headline, 아니면 calculate saved_vs_current
  const annualSavingManwon = isStressMode
    ? taxSource?.headline.annual_tax_saving != null
      ? Math.round(taxSource.headline.annual_tax_saving / 10000)
      : null
    : selectedTax
      ? Math.round(selectedTax.saved_vs_current / 10000)
      : null;

  // taxSource.headline 의 전→후 금융소득세 (만원)
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

  // 절세 제안 카드: 소스가 있으면 strategy_cards, 없으면 프론트 계산
  const liveStrategyCards = taxSource?.strategy_cards ?? null;

  /*
   * 절세계좌 배분과 세금 흐름은 lib/taxPlan.ts 가 계산한다. 화면 안에서 계산하면
   * store 만 읽는 PDF 가 같은 값을 볼 수 없어 리포트가 다른 배분을 인쇄한다.
   */
  const {
    plan,
    pensionRequestManwon: pensionRequest,
    setPensionRequestManwon: setPensionRequest,
    pensionCeilingForNeed,
  } = useTaxPlan();
  const waterfallFlow = useTaxFlow();

  /*
   * 머리 박스의 배지는 아래 흐름 막대가 어느 안을 기준으로 그려졌는지를 말한다.
   * 막대가 확정 대상 안을 따르므로 배지도 같은 이름이어야 한다 — 안 그러면
   * PB 가 비중을 조정했을 때 배지는 "안정 추구", 막대는 "제안 조정" 이 된다.
   */
  const baseLabel =
    waterfallFlow?.selected.name ?? selectedPortfolio?.name ?? "포트폴리오";
  const selectedAfterTax =
    waterfallFlow?.selected.afterTaxReturnPct ?? selectedAfterTaxBase;

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
    /*
      제목 줄과 카드 위치는 그대로 두고 카드 상자만 아래로 늘려 중앙 열 바닥을
      메운다. 안쪽 내용은 자연 높이 그대로라 남는 높이는 카드 안쪽 여백이 된다 —
      차트에 flex-1 을 흘려보내면 막대 세 개가 흩어져 오히려 성겨 보였다.
      min-h-0 이 없으면 flex 자식이 내용 높이 아래로 줄지 않아 세로 스크롤이 생긴다.
    */
    <Tabs defaultValue="effect" className="flex min-h-0 flex-1 flex-col">
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
        </div>
        <TabsList className="h-auto rounded-lg bg-muted p-0.5">
          <TabsTrigger
            value="effect"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            절세 효과
          </TabsTrigger>
          <TabsTrigger
            value="advice"
            className="rounded-md px-2.5 py-0.5 text-[12px] font-bold data-[state=active]:bg-white data-[state=active]:text-brand-dark data-[state=active]:shadow-sm"
          >
            절세 제안
          </TabsTrigger>
        </TabsList>
      </div>

      <Card className="min-h-0 flex-1 gap-0 p-3">
        {/* 탭 1: 절세 효과 */}
        <TabsContent value="effect" className="flex min-h-0 flex-1 flex-col gap-2">
          {/*
            절세 효과 금액이 없는 상태에서는 왼쪽이 배지 한 줄뿐이라 박스가 비어
            보인다. 세로 여백과 지표 카드를 줄여 내용만큼만 차지하게 한다.
          */}
          <div className="flex items-center gap-3 rounded-xl border border-brand/20 bg-brand/5 px-3.5 py-2">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                {/*
                  이 배지가 왼쪽 칸에 홀로 남는다(절세 효과 금액이 없을 때).
                  오른쪽 지표 카드와 무게를 맞추려면 이 정도는 되어야 한다.
                */}
                <span className="rounded-full border border-brand/20 bg-white px-3 py-1 text-[15px] font-extrabold text-brand-dark">
                  {baseLabel}
                </span>
              </div>
              {/*
                절세 효과 금액이 없으면 아무것도 적지 않는다. "분석 후 계산됩니다"
                라고 적어 두었는데, 같은 패널의 세후 수익률·세금 흐름·계좌 배치는
                이미 값을 보여주고 있어 화면이 스스로 어긋났다. 분석해도 이 숫자만
                채워지지 않는 상태라 안내가 지켜지지도 않았다.
              */}
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
              ) : null}
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
                    // 값이 전→후 세액이라 늘어날 수도 있다. "절감" 이라 쓰면
                    // 세금이 는 화면에서도 아꼈다는 말이 된다.
                    k="금융소득세"
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

          {/*
            두 그림을 위아래로 쌓는다. 좌우로 놓으면 폭이 절반이라 막대가 짧고
            오른쪽 금액 라벨이 붙어 읽혔는데, 그러면서 카드 아래는 비었다.
            세로로 쌓으면 남는 높이가 두 그림의 폭으로 바뀐다.
            각각 테두리로 묶어 어디까지가 한 그림인지 경계를 준다.
          */}
          <div className="flex min-h-0 flex-1 flex-col gap-2.5">
            <div className="flex min-h-0 flex-1 flex-col rounded-xl border p-3">
              <TaxWaterfall
                waterfallData={isStressMode ? null : waterfallData}
                liveHeadline={isStressMode ? (taxSource?.headline ?? null) : null}
                liveAumEokwon={customer?.aumEokwon}
                flow={waterfallFlow}
              />
            </div>
            <div className="flex min-h-0 flex-1 flex-col rounded-xl border p-3">
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
          </div>
        </TabsContent>

        {/* 탭 2: 절세 제안 */}
        <TabsContent value="advice" className="flex min-h-0 flex-1 flex-col gap-2.5">
          {plan &&
            customer &&
            (customer.annualContributionManwon ?? 0) > 0 &&
            (customer.nearTermNeedYears ?? 0) > 0 && (
            <ContributionSplit
              plan={plan}
              budgetManwon={customer.annualContributionManwon ?? 0}
              pensionRequestManwon={pensionRequest}
              onPensionRequestChange={setPensionRequest}
              needManwon={customer.nearTermNeedManwon}
              needYears={customer.nearTermNeedYears ?? 0}
              needLabel={customer.nearTermNeedLabel ?? "근시일 필요자금"}
              maxPensionKeepingNeed={pensionCeilingForNeed}
              targetReturnPct={ips.returnPct}
              horizonYears={customer.horizonYears}
              rationale={demoContributionRationale(
                {
                  manwon: customer.nearTermNeedManwon,
                  years: customer.nearTermNeedYears ?? 0,
                  kind: customer.nearTermNeedKind,
                  label: customer.nearTermNeedLabel,
                },
                plan.pension.lockupYears,
              )}
            />
          )}
          <AdviceCards liveCards={liveStrategyCards?.cards ?? null} plan={plan} />
        </TabsContent>
      </Card>
    </Tabs>
  );
}

/**
 * 탭 이름. 제도 설명은 가이드 툴팁으로 옮겨서 이 탭에는 배분 숫자만 남는다.
 * 상품추천이 "무엇을 살까"라면 이쪽은 "얼마를 넣을까"다.
 */
type AdviceTab = "납입안" | "상품추천";


interface AdviceCardsProps {
  liveCards: StressTaxStrategyCard[] | null;
  /** 백엔드 응답이 없을 때 쓰는 프론트 계산 결과. */
  plan: AllocationPlan | null;
}

function AdviceCards({ liveCards, plan }: AdviceCardsProps) {
  const [tabs, setTabs] = useState<Record<string, AdviceTab>>({});
  const helpMode = useDashboardStore((s) => s.helpMode);

  const { cards, totalSaving } = deriveAdviceCards(plan, liveCards);

  return (
    /*
      총합 바만 카드 바닥에 붙인다. 납입안 카드는 내용만큼만 차지한다 — 함께
      늘리면 본문이 h-[104px] 로 고정이라 절감액 줄 아래가 하얗게 빈다.
      남는 높이는 카드 목록과 총합 바 사이의 여백이 된다.
    */
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 max-h-[520px] overflow-y-auto">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {cards.map((card) => {
            // 연계 상품 목록이 비면 "상품추천" 탭 자체를 감춘다 — 빈 탭·빈 박스를 남기지 않는다.
            const hasProducts = card.products.length > 0;
            const active = hasProducts
              ? (tabs[card.title] ?? "납입안")
              : "납입안";
            return (
              <div
                key={card.title}
                className={`flex flex-col rounded-xl border p-2.5 ${!card.applicable ? "opacity-50" : ""}`}
              >
                <div className="mb-1.5 flex items-center gap-1.5">
                  {/*
                    설명을 여는 자리는 제목이다. 본문을 감싸면 배분액·절감액 위에서
                    툴팁이 떠 읽던 숫자를 덮고, 어디에 붙은 설명인지도 알 수 없다.
                    도움말 모드의 테두리는 사이드바의 자산 비중 조절기·백테스트·
                    세금 흐름 비교와 같은 규격이다.
                  */}
                  <HelpTooltip text={card.explain} className="flex-1" wide>
                    <p className="cursor-default text-[13px] font-extrabold leading-tight">
                      <span
                        className={
                          helpMode
                            ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                            : ""
                        }
                      >
                        {card.title}
                      </span>
                    </p>
                  </HelpTooltip>
                  {hasProducts && (
                    <div className="flex shrink-0 rounded-md bg-muted p-0.5">
                      {(["납입안", "상품추천"] as AdviceTab[]).map((t) => (
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

                {active === "납입안" ? (
                  <div className="h-[104px]">
                    <div className="flex h-full flex-col overflow-y-auto pr-0.5">
                      <p className="pt-1.5 text-[13px] font-semibold leading-snug text-muted-foreground">
                        {card.summary}
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
                  </div>
                ) : (
                  <div className="h-[104px] overflow-y-auto pr-0.5">
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
      <div className="mt-auto flex shrink-0 items-center justify-between rounded-xl bg-brand/10 px-3 py-2">
        <span className="text-[13px] font-bold text-brand-dark">
          {TAX_ADVICE.totalLabel}
        </span>
        <span className="text-[13px] font-extrabold tabular-nums text-brand-dark">
          {totalSaving}
        </span>
      </div>
    </div>
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
  // 값과 증감을 한 줄에 둔다. 세 줄로 쌓으면 카드 높이가 박스 전체를 밀어 올린다.
  return (
    <div className="min-w-29.5 rounded-xl border bg-white px-3 py-1.5">
      <p className="text-[12px] font-bold text-muted-foreground">{k}</p>
      <p className="mt-0.5 flex items-baseline gap-1.5 whitespace-nowrap">
        <span className="text-[14px] font-extrabold tabular-nums">{v}</span>
        {d && (
          <span className={`text-[12px] font-extrabold tabular-nums ${dCls}`}>
            {d}
          </span>
        )}
      </p>
    </div>
  );
}
