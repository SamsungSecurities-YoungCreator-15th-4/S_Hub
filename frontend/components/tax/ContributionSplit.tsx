"use client";

import { Slider } from "@/components/ui/slider";
import { CircleHelp, Sparkles } from "lucide-react";
import HelpTooltip from "@/components/common/HelpTooltip";
import { ASSUMPTIONS, type AllocationPlan } from "@/lib/taxAccounts";
import type { ContributionNarrative } from "@/lib/demo/fixtures/api";
import { fmtSaving } from "@/lib/formatKrw";

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
  `${needYears}년 뒤 가용액은 납입 원금만: 운용수익 미반영`,
  // 어디까지가 상담에서 온 값이고 어디부터가 계산인지 긋는다. AI 코멘트만 AI 가
  // 쓴 문장이고, 화면의 금액은 전부 법정 한도로 계산한 값이다.
  "필요액·시점·자금 이름은 상담 전사에서 뽑은 값: 나머지 금액은 법정 한도로 계산",
  // IPS 가 비어 있으면 목표수익률이 0 으로 내려온다. 0% 라고 적으면 거짓이라
  // 숫자 없이 말한다.
  targetReturnPct > 0
    ? `목표수익률 ${targetReturnPct}%는 ${horizonYears}년 은퇴자산 기준: 단기 자금에 적용하지 않음`
    : `목표수익률은 장기 은퇴자산 기준: 단기 자금에 적용하지 않음`,
  "기존 보유자산은 매도 시점 평가손익에 좌우돼 미포함 (IPS 상 국내 반도체주 비중이 큼)",
  "연금계좌는 연금저축 단독 한도 600만원을 채운 뒤 나머지를 IRP 로 배분",
  // 화면 금액을 만원 단위로 반올림하므로 유도는 여기서 들고 있는다.
  ...(plan.pensionManwon > 0
    ? [
        `연금 세액공제 = 연금 배분 ${plan.pensionManwon.toLocaleString()}만원 × ${(plan.pensionRate * 100).toFixed(1)}% = ${(plan.pensionManwon * plan.pensionRate).toFixed(1)}만원`,
      ]
    : []),
  `ISA 절감액은 잔액이 연 ${(ASSUMPTIONS.isaAssumedIncomeYield * 100).toFixed(1)}% 이자·배당을 낸다는 가정 (법정 수치 아님)`,
  /*
    "왜 3% 냐" 는 질문에 댈 것이 있어야 한다. 다른 상수는 조문 번호를 대면 되지만
    이 값만 시장 가정이라, 같은 시점의 실제 시장값을 나란히 적어 어림한 근거를
    남긴다. 안정 추구 비중에 가중하면 2.4% 근처가 나오므로 3% 는 다소 높은 쪽이다.
    자산군별 소득수익률이 붙으면 이 줄과 상수를 함께 걷어낸다.
  */
  "같은 시점 시장값: 국고채 3년 3.91%(2026-09-09) · 코스피 배당수익률 0.92%(2026-05)",
  `ISA 비과세 ${ASSUMPTIONS.isaGeneralTaxFreeManwon}만원(서민형 ${ASSUMPTIONS.isaSeogminTaxFreeManwon}만원)은 계약기간 통산에 한 번: 연 단위 화면이라 의무보유 ${ASSUMPTIONS.isaMandatoryHoldingYears}년으로 나눠 반영`,
  "계좌 내 손익 통산·만기까지의 과세이연은 미반영: 둘 다 절감액을 키우는 쪽이라 이 값은 보수적",
  "국내 상장주식 매매차익은 원래 비과세라 ISA 실익은 이보다 작을 수 있음",
  "세액공제는 산출세액을 넘을 수 없으나 그 한도는 미반영: 낼 세금이 적으면 과대계산",
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
  needYears: number;
  /** IPS 목표수익률(%) — 화면 문구가 IPS 조율기 값을 따라가야 한다. */
  targetReturnPct: number;
  /** IPS 투자기간(년) */
  horizonYears: number;
  /**
   * 필요 금액·시점의 근거 문장. LLM 이 상담 전사·IPS 를 읽어 만드는 값이며 지금은
   * 시연 대역이 들어온다. 비어 있으면(상담 전 고객) 줄을 그리지 않는다 — 빈 상자만
   * 남으면 근거가 있는 것처럼 보이면서 정작 아무것도 없는 상태가 된다.
   */
  narrative?: ContributionNarrative | null;
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
  needYears,
  targetReturnPct,
  horizonYears,
  narrative,
}: Props) {
  const sliderMax = Math.min(plan.pension.headroomManwon, budgetManwon);

  return (
    /*
      grow·justify-between — 절세 제안 탭이 절세 효과 탭 높이에 맞춰 늘어나면, 늘어난 몫의
      절반을 이 상자가 받아 머리줄·슬라이더·AI 코멘트·가정 줄 사이에 고르게 나눈다.
    */
    <div className="flex grow flex-col justify-between rounded-xl border p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-[13px] font-extrabold">
          연 납입여력 {fmt(budgetManwon)}만원
        </p>
        <span className="text-[11px] font-semibold text-muted-foreground">
          연금은 {plan.pension.lockupYears}년 뒤, 만 55세부터 받을 수 있습니다
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-center">
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

        {/*
          "3년 뒤 쓸 수 있는 돈" 카드를 뺐다. 고객이 알고 싶은 것은 목표 시점에
          되느냐 안 되느냐이지 얼마가 쌓이느냐가 아니고, 그 결론은 아래 AI 상자가
          한 줄로 말한다. 카드가 빠진 만큼 슬라이더가 넓어져 눈금이 잘 읽힌다.
        */}
        <div className="lg:w-[220px]">
          <div className="rounded-lg border border-brand/20 bg-brand/5 px-3 py-2">
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
        </div>
      </div>

      {/*
        판정과 코멘트를 한 상자에 담는다. 둘 다 LLM 이 쓴 문장이라 출처가 같은데
        따로 떨어져 있으면 어느 것이 사람이 정한 문구이고 어느 것이 AI 가 쓴 것인지
        화면에서 알 수 없다.

        색은 하나로 둔다. 슬라이더를 미는 동안 파랑↔빨강이 오가면 값이 바뀌는 것보다
        색이 먼저 눈에 들어와 읽기가 어렵고, 파랑은 이 화면에서 이미 "좋다" 는 뜻을
        갖고 있어(절세액·배지) 판정이 아닌 것에 쓰면 뜻이 겹친다. 결론은 문장이
        말한다 — 색은 "여기는 AI 가 쓴 자리" 만 말하면 된다.
      */}
      {narrative && (
        <div className="mt-4 rounded-lg border border-[#F5A623]/25 bg-muted/50 px-3.5 py-3">
          <div className="flex gap-1.5">
            {/*
              아이콘만 색을 준다. 상자 자체는 회색이라 판정의 좋고 나쁨을 말하지
              않고, 노란 별과 옅은 테두리가 "AI 가 쓴 자리" 라는 것만 표시한다.
            */}
            <Sparkles className="mt-[3px] size-3 shrink-0 text-[#F5A623]" />
            <div className="min-w-0">
              {/*
                굵은 첫 줄은 "AI 코멘트" 로 고정한다. 판정 문장을 제목 자리에 두면
                슬라이더를 밀 때마다 제목이 바뀌어 상자 자체가 흔들려 보이고, 지금은
                문장이 실시간으로 다시 쓰이는 것도 아니다(값만 갈아 끼운다). 고정된
                라벨은 "여기부터는 AI 가 쓴 말" 이라는 한 가지만 말한다.
              */}
              <p className="text-[13px] font-extrabold text-foreground">
                AI 코멘트
              </p>
              <p className="mt-0.5 text-[12px] font-semibold leading-relaxed text-foreground/80">
                {narrative.verdict}. {narrative.detail}
              </p>
              <p className="mt-1.5 text-[11px] font-semibold leading-relaxed text-muted-foreground">
                {narrative.comment}
              </p>
            </div>
          </div>
        </div>
      )}

      {/*
        가정·한계는 여덟 줄이나 되는데 전부 펼쳐 두면 판정 문구를 덮는다.
        가이드 토글과 같은 방식으로 접는다 — 항상 보이는 한 줄에 가장 큰 세 가지를
        적고, 나머지는 hover 로 편다. 화면에서 근거가 사라지지는 않는다.
      */}
      <HelpTooltip text={ASSUMPTION_LINES(plan, needYears, targetReturnPct, horizonYears)} wide>
        <p className="mt-3 flex items-center gap-1 text-[10px] font-semibold text-muted-foreground">
          <CircleHelp className="size-3 shrink-0" />
          납입 원금만 계산 · 운용수익·산출세액 한도 미반영 · ISA 절감액은 가정 포함
        </p>
      </HelpTooltip>
    </div>
  );
}
