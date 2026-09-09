"use client";

import {
  CALC_UNITS,
  type CalcUnitId,
  isCurrentWeightsInputValid,
  sumCurrentWeightsInput,
} from "@/lib/assetMapping";
import { useDashboardStore } from "@/lib/store";

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

// assetMapping.ts의 TODO(팀 확정 필요) — 11종 계산단위 중 3개는 백엔드 자산군과
// 라벨이 어긋난 채로 매핑돼 있다(mapFrontendWeightsToBackend 참조). 계좌 배치
// 패널(AccountAllocation 등)에서는 이 값이 항상 표시 전용이라 무해했지만, 여기서는
// PB가 직접 입력한 값이 그대로 계산에 들어가므로 최소한 실제 계산에 쓰이는 대리자산을
// 밝혀둔다. 매핑이 확정되면 이 표기는 제거한다.
const PROXY_NOTE: Partial<Record<FieldId, string>> = {
  emergingEquity: "나스닥(QQQ) 대리",
  overseasBond: "달러인덱스 대리",
  infraFund: "원자재(DBC) 대리",
};

/**
 * 고객이 지금 실제로 들고 있는 자산 비중 입력 — "현재 포트폴리오"의 실데이터 기준선.
 * 미입력 시 백엔드는 현금 100%로 계산한다(중앙 대시보드 "현재" 카드·절세 효과·
 * 스트레스 테스트가 전부 이 값을 공유하므로, 여기 값이 세 화면 모두에 반영된다).
 *
 * 합계가 100이 아니면 분석하기를 막는다(Sidebar.tsx의 isCurrentWeightsInputValid
 * 게이트) — 백엔드가 조용히 100%로 재정규화해버리면 "화면 합계 ≠ 실제 계산에 쓰인
 * 비중"이 되어 추적성이 깨지기 때문에, 여기서 정직하게 막는 쪽을 택했다.
 */
export default function CurrentPortfolioInput() {
  const {
    currentWeightsInput,
    setCurrentWeightsInput,
    customWeightsInput,
    setCustomWeightsInput,
    weightsEditTarget,
    setWeightsEditTarget,
  } = useDashboardStore();

  const isCustom = weightsEditTarget === "custom";
  const weights = isCustom ? customWeightsInput : currentWeightsInput;
  const setWeights = isCustom ? setCustomWeightsInput : setCurrentWeightsInput;

  const total = sumCurrentWeightsInput(weights);
  const hasAnyInput = total > 0;
  const isValid = isCurrentWeightsInputValid(weights);

  const handleChange = (id: FieldId, raw: string) => {
    const cleaned = raw.replace(/[^0-9.]/g, "");
    if (cleaned === "") {
      setWeights({ [id]: undefined });
      return;
    }
    const parsed = Number(cleaned);
    setWeights({ [id]: Number.isFinite(parsed) ? parsed : undefined });
  };

  return (
    <div className="rounded-xl border p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[14px] font-bold">자산 비중</p>
        {hasAnyInput && (
          <button
            type="button"
            onClick={() => setWeights(Object.fromEntries(
              [...CALC_UNITS.map((u) => u.id), "cash"].map((id) => [id, undefined]),
            ))}
            className="text-[11px] font-semibold text-muted-foreground hover:text-foreground"
          >
            초기화
          </button>
        )}
      </div>

      {/*
        같은 폼으로 두 값을 편집한다. 왼쪽은 고객이 실제 보유한 사실이고 오른쪽은
        "이렇게 바꾸면?" 이라는 가정이라, 어느 쪽을 만지는 중인지 늘 보이게 한다.
        중앙 제안 카드의 세그먼트와 같은 상태를 쓰므로 양쪽이 함께 움직인다.
      */}
      <div className="mb-2.5 flex rounded-lg bg-muted p-0.5">
        {([
          { key: "current" as const, label: "현재 자산" },
          { key: "custom" as const, label: "사용자 정의" },
        ]).map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setWeightsEditTarget(key)}
            aria-pressed={weightsEditTarget === key}
            className={`flex-1 rounded-md py-1 text-[11px] font-bold transition-colors ${
              weightsEditTarget === key
                ? "bg-white text-brand-dark shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <p className="mb-2 text-[10.5px] font-medium leading-snug text-muted-foreground">
        {isCustom
          ? "현재 자산에서 복사한 값입니다. 조정해도 고객의 실제 보유는 그대로입니다."
          : "고객이 지금 실제로 들고 있는 비중입니다. 상담 기준선이 되므로 한 번만 입력합니다."}
      </p>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2">
        {GROUPS.map(({ group, ids }) => (
          <div key={group} className="col-span-2">
            <p className="mb-1 text-[10px] font-bold text-muted-foreground">{group}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              {ids.map((id) => {
                const proxyNote = PROXY_NOTE[id];
                return (
                  <label
                    key={id}
                    className="flex items-center justify-between gap-1"
                    title={proxyNote ? `계산상 ${proxyNote} 자산으로 반영됨 (자산 매핑 확정 전)` : undefined}
                  >
                    <span className="text-[12px] font-semibold text-foreground/80">
                      {LABELS[id]}
                      {proxyNote && <span className="text-up">*</span>}
                    </span>
                    <span className="flex items-center gap-0.5">
                      <input
                        type="text"
                        inputMode="decimal"
                        value={weights[id] ?? ""}
                        onChange={(e) => handleChange(id, e.target.value)}
                        placeholder="0"
                        className="h-6 w-12 rounded-md border border-input bg-card px-1.5 text-right text-[12px] font-bold tabular-nums outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      />
                      <span className="text-[11px] text-muted-foreground">%</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-muted pt-2">
        <span className="text-[11px] font-semibold text-muted-foreground">합계</span>
        <span
          className={`text-[13px] font-extrabold tabular-nums ${
            !hasAnyInput ? "text-muted-foreground" : isValid ? "text-brand-dark" : "text-down"
          }`}
        >
          {total.toLocaleString()}%
        </span>
      </div>
      {!isValid && (
        <p className="mt-1 text-[11px] font-semibold text-down">
          합계가 100%가 아닙니다. 맞춰야 분석하기를 실행할 수 있습니다.
        </p>
      )}
      <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
        * 자산 매핑 확정 전이라 신흥국주식·해외채권·인프라펀드는 각각 나스닥·달러인덱스·원자재로
        계산됩니다.
      </p>
    </div>
  );
}
