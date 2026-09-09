"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CALC_UNITS, sumCurrentWeightsInput } from "@/lib/assetMapping";
import { useDashboardStore } from "@/lib/store";

/** 입력 비중 키의 표시 이름. cash 는 계산단위가 아니라 별도 항목이다. */
function weightLabel(id: string): string {
  if (id === "cash") return "현금";
  return CALC_UNITS.find((u) => u.id === id)?.label ?? id;
}

/**
 * 분석 실행 전 PB 승인 게이트.
 *
 * 승인 대상이 무엇인지 보이지 않으면 승인이 형식이 된다 — 계산에 그대로 들어가는
 * 두 입력(IPS 조율기 값·현재 보유 비중)을 실제 store 값으로 보여준다.
 * 표시만 하고 아무 값도 바꾸지 않는다(판단은 사람이 한다).
 *
 * 형태는 RightPanel 의 IPS 반영 확인 다이얼로그와 같다 — 닫기(X) 없이 승인/거절
 * 두 버튼만 두고, ESC·백드롭·포커스 트랩은 Dialog 프리미티브에서 얻는다.
 */
export default function AnalyzeGateDialog({
  open,
  onOpenChange,
  onApprove,
  onReject,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const ips = useDashboardStore((s) => s.ips);
  const currentWeightsInput = useDashboardStore((s) => s.currentWeightsInput);

  const weights = Object.entries(currentWeightsInput).filter(
    ([, v]) => typeof v === "number" && v > 0,
  ) as [string, number][];
  const weightTotal = sumCurrentWeightsInput(currentWeightsInput);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        overlayClassName="bg-black/40 backdrop-blur-sm"
        className="block w-96 rounded-2xl bg-card p-6 text-foreground shadow-xl sm:max-w-none"
      >
        <DialogHeader className="block">
          <DialogTitle className="font-sans text-[15px] leading-normal font-extrabold">
            이 입력으로 분석하시겠습니까?
          </DialogTitle>
          <DialogDescription className="mt-1.5 text-[13px] font-medium text-muted-foreground">
            아래 IPS와 보유 비중이 그대로 계산에 들어갑니다.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 max-h-64 overflow-y-auto rounded-xl border p-3 text-[12px]">
          <p className="mb-1.5 font-bold">IPS</p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
            <Row k="목표 수익률" v={`${ips.returnPct}%`} />
            <Row k="위험 성향" v={ips.risk || "미입력"} />
            <Row k="투자 기간" v={ips.timeYears ? `${ips.timeYears}년` : "미입력"} />
            <Row k="유동성" v={ips.liquidity || "미입력"} />
          </dl>

          <p className="mt-3 mb-1.5 font-bold">
            현재 보유 비중{" "}
            <span className="font-medium text-muted-foreground">
              (합계 {weightTotal}%)
            </span>
          </p>
          {weights.length === 0 ? (
            <p className="text-muted-foreground">
              미입력 — 현금 100%로 계산합니다.
            </p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
              {weights.map(([id, v]) => (
                <Row key={id} k={weightLabel(id)} v={`${v}%`} />
              ))}
            </dl>
          )}
        </div>

        <div className="mt-4 flex gap-2">
          <Button className="flex-1" onClick={onApprove}>
            승인
          </Button>
          <Button variant="outline" className="flex-1" onClick={onReject}>
            거절
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="font-semibold">{v}</dd>
    </div>
  );
}
