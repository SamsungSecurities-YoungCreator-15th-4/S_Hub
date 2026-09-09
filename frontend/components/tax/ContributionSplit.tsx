"use client";

import { Slider } from "@/components/ui/slider";
import { CircleHelp, Sparkles } from "lucide-react";
import HelpTooltip from "@/components/common/HelpTooltip";
import { fmtSaving } from "@/lib/formatKrw";
import { ASSUMPTIONS, type AllocationPlan } from "@/lib/taxAccounts";

/**
 * 계산에 들어간 가정과 한계. 화면에 접어 두되 지우지는 않는다 — "이 숫자 어디서
 * 왔습니까"에 답할 수 있어야 한다.
 */
const ASSUMPTION_LINES = (
  plan: AllocationPlan,
  needYears: number,
  targetReturnPct: number,
  horizonYears: number,
): string[] => [
  `${needYears}년 뒤 가용액은 납입 원금만 — 운용수익 미반영`,
  // IPS 가 비어 있으면 목표수익률이 0 으로 내려온다. 0% 라고 적으면 거짓이라
  // 숫자 없이 말한다.
  targetReturnPct > 0
    ? `목표수익률 ${targetReturnPct}%는 ${horizonYears}년 은퇴자산 기준 — 단기 자금에 적용하지 않음`
    : `목표수익률은 장기 은퇴자산 기준 — 단기 자금에 적용하지 않음`,
  "기존 보유자산은 매도 시점 평가손익에 좌우돼 미포함 (IPS 상 국내 반도체주 비중이 큼)",
  "연금계좌는 연금저축 단독 한도 600만원을 채운 뒤 나머지를 IRP 로 배분",
  // 화면 금액을 만원 단위로 반올림하므로 유도는 여기서 들고 있는다.
  ...(plan.pensionManwon > 0
    ? [
        `연금 세액공제 = 연금 배분 ${plan.pensionManwon.toLocaleString()}만원 × ${(plan.pensionRate * 100).toFixed(1)}% = ${(plan.pensionManwon * plan.pensionRate).toFixed(1)}만원`,
      ]
    : []),
  `ISA 절감액은 잔액이 연 ${(ASSUMPTIONS.isaAssumedIncomeYield * 100).toFixed(1)}% 이자·배당을 낸다는 가정 (법정 수치 아님)`,
  "국내 상장주식 매매차익은 원래 비과세라 ISA 실익은 이보다 작을 수 있음",
  "세액공제는 산출세액을 넘을 수 없으나 그 한도는 미반영 — 낼 세금이 적으면 과대계산",
  "납입한도·세액공제율·의무보유기간·비과세 한도는 2026년 법정 기준",
];

const fmt = (n: number) => Math.round(n).toLocaleString("ko-KR");

interface Props {
  plan: AllocationPlan;
  /** 연 납입여력(만원) */
  budgetManwon: number;
  /** 슬라이더가 요청한 연금 납입액(만원) */
  pensionRequestManwon: number;
  onPensionRequestChange: (manwon: number) => void;
  /** 단기 필요자금(만원)과 시점(년) — IPS Unique */
  needManwon: number;
  needYears: number;
  /**
   * 그 돈의 이름(전세 보증금 인상분·자녀 대학 등록금·인출 예정 자금…).
   * 고객마다 다르므로 화면에 문구를 박아 두지 않는다 — 박아 두면 등록금이
   * 필요한 고객에게 "전세 자금이 모자랍니다" 라고 말하게 된다.
   */
  needLabel: string;
  /**
   * 목표 시점 필요액을 지키면서 연금에 넣을 수 있는 최대 납입액(만원).
   * 유동액과 같은 규칙으로 구해야 해서 lib/taxAccounts.ts 가 계산하고 여기는 받기만
   * 한다. 어떤 배분으로도 못 맞추면 null 이다.
   */
  maxPensionKeepingNeed: number | null;
  /** IPS 목표수익률(%) — 화면 문구가 IPS 조율기 값을 따라가야 한다. */
  targetReturnPct: number;
  /** IPS 투자기간(년) */
  horizonYears: number;
  /**
   * 필요 금액·시점의 근거 문장. LLM 이 상담 전사·IPS 를 읽어 만드는 값이며 지금은
   * 시연 대역이 들어온다. 비어 있으면(상담 전 고객) 줄을 그리지 않는다 — 빈 상자만
   * 남으면 근거가 있는 것처럼 보이면서 정작 아무것도 없는 상태가 된다.
   */
  rationale?: string;
}

/**
 * 연 납입여력을 연금계좌와 ISA 에 어떻게 나눌 것인가.
 *
 * 세액공제만 보면 연금 한도를 꽉 채우는 것이 답이다. 그런데 연금은 만 55세까지
 * 잠기고, 고객마다 근시일에 써야 할 돈이 있다. 한쪽을 최대화하면 다른 쪽이
 * 무너지는 구조라 슬라이더 하나로 양쪽을 동시에 보여준다.
 *
 * 유동성은 **누적 납입액**만 센다. 기존 보유자산은 넣지 않는다 — 매도 시점의
 * 평가손익에 좌우되는 값이라 "3년 뒤 확보된다"고 단정할 수 없기 때문이다.
 * 이 고객은 IPS 상 국내 반도체주 비중이 커서 특히 그렇다.
 */
export default function ContributionSplit({
  plan,
  budgetManwon,
  pensionRequestManwon,
  onPensionRequestChange,
  needManwon,
  needYears,
  needLabel,
  maxPensionKeepingNeed,
  targetReturnPct,
  horizonYears,
  rationale,
}: Props) {
  const sliderMax = Math.min(plan.pension.headroomManwon, budgetManwon);
  const shortfall = Math.max(needManwon - plan.liquidAtTargetManwon, 0);

  /*
   * 부족할 때 읽는 사람이 알아야 하는 건 "얼마를 얼마와 바꾸는가"다. 앞뒤 절대값만
   * 적으면(148.5 → 137) 차이를 스스로 빼야 하고, 슬라이더가 상한 근처로 오면
   * 숫자가 작아져 교환비가 아예 안 보인다.
   *
   * 감소분은 화면에 찍히는 반올림값끼리 뺀다. 원값으로 빼면 세 숫자가 화면에서
   * 안 맞는 경우가 생긴다(예: 149 − 137 = 12 인데 원값 차이는 11.5).
   */
  const capSavingManwon =
    maxPensionKeepingNeed != null ? maxPensionKeepingNeed * plan.pensionRate : 0;
  const shownSaving = Math.round(plan.pensionSavingManwon);
  const shownCapSaving = Math.round(capSavingManwon);
  const savingDrop = Math.max(shownSaving - shownCapSaving, 0);
  const pensionDrop =
    maxPensionKeepingNeed != null
      ? Math.max(plan.pensionManwon - maxPensionKeepingNeed, 0)
      : 0;

  return (
    <div className="rounded-xl border p-3.5">
      <div className="flex items-baseline justify-between">
        <p className="text-[13px] font-extrabold">
          연 납입여력 {fmt(budgetManwon)}만원
        </p>
        <span className="text-[11px] font-semibold text-muted-foreground">
          연금은 만 55세까지 {plan.pension.lockupYears}년 잠깁니다
        </span>
      </div>

      <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-center">
        {/* 배분 */}
        <div className="flex-1">
          <div className="flex items-end justify-between text-[12px] font-bold">
            <span className="text-muted-foreground">
              연금계좌{" "}
              <b className="ml-0.5 text-[15px] tabular-nums text-foreground">
                {fmt(plan.pensionManwon)}
              </b>
              만원
              {/* 연금저축 단독 한도가 600만원이라 넘는 금액은 IRP 로 가야 공제된다. */}
              {plan.pensionManwon > 0 && (
                <span className="ml-1.5 text-muted-foreground/70">
                  (연금저축 {fmt(plan.pensionSavingsManwon)} · IRP {fmt(plan.irpManwon)})
                </span>
              )}
            </span>
            <span className="text-muted-foreground">
              ISA{" "}
              <b className="ml-0.5 text-[15px] tabular-nums text-foreground">
                {fmt(plan.isaManwon)}
              </b>
              만원
              {plan.generalManwon > 0 && (
                <span className="ml-1.5 text-muted-foreground/70">
                  · 일반 {fmt(plan.generalManwon)}만원
                </span>
              )}
            </span>
          </div>
          <Slider
            value={[Math.min(pensionRequestManwon, sliderMax)]}
            onValueChange={([v]) => onPensionRequestChange(v)}
            min={0}
            max={sliderMax}
            step={10}
            className="mt-2"
          />
          <div className="mt-1 flex justify-between text-[10px] font-semibold text-muted-foreground/70">
            <span>연금 0</span>
            <span>연금 한도 {fmt(sliderMax)}만원</span>
          </div>
        </div>

        {/* 두 결과가 반대로 움직인다 */}
        <div className="flex gap-2 lg:w-[380px]">
          <div className="flex-1 rounded-lg border border-brand/20 bg-brand/5 px-3 py-2">
            <p className="text-[11px] font-bold text-muted-foreground">
              연 절세액
            </p>
            <p className="mt-0.5 text-[17px] font-extrabold tabular-nums text-brand-dark">
              <span className="text-[12px] font-bold">약 </span>
              {fmtSaving(plan.totalSavingManwon)}
              <span className="text-[12px]">만원</span>
            </p>
            <p className="mt-0.5 text-[10px] font-semibold text-muted-foreground">
              세액공제 {(plan.pensionRate * 100).toFixed(1)}% 적용
            </p>
          </div>
          <div
            className={`flex-1 rounded-lg border px-3 py-2 ${
              shortfall > 0
                ? "border-up/30 bg-[#FEECEE]"
                : "border-brand/20 bg-brand/5"
            }`}
          >
            <p className="text-[11px] font-bold text-muted-foreground">
              {needYears}년 뒤 쓸 수 있는 돈
            </p>
            <p
              className={`mt-0.5 text-[17px] font-extrabold tabular-nums ${
                shortfall > 0 ? "text-up" : "text-brand-dark"
              }`}
            >
              {fmt(plan.liquidAtTargetManwon)}
              <span className="text-[12px]">만원</span>
            </p>
            <p className="mt-0.5 text-[10px] font-semibold text-muted-foreground">
              필요 {fmt(needManwon)}만원
            </p>
          </div>
        </div>
      </div>

      {/* 판정 — 한 줄 결론 + 한 줄 근거. 읽는 사람이 찾는 건 "그래서 얼마냐"다. */}
      <div
        className={`mt-3 rounded-lg px-3 py-2 ${
          shortfall > 0 ? "bg-[#FEECEE]" : "bg-brand/5"
        }`}
      >
        {shortfall > 0 && maxPensionKeepingNeed == null ? (
          // 연금을 0으로 해도 못 맞추는 경우. 남는 돈이 목표 시점에 안 풀리는 ISA 로
          // 흘러갈 때 생긴다. 이때 "N만원으로 낮추면 된다"고 말하면 거짓이 된다.
          <>
            <p className="text-[13px] font-extrabold text-up">
              어떻게 배분해도 {needYears}년 뒤 {fmt(needManwon)}만원을 못 만듭니다
            </p>
            <p className="mt-0.5 text-[12px] font-semibold text-muted-foreground">
              연금 0으로 해도 {fmt(shortfall)}만원 부족 · ISA 의무보유{" "}
              {plan.isa.lockupYears}년이라 그 돈도 안 풀립니다
            </p>
          </>
        ) : shortfall > 0 ? (
          <>
            <p className="text-[13px] font-extrabold text-up">
              {needLabel} {fmt(shortfall)}만원 부족
            </p>
            <p className="mt-0.5 text-[12px] font-semibold text-muted-foreground">
              연금 <b className="text-foreground">{fmt(pensionDrop)}만원</b> 줄이면
              해소 ·{" "}
              {savingDrop > 0 ? (
                <>
                  세액공제 <b className="text-foreground">약 {fmt(savingDrop)}만원</b>{" "}
                  감소
                </>
              ) : (
                <>세액공제는 거의 그대로</>
              )}{" "}
              (약 {fmtSaving(plan.pensionSavingManwon)} →{" "}
              {fmtSaving(capSavingManwon)}만원)
            </p>
          </>
        ) : (
          <>
            <p className="text-[13px] font-extrabold text-brand-dark">
              {needYears}년 뒤 {fmt(needManwon)}만원 확보
            </p>
            <p className="mt-0.5 text-[12px] font-semibold text-muted-foreground">
              {maxPensionKeepingNeed != null
                ? `연금 상한 ${fmt(maxPensionKeepingNeed)}만원 · 더 넣으면 ${needLabel}이 모자랍니다`
                : `연금 한도까지 ${fmt(sliderMax - plan.pensionManwon)}만원 남았습니다`}
            </p>
          </>
        )}
      </div>

      {/*
        근거 문장 — LLM 이 채우는 자리다. 상담 전사와 IPS 를 읽어 "왜 이 시점에 이
        금액이 필요한지"를 만든다. 지금은 호출을 붙일 수 없어 시연 대역
        (demoContributionRationale)이 들어가며, demoTaxSummary·demoInsight 와 같은
        방식이다. 엔드포인트가 생기면 문장을 만드는 쪽만 바뀌고 이 자리는 그대로다.

        화면 숫자는 customer.nearTermNeedManwon 에서 오고 IPS Unique 는 자연어라
        아무도 파싱하지 않는다. 이 문장이 그 사이를 사람이 읽는 말로 잇는다.
      */}
      {rationale && (
        <p className="mt-2 flex gap-1.5 rounded-lg bg-brand/[0.06] px-2.5 py-2 text-[11px] font-semibold leading-relaxed text-muted-foreground">
          <Sparkles className="mt-[1px] size-3 shrink-0 text-brand" />
          <span>
            <b className="mr-1 text-brand-dark">AI 코멘트</b>
            {rationale}
          </span>
        </p>
      )}

      {/*
        가정·한계는 여덟 줄이나 되는데 전부 펼쳐 두면 판정 문구를 덮는다.
        가이드 토글과 같은 방식으로 접는다 — 항상 보이는 한 줄에 가장 큰 세 가지를
        적고, 나머지는 hover 로 편다. 화면에서 근거가 사라지지는 않는다.
      */}
      <HelpTooltip text={ASSUMPTION_LINES(plan, needYears, targetReturnPct, horizonYears)} wide>
        <p className="mt-2 flex items-center gap-1 text-[10px] font-semibold text-muted-foreground">
          <CircleHelp className="size-3 shrink-0" />
          납입 원금만 계산 · 운용수익·산출세액 한도 미반영 · ISA 절감액은 가정 포함
        </p>
      </HelpTooltip>
    </div>
  );
}
