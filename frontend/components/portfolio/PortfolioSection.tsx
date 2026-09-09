"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import ReportDetailModal from "@/components/dashboard/ReportDetailModal";
import AssetDonut from "@/components/portfolio/AssetDonut";
import {
  BACKEND_ASSET_COLORS,
  CALC_UNITS,
  toCalcUnitAllocation,
} from "@/lib/assetMapping";
import { type Portfolio, type PortfolioMetrics } from "@/lib/mockData";
import { pctOfAumLabel } from "@/lib/formatKrw";
import { formatSharpe } from "@/lib/sharpe";
import { RUN_STATUS } from "@/lib/runStatus";
import {
  selectAnalysisEmpty,
  selectViewedPlanKey,
  useDashboardStore,
  useRunStatus,
} from "@/lib/store";
import HelpTooltip from "@/components/common/HelpTooltip";
import AsOfNote from "@/components/common/AsOfNote";

/**
 * 지표 도움말 — 고객이 함께 보는 화면이라 전문용어 대신 일상어로 적는다.
 * 각 문구는 "무엇을 보여주는가" 한 줄 + "어떻게 읽는가" 한 줄로 끊는다.
 */
const METRIC_HELP: Record<string, string> = {
  MDD:
    "투자하면서 내 돈이 가장 많이 줄어들었던 순간이 얼마나 컸는지 보여줍니다. " +
    "예를 들어 1,000만 원이 800만 원까지 떨어졌다면 MDD는 -20%입니다.",
  변동성:
    "투자금이 평소 얼마나 크게 오르내리는지 보여줍니다. " +
    "높을수록 수익도 손실도 크게 움직여 투자금의 변화가 커질 수 있습니다.",
  소르티노:
    "돈을 잃을 때의 위험에 비해 얼마나 수익을 냈는지 보여줍니다. " +
    "값이 높을수록 손실은 상대적으로 적고 수익은 잘 낸 투자입니다.",
  샤프지수:
    "투자하면서 감수한 위험에 비해 얼마나 수익을 냈는지 보여줍니다. " +
    "값이 높을수록 비슷한 위험으로 더 많은 수익을 낸 투자입니다.",
  기대수익률:
    "과거 데이터를 바탕으로 앞으로 1년 동안 얼마나 벌 수 있을지 예상한 값입니다. " +
    "예상치일 뿐이라 실제로 이만큼 벌 수 있다는 보장은 없습니다.",
  세후수익률:
    "투자로 번 돈에서 세금까지 내고 실제로 남는 수익이 얼마나 되는지 보여줍니다. " +
    "따라서 실제로 내 손에 남는 돈을 비교할 때 유용합니다.",
};

/**
 * 카드가 그릴 수 있는 포트폴리오.
 *
 * Portfolio.id 는 "current"|"a"|"b" 로 고정돼 있고 세금·PDF·인사이트가 그 전제로
 * 읽는다. 화면에만 존재하는 "proposed" 를 그 유니온에 넣으면 그쪽들이 오류 없이
 * 조용히 폴백하므로, 카드 쪽에서만 id 를 넓혀 받는다.
 */
type CardPortfolio = Omit<Portfolio, "id"> & { id: string };

/**
 * 제안 카드 세그먼트 라벨. 두 안은 같은 축의 양끝이라 성향 이름으로 부른다.
 * 세 칸이 나란히 서므로 띄어쓰기를 "제안 조정" 과 같은 형태로 맞춘다.
 */
const PROPOSAL_LABEL: Record<string, string> = {
  a: "안정 추구",
  b: "수익 추구",
};

/** 조정안 칸의 키·라벨. 손댄 뒤에만 열린다. */
const ADJUSTED_KEY = "proposed";
const ADJUSTED_LABEL = "제안 조정";

/** 중앙 상단: 현재(1/3) + 제안(2/3, 세그먼트 전환) */
export default function PortfolioSection() {
  const {
    selectedPortfolioId,
    selectPortfolio,
    proposedWeightsInput,
    setWeightsTab,
    portfolios,
    portfolioSource,
    analyzing,
  } = useDashboardStore();
  const [detailOpen, setDetailOpen] = useState(false);
  const runStatus = useRunStatus();

  // 분석 전(=빈 상태)에는 볼 리포트가 없으므로 자세히도 내보내지 않는다.
  const isEmpty = useDashboardStore(selectAnalysisEmpty);
  // draft 는 분석 승인 전(또는 거절·IPS 반영으로 되돌아온 뒤)이라 확정할 리포트가
  // 아직 없다. 버튼을 숨기지 않고 비활성으로 두어 이유가 보이게 한다.
  const detailBlockReason =
    runStatus === RUN_STATUS.DRAFT ? "분석 후 확인할 수 있습니다." : "";

  const current = portfolios.find((pf) => pf.id === "current");
  const proposals = portfolios.filter((pf) => pf.id !== "current");
  const selectedProposal =
    proposals.find((pf) => pf.id === selectedPortfolioId) ?? proposals[0];
  /*
    중앙 카드가 조정안을 보여주는 조건은 "제안 조정 탭에 있는가" 가 아니라
    "그 값을 손댔는가" 다. 분석 직후 제안 조정 탭에는 선택한 제안의 값이 그대로
    들어가 있어서, 그때의 조정안은 안정 추구·수익 추구와 같은 안이다.
    판정 식은 store 의 selectViewedPlanKey 하나뿐이다 — 화면에서 활성인 칸과
    PDF 확정 대조의 기준이 갈라지면 안 된다.
  */
  const viewedPlanKey = useDashboardStore(selectViewedPlanKey);
  const isProposedEdit = viewedPlanKey === ADJUSTED_KEY;

  /**
   * 제안 조정 안. 비중은 PB 가 사이드바에서 손본 값(proposedWeightsInput)을 그대로 쓴다.
   * 지표는 비워 둔다 — 임의 비중의 기대수익률·변동성·MDD 를 산출하려면 자산군별
   * 수익률·공분산이 필요한데 프론트에 그 데이터가 없다. 근거 없는 숫자를 지어
   * 넣지 않는다(lib/sharpe.ts 가 같은 이유로 샤프만 계산으로 승격했다).
   */
  const editBase = selectedProposal ?? proposals[0];
  const adjustedPortfolio: CardPortfolio | undefined = isProposedEdit && editBase
    ? {
        ...editBase,
        // 백엔드 원본 allocation 을 지운다 — 도넛이 사람이 조정한 weights 를 쓰게 한다.
        allocation: undefined,
        id: ADJUSTED_KEY,
        name: ADJUSTED_LABEL,
        weights: CALC_UNITS.reduce(
          (acc, unit) => ({ ...acc, [unit.id]: proposedWeightsInput[unit.id] ?? 0 }),
          {} as Portfolio["weights"],
        ),
      }
    : undefined;

  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-extrabold">포트폴리오 대시보드</h2>
          {analyzing ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              분석중...
            </div>
          ) : portfolioSource === "live" ? (
            <div className="flex items-center gap-1.5 rounded-lg bg-brand/5 px-2 py-0.5 text-[10px] font-bold text-brand-dark">
              <span className="size-1.5 rounded-full bg-positive shadow-[0_0_0_2px_rgba(22,180,122,0.18)]" />
              연동 완료
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {portfolioSource !== "fallback" && <AsOfNote />}
          {!isEmpty && (
            // disabled 버튼은 hover 이벤트를 받지 못해 title 이 뜨지 않는다 —
            // 래퍼 span 이 대신 받아 왜 못 누르는지를 보여 준다.
            <span title={detailBlockReason || "리포트 전체를 확인합니다."}>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDetailOpen(true)}
                disabled={!!detailBlockReason}
                className="h-7 text-[12px] font-bold"
              >
                자세히
              </Button>
            </span>
          )}
        </div>
      </div>

      {isEmpty ? (
        <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[14px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {current && (
            <PortfolioCard
              pf={current}
              header={
                <span className="text-[13px] font-extrabold">
                  {current.name}
                </span>
              }
            />
          )}
          {/*
            제안 A·B 를 한 카드로 합치고 세그먼트로 전환한다. 두 안은 같은 축
            (안정 ↔ 수익)의 양끝이라 나란히 두는 것보다 하나를 바꿔 보는 편이
            비교가 된다. 현재 카드와 같은 폭으로 둬 두 도넛·지표가 같은 크기로
            맞붙게 한다 — 비교가 이 화면의 목적이다.
          */}
          {(adjustedPortfolio ?? selectedProposal) && (
            <PortfolioCard
              pf={(adjustedPortfolio ?? selectedProposal)!}
              metricsUnavailableNote={
                isProposedEdit
                  ? "직접 조정한 비중의 지표는 자산군별 수익률·변동성 데이터가 연결되면 계산됩니다."
                  : undefined
              }
              header={
                <>
                {/*
                  왼쪽 카드에는 "현재" 라는 이름이 있는데 오른쪽에는 세그먼트만
                  있어 무엇을 보는 화면인지 드러나지 않았다. 같은 무게의 라벨을
                  붙여 현재 ↔ 제안으로 짝을 맞춘다. 세그먼트가 이미 쓰던 줄이라
                  높이는 늘지 않는다.
                */}
                <span className="text-[13px] font-extrabold">제안</span>
                <div className="flex rounded-lg bg-muted p-0.5">
                  {proposals.map((pf) => {
                    const active = viewedPlanKey === pf.id;
                    return (
                      <button
                        key={pf.id}
                        type="button"
                        // 제안을 고르면 store 가 그 안의 비중을 제안 조정 입력에
                        // 심는다 — PB 는 빈 칸이 아니라 이 안에서 출발해 손본다.
                        onClick={() => {
                          selectPortfolio(pf.id);
                          setWeightsTab("proposed");
                        }}
                        aria-pressed={active}
                        className={`rounded-md px-3 py-1 text-[11px] font-bold transition-colors ${
                          active
                            ? "bg-white text-brand-dark shadow-sm"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {PROPOSAL_LABEL[pf.id] ?? pf.name}
                      </button>
                    );
                  })}
                  {/*
                    조정안 칸은 손댄 뒤에만 열린다. 손대기 전에는 선택한 제안과
                    같은 값이라, 열어두면 같은 안이 두 이름으로 보인다.
                    비활성일 때도 왜 못 누르는지 이유를 띄운다(무반응 금지).
                  */}
                  <span
                    title={
                      isProposedEdit
                        ? "직접 조정한 안입니다."
                        : "좌측 자산 비중 조절기의 제안 조정 탭에서 비중을 수정하면 열립니다."
                    }
                  >
                    <button
                      type="button"
                      disabled={!isProposedEdit}
                      onClick={() => setWeightsTab("proposed")}
                      aria-pressed={isProposedEdit}
                      className={`rounded-md px-3 py-1 text-[11px] font-bold transition-colors ${
                        isProposedEdit
                          ? "bg-white text-brand-dark shadow-sm"
                          : "text-muted-foreground/40"
                      }`}
                    >
                      {ADJUSTED_LABEL}
                    </button>
                  </span>
                </div>
                </>
              }
            />
          )}
        </div>
      )}

      {detailOpen && <ReportDetailModal onClose={() => setDetailOpen(false)} />}
    </section>
  );
}

function PortfolioCard({
  pf,
  header,
  className,
  metricsUnavailableNote,
}: {
  pf: CardPortfolio;
  /** 카드 상단 — 현재 카드는 이름, 제안 카드는 세그먼트 컨트롤이 온다. */
  header: React.ReactNode;
  className?: string;
  /** 지표를 계산할 근거가 없을 때의 안내. 있으면 지표 격자 대신 이 문장을 보여준다. */
  metricsUnavailableNote?: string;
}) {
  // 지표의 원화 병기 기준. 고객 총자산이 없으면 pctOfAumLabel 이 병기를 생략한다.
  const aumEokwon = useDashboardStore(
    (s) =>
      (s.customers.find((c) => c.id === s.selectedCustomerId) ?? s.customers[0])
        ?.aumEokwon ?? 0,
  );

  // 백엔드 8개 자산군이 있으면 직접 사용, 없으면 구형 6분류 변환으로 폴백
  const allocation = pf.allocation
    ? pf.allocation
        .filter((a) => a.weight > 0)
        .map((a) => ({
          label: a.name,
          weight: a.weight,
          color: BACKEND_ASSET_COLORS[a.asset_class] ?? "#8899AA",
        }))
    : toCalcUnitAllocation(pf.weights);
  const m = pf.metrics as PortfolioMetrics & {
    afterTaxReturnRangeLabel?: string;
    mddRangeLabel?: string;
  };

  return (
    <Card className={`gap-0 p-3 ${className ?? ""}`}>
      <div className="mb-2 flex min-h-7 items-center justify-between">
        {header}
      </div>

      <div className="flex min-h-72 items-stretch gap-2.5">
        <div className="flex flex-1 flex-col items-center">
          <AssetDonut allocation={allocation} />
        </div>
      </div>

      {/*
        지표 순서는 "얼마나 잃을 수 있나"(윗줄) → "얼마나 벌 수 있나"(아랫줄)다.
        쓸 날이 정해진 자금을 다루는 상담에서는 기대수익보다 낙폭이 먼저 읽혀야 한다.
        소르티노는 하락 위험만으로 계산하는 지표라 윗줄에 둔다.

        원화 병기는 백엔드 실계산 값이 있으면 그것을 쓰고, 없으면
        pctOfAumLabel(비율 × 고객 총자산)로 만든다. 어느 경로든 값의 출처가
        코드에서 하나로 추적된다.
      */}
      {metricsUnavailableNote ? (
        <div className="mt-2.5 rounded-lg border border-dashed border-muted-foreground/25 bg-muted/30 px-3 py-5">
          <p className="text-center text-[12px] font-semibold leading-relaxed text-muted-foreground">
            {metricsUnavailableNote}
          </p>
        </div>
      ) : (
        <div className="mt-2.5 grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-muted">
        {/*
          2열 3행. 왼쪽 열은 버는 쪽, 오른쪽 열은 잃는·흔들리는 쪽으로 세로를 맞춘다.

            세후수익률 · MDD      원화 금액이 붙는 두 지표 — 벌 돈과 잃을 수 있는 돈
            기대수익률 · 변동성    같은 두 축의 세전·비율 버전
            샤프지수  · 소르티노   위험 대비 수익 비율. 소르티노는 하방만 보므로 오른쪽

          금액이 붙는 두 지표를 같은 행에 둬야 행 높이도 어긋나지 않는다.
        */}
        <Metric
          k="세후수익률"
          v={`${Math.abs(m.afterTaxReturnPct).toFixed(1)}%`}
          rangeSub={m.afterTaxReturnRangeLabel}
          sub={
            m.afterTaxAmountLabel ??
            pctOfAumLabel(
              m.afterTaxReturnPct,
              aumEokwon,
              m.afterTaxReturnPct < 0 ? "-" : "+",
            )
          }
          tone={
            m.afterTaxReturnPct > 0
              ? "up"
              : m.afterTaxReturnPct < 0
                ? "down"
                : undefined
          }
          value={m.afterTaxReturnPct}
        />
        <Metric
          k="MDD"
          v={`${m.mddPct.toFixed(1)}%`}
          rangeSub={m.mddRangeLabel}
          sub={m.mddAmountLabel ?? pctOfAumLabel(m.mddPct, aumEokwon, "-")}
          tone={m.mddPct > 0 ? "down" : undefined}
          value={m.mddPct}
        />
        <Metric k="기대수익률" v={`${m.expectedReturnPct.toFixed(2)}%`} />
        <Metric
          k="변동성"
          v={`${m.volatilityPct.toFixed(2)}%`}
          sub={m.volatilityAmountLabel ?? pctOfAumLabel(m.volatilityPct, aumEokwon, "±")}
          value={m.volatilityPct}
        />
        <Metric k="샤프지수" v={formatSharpe(m.sharpe)} />
        <Metric
          k="소르티노"
          v={m.sortino != null ? m.sortino.toFixed(2) : "-"}
        />
        </div>
      )}
    </Card>
  );
}

function Metric({
  k,
  v,
  rangeSub,
  sub,
  tone,
  value,
}: {
  k: string;
  v: string;
  rangeSub?: string;
  sub?: string;
  tone?: "up" | "down";
  value?: number;
}) {
  const helpMode = useDashboardStore((s) => s.helpMode);
  const effectiveTone = value === 0 ? undefined : tone;
  const toneCls =
    effectiveTone === "up"
      ? "text-up"
      : effectiveTone === "down"
        ? "text-down"
        : "";
  const arrow =
    effectiveTone === "up" ? "▲" : effectiveTone === "down" ? "▼" : null;
  return (
    <HelpTooltip text={METRIC_HELP[k] ?? ""}>
      <div className="h-full bg-card px-2 py-1.5">
        <div
          className={`w-fit text-[12px] font-bold text-muted-foreground ${
            helpMode
              ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
              : ""
          }`}
        >
          {k}
        </div>
        {/*
          원화 금액을 먼저 읽히게 한다 — 매스 고객은 비율보다 금액으로 이해한다.
          원화 병기가 없는 지표(샤프·소르티노 등)는 비율·수치가 그대로 큰 값이 된다.
        */}
        <div
          className={`mt-1 whitespace-nowrap text-[14px] font-extrabold leading-none tabular-nums ${toneCls}`}
        >
          {/* 금액은 부호(+ · - · ±)만 달고 삼각형은 아래 비율이 가져간다. */}
          {sub ? (
            value === 0 ? (
              sub.replace(/^[+\-±]/, "")
            ) : (
              sub
            )
          ) : (
            <>
              {arrow && <span className="mr-0.5 text-[14px]">{arrow}</span>}
              {v}
            </>
          )}
        </div>
        {sub && (
          <div className={`mt-0.5 whitespace-nowrap text-[12px] font-bold tabular-nums ${toneCls}`}>
            {arrow && <span className="mr-0.5">{arrow}</span>}
            {v}
          </div>
        )}
        {rangeSub && (
          <div className="mt-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
            {rangeSub}
          </div>
        )}
      </div>
    </HelpTooltip>
  );
}
