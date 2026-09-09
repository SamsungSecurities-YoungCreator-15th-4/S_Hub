"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RUN_STATUS, canTransition } from "@/lib/runStatus";
import { useDashboardStore, useRunStatus } from "@/lib/store";

// PDF 추출과 같은 템플릿을 그대로 보여준다 — PB가 확정하는 대상은 "화면 요약"이
// 아니라 고객에게 나가는 리포트 그 자체여야 한다. new Date() hydration mismatch를
// 피하려고 추출 버튼과 동일하게 ssr:false 로 불러온다.
const PbPdfTemplate = dynamic(() => import("@/components/pdf/PbPdfTemplate"), {
  ssr: false,
});

/**
 * 리포트 상세 화면 — 확정(locked) 승인이 나오는 유일한 자리.
 *
 * 분석 승인(게이트 1)은 계산을 시작해도 되는가에 대한 승인이지, 고객에게 내보내도
 * 되는가에 대한 승인이 아니다. 그래서 게이트 1은 reviewed 까지만 올리고 PDF는 계속
 * 잠긴 채로 둔다. 리포트를 끝까지 확인한 뒤 여기서만 확정된다.
 */
export default function ReportDetailModal({ onClose }: { onClose: () => void }) {
  const runStatus = useRunStatus();
  const setRunStatus = useDashboardStore((s) => s.setRunStatus);
  const [atBottom, setAtBottom] = useState(false);

  const isLocked = runStatus === RUN_STATUS.LOCKED;
  // 같은 상태 유지는 canTransition 이 항상 허용하므로 locked 는 따로 걸러낸다.
  const transitionAllowed =
    !isLocked && canTransition(runStatus, RUN_STATUS.LOCKED);

  const blockReason = isLocked
    ? "이미 확정한 리포트입니다."
    : !transitionAllowed
      ? "분석하기에서 승인을 받은 뒤 확정할 수 있습니다."
      : !atBottom
        ? "리포트를 끝까지 내려 확인하면 확정 버튼이 열립니다."
        : "";

  const handleApprove = () => {
    setRunStatus(RUN_STATUS.LOCKED);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/60 p-4 sm:p-8">
      <div className="mx-auto flex max-h-full w-full max-w-[860px] flex-col overflow-hidden rounded-2xl bg-card shadow-2xl">
        {/* 헤더 */}
        <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
          <div>
            <h2 className="text-[15px] font-extrabold">리포트 상세</h2>
            <p className="text-[11px] font-semibold text-muted-foreground">
              고객에게 나가는 리포트 전체입니다. 끝까지 확인한 뒤 확정하세요.
            </p>
          </div>
          <button
            onClick={onClose}
            title="닫기"
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        {/*
          스크롤 끝까지 내려야 확정이 열린다. 스크롤 이벤트로만 판정하는데,
          템플릿이 A4 5장(5,615px)이라 어떤 뷰포트에서도 반드시 스크롤이 생긴다.
          ponytail: 내용이 뷰포트보다 짧아질 수 있게 되면 ResizeObserver 로 바꾼다.
        */}
        <div
          onScroll={(e) => {
            const el = e.currentTarget;
            setAtBottom(el.scrollTop + el.clientHeight >= el.scrollHeight - 8);
          }}
          className="min-h-0 flex-1 overflow-auto bg-muted/40 p-4"
        >
          <div className="mx-auto w-[794px] origin-top">
            <PbPdfTemplate />
          </div>
        </div>

        {/* 최하단 — 승인 주체는 PB다 */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-t px-4 py-3">
          <p className="text-[12px] font-semibold text-muted-foreground">
            {blockReason || "리포트를 끝까지 확인했습니다. 확정하면 PDF 추출이 열립니다."}
          </p>
          {/* disabled 버튼은 hover 이벤트를 받지 못해 title 이 뜨지 않는다 —
              래퍼 span 이 대신 받아 이유를 항상 보여 준다. */}
          <span title={blockReason || "확정하면 PDF 추출이 열립니다."}>
            <Button
              onClick={handleApprove}
              disabled={!!blockReason}
              className="shrink-0 font-extrabold"
            >
              PB 확정 승인
            </Button>
          </span>
        </div>
      </div>
    </div>
  );
}
