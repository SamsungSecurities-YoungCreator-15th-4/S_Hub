"use client";

import { useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import InsightSection from "@/components/right-panel/InsightSection";
import HelpTooltip from "@/components/common/HelpTooltip";
import { useAutoCollapse } from "@/lib/useAutoCollapse";
import { useDashboardStore } from "@/lib/store";

/** 우측 패널: 시나리오 Test + AI 인사이트 — 여닫기 토글 포함 */
export default function RightPanel() {
  const [isOpen, setIsOpen] = useAutoCollapse(1280);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { insightResult, ips, setIps } = useDashboardStore();

  const summary =
    insightResult?.source !== "empty" ? insightResult?.data?.summary : null;

  const handleIpsReflect = () => {
    if (!summary) return;
    setConfirmOpen(true);
  };

  const handleConfirm = () => {
    if (!summary) return;
    const prev = (ips.unique ?? "").trim();
    setIps({ unique: prev ? `${prev}\n${summary}` : summary });
    setConfirmOpen(false);
  };

  if (!isOpen) {
    return (
      <div className="flex w-10 self-start shrink-0 flex-col items-center rounded-2xl bg-card py-3 ring-1 ring-foreground/10">
        <button
          onClick={() => setIsOpen(true)}
          title="우측 패널 열기"
          className="flex flex-col items-center gap-2 rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <PanelRightOpen className="size-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-[320px] shrink-0 flex-col gap-2.5 rounded-2xl bg-card p-2.5 ring-1 ring-foreground/10">
      {/* 패널 헤더 */}
      <div className="flex items-center px-0.5 pb-0.5">
        <button
          onClick={() => setIsOpen(false)}
          title="우측 패널 닫기"
          className="rounded p-0.5 text-muted-foreground hover:text-foreground"
        >
          <PanelRightClose className="size-4" />
        </button>
      </div>

      <InsightSection />

      <HelpTooltip
        text="PB 승인 시, AI 분석 요약 답변이 좌측 패널 IPS Unique 항목에 추가되어 포트폴리오 분석에 활용됩니다."
        placement="top"
      >
        <Button
          size="lg"
          onClick={handleIpsReflect}
          disabled={!summary}
          className="w-full rounded-xl py-6 text-sm font-extrabold shadow-[0_4px_14px_rgba(0,100,255,0.28)]"
        >
          IPS 반영하기
        </Button>
      </HelpTooltip>

      {/* IPS 승인 확인 — 닫기(X) 없이 승인/거절만 두던 기존 UI를 그대로 두고,
          ESC·백드롭 클릭·포커스 트랩만 Dialog 프리미티브에서 얻는다. */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent
          showCloseButton={false}
          overlayClassName="bg-black/40 backdrop-blur-sm"
          className="block w-80 rounded-2xl bg-card p-6 text-foreground shadow-xl sm:max-w-none"
        >
          <DialogHeader className="block">
            <DialogTitle className="font-sans text-[15px] leading-normal font-extrabold">
              IPS에 반영하시겠습니까?
            </DialogTitle>
            <DialogDescription className="mt-1.5 text-[13px] font-medium text-muted-foreground">
              AI 인사이트 요약을 IPS의 <b>Unique</b> 항목에 추가합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex gap-2">
            <Button className="flex-1" onClick={handleConfirm}>
              승인
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => setConfirmOpen(false)}
            >
              거절
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
