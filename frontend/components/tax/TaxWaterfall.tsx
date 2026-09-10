"use client";

import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import HelpTooltip from "@/components/common/HelpTooltip";
import {
  deriveTaxFlowRows,
  type TaxFlowBreakdown,
  type TaxFlowInput,
} from "@/lib/taxPlan";
import { TAX_EFFECT } from "@/lib/mockData";
import { ASSUMPTIONS } from "@/lib/taxAccounts";
import type { StressTaxHeadline, TaxWaterfallResponse } from "@/lib/api";

// 현재(회색) / 포폴A(원래 파랑) / 절세제안(약간 밝은 파랑)
const AFTER_TAX_COLORS = ["#AEB5BD", "#0064FF", "#3D8BFF"];
const TAX_COLORS = ["#F04452", "#F4A8AE", "transparent"];
/** 프론트 계산 흐름 — 3행 모두 세금이 있으므로 마지막을 transparent 로 두지 않는다. */
const FLOW_TAX_COLORS = ["#F04452", "#F04452", "#F4A8AE"];
/** 연금 세액공제. 근로소득세에서 돌려받는 돈이라 금융소득세(빨강)와 세목이 달라 색을 나눈다. */
const CREDIT_COLOR = "#16B47A";

/*
  머리말 분해 줄에 쓰는 부호 표기. 세 항이 그대로 더해져 금융소득이 되므로
  각 항의 부호는 "금융소득에 얼마를 더하고 빼는가"를 뜻한다 — 전환 세금은
  나가는 돈이라 음수로 적힌다.
*/
const signed = (v: number) =>
  `${v >= 0 ? "+" : "−"}${Math.abs(v).toLocaleString()}`;

/** 만원 값 표기. 1억 미만을 "0.04억"으로 적으면 읽히지 않는다. */
const money = (manwon: number) =>
  manwon >= 10000 ? `${(manwon / 10000).toFixed(2)}억` : `${Math.round(manwon).toLocaleString()}만`;

/**
 * 프론트 계산 흐름 — 위에서 고른 포트폴리오와 절세 제안을 그대로 잇는다.
 *
 * 세 단계가 서로 다른 말을 한다.
 *   현재 → 제안   수익이 늘고 **세금도 같이 는다**. 전환은 절세가 아니다.
 *   제안 → +절세  금융소득세가 줄고(ISA), 근로소득세에서 환급이 들어온다(연금).
 *
 * 연금 세액공제는 **근로소득세** 환급이라 금융소득세 막대에서 뺄 수 없다. 뺐다가는
 * 세금(150만)보다 절감(155만)이 커져 음수가 난다. 별도 조각으로 오른쪽에 붙인다 —
 * 세목은 안 섞이면서 "손에 들어오는 돈"이라는 한 줄기로 읽힌다.
 */
/*
  입력 타입은 lib/taxPlan.ts 가 갖는다 — 리포트도 같은 값을 그리므로 한 곳에만
  두어야 두 그림이 갈리지 않는다. 종전 이름은 쓰던 곳이 있어 별칭으로 남긴다.
*/
export type PortfolioFlowInput = TaxFlowInput;

interface Props {
  /**
   * POST /portfolio/calculate 응답의 portfolio.tax.waterfall — 최우선.
   * savingManwon: saved_vs_current / 10000 (최적화 전후 차이 행 계산용)
   */
  waterfallData?: { waterfall: TaxWaterfallResponse; savingManwon: number } | null;
  /** stressed_tax.headline + total_asset(억원) — waterfallData 없을 때 폴백 */
  liveHeadline?: StressTaxHeadline | null;
  liveAumEokwon?: number | null;
  /** 백엔드 값이 없을 때 쓰는 프론트 계산 입력. */
  flow?: PortfolioFlowInput | null;
}

/**
 * 세금 흐름 비교 — 절세 전/후 세금·세후수익 가로 누적 바.
 * liveHeadline 제공 시 API 실데이터 사용, 없으면 mock 폴백.
 */
export default function TaxWaterfall({
  waterfallData,
  liveHeadline,
  liveAumEokwon,
  flow,
}: Props) {
  let data: {
    name: string;
    afterTax: number;
    tax: number;
    /** 막대에 그릴 세금 길이. 세금이 세후 수익의 1/5 수준이라 실제 비율로 그리면
     *  80만과 150만의 차이가 몇 px 로 뭉개진다. 길이만 늘리고 라벨은 실제 값을
     *  쓰며, 확대했다는 사실을 차트 아래에 적는다. */
    taxPlot?: number;
    refund?: number;
  }[];
  /** 세금 막대를 몇 배로 늘려 그렸는지. 1 이면 실제 비율 그대로다. */
  let taxScale = 1;
  let totalSavingManwon: number;
  let pretaxLabel: string;
  let totalLabel: string;
  let domainMax: number;
  /*
   * 총액을 세목으로 쪼갠 줄. 금융소득세에서 아낀 돈과 근로소득세에서 돌려받는
   * 돈은 다른 세목인데 합계만 적으면 한 덩어리로 읽힌다. 세금이 얼마나 늘었는지도
   * 이 줄에서만 보인다 — 막대는 세후 기준이라 증가분이 이미 안에 녹아 있다.
   */
  /*
   * 총액을 세목으로 쪼갠 줄. 금융소득세에서 아낀 돈과 근로소득세에서 돌려받는
   * 돈은 다른 세목인데 합계만 적으면 한 덩어리로 읽힌다. 세금이 얼마나 늘었는지도
   * 이 줄에서만 보인다 — 막대는 세후 기준이라 증가분이 이미 안에 녹아 있다.
   */
  let breakdown: TaxFlowBreakdown | null = null;

  if (waterfallData) {
    // /portfolio/calculate tax.waterfall 실데이터
    const wf = waterfallData.waterfall;
    const grossManwon    = Math.round(wf.gross_return / 10000);
    const afterTaxManwon = Math.round(wf.after_tax / 10000);
    const actualTax      = grossManwon - afterTaxManwon;           // 실제 납부 세액(만원)
    const baselineTax    = actualTax + waterfallData.savingManwon; // 전략 없을 때 예상 세액
    const baselineAfter  = grossManwon - baselineTax;
    totalSavingManwon = waterfallData.savingManwon;
    pretaxLabel = `세전 총수익 ${grossManwon.toLocaleString()}만원`;
    totalLabel = "연간 절세 효과";
    domainMax = Math.max(grossManwon, afterTaxManwon + actualTax) * 1.15;
    data = [
      { name: "전략 전",       afterTax: baselineAfter,  tax: baselineTax },
      { name: "절세 전략 적용", afterTax: afterTaxManwon, tax: actualTax  },
    ];
  } else if (liveHeadline != null && liveAumEokwon != null && liveAumEokwon > 0) {
    // stress-metrics headline 폴백
    const aumManwon = liveAumEokwon * 10000;
    const beforeAfterTax = Math.round(liveHeadline.after_tax_return_before * aumManwon);
    const afterAfterTax  = Math.round(liveHeadline.after_tax_return_after  * aumManwon);
    const beforeTax = Math.round(liveHeadline.tax_amount_before / 10000);
    const afterTax  = Math.round(liveHeadline.tax_amount_after  / 10000);
    totalSavingManwon = Math.round(liveHeadline.annual_tax_saving / 10000);
    const pretaxManwon = beforeAfterTax + beforeTax;
    pretaxLabel = `세전 총수익 ${pretaxManwon.toLocaleString()}만원`;
    totalLabel = "연간 절세 효과";
    domainMax = Math.max(pretaxManwon, afterAfterTax + afterTax) * 1.15;
    data = [
      { name: "현재 포트폴리오", afterTax: beforeAfterTax, tax: beforeTax },
      { name: "절세 제안 적용",  afterTax: afterAfterTax,  tax: afterTax  },
    ];
  } else if (flow && flow.aumManwon > 0) {
    // 막대와 분해 줄은 lib/taxPlan.ts 가 만든다 — 리포트도 같은 값을 그린다.
    const derived = deriveTaxFlowRows(flow);
    const rows = derived.rows;

    // 가장 큰 세금 막대가 가장 긴 세후 막대의 이만큼을 차지하도록 늘린다.
    const TAX_TARGET_SHARE = 0.32;
    const maxAfter = Math.max(...rows.map((r) => r.afterTax));
    const maxTax = Math.max(...rows.map((r) => r.tax));
    taxScale =
      maxTax > 0 ? Math.max((maxAfter * TAX_TARGET_SHARE) / maxTax, 1) : 1;
    data = rows.map((r) => ({ ...r, taxPlot: r.tax * taxScale }));

    totalSavingManwon = derived.totalSavingManwon;
    pretaxLabel = derived.pretaxLabel;
    totalLabel = derived.totalLabel;
    breakdown = derived.breakdown;
    domainMax =
      Math.max(...data.map((d) => d.afterTax + (d.taxPlot ?? 0) + (d.refund ?? 0))) *
      1.1;
  } else {
    const { rows, pretaxLabel: pl, totalLabel: tl, totalSavingManwon: ts } = TAX_EFFECT.flow;
    data = rows.map((r, i) => ({
      name: i === 1 ? "제안 포트폴리오" : r.label,
      afterTax: r.afterTaxManwon,
      tax: r.taxManwon,
    }));
    totalSavingManwon = ts;
    pretaxLabel = pl;
    totalLabel = tl;
    domainMax = 27000;
  }

  const isLiveData =
    waterfallData != null || (liveHeadline != null && liveAumEokwon != null) || flow != null;
  const colors = flow
    ? { after: AFTER_TAX_COLORS, tax: FLOW_TAX_COLORS }
    : isLiveData
      ? { after: ["#AEB5BD", "#0064FF"], tax: ["#F04452", "#F4A8AE"] }
      : { after: AFTER_TAX_COLORS, tax: TAX_COLORS };

  /**
   * 막대 오른쪽에 세금·세액공제를 적는다.
   *
   * 두 조각 모두 폭이 좁아 안에 넣으면 글자가 잘린다(세금은 세후 수익의 1/5,
   * 세액공제는 확대도 안 한 원래 크기). 조각을 더 키우면 비율 왜곡만 커지므로
   * 숫자를 밖으로 뺀다. 스택 마지막 Bar 에 붙여 값이 0 인 행에서도 스택 끝
   * 좌표를 받는다.
   */
  // recharts 의 LabelList content 는 x·y·width 를 string | number 로 넘긴다.
  const num = (v: unknown) => (typeof v === "number" ? v : Number(v) || 0);
  const RowSummary = (props: {
    x?: string | number;
    y?: string | number;
    width?: string | number;
    height?: string | number;
    index?: number;
  }) => {
    const row = data[props.index ?? -1];
    if (!row) return null;
    const tx = num(props.x) + num(props.width) + 8;
    const cy = num(props.y) + num(props.height) / 2;
    const hasRefund = (row.refund ?? 0) > 0;
    return (
      <text x={tx} y={cy} dominantBaseline="middle" fontSize={11} fontWeight={800}>
        <tspan x={tx} dy={hasRefund ? -6 : 0} fill="#F04452">
          세금 {row.tax.toLocaleString()}만
        </tspan>
        {hasRefund && (
          <tspan x={tx} dy={13} fill={CREDIT_COLOR}>
            세액공제 +{row.refund!.toLocaleString()}만
          </tspan>
        )}
      </text>
    );
  };

  const chartHelp = [
    "막대 전체 길이 = 세전 수익 (세후 수익 + 금융소득세)",
    "전환은 절세가 아니라 수익 증가 — 수익이 커지면 세금도 는다",
    "ISA 절감은 금융소득세를 직접 깎아 세후 수익 쪽으로 넘어간다",
    "세액공제는 근로소득세 환급이라 세목이 달라 막대 밖에 붙인다",
    ...(breakdown
      ? [
          `전환으로 금융소득세가 ${breakdown.switchTaxManwon.toLocaleString()}만원 늘고 ISA 가 ${breakdown.isaCutManwon.toLocaleString()}만원을 도로 깎는다`,
          /*
            그 ISA 몫만 법정 수치가 아니라 시장 가정에서 나온다. 이 툴팁에도
            18만원이 적히므로 근거가 여기 없으면 이 탭만 열어 본 사람에게는
            출처가 보이지 않는다. 납입 배분 화면의 같은 줄과 문구를 맞춘다.
          */
          `그 ISA 몫은 잔액이 연 ${(ASSUMPTIONS.isaAssumedIncomeYield * 100).toFixed(1)}% 이자·배당을 낸다는 가정 (법정 수치 아님)`,
          "같은 시점 시장값 — 국고채 3년 3.91%(2026-09-09) · 코스피 배당수익률 0.92%(2026-05)",
        ]
      : []),
    ...(taxScale > 1.05
      ? [
          `금융소득세 막대는 보이도록 ${taxScale.toFixed(1)}배로 늘려 그렸다 (적힌 금액은 실제 값)`,
        ]
      : []),
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/*
        막대 길이를 손본 사실과 세목 구분을 가이드 툴팁에 둔다. 화면에 늘 띄우면
        차트보다 주석이 길어지는데, 근거 없이 지우면 2배로 늘려 그린 막대에 아무
        표시가 없게 된다. 가이드를 켜면 나온다.
      */}
      <HelpTooltip text={flow ? chartHelp : []} placement="bottom">
        <p className="mb-2 flex items-center gap-1.5 text-[13px] font-extrabold">
          세금 흐름 비교
          <span className="text-[13px] font-semibold text-muted-foreground">
            {pretaxLabel}
          </span>
        </p>
      </HelpTooltip>
      <div className="mb-2 flex items-center justify-between gap-2 rounded-lg bg-muted/60 px-2.5 py-1.5">
        <div className="min-w-0">
          <span className="text-[12px] font-semibold text-muted-foreground">
            {totalLabel}
          </span>
          {breakdown && (
            /*
              세목을 나눠 적는다. 왼쪽은 금융소득세를 덜 내서 남는 돈, 오른쪽은
              근로소득세에서 돌려받는 돈이다. 괄호 안의 세전·세금은 왼쪽 금액이
              어떻게 나왔는지를 보인다 — 더 벌면 세금도 는다는 사실이 여기서만
              드러난다(막대는 세후 기준이라 증가분이 이미 녹아 있다).
            */
            <div className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-[11px] font-semibold leading-tight">
              <span className="text-brand-dark">
                금융소득 +{breakdown.financialManwon.toLocaleString()}만
              </span>
              <span className="text-muted-foreground">
                {/*
                  전환이 세금을 줄이는 안도 있다(채권 비중이 늘면 그렇다).
                  그때 "전환 세금 +20" 은 세금이 20 늘었다는 말로 읽히므로
                  말 자체를 바꾼다. 부호는 금융소득에 더하고 빼는 몫이다.
                */}
                (세전 {signed(breakdown.pretaxGainManwon)} ·{" "}
                {breakdown.switchTaxManwon >= 0 ? "전환 세금 " : "전환 세금 절감 "}
                {signed(-breakdown.switchTaxManwon)} · ISA 절감{" "}
                {signed(breakdown.isaCutManwon)})
              </span>
              <span className="text-muted-foreground/60">·</span>
              <span style={{ color: CREDIT_COLOR }}>
                근로소득세 환급 +{breakdown.refundManwon.toLocaleString()}만
              </span>
            </div>
          )}
        </div>
        <span
          className={`shrink-0 whitespace-nowrap text-[13px] font-extrabold tabular-nums ${
            flow ? "text-brand-dark" : "text-up"
          }`}
        >
          +{totalSavingManwon.toLocaleString()}만원
        </span>
      </div>

      {/*
        고정 높이 대신 상한·하한 사이에서 남거나 모자란 높이를 흡수한다. 좌측
        사이드바가 행 높이를 정하므로 이쪽이 따라 줄어야 카드가 그 아래로
        비어져 나오지 않는다. 상한은 종전 높이라 더 커지지는 않는다.
      */}
      <div className={flow ? "min-h-24 max-h-40 flex-1" : "h-32"}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: flow ? 108 : 52, bottom: 0, left: 0 }}
            barSize={flow ? 40 : 28}
          >
            <XAxis type="number" hide domain={[0, domainMax]} />
            <YAxis
              type="category"
              dataKey="name"
              width={90}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fontWeight: 800, fill: "#4E5968" }}
            />
            <Bar dataKey="afterTax" stackId="flow" isAnimationActive={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={colors.after[i] ?? "#3D8BFF"} radius={10} />
              ))}
              <LabelList
                dataKey="afterTax"
                position="insideLeft"
                formatter={(v: unknown) => `세후 ${money(Number(v))}`}
                style={{ fontSize: 12, fontWeight: 800, fill: "#fff" }}
              />
            </Bar>
            {/*
              환급을 세금보다 앞에 쌓는다. 세금 막대는 세 행 모두 값이 있어 스택의
              마지막에 두면 오른쪽 라벨이 항상 스택 끝 좌표를 받는다. 환급을 마지막에
              두면 값이 0 인 행에서 라벨 자체가 렌더되지 않고, 남은 하나가 다른 행의
              값을 엉뚱한 자리에 찍는다.

              읽기에도 이 순서가 낫다 — 손에 남는 돈(세후·환급)이 붙어 있고 나가는
              돈(세금)이 끝에 온다.
            */}
            {flow && (
              <Bar dataKey="refund" stackId="flow" isAnimationActive={false}>
                {data.map((_, i) => (
                  <Cell key={i} fill={CREDIT_COLOR} radius={10} />
                ))}
              </Bar>
            )}
            {/*
              세금 막대. flow 에서는 taxPlot(확대한 길이)으로 그리고 숫자는 막대 밖
              RowSummary 가 적는다. 실제 비율로는 세후 수익의 1/5 이라 80만과 150만의
              차이가 몇 px 로 뭉개지고, 조각 안에 글자를 넣으면 잘린다.
            */}
            <Bar
              dataKey={flow ? "taxPlot" : "tax"}
              stackId="flow"
              isAnimationActive={false}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={colors.tax[i] ?? "transparent"} radius={10} />
              ))}
              {flow ? (
                <LabelList dataKey="tax" content={RowSummary} />
              ) : (
                <LabelList
                  dataKey="tax"
                  position="right"
                  formatter={(v: unknown) =>
                    Number(v) > 0 ? `${Number(v).toLocaleString()}만` : ""
                  }
                  style={{ fontSize: 12, fontWeight: 800, fill: "#F04452" }}
                />
              )}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className={`flex flex-wrap gap-x-3 gap-y-1 ${flow ? "mt-2" : "mt-8"}`}>
        <LegendDot color="#0064FF" label="세후 수익" />
        <LegendDot color="#F04452" label={flow ? "금융소득세" : "세금"} />
        {flow && (
          <LegendDot color={CREDIT_COLOR} label="세액공제" />
        )}
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[12px] font-bold text-muted-foreground">
      <span
        className="size-2 rounded-[3px]"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
