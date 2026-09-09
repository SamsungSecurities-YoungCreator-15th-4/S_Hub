"use client";

import { Slider } from "@/components/ui/slider";
import { ASSUMPTIONS, type AllocationPlan } from "@/lib/taxAccounts";

const fmt = (n: number) => Math.round(n).toLocaleString("ko-KR");
/**
 * 절감액 표기(만원). 148.5만원을 149만원으로 반올림하면 세액공제 한도 900만 × 16.5%
 * 라는 근거가 화면에서 사라진다. 소수 첫째 자리는 살리고 .0 만 떨어뜨린다.
 */
const fmtSaving = (n: number) => {
  const r = Math.round(n * 10) / 10;
  const whole = Math.trunc(r);
  const frac = Math.round(Math.abs(r - whole) * 10);
  return frac === 0 ? whole.toLocaleString("ko-KR") : `${whole.toLocaleString("ko-KR")}.${frac}`;
};

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
}

/**
 * 연 납입여력을 연금계좌와 ISA 에 어떻게 나눌 것인가.
 *
 * 세액공제만 보면 연금 한도를 꽉 채우는 것이 답이다. 그런데 연금은 만 55세까지
 * 잠기고, 이 고객은 3년 뒤 전세 보증금이 필요하다. 한쪽을 최대화하면 다른 쪽이
 * 무너지는 구조라 슬라이더 하나로 양쪽을 동시에 보여준다.
 *
 * 유동성은 **누적 납입액**만 센다. 기존 보유자산은 넣지 않는다 — 매도 시점의
 * 평가손익에 좌우되는 값이라 "3년 뒤 확보된다"고 단정할 수 없기 때문이다.
 * 이 고객은 IPS 상 국내 반도체주 비중이 커서 특히 그렇다.
 */
export default function TaxAllocation({
  plan,
  budgetManwon,
  pensionRequestManwon,
  onPensionRequestChange,
  needManwon,
  needYears,
}: Props) {
  const sliderMax = Math.min(plan.pension.headroomManwon, budgetManwon);
  const shortfall = Math.max(needManwon - plan.liquidAtTargetManwon, 0);

  // 필요액을 지키면서 연금에 넣을 수 있는 최대치. (budget − pension) × years ≥ need
  const maxPensionKeepingNeed = Math.max(
    Math.floor((budgetManwon - needManwon / Math.max(needYears, 1)) / 10) * 10,
    0,
  );

  return (
    <div className="rounded-xl border p-3.5">
      <div className="flex items-baseline justify-between">
        <p className="text-[13px] font-extrabold">
          연 납입여력 {fmt(budgetManwon)}만원을 어디에 넣을까
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

      {/* 판정 */}
      <div
        className={`mt-3 rounded-lg px-3 py-2 text-[12px] font-semibold leading-relaxed ${
          shortfall > 0 ? "bg-[#FEECEE]" : "bg-brand/5"
        }`}
      >
        {shortfall > 0 ? (
          <>
            <b className="text-up">전세 자금이 {fmt(shortfall)}만원 모자랍니다.</b>{" "}
            연금 납입을 <b>{fmt(maxPensionKeepingNeed)}만원</b>으로 낮추면 {needYears}
            년 뒤 {fmt(needManwon)}만원이 맞춰집니다. 세액공제는{" "}
            {fmtSaving(plan.pensionSavingManwon)}만원에서{" "}
            {fmtSaving(maxPensionKeepingNeed * plan.pensionRate)}만원으로 줄어듭니다 —
            한도를 꽉 채우는 것이 이 고객에게는 답이 아닙니다.
          </>
        ) : (
          <>
            <b className="text-brand-dark">
              {needYears}년 뒤 {fmt(needManwon)}만원을 확보합니다.
            </b>{" "}
            연금 한도까지는 {fmt(sliderMax - plan.pensionManwon)}만원 남았지만, 더
            넣으면 전세 자금이 모자랍니다. 이 고객의 상한은{" "}
            <b>{fmt(maxPensionKeepingNeed)}만원</b>입니다.
          </>
        )}
      </div>

      <p className="mt-2 text-[10px] font-semibold leading-relaxed text-muted-foreground">
        {needYears}년 뒤 가용액은 <b>납입 원금만</b> 센 값입니다 — 운용수익을 더하지
        않았습니다. 목표수익률 {"7%"}는 22년짜리 은퇴자산에 대한 것이고, {needYears}년
        뒤 써야 할 돈을 그 수익률로 미리 세면 시장이 나빴을 때 계획이 무너집니다.
        기존 보유자산도 매도 시점의 평가손익에 좌우되므로 확보된 것으로 보지
        않았습니다(IPS 상 국내 반도체주 비중이 큼). 연금계좌 배분은 연금저축 단독
        한도 600만원을 채운 뒤 나머지를 IRP 로 보낸 것입니다 — 연금저축에만 900만원을
        넣으면 600만원까지만 공제됩니다. ISA 절감액은 계좌 잔액이 연{" "}
        {(ASSUMPTIONS.isaAssumedIncomeYield * 100).toFixed(1)}%의 이자·배당을 낸다는{" "}
        <b>가정</b>이며 법정 수치가 아닙니다(국내 상장주식 매매차익은 원래 비과세라
        실제 실익은 이보다 작을 수 있습니다). 납입한도·세액공제율·의무보유기간·비과세
        한도는 2026년 법정 기준입니다.
      </p>
    </div>
  );
}
