"use client";

import { CALC_UNITS, type CalcUnitId } from "@/lib/assetMapping";
import { type CurrentWeightsInput, useDashboardStore } from "@/lib/store";

type FieldId = CalcUnitId | "cash";

const GROUPS: { group: string; ids: FieldId[] }[] = [
  { group: "주식", ids: CALC_UNITS.filter((u) => u.group === "주식").map((u) => u.id) },
  { group: "채권", ids: CALC_UNITS.filter((u) => u.group === "채권").map((u) => u.id) },
  {
    group: "대체·현금",
    ids: [...CALC_UNITS.filter((u) => u.group === "대체").map((u) => u.id), "cash"],
  },
];

const LABELS: Record<FieldId, string> = {
  ...Object.fromEntries(CALC_UNITS.map((u) => [u.id, u.label])),
  cash: "현금",
} as Record<FieldId, string>;

function sum(input: CurrentWeightsInput): number {
  return Object.values(input).reduce(
    (acc, v) => acc + (typeof v === "number" && Number.isFinite(v) ? v : 0),
    0,
  );
}

/**
 * 고객이 지금 실제로 들고 있는 자산 비중 입력 — "현재 포트폴리오"의 실데이터 기준선.
 * 미입력 시 백엔드는 현금 100%로 계산한다(중앙 대시보드 "현재" 카드·절세 효과·
 * 스트레스 테스트가 전부 이 값을 공유하므로, 여기 값이 세 화면 모두에 반영된다).
 */
export default function CurrentPortfolioInput() {
  const { currentWeightsInput, setCurrentWeightsInput } = useDashboardStore();
  const total = sum(currentWeightsInput);
  const hasAnyInput = total > 0;

  const handleChange = (id: FieldId, raw: string) => {
    const cleaned = raw.replace(/[^0-9.]/g, "");
    if (cleaned === "") {
      setCurrentWeightsInput({ [id]: undefined });
      return;
    }
    const parsed = Number(cleaned);
    setCurrentWeightsInput({ [id]: Number.isFinite(parsed) ? parsed : undefined });
  };

  return (
    <div className="rounded-xl border p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[14px] font-bold">현재 보유 자산 비중</p>
        {hasAnyInput && (
          <button
            type="button"
            onClick={() => setCurrentWeightsInput(Object.fromEntries(
              [...CALC_UNITS.map((u) => u.id), "cash"].map((id) => [id, undefined]),
            ))}
            className="text-[11px] font-semibold text-muted-foreground hover:text-foreground"
          >
            초기화
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2">
        {GROUPS.map(({ group, ids }) => (
          <div key={group} className="col-span-2">
            <p className="mb-1 text-[10px] font-bold text-muted-foreground">{group}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              {ids.map((id) => (
                <label key={id} className="flex items-center justify-between gap-1">
                  <span className="text-[12px] font-semibold text-foreground/80">
                    {LABELS[id]}
                  </span>
                  <span className="flex items-center gap-0.5">
                    <input
                      type="text"
                      inputMode="decimal"
                      value={currentWeightsInput[id] ?? ""}
                      onChange={(e) => handleChange(id, e.target.value)}
                      placeholder="0"
                      className="h-6 w-12 rounded-md border border-input bg-white px-1.5 text-right text-[12px] font-bold tabular-nums outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    />
                    <span className="text-[11px] text-muted-foreground">%</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-muted pt-2">
        <span className="text-[11px] font-semibold text-muted-foreground">합계</span>
        <span
          className={`text-[13px] font-extrabold tabular-nums ${
            !hasAnyInput
              ? "text-muted-foreground"
              : Math.abs(total - 100) < 0.5
                ? "text-brand-dark"
                : "text-up"
          }`}
        >
          {total.toLocaleString()}%
        </span>
      </div>
    </div>
  );
}
