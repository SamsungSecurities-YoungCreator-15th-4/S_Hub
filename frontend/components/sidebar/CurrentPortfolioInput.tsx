"use client";

import {
  CALC_UNITS,
  type CalcUnitId,
  type CurrentWeightsInput,
  isCurrentWeightsInputValid,
  sumCurrentWeightsInput,
} from "@/lib/assetMapping";
import { isTrusted } from "@/lib/api/result";
import HelpTooltip from "@/components/common/HelpTooltip";
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

const ALL_FIELD_IDS: FieldId[] = [...CALC_UNITS.map((u) => u.id), "cash"];

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

type WeightTab = "current" | "proposed";

/** 별표(*)가 붙은 자산의 계산 근거. 화면 글자를 줄이려고 하단 주석 대신 여기 둔다. */
const PROXY_HELP =
  "고객이 지금 들고 있는 비중과, 제안을 직접 손본 비중을 각각 입력합니다. " +
  "별표(*)가 붙은 신흥국주식·해외채권·인프라펀드는 자산 매핑이 확정되기 전이라 " +
  "각각 나스닥·달러인덱스·원자재로 계산됩니다.";

/**
 * 자산 비중 입력 — 탭 2개.
 *
 *   현재 보유 : 고객이 지금 실제로 들고 있는 비중. 계산 요청에 그대로 실린다.
 *   제안 조정 : 제안 포트폴리오를 PB가 손보는 값. 분석 결과가 있어야 연다 —
 *               비교 대상이 없는 상태에서 "제안을 조정"한다는 말이 성립하지 않는다.
 *
 * 제안 조정은 빈 칸에서 시작하지 않는다. 분석 결과가 나오거나 중앙에서 다른 제안을
 * 고르면 store 가 그 안의 비중을 여기에 심는다(`selectPortfolio`·`setPortfolios`).
 * 그 값을 실제로 고쳐야 비로소 별개의 안이 되고, 중앙 카드도 그때 조정안으로 넘어간다.
 *
 * 제안 조정 값이 바뀌면 확정본과 갈라지므로 PDF 추출이 잠긴다(`selectExportAllowed`).
 * 승인은 그때 그 비중에 대한 것이라, 입력이 바뀐 뒤에도 추출이 열려 있으면
 * 승인받지 않은 내용이 확정본으로 나간다.
 *
 * 합계가 100이 아니면 분석하기를 막는다(Sidebar.tsx의 isCurrentWeightsInputValid
 * 게이트) — 백엔드가 조용히 100%로 재정규화해버리면 "화면 합계 ≠ 실제 계산에 쓰인
 * 비중"이 되어 추적성이 깨지기 때문에, 여기서 정직하게 막는 쪽을 택했다.
 */
export default function CurrentPortfolioInput() {
  const currentWeightsInput = useDashboardStore((s) => s.currentWeightsInput);
  const setCurrentWeightsInput = useDashboardStore(
    (s) => s.setCurrentWeightsInput,
  );
  const proposedWeightsInput = useDashboardStore((s) => s.proposedWeightsInput);
  const setProposedWeightsInput = useDashboardStore(
    (s) => s.setProposedWeightsInput,
  );
  const resetProposedToSelected = useDashboardStore(
    (s) => s.resetProposedToSelected,
  );
  const portfolioSource = useDashboardStore((s) => s.portfolioSource);

  // 탭 상태는 스토어에 둔다 — 중앙 제안 카드의 세그먼트가 같은 값을 보고 함께 움직인다.
  const tab = useDashboardStore((s) => s.weightsTab);
  const setTab = useDashboardStore((s) => s.setWeightsTab);

  // 제안 조정은 분석 결과가 있을 때만 연다. live·demo 둘 다 결과가 있는 상태다.
  const proposedEnabled = isTrusted(portfolioSource);
  // 결과가 사라지면(고객 전환 등) 열어둔 제안 탭에 머물지 않게 되돌린다.
  const active: WeightTab = tab === "proposed" && !proposedEnabled ? "current" : tab;

  const value = active === "current" ? currentWeightsInput : proposedWeightsInput;
  const setValue =
    active === "current" ? setCurrentWeightsInput : setProposedWeightsInput;

  const total = sumCurrentWeightsInput(value);
  const hasAnyInput = total > 0;
  const isValid = isCurrentWeightsInputValid(value);
  const helpMode = useDashboardStore((s) => s.helpMode);

  const handleChange = (id: FieldId, raw: string) => {
    const cleaned = raw.replace(/[^0-9.]/g, "");
    if (cleaned === "") {
      setValue({ [id]: undefined });
      return;
    }
    const parsed = Number(cleaned);
    setValue({ [id]: Number.isFinite(parsed) ? parsed : undefined });
  };

  /**
   * 초기화의 뜻이 탭마다 다르다.
   *
   *   현재 보유 : 비운다. 아직 아무것도 없던 상태로 돌아가는 것이 초기 상태다.
   *   제안 조정 : 고른 제안의 비중으로 되돌린다. 여기서의 출발점은 빈 칸이 아니라
   *              그 제안이고, 0으로 비우면 손대지 않은 상태가 아니라 "전부 0인
   *              조정안"이 되어 중앙 카드가 빈 도넛으로 넘어간다.
   */
  const handleReset = () => {
    if (active === "proposed") {
      resetProposedToSelected();
      return;
    }
    setCurrentWeightsInput(
      Object.fromEntries(
        ALL_FIELD_IDS.map((id) => [id, undefined]),
      ) as CurrentWeightsInput,
    );
  };

  return (
    <div className="rounded-xl border p-3">
      {/*
        제목과 초기화를 한 줄에 두고 세그먼트는 아래에서 폭을 다 쓴다 —
        같은 줄에 두면 세그먼트가 눌려 두 탭이 무엇을 고르는 것인지 잘 안 읽힌다.
        제목은 사이드바의 다른 카드(고객 선택·상담 입력·IPS 조율기)와 같은 규격이다.
      */}
      <div className="mb-2 flex items-center justify-between">
        <HelpTooltip text={PROXY_HELP} placement="bottom">
          {/* 도움말 모드에서 제목에 표시를 남긴다 — 백테스트·지표 등 다른 도움말
              대상과 같은 규격이라, 어디에 설명이 붙어 있는지 한눈에 보인다. */}
          <p className="cursor-default text-[14px] font-bold">
            <span
              className={
                helpMode
                  ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                  : ""
              }
            >
              자산 비중 조절기
            </span>
          </p>
        </HelpTooltip>
        {hasAnyInput && (
          <button
            type="button"
            onClick={handleReset}
            className="text-[11px] font-semibold text-muted-foreground hover:text-foreground"
          >
            초기화
          </button>
        )}
      </div>

      <div className="mb-2 flex rounded-lg bg-muted p-0.5">
        <TabButton
          active={active === "current"}
          onClick={() => setTab("current")}
        >
          현재 보유
        </TabButton>
        <TabButton
          active={active === "proposed"}
          onClick={() => setTab("proposed")}
          disabled={!proposedEnabled}
          reason="분석 후 활성"
        >
          제안 조정
        </TabButton>
      </div>

      <div className="grid grid-cols-2 gap-x-3">
        {GROUPS.map(({ group, ids }, gi) => (
          <div
            key={group}
            className={`col-span-2 ${gi > 0 ? "mt-3 border-t border-muted pt-3" : ""}`}
          >
            <p className="mb-2 text-[10px] font-bold text-muted-foreground">{group}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
              {ids.map((id) => {
                const proxyNote = PROXY_NOTE[id];
                return (
                  <label
                    key={id}
                    className="flex items-center justify-between gap-0.5"
                    title={proxyNote ? `계산상 ${proxyNote} 자산으로 반영됨 (자산 매핑 확정 전)` : undefined}
                  >
                    {/* whitespace-nowrap: "국내일반채권" 처럼 긴 이름이 두 줄로 깨지지 않게. */}
                    <span className="whitespace-nowrap text-[11px] font-semibold text-foreground/80">
                      {LABELS[id]}
                      {proxyNote && <span className="text-up">*</span>}
                    </span>
                    <span className="flex items-center gap-0.5">
                      <input
                        type="text"
                        inputMode="decimal"
                        value={value[id] ?? ""}
                        onChange={(e) => handleChange(id, e.target.value)}
                        placeholder="0"
                        className="h-6 w-11 shrink-0 rounded-md border border-input bg-card px-1 text-right text-[12px] font-bold tabular-nums outline-none focus-visible:ring-1 focus-visible:ring-ring"
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
            !hasAnyInput
              ? "text-muted-foreground"
              : isValid
                ? "text-brand-dark"
                : "text-destructive"
          }`}
        >
          {total.toLocaleString()}%
        </span>
      </div>
    </div>
  );
}

/** 탭 버튼. 비활성일 때도 왜 못 누르는지 이유를 띄운다(무반응 금지). */
function TabButton({
  active,
  onClick,
  disabled,
  reason,
  children,
}: {
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
  reason?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={disabled ? reason : undefined}
      // 중앙 제안 카드의 세그먼트와 같은 규격이다 — 좌·우가 같은 상태를 보므로
      // 생김새도 같아야 두 곳이 한 컨트롤임이 드러난다.
      className={`flex-1 rounded-md px-3 py-1 text-[11px] font-bold transition-colors ${
        active
          ? "bg-white text-brand-dark shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      } disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-muted-foreground`}
    >
      {children}
    </button>
  );
}
