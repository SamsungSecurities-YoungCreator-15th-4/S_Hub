"use client";

import { TAX_EFFECT, PORTFOLIOS } from "@/lib/mockData";
import { toCalcUnitAllocation } from "@/lib/assetMapping";
import { useDashboardStore } from "@/lib/store";
import HelpTooltip from "@/components/common/HelpTooltip";
import { useViewedPortfolio } from "@/lib/viewedPortfolio";
import { useTaxPlan } from "@/lib/taxPlan";
import type { AccountSlot } from "@/lib/types";

/*
  두 계좌의 한도는 성격이 다르다.

    ISA   조특법 §91의18 ③5 — 2,000만원 × (1 + 가입 후 경과연수) − 누적 납입금액.
          해마다 2,000 씩 쌓이고 리셋되지 않는다. "올해 한도" 라는 것이 없어서,
          2년 묵힌 사람은 올해 6,000만원을 한 번에 넣을 수 있다.
    연금  소득세법 §59의3 — 세액공제 한도 연 900만원. 1월 1일에 리셋된다.

  한 축(0~2,000만원)에 나란히 그리고 있었다. 그래서 이월분이 쌓인 고객은 막대가
  축 끝에서 잘려 "한도 소진" 으로 보였다 — 같은 화면의 납입안 카드는 "잔여
  4,200만원" 이라고 적는데. 각자 자기 한도 대비 비율로 그린다. 금액은 옆에 적어
  잃지 않는다.
*/
const PENSION_ANNUAL_LIMIT_MAN = 900;

/*
  이 막대의 8,000만원이 어디서 나왔는지는 조문에만 있다. 화면 아래 한 줄은 "누적
  한도" 라고만 말하고 산식은 보여주지 않으므로, 근거는 가이드에 둔다.
*/
const ACCOUNT_HELP = (isaLimitManwon: number) => [
  `ISA 납입한도 = 2,000만원 × (1 + 가입 후 경과연수) − 누적 납입금액 (조특법 §91의18)`,
  "미사용분은 해마다 쌓인다 — 리셋되지 않는다",
  `총 납입한도 1억원 — 5년차에 닿고 그 뒤로는 늘지 않는다${
    isaLimitManwon >= 10000 ? " (이 고객이 그 자리다)" : ""
  }`,
  "인출해도 한도는 복원되지 않는다 — 넣었다 뺀 금액도 누적에 남는다",
  "연금계좌는 연 900만원 세액공제 한도 — 1월 1일에 리셋된다 (소득세법 §59의3)",
  "막대는 이미 납입한 금액 — 올해 배분안은 납입안 탭이 적는다",
  "전체 계좌 띠는 확정 대상 안의 자산 구성 — 제안을 조정하면 함께 바뀐다",
];

const ACCOUNT_META: Record<string, { name: string }> = {
  isa: { name: "ISA" },
  pension: { name: "연금저축 + IRP" },
};

interface AccountBar {
  key: string;
  name: string;
  usedManwon: number;
  limitManwon: number;
  /** 한도의 성격 — 누적인지 그 해 기준인지. 둘을 섞으면 숫자가 거짓이 된다. */
  basis: string;
  color: string;
}


/** ② 절세 계좌 배치 활용도 — 포트폴리오 구성 세그먼트 바 + ISA / 연금저축+IRP 바 차트 */
export default function AccountAllocation({
  accounts,
}: {
  accounts?: AccountSlot[];
}) {
  /*
   * store 의 portfolios 를 읽는다. mockData 상수를 읽고 있어서, PB 가 현재 보유
   * 비중을 입력해도(demoPortfolioCalc 의 withCurrentWeights) 이 막대만 따라오지
   * 않았다. 같은 화면의 도넛·스트레스는 store 를 읽는데 여기만 상수였다.
   */
  const portfolios = useDashboardStore((s) => s.portfolios);
  const helpMode = useDashboardStore((s) => s.helpMode);
  /*
   * 확정 대상 안을 따른다 — PB 가 제안 조정으로 비중을 손보면 이 막대도 같이
   * 움직여야 한다. PDF(PB·고객) 의 같은 막대도 같은 훅을 읽는다.
   */
  const { viewed } = useViewedPortfolio();
  const portfolio = viewed ?? portfolios[1] ?? PORTFOLIOS[1];
  /*
   * 11종 계산 단위를 그대로 쓴다. 6분류(toDisplayAllocation)는 세제 기준 묶음이라
   * 리츠·금·인프라펀드가 전부 "분리과세" 한 조각이 되고, 신흥국주식이 해외성장주에
   * 합쳐진다. 그 결과 바로 위 도넛과 리포트는 "해외성장주 9%" 인데 이 막대만
   * "해외성장주 12%" 라고 적혀, 같은 이름이 한 화면에서 다른 숫자를 말했다.
   * 도넛(PortfolioSection)·리포트(buildPdfAllocation)와 같은 축으로 맞춘다.
   */
  const allocation = toCalcUnitAllocation(portfolio.weights).filter(
    ({ weight }) => weight > 0,
  );

  /*
   * ISA 한도는 배분 계산이 들고 있는 누적 산식을 그대로 쓴다 — 납입안 카드가
   * 적는 잔여 한도와 늘 같은 값이어야 한다. 화면에서 따로 유도하면 두 탭이
   * 다른 한도를 말한다.
   */
  const { plan, customer } = useTaxPlan();

  const slot = (key: string) =>
    accounts?.find((a) => a.key === key) ??
    (() => {
      const fallback = TAX_EFFECT.accounts.find(
        (a) => a.name === ACCOUNT_META[key].name,
      );
      return fallback
        ? { key, usedManwon: fallback.used, limitManwon: fallback.limit }
        : null;
    })();

  const isaSlot = slot("isa");
  const pensionSlot = slot("pension");

  const isaUsed = isaSlot?.usedManwon ?? customer?.isaUsedManwon ?? 0;
  // 누적 한도 = 이미 넣은 돈 + 아직 넣을 수 있는 돈. 산식은 lib/taxAccounts.ts.
  // ⚠️ 백엔드 account_cards 가 붙으면 그쪽 한도가 이겨야 한다. 지금은 그 응답에
  //    누적 산식이 반영돼 있는지 확인할 수 없어 프론트 계산을 우선한다.
  const isaLimit = plan
    ? isaUsed + plan.isa.headroomManwon
    : (isaSlot?.limitManwon ?? 2000);
  const isaYears = customer?.isaYearsSinceOpen;

  const pensionUsed = pensionSlot?.usedManwon ?? customer?.pensionUsedManwon ?? 0;
  const pensionLimit = pensionSlot?.limitManwon ?? PENSION_ANNUAL_LIMIT_MAN;

  const bars: AccountBar[] = [
    {
      key: "isa",
      name: ACCOUNT_META.isa.name,
      usedManwon: isaUsed,
      limitManwon: isaLimit,
      basis:
        isaYears != null && isaYears > 0
          ? `가입 ${isaYears + 1}년차 누적`
          : "누적",
      color: "#0064FF",
    },
    {
      key: "pension",
      name: ACCOUNT_META.pension.name,
      usedManwon: pensionUsed,
      limitManwon: pensionLimit,
      basis: "올해",
      color: "#3D8BFF",
    },
  ];

  return (
    <div className="flex flex-col">
      {/*
        여는 자리는 제목 글자뿐이다 — 세금 흐름 비교·절세 제안 카드와 같은 규격이라,
        가이드를 켜면 설명이 붙은 자리가 화면 전체에서 같은 모양으로 보인다.
      */}
      <HelpTooltip text={ACCOUNT_HELP(isaLimit)} placement="bottom" className="w-fit" wide>
        <p className="mb-2 cursor-default text-[13px] font-extrabold">
          <span
            className={
              helpMode
                ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                : ""
            }
          >
            계좌 배치 활용도
          </span>
        </p>
      </HelpTooltip>

      {/* 전체 계좌 세그먼트 바 — YAxis width(72px) 기준 정렬, 2px 여백 */}
      <div className="mb-1 flex items-center">
        <span className="w-[72px] shrink-0 text-right text-[12px] font-extrabold text-[#4E5968]">
          전체 계좌
        </span>
        <div className="ml-[2px] mr-[16px] flex h-[12px] flex-1 overflow-hidden rounded-md">
          {allocation.map(({ label, weight, color }) => (
            <div
              key={label}
              style={{ width: `${weight}%`, backgroundColor: color }}
            />
          ))}
        </div>
      </div>

      {/* 세그먼트 범례 */}
      {/*
        6분류일 때는 한 줄이었지만 11종이면 두 줄이 된다. 아래 차트가 상한·하한
        사이에서 줄어 그만큼을 흡수하므로 카드 높이는 그대로다. 간격을 좁혀 두
        줄 안에 들어오게 한다.
      */}
      <div className="mb-2 ml-[74px] mr-[16px] flex flex-wrap gap-x-1.5 gap-y-0 leading-tight">
        {allocation.map(({ label, weight, color }) => (
          <span
            key={label}
            className="flex items-center gap-1 text-[11px] font-semibold text-muted-foreground"
          >
            <span
              className="inline-block size-1.5 rounded-[2px]"
              style={{ backgroundColor: color }}
            />
            {label} {weight}%
          </span>
        ))}
      </div>

      {/* ISA / 연금저축+IRP — 각자 자기 한도 대비 비율 */}
      {/* 흐름 차트와 같은 규칙 — 상한은 종전 높이, 모자라면 하한까지 줄어든다. */}
      {/* 막대가 납작해 보이지 않게 두께와 간격을 함께 준다. */}
      <div className="flex flex-col gap-3.5 py-1">
        {bars.map((bar) => {
          const pct =
            bar.limitManwon > 0 ? (bar.usedManwon / bar.limitManwon) * 100 : 0;
          return (
            <div key={bar.key} className="flex items-center">
              <span className="w-[72px] shrink-0 text-right text-[12px] font-extrabold leading-tight text-[#4E5968]">
                {bar.name}
              </span>
              <div className="ml-[10px] mr-[10px] h-[18px] flex-1 overflow-hidden rounded-md bg-[#E9EDF3]">
                <div
                  className="h-full rounded-md"
                  style={{
                    // 한도를 넘는 데이터가 와도 막대는 칸을 넘지 않는다. 숫자는 옆에 그대로 적힌다.
                    width: `${Math.min(Math.max(pct, 0), 100)}%`,
                    backgroundColor: bar.color,
                  }}
                />
              </div>
              <span className="shrink-0 whitespace-nowrap text-[12px] font-semibold tabular-nums text-muted-foreground">
                <b className="font-extrabold text-foreground">
                  {bar.usedManwon.toLocaleString()}
                </b>
                {" / "}
                {bar.limitManwon.toLocaleString()}만원
                <span className="ml-1 font-extrabold" style={{ color: bar.color }}>
                  {pct.toFixed(0)}%
                </span>
              </span>
            </div>
          );
        })}
      </div>

      {/*
        두 막대의 한도가 서로 다른 것을 재고 있다는 사실을 여기서 말한다. 한 줄로
        붙여 두지 않으면 8,000 과 900 이 같은 성격의 숫자로 읽힌다.
      */}
      <p className="mt-2 text-[11px] font-semibold leading-tight text-muted-foreground">
        ISA 는 {bars[0].basis} 한도 — 미사용분이 해마다 쌓인다 · 연금은 올해
        세액공제 한도
      </p>
    </div>
  );
}
