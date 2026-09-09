"use client";

import { useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AccountAllocation from "@/components/tax/AccountAllocation";
import TaxWaterfall from "@/components/tax/TaxWaterfall";
import AsOfNote from "@/components/common/AsOfNote";
import HelpTooltip from "@/components/common/HelpTooltip";
// 계좌별 활용도 막대(AccountAllocation)와 이름이 헷갈리지 않도록 "납입 배분"으로 둔다.
import ContributionSplit from "@/components/tax/ContributionSplit";
import { TAX_ADVICE } from "@/lib/mockData";
import { PRODUCT_LINKS } from "@/lib/productLinks";
import { useDashboardStore } from "@/lib/store";
// LLM 자리의 시연 대역. 엔드포인트가 생기면 이 import 만 fetch 로 바뀐다.
import { demoContributionRationale } from "@/lib/demo/fixtures/api";
import {
  allocationPlan,
  maxPensionKeepingNeed as calcMaxPensionKeepingNeed,
  pensionAccount,
  type AllocationPlan,
} from "@/lib/taxAccounts";
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

  /**
   * 절세계좌 배분 — 백엔드 없이 프론트에서 계산한다(`lib/taxAccounts.ts`).
   * 한도·세액공제율·의무보유기간은 전부 법정 상수라 조회할 외부 소스가 없다.
   * 기본값은 연금 한도를 꽉 채운 상태다. "한도부터 채운다"는 통념이 이 고객에게는
   * 왜 틀리는지가 슬라이더를 건드리기 전에 바로 보여야 하기 때문이다.
   */
  const accountInput = customer
    ? {
        salaryManwon: customer.salaryManwon,
        isaUsedManwon: customer.isaUsedManwon,
        isaYearsSinceOpen: customer.isaYearsSinceOpen,
        pensionUsedManwon: customer.pensionUsedManwon,
        age: customer.age,
        horizonYears: customer.horizonYears,
        isaOpened: customer.isaOpened,
        isaYearsUntilLiquid: customer.isaYearsUntilLiquid,
      }
    : null;

  const defaultPension = accountInput ? pensionAccount(accountInput).headroomManwon : 0;
  const [pensionRequest, setPensionRequest] = useState(defaultPension);
  // 고객을 바꾸면 한도가 달라지므로 슬라이더도 그 고객의 기본값으로 되돌린다.
  const [pensionOwner, setPensionOwner] = useState(selectedCustomerId);
  if (pensionOwner !== selectedCustomerId) {
    setPensionOwner(selectedCustomerId);
    setPensionRequest(defaultPension);
  }

  const plan: AllocationPlan | null =
    accountInput && customer
      ? allocationPlan(
          accountInput,
          customer.annualContributionManwon ?? 0,
          pensionRequest,
          customer.nearTermNeedYears ?? 0,
        )
      : null;

  // 유동액과 같은 규칙으로 구해야 해서 계산 모듈에 맡긴다. 화면에서 따로 유도하면
  // ISA 의무보유가 목표 시점 뒤에 풀리는 고객에서 두 값이 갈린다.
  const pensionCeilingForNeed =
    accountInput && customer
      ? calcMaxPensionKeepingNeed(
          accountInput,
          customer.annualContributionManwon ?? 0,
          customer.nearTermNeedManwon,
          customer.nearTermNeedYears ?? 0,
        )
      : null;

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
                  분석 후 계산됩니다
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

        {/* 탭 2: 절세 제안 */}
        <TabsContent value="advice" className="flex flex-col gap-2.5">
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

/**
 * 절감액 표기(만원). 만원 단위로 반올림하고 "약"을 붙인다.
 *
 * 소수 첫째 자리까지 적으면(148.5만원) 900만 × 16.5% 라는 유도가 화면에 남지만,
 * PB 가 고객에게 그렇게 말하지 않고 ISA 절감액은 애초에 이자·배당 3% **가정** 위에
 * 얹힌 값이라 그 자리에 의미가 없다. 없는 정밀도를 주장하지 않는다.
 * 유도는 가이드 툴팁이 "배분액 × 공제율"로 들고 있다.
 *
 * "약"을 빼면 반올림한 값이 정확한 값처럼 읽히므로 접두는 호출부에서 반드시 붙인다.
 */
const fmtSaving = (n: number) => {
  const r = Math.round(n);
  // 5천원짜리를 "약 0만원"으로 적을 수는 없다.
  return r === 0 && n > 0 ? "1만원 미만" : r.toLocaleString("ko-KR");
};

interface AdviceCardsProps {
  liveCards: StressTaxStrategyCard[] | null;
  /** 백엔드 응답이 없을 때 쓰는 프론트 계산 결과. */
  plan: AllocationPlan | null;
}

function AdviceCards({ liveCards, plan }: AdviceCardsProps) {
  const [tabs, setTabs] = useState<Record<string, AdviceTab>>({});

  const liveByKey = new Map(liveCards?.map((card) => [card.key, card]) ?? []);

  /*
   * 카드마다 따로 폴백하면 백엔드가 일부만 내려줄 때 한 줄에 백엔드 숫자와 프론트
   * 계산이 나란히 뜨는데 화면에는 구분이 없다. 어느 하나라도 오면 전부 백엔드 경로로
   * 간다 — 출처가 섞이느니 비어 있는 편이 추적 가능하다.
   */
  const useLive = (liveCards?.length ?? 0) > 0;

  /**
   * 백엔드 응답이 없을 때(데모·연결 실패) 프론트 계산을 같은 모양으로 돌려준다.
   * 예전에는 이 자리가 비어 카드 세 장이 금액 없이 설명문만 남았다.
   */
  const fromPlan = (card: (typeof TAX_ADVICE.cards)[number]) => {
    if (!plan) return null;
    const isIsa = card.sourceKey === "isa";
    const account = isIsa ? plan.isa : plan.pension;
    // 연금계좌는 한 덩어리로 계산하지만 배분은 카드별로 다르다 — 연금저축은 단독
    // 한도 600만원까지, 넘는 금액은 IRP 로 간다. 카드마다 제 몫을 말해야 PB 가
    // "연금저축에 900만원"처럼 안내하지 않는다.
    const allocated = isIsa
      ? plan.isaManwon
      : card.key === "irp"
        ? plan.irpManwon
        : plan.pensionSavingsManwon;
    /*
     * 카드마다 걸리는 한도가 다르다. 연금저축에는 단독 한도 600만원이 따로 있고,
     * IRP 는 연금저축과 900만원 통을 나눠 쓴다. 그래서 IRP 의 소진 여부는 자기
     * 배분액이 아니라 **연금 배분 합계**로 판단해야 한다 — irpManwon 으로 재면
     * "900 중 300" 이 되어 600만원이 남은 것처럼 읽히는데, 그 600만원은 옆 카드
     * (연금저축)가 이미 쓴 돈이다.
     */
    const cap = isIsa
      ? { limit: plan.isa.headroomManwon, used: plan.isaManwon, full: "한도 소진", left: "잔여" }
      : card.key === "irp"
        ? {
            limit: plan.pension.headroomManwon,
            used: plan.pensionManwon,
            full: `합산 ${plan.pension.headroomManwon.toLocaleString()}만원 소진`,
            left: "합산 한도 잔여",
          }
        : {
            limit: plan.pensionSavingsRoomManwon,
            used: plan.pensionSavingsManwon,
            full: "단독 한도 소진",
            left: "단독 한도 잔여",
          };
    const remaining = Math.max(cap.limit - cap.used, 0);
    const capText =
      remaining > 0 ? `${cap.left} ${remaining.toLocaleString()}만원` : cap.full;

    return {
      applicable: account.eligible,
      reason: account.reason,
      allocatedManwon: allocated,
      capText,
      headroomManwon: account.headroomManwon,
      savingManwon: isIsa ? plan.isaSavingManwon : plan.pensionSavingManwon,
      note: isIsa
        ? `이 고객은 ${plan.isaType.type === "seogmin" ? "서민형" : "일반형"} — 비과세 ${plan.isaType.taxFreeManwon}만원 (${plan.isaType.reason})`
        : card.key === "irp"
          ? "연금저축 단독 한도 600만원 초과분이 여기로 배분"
          : "연금저축 단독 한도는 600만원",
    };
  };

  // 화면은 Mass 고객의 3대 절세계좌만 보여 준다. 연금저축·IRP는 pension_credit
  // 합산 계산을 공유하므로 연금저축 카드에만 금액을 표시한다.
  const cards = TAX_ADVICE.cards.map((copy) => {
    const live = liveByKey.get(copy.sourceKey);
    const calc = useLive ? null : fromPlan(copy);

    const applicable = live?.applicable ?? calc?.applicable ?? true;
    const reason = live?.reason ?? live?.ineligibleReason ?? calc?.reason ?? null;
    const transferManwon = live?.transferableManwon ?? calc?.headroomManwon ?? null;

    /*
     * 카드에는 이 고객의 숫자와 결론만 두고, 제도 설명은 가이드 툴팁으로 보낸다.
     * 세 장이 나란히 서는 자리라 제도 문장까지 본문에 두면 읽히지 않는다.
     * 가이드가 OFF 여도 숫자는 남아야 하므로 둘을 섞지 않는다.
     *
     *   summary — 잔여 한도·배분액 (항상 카드에 보인다)
     *   explain — 제도 설명·판정 근거 (가이드 ON 일 때 hover 로 뜬다)
     */
    let summary: string;
    let explain: string[] = copy.helpLines;

    if (!applicable && reason) {
      summary = "적용 불가";
      explain = [reason];
    } else if (calc) {
      // 배분액이 답이라 앞에, 한도는 맥락이라 뒤에 둔다.
      summary =
        calc.allocatedManwon > 0
          ? `${calc.allocatedManwon.toLocaleString()}만원 배분 · ${calc.capText}`
          : `배분 없음 · ${calc.capText}`;
      // 판정 근거(일반형/서민형, 연금저축 단독 한도)도 설명 쪽이다.
      explain = [...copy.helpLines, calc.note];
    } else if (transferManwon != null) {
      summary =
        copy.sourceKey === "isa"
          ? `이전 가능액 ${transferManwon.toLocaleString()}만원`
          : `합산 잔여 활용 가능액 ${transferManwon.toLocaleString()}만원`;
    } else {
      summary = "";
    }

    /*
     * ⚠️ 두 값의 의미가 다르다.
     *     live.combined_contribution_manwon — 백엔드가 계산한 **납입액**
     *     calc.savingManwon                 — 프론트가 계산한 **절감액**
     * 그런데 같은 "+N만원" 절세액 슬롯에 들어간다. 백엔드가 붙으면 900만원 납입이
     * "+900만원 절세"로 보인다. live 쪽 표기는 이 PR 이전부터의 동작이라 여기서
     * 바꾸지 않지만, 백엔드를 연동할 때 반드시 손봐야 하는 자리다.
     * (아래 총액도 같은 문제를 갖는다.)
     */
    const liveContributionManwon = live?.applicable
      ? live.combined_contribution_manwon
      : 0;
    const calcSavingManwon = calc?.applicable ? calc.savingManwon : 0;
    const shownManwon = live ? liveContributionManwon : calcSavingManwon;

    const saving =
      copy.savingRole === "included"
        ? shownManwon > 0
          ? copy.saving
          : ""
        : shownManwon > 0
          ? `약 +${fmtSaving(shownManwon)}만원`
          : "";

    return { ...copy, summary, explain, saving, applicable };
  });

  // 기존 6종 combined_total에는 화면에서 제외한 전략도 들어 있다. 표시 총액은
  // ISA와 pension_credit을 각각 한 번만 합산해 3개 카드와 계산 범위를 맞춘다.
  // ⚠️ 위와 같은 의미 불일치 — live 쪽은 납입액 합, 프론트 쪽은 절감액 합이다.
  const massTotalManwon = useLive
    ? MASS_TAX_SOURCE_KEYS.reduce(
        (sum, key) =>
          sum + (liveByKey.get(key)?.combined_contribution_manwon ?? 0),
        0,
      )
    : (plan?.totalSavingManwon ?? null);
  const totalSaving =
    massTotalManwon != null
      ? `약 +${fmtSaving(massTotalManwon)}만원`
      : TAX_ADVICE.totalSaving;

  return (
    <>
      <div className="max-h-[520px] overflow-y-auto">
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
                  <span className="flex-1 text-[13px] font-extrabold leading-tight">
                    {card.title}
                  </span>
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
                  /* 카드 전체가 아니라 본문만 감싼다 — 탭 버튼·상품 링크 위에서
                     툴팁이 떠 카드를 덮으면 누르기 거슬린다. */
                  <HelpTooltip text={card.explain} className="h-[104px]" wide>
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
                  </HelpTooltip>
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
