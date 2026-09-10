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
  useDashboardStore,
  useRunStatus,
} from "@/lib/store";
import {
  CITATIONS,
  DISCLAIMERS,
  REPORT_AS_OF,
  REPORT_META,
  REPRODUCIBILITY_HASHES,
  REPRODUCIBILITY_NOTE,
  VERIFICATIONS,
  VERIFICATION_NOTE,
  formatWon,
} from "@/lib/mock/symphonyReport";
import { STRESS_SCENARIOS, runStress } from "@/lib/stressScenarios";
import { conflictSummary, evaluateIpsConflicts } from "@/lib/ipsConflicts";
import {
  CONFIDENCE_LEVEL_PCT,
  cvarContributions,
  riskMetricRows,
} from "@/lib/riskModel";
import { useSymphonySubject } from "@/lib/symphonySubject";

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
  const { totalKrw, label } = useSymphonySubject();
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
                총 평가금액 {formatWon(totalKrw)}
              </span>
            </div>
          </div>
          <DialogDescription className="mt-1 text-[11px] font-semibold text-muted-foreground">
            진단 대상은 {label} 구성입니다. 상담 전 보유 비중은 충돌 검사에서
            비교 대상으로만 씁니다.
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
  sub,
  children,
  note,
}: {
  title: string;
  /** 제목 옆 부가정보(건수·조건). 백테스트 제목과 같은 방식이다. */
  sub?: string;
  children: React.ReactNode;
  /** 블록 하단 한 줄. 이 블록을 어떻게 읽어야 하는지의 안내다. */
  note?: string;
}) {
  return (
    <section className="rounded-xl border bg-card p-4">
      <h3 className="mb-2.5 text-[13px] font-extrabold">
        {title}
        {sub && (
          <span className="ml-1.5 text-[11px] font-semibold text-muted-foreground">
            {sub}
          </span>
        )}
      </h3>
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
 * 자산 배분 — 확정 대상 안 기준.
 *
 * 이 리포트가 진단하는 대상은 **옮겨 갈 안**이다. 아래 칸이 전부 같은 비중을
 * 본다 — IPS 충돌·VaR·손실 기여도·스트레스가 한 포트폴리오를 두고 말하므로
 * 한 문서 안에서 국내주식이 두 값을 갖는 일이 없다.
 *
 * 상담 전 보유 비중은 사라진 것이 아니라 **비교 대상**이 되었다. 충돌 검사가
 * "상한을 넘었었고 이 안에서 풀렸다" 를 말할 수 있는 것이 그 자리다.
 */
function AllocationBlock() {
  const { portfolio, label } = useSymphonySubject();

  const weights: Record<string, number | undefined> = portfolio?.weights ?? {};

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
    <Block title="자산 배분" sub={`${label} 기준`}>
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

/**
 * IPS 충돌 검사 — 확정 대상 안을 `config/ips_policy.yaml` 기준으로 판정한다.
 *
 * 상담 전 비중도 함께 넘겨 "그때는 걸렸고 이 안에서 풀렸다" 를 한 줄로 남긴다.
 * 해소된 항목까지 보여야 제안이 무엇을 고쳤는지가 문서에 남는다.
 */
function ConflictBlock() {
  const { portfolio, baselineWeights, totalKrw, customer, label } =
    useSymphonySubject();
  if (!portfolio) return null;

  const rows = evaluateIpsConflicts({
    weights: portfolio.weights,
    baselineWeights,
    nearTermNeedManwon: customer?.nearTermNeedManwon ?? 0,
    nearTermNeedYears: customer?.nearTermNeedYears ?? null,
    nearTermNeedLabel: customer?.nearTermNeedLabel,
    totalKrw,
  });
  const { sub, note } = conflictSummary(rows);

  return (
    <Block title="IPS 충돌 검사" sub={`${label} 기준 · ${sub}`} note={note}>
      <div className="space-y-2">
        {rows.map((c) => {
          const resolved = c.status === "resolved";
          return (
            <div key={c.rule} className="rounded-lg border bg-muted/30 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-extrabold uppercase ${
                    resolved
                      ? "bg-positive/10 text-positive"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {resolved ? "해소" : c.severity}
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
                {c.previousObserved ? (
                  <span className="text-muted-foreground">
                    상담 전 {c.previousObserved}
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-[11px] font-semibold text-muted-foreground">
                {c.basis}
              </p>
            </div>
          );
        })}
      </div>
    </Block>
  );
}

/**
 * VaR / CVaR — 확정 대상 안의 연 변동성과 고객 총 평가금액으로 계산한다.
 * 산식과 근거는 `lib/riskModel.ts` 주석에 있다.
 */
function RiskMetricBlock() {
  const { portfolio, totalKrw, label } = useSymphonySubject();
  if (!portfolio || totalKrw <= 0) return null;
  const metrics = riskMetricRows(portfolio.metrics.volatilityPct, totalKrw);

  return (
    <Block
      title="VaR / CVaR"
      sub={`${label} · 신뢰수준 ${CONFIDENCE_LEVEL_PCT}% · ${formatWon(totalKrw)} 기준`}
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
            {metrics.map((m) => (
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

/**
 * CVaR 자산군 기여도 — 확정 대상 안의 비중에서 한계기여도로 계산한다.
 * 배분 칸과 같은 계산단위 이름을 써서 "비중은 얼마인데 기여도는 얼마" 를 나란히 읽는다.
 */
function ContributionBlock() {
  const { portfolio, label } = useSymphonySubject();
  const rows = portfolio ? cvarContributions(portfolio.weights) : [];
  if (rows.length === 0) return null;

  const total = rows.reduce((a, r) => a + r.weightPct, 0);
  const max = Math.max(...rows.map((r) => r.weightPct), 1);
  // 비중보다 기여도가 큰 자산군이 이 안의 손실을 끌고 간다 — 그 한 줄만 남긴다.
  const top = rows[0];
  const note = `${top.label}이(가) 손실의 ${top.weightPct.toFixed(1)}% 를 차지합니다.`;

  return (
    <Block
      title="CVaR 자산군 기여도"
      sub={`${label} · 합계 ${total.toFixed(1)}%`}
      note={note}
    >
      <div className="space-y-1.5">
        {rows.map((row) => (
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

/**
 * 스트레스 시나리오 — 확정 대상 안 기준.
 *
 * 상수로 적어 두지 않고 PDF 와 같은 `runStress` 로 계산한다. 예전에는 여기만
 * 상수였는데, 그 표에는 엔진에 존재하지 않는 시나리오(2008)가 들어 있었고
 * 같은 "2022 금리" 가 PDF 와 520만원 어긋났다. 숫자의 출처가 하나여야 두 화면이
 * 같은 말을 한다 — SSOT 는 `engine/engine/stress.py` 이고 프론트 사본은
 * `lib/stressScenarios.ts` 다.
 */
function StressBlock() {
  const { portfolio, customer, totalKrw, label } = useSymphonySubject();
  if (!portfolio || totalKrw <= 0) return null;

  // lossKrw 는 양수가 손실이다(lib/stressScenarios.ts StressLoss).
  const rows = STRESS_SCENARIOS.map((sc) => ({
    key: sc.key,
    label: sc.label,
    loss: runStress(portfolio.weights, totalKrw, sc),
  }));
  const worst = rows.reduce((w, r) => (r.loss.lossKrw > w.loss.lossKrw ? r : w));

  /*
    근시일에 써야 할 돈과 견준다. 금액을 문구에 박아 두면 고객이 바뀌었을 때
    남의 숫자를 말하게 되므로 레코드에서 읽는다. 쓸 시점이 없는 고객에게는
    비교 자체가 성립하지 않아 문장을 만들지 않는다.
  */
  const needKrw = (customer?.nearTermNeedManwon ?? 0) * 10_000;
  const needYears = customer?.nearTermNeedYears ?? 0;
  const overNeed = rows.filter((r) => r.loss.lossKrw >= needKrw);
  // 배열 순서가 손실 크기 순이 아니므로 최솟값을 따로 고른다.
  const mildestOverNeed = overNeed.reduce(
    (m, r) => (m && m.loss.lossKrw <= r.loss.lossKrw ? m : r),
    overNeed[0],
  );
  const note =
    needKrw > 0 && needYears > 0
      ? overNeed.length > 0
        ? `${needYears}년 내 필요자금 ${formatWon(needKrw)}을 넘는 손실이 ${overNeed.length}개 시나리오에서 납니다: 그중 가장 작은 것이 ${mildestOverNeed.label} ${formatWon(-mildestOverNeed.loss.lossKrw)}입니다.`
        : `${rows.length}개 시나리오 모두 손실이 ${needYears}년 내 필요자금 ${formatWon(needKrw)}보다 작습니다.`
      : undefined;

  return (
    <Block
      title="스트레스 시나리오"
      sub={`${rows.length}종 · ${label} 기준`}
      note={note}
    >
      <div className="rounded-lg border border-down/30 bg-down/5 p-3">
        <p className="text-[11px] font-bold text-muted-foreground">
          최악 시나리오
        </p>
        <div className="mt-0.5 flex flex-wrap items-baseline gap-x-3">
          <span className="text-[13px] font-extrabold">{worst.label}</span>
          <span className="text-[18px] font-extrabold tabular-nums text-down">
            {formatWon(-worst.loss.lossKrw)}
          </span>
          <span className="text-[13px] font-bold tabular-nums text-down">
            {(-worst.loss.lossPct * 100).toFixed(1)}%
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
            {rows.map((r) => (
              <tr key={r.key} className="border-b last:border-0">
                <td className={`${TD} ${r.key === worst.key ? "font-bold" : ""}`}>
                  {r.label}
                </td>
                <td className={`${TD} text-right tabular-nums text-down`}>
                  {(-r.loss.lossPct * 100).toFixed(1)}%
                </td>
                <td className={`${TD} text-right tabular-nums text-down`}>
                  {formatWon(-r.loss.lossKrw)}
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
    <Block title="인용·출처" sub={`${CITATIONS.length}건`}>
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
      title="검증 항목"
      sub={`${passed}/${VERIFICATIONS.length} 통과`}
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
      title="재현성 해시"
      sub={`엔진 ${REPORT_META.engineVersion}`}
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
