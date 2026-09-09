"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { RUN_STATUS, canTransition } from "@/lib/runStatus";
import { CALC_UNITS } from "@/lib/assetMapping";
import {
  selectViewedPlanKey,
  useDashboardStore,
  useRunStatus,
} from "@/lib/store";
import {
  CITATIONS,
  CVAR_CONTRIBUTIONS,
  CVAR_CONTRIBUTION_NOTE,
  DISCLAIMERS,
  IPS_CONFLICTS,
  IPS_CONFLICT_NOTE,
  REPORT_AS_OF,
  REPORT_META,
  REPRODUCIBILITY_HASHES,
  REPRODUCIBILITY_NOTE,
  RISK_METRICS,
  STRESS_NOTE,
  STRESS_SCENARIOS,
  VERIFICATIONS,
  VERIFICATION_NOTE,
  WORST_STRESS_KEY,
  formatWon,
} from "@/lib/mock/symphonyReport";

/** 스크롤 게이트의 여유. 하단에서 이 거리 안에 들어오면 끝까지 본 것으로 본다. */
const BOTTOM_THRESHOLD_PX = 24;

/**
 * S.ymphony 리스크 리포트 — 확정(locked) 승인이 나오는 유일한 자리.
 *
 * 분석 승인(게이트 1)은 계산을 시작해도 되는가에 대한 승인이지, 고객에게 내보내도
 * 되는가에 대한 승인이 아니다. 그래서 게이트 1은 reviewed 까지만 올리고 추출은 계속
 * 잠긴 채로 둔다. 근거·검증·재현성을 끝까지 확인한 뒤 여기서만 확정된다.
 *
 * 표시하는 값은 전부 lib/mock/symphonyReport.ts 의 상수다. 이 화면은 지표를 다시
 * 계산하지 않는다 — 6지표 산출의 SSOT 는 엔진의 calculate_metrics 하나뿐이다.
 */
export default function ReportDetailModal({ onClose }: { onClose: () => void }) {
  const runStatus = useRunStatus();
  const lockReport = useDashboardStore((s) => s.lockReport);
  const [atBottom, setAtBottom] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isLocked = runStatus === RUN_STATUS.LOCKED;
  // 같은 상태 유지는 canTransition 이 항상 허용하므로 locked 는 따로 걸러낸다.
  const transitionAllowed =
    !isLocked && canTransition(runStatus, RUN_STATUS.LOCKED);

  /**
   * 스크롤이 하단에 닿았는지 본다. 한 번 닿으면 위로 올려도 유지한다 —
   * 게이트의 뜻은 "끝까지 확인했는가"이지 "지금 하단에 있는가"가 아니다.
   * 내용이 뷰포트보다 짧아 스크롤 자체가 없으면 이미 전부 본 것으로 처리한다.
   */
  const checkBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (
      el.scrollTop + el.clientHeight >=
      el.scrollHeight - BOTTOM_THRESHOLD_PX
    ) {
      setAtBottom(true);
    }
  }, []);

  // 첫 렌더에서 한 번 본다(스크롤 없는 뷰포트에서 즉시 활성화되는 경로).
  useEffect(checkBottom, [checkBottom]);

  const blockReason = !transitionAllowed
    ? "분석 승인을 받은 뒤 확정할 수 있습니다."
    : !atBottom
      ? "리포트를 끝까지 확인하신 후 승인할 수 있습니다."
      : "";

  const handleApprove = () => {
    lockReport();
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="flex h-[92vh] w-full max-w-[980px] flex-col gap-0 overflow-hidden p-0 sm:max-w-[980px]"
      >
        {/* 상태 헤더 — 스크롤과 무관하게 상단 고정 */}
        <div className="shrink-0 border-b px-5 py-3.5">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 pr-9">
            <DialogTitle className="text-[16px] font-extrabold">
              S.ymphony 리스크 리포트
            </DialogTitle>
            <div className="flex items-center gap-2 text-[12px] font-bold text-muted-foreground">
              <span
                className={`rounded-md px-2 py-0.5 text-[11px] font-extrabold ${
                  isLocked
                    ? "bg-positive/10 text-positive"
                    : "bg-brand/10 text-brand-dark"
                }`}
              >
                {isLocked ? "확정" : "확정 가능"}
              </span>
              <span className="tabular-nums">기준일 {REPORT_AS_OF}</span>
              <span className="text-muted-foreground/40">·</span>
              <span className="tabular-nums">
                총 평가금액 {formatWon(REPORT_META.totalValuationKrw)}
              </span>
            </div>
          </div>
          <DialogDescription className="mt-1 text-[11px] font-semibold text-muted-foreground">
            리스크 연산은 6개 자산군 기준입니다.
          </DialogDescription>
        </div>

        <div
          ref={scrollRef}
          onScroll={checkBottom}
          className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-muted/30 px-5 py-4"
        >
          <AllocationBlock />
          <ConflictBlock />
          <RiskMetricBlock />
          <ContributionBlock />
          <StressBlock />
          <CitationBlock />
          <VerificationBlock />
          <HashBlock />
          <DisclaimerBlock />
        </div>

        {/* 하단 고정 액션 바 — 승인 주체는 PB다 */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-t px-5 py-3">
          {isLocked ? (
            <p className="flex items-center gap-1.5 text-[12px] font-bold text-positive">
              <Check className="size-4" />
              승인 완료 · {REPORT_AS_OF}
            </p>
          ) : (
            <>
              <p className="text-[12px] font-semibold text-muted-foreground">
                {blockReason ||
                  "승인하면 이 안이 확정되고 리포트 추출이 가능해집니다."}
              </p>
              {/* disabled 버튼은 hover 이벤트를 받지 못해 title 이 뜨지 않는다 —
                  래퍼 span 이 대신 받아 이유를 항상 보여 준다. */}
              <span title={blockReason || "승인하면 리포트 추출이 열립니다."}>
                <Button
                  onClick={handleApprove}
                  disabled={!!blockReason}
                  className="shrink-0 font-extrabold"
                >
                  PB 승인
                </Button>
              </span>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── 블록 ────────────────────────────────────────────────────────

function Block({
  title,
  children,
  note,
}: {
  title: string;
  children: React.ReactNode;
  /** 블록 하단 한 줄. 이 블록을 어떻게 읽어야 하는지의 안내다. */
  note?: string;
}) {
  return (
    <section className="rounded-xl border bg-card p-4">
      <h3 className="mb-2.5 text-[13px] font-extrabold">{title}</h3>
      {children}
      {note && (
        <p className="mt-2.5 text-[11px] font-semibold leading-relaxed text-muted-foreground">
          {note}
        </p>
      )}
    </section>
  );
}

/** 표 안의 회색 라벨 셀. */
const TH = "px-2 py-1.5 text-left text-[11px] font-bold text-muted-foreground";
const TD = "px-2 py-1.5 text-[12px] font-semibold";

/**
 * 배분만 실제 값에서 읽는다.
 *
 * 확정 대상은 지금 보고 있는 제안이다. 상수로 적어 두면 대시보드에서 안을 바꿔도
 * 리포트는 그대로라, 두 화면이 다른 포트폴리오를 말하게 된다. 배분은 비중을
 * 옮겨 적는 일이라 계산이 필요 없어 화면에서 바로 읽을 수 있다.
 *
 * VaR·스트레스 등 나머지 수치는 상수로 둔다 — 수익률 시계열이 있어야 나오는
 * 값이라 화면에서 다시 만들 수 없다.
 */
function AllocationBlock() {
  const planKey = useDashboardStore(selectViewedPlanKey);
  const proposedWeightsInput = useDashboardStore((s) => s.proposedWeightsInput);
  const portfolios = useDashboardStore((s) => s.portfolios);

  const weights: Record<string, number | undefined> =
    planKey === "proposed"
      ? proposedWeightsInput
      : (portfolios.find((pf) => pf.id === planKey)?.weights ?? {});

  const rows = CALC_UNITS.map((unit) => ({
    label: unit.label,
    weightPct: weights[unit.id] ?? 0,
  }));

  // 대분류 집계 — 현금은 계산단위가 아니라 별도 항목이라 따로 더한다.
  const groupSum = (group: string) =>
    CALC_UNITS.filter((u) => u.group === group).reduce(
      (acc, u) => acc + (weights[u.id] ?? 0),
      0,
    );
  const summary = [
    { label: "주식", weightPct: groupSum("주식") },
    { label: "채권", weightPct: groupSum("채권") },
    { label: "대체", weightPct: groupSum("대체") },
    { label: "현금", weightPct: weights.cash ?? 0 },
  ];

  return (
    <Block title="자산 배분">
      <div className="mb-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {summary.map((row) => (
          <span key={row.label} className="text-[12px] font-bold tabular-nums">
            {row.label}{" "}
            <span className="text-brand-dark">{row.weightPct.toFixed(0)}%</span>
          </span>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
        {rows.map((row) => (
          <div
            key={row.label}
            className={`flex justify-between border-b border-dashed py-1 text-[12px] tabular-nums ${
              row.weightPct === 0 ? "text-muted-foreground/60" : "font-semibold"
            }`}
          >
            <span>{row.label}</span>
            <span>{row.weightPct.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </Block>
  );
}

function ConflictBlock() {
  return (
    <Block
      title={`IPS 충돌 검사 — ${IPS_CONFLICTS.length}건`}
      note={IPS_CONFLICT_NOTE}
    >
      <div className="space-y-2">
        {IPS_CONFLICTS.map((c) => (
          <div key={c.rule} className="rounded-lg border bg-muted/30 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-extrabold uppercase text-amber-700">
                {c.severity}
              </span>
              <span className="text-[12px] font-extrabold">{c.message}</span>
              <code className="text-[10px] font-semibold text-muted-foreground">
                {c.rule}
              </code>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-5 gap-y-0.5 text-[12px] font-semibold tabular-nums">
              <span>
                <span className="text-muted-foreground">관측값</span>{" "}
                {c.observed}
              </span>
              <span>
                <span className="text-muted-foreground">기준값</span>{" "}
                {c.threshold}
              </span>
            </div>
            <p className="mt-1 text-[11px] font-semibold text-muted-foreground">
              {c.basis}
            </p>
          </div>
        ))}
      </div>
    </Block>
  );
}

function RiskMetricBlock() {
  return (
    <Block
      title={`VaR / CVaR — 신뢰수준 ${REPORT_META.confidenceLevelPct}% · ${formatWon(REPORT_META.totalValuationKrw)} 기준`}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse">
          <thead>
            <tr className="border-b">
              <th className={TH}>지표</th>
              <th className={`${TH} text-right`}>비율</th>
              <th className={`${TH} text-right`}>금액</th>
              <th className={`${TH} text-right`}>90% 신뢰구간</th>
            </tr>
          </thead>
          <tbody>
            {RISK_METRICS.map((m) => (
              <tr key={m.label} className="border-b last:border-0">
                <td className={`${TD} font-bold`}>{m.label}</td>
                <td className={`${TD} text-right tabular-nums`}>
                  {m.ratioPct.toFixed(2)}%
                </td>
                <td className={`${TD} text-right tabular-nums`}>
                  -{formatWon(m.amountKrw)}
                </td>
                <td
                  className={`${TD} text-right tabular-nums text-muted-foreground`}
                >
                  {m.ciPct[0].toFixed(2)}% ~ {m.ciPct[1].toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Block>
  );
}

function ContributionBlock() {
  const total = CVAR_CONTRIBUTIONS.reduce((a, r) => a + r.weightPct, 0);
  const max = Math.max(...CVAR_CONTRIBUTIONS.map((r) => r.weightPct), 1);
  return (
    <Block
      title={`CVaR 자산군 기여도 — 6자산군 · 합계 ${total.toFixed(1)}%`}
      note={CVAR_CONTRIBUTION_NOTE}
    >
      <div className="space-y-1.5">
        {CVAR_CONTRIBUTIONS.map((row) => (
          <div key={row.label} className="flex items-center gap-2">
            <span className="w-[78px] shrink-0 text-[12px] font-semibold">
              {row.label}
            </span>
            <div className="h-3.5 min-w-0 flex-1 rounded-sm bg-muted">
              <div
                className="h-full rounded-sm bg-brand"
                style={{ width: `${(row.weightPct / max) * 100}%` }}
              />
            </div>
            <span className="w-[52px] shrink-0 text-right text-[12px] font-bold tabular-nums">
              {row.weightPct.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </Block>
  );
}

function StressBlock() {
  const worst =
    STRESS_SCENARIOS.find((s) => s.key === WORST_STRESS_KEY) ??
    STRESS_SCENARIOS[0];
  return (
    <Block
      title={`스트레스 시나리오 — ${STRESS_SCENARIOS.length}종`}
      note={STRESS_NOTE}
    >
      <div className="rounded-lg border border-down/30 bg-down/5 p-3">
        <p className="text-[11px] font-bold text-muted-foreground">
          최악 시나리오
        </p>
        <div className="mt-0.5 flex flex-wrap items-baseline gap-x-3">
          <span className="text-[13px] font-extrabold">{worst.label}</span>
          <span className="text-[18px] font-extrabold tabular-nums text-down">
            {formatWon(worst.lossKrw)}
          </span>
          <span className="text-[13px] font-bold tabular-nums text-down">
            {worst.lossPct.toFixed(1)}%
          </span>
        </div>
      </div>
      <div className="mt-2.5 overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse">
          <thead>
            <tr className="border-b">
              <th className={TH}>시나리오</th>
              <th className={`${TH} text-right`}>손실률</th>
              <th className={`${TH} text-right`}>손실액</th>
            </tr>
          </thead>
          <tbody>
            {STRESS_SCENARIOS.map((s) => (
              <tr key={s.key} className="border-b last:border-0">
                <td className={`${TD} ${s.key === worst.key ? "font-bold" : ""}`}>
                  {s.label}
                </td>
                <td className={`${TD} text-right tabular-nums text-down`}>
                  {s.lossPct.toFixed(1)}%
                </td>
                <td className={`${TD} text-right tabular-nums text-down`}>
                  {formatWon(s.lossKrw)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Block>
  );
}

function CitationBlock() {
  return (
    <Block title={`인용·출처 — ${CITATIONS.length}건`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse">
          <thead>
            <tr className="border-b">
              <th className={`${TH} w-8`}>#</th>
              <th className={TH}>출처</th>
              <th className={TH}>참조 위치</th>
              <th className={`${TH} w-20`}>반영 블록</th>
            </tr>
          </thead>
          <tbody>
            {CITATIONS.map((c) => (
              <tr key={c.no} className="border-b last:border-0">
                <td className={`${TD} tabular-nums text-muted-foreground`}>
                  {c.no}
                </td>
                <td className={TD}>{c.source}</td>
                <td className={`${TD} text-muted-foreground`}>{c.locator}</td>
                <td className={`${TD} tabular-nums`}>{c.usedIn}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Block>
  );
}

function VerificationBlock() {
  const passed = VERIFICATIONS.filter((v) => v.passed).length;
  return (
    <Block
      title={`검증 항목 — ${passed}/${VERIFICATIONS.length} 통과`}
      note={VERIFICATION_NOTE}
    >
      <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {VERIFICATIONS.map((v) => (
          <div
            key={v.label}
            className="flex items-center gap-1.5 border-b border-dashed py-1 text-[12px] font-semibold"
          >
            <Check
              className={`size-3.5 shrink-0 ${v.passed ? "text-positive" : "text-down"}`}
            />
            <span>{v.label}</span>
            {v.ratio && (
              <span className="tabular-nums text-muted-foreground">
                ({v.ratio})
              </span>
            )}
          </div>
        ))}
      </div>
    </Block>
  );
}

function HashBlock() {
  return (
    <Block
      title={`재현성 해시 — 엔진 ${REPORT_META.engineVersion}`}
      note={REPRODUCIBILITY_NOTE}
    >
      <div className="space-y-1">
        {REPRODUCIBILITY_HASHES.map((h) => (
          <div
            key={h.label}
            className="flex flex-wrap items-center justify-between gap-x-4 border-b border-dashed py-1"
          >
            <span className="text-[12px] font-semibold">{h.label}</span>
            <code className="text-[11px] font-bold tabular-nums text-muted-foreground">
              {h.value}
            </code>
          </div>
        ))}
      </div>
    </Block>
  );
}

function DisclaimerBlock() {
  return (
    <Block title="면책">
      <ul className="space-y-1">
        {DISCLAIMERS.map((d) => (
          <li
            key={d.code}
            className="flex gap-2 text-[11px] font-semibold leading-relaxed text-muted-foreground"
          >
            <span className="shrink-0 font-extrabold">{d.code}</span>
            <span>{d.text}</span>
          </li>
        ))}
      </ul>
    </Block>
  );
}
