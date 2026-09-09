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
import { useDashboardStore, useRunStatus } from "@/lib/store";
import { RUN_STATUS, canTransition } from "@/lib/runStatus";

/**
 * IPS 반영 거절 사유. 좌측 분석 게이트의 ANALYZE_REJECT_REASON 과 같은 문형이다 —
 * 두 게이트는 같은 성격의 승인이라 화면 문구도 같은 모양으로 읽혀야 한다.
 */
const IPS_REFLECT_REJECT_REASON = "IPS 반영을 거절했습니다";

/** 우측 패널: 시나리오 Test + AI 인사이트 — 여닫기 토글 포함 */
export default function RightPanel() {
  const [isOpen, setIsOpen] = useAutoCollapse(1280);

  const [confirmOpen, setConfirmOpen] = useState(false);
  /** 직전 IPS 반영을 거절했는지 — 무엇이 실행되지 않았는지 남긴다. */
  const [reflectRejected, setReflectRejected] = useState(false);
  const { insightResult, ips, setIps, setRunStatus, resetRunStatus } =
    useDashboardStore();
  const runStatus = useRunStatus();

  const summary =
    insightResult?.source !== "empty" ? insightResult?.data?.summary : null;
  /** 요약이 붙을 자리. 다이얼로그가 붙기 전 상태를 그대로 보여준다. */
  const uniqueBefore = (ips.unique ?? "").trim();

  const handleIpsReflect = () => {
    if (!summary) return;
    setReflectRejected(false);
    setConfirmOpen(true);
  };

  const handleConfirm = () => {
    if (!summary) return;
    setIps({
      unique: uniqueBefore ? `${uniqueBefore}\n${summary}` : summary,
    });
    setConfirmOpen(false);
    setReflectRejected(false);
    // PB가 IPS 변경을 승인했으므로 reviewed 로 올린다.
    // locked·blocked 에서는 reviewed 로 가는 전이가 전이표에 없다(lib/runStatus.ts:48).
    // IPS 가 바뀌면 확정본 내용도 함께 바뀌므로, 확정을 유지한 채 두지 않고
    // 초기화(draft)한 뒤 다시 검토 상태로 올린다 — 확정은 상세 화면에서 다시 받는다.
    if (!canTransition(runStatus, RUN_STATUS.REVIEWED)) resetRunStatus();
    setRunStatus(RUN_STATUS.REVIEWED);
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

      {/*
        좌측 분석하기와 같은 자리(버튼 바로 위)·같은 문형으로 적는다. 버튼 아래에
        두면 패널 맨 끝이라 화면 밖으로 밀려 보이지 않는다 — 거절했는데 아무
        반응이 없는 것처럼 읽힌다.
      */}
      {reflectRejected && (
        <p className="-mb-1 px-0.5 text-[11px] font-semibold text-destructive">
          {IPS_REFLECT_REJECT_REASON}
        </p>
      )}

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
          className="block w-96 rounded-2xl bg-card p-6 text-foreground shadow-xl sm:max-w-none"
        >
          <DialogHeader className="block">
            <DialogTitle className="font-sans text-[15px] leading-normal font-extrabold">
              IPS에 반영하시겠습니까?
            </DialogTitle>
            <DialogDescription className="mt-2 text-[13px] font-medium leading-relaxed text-muted-foreground">
              아래 요약이 IPS의 <b>Unique</b> 항목 끝에 그대로 덧붙습니다.
            </DialogDescription>
          </DialogHeader>

          {/*
            승인 대상이 보이지 않으면 승인이 형식이 된다 — 좌측 분석 게이트와 같은
            이유로, 무엇이 어디에 붙는지를 실제 store 값으로 보여준다. Unique 는
            이후 분석의 입력이라 붙기 전후를 함께 봐야 판단할 수 있다.
            표시만 하고 아무 값도 바꾸지 않는다.
          */}
          <div className="mt-5 max-h-64 overflow-y-auto rounded-xl border p-4 text-[12px]">
            <p className="mb-2 font-bold">추가할 내용</p>
            <p className="whitespace-pre-wrap leading-relaxed">{summary}</p>

            <p className="mt-4 mb-2 border-t pt-4 font-bold">
              현재 IPS Unique{" "}
              <span className="font-medium text-muted-foreground">
                {uniqueBefore ? `(${uniqueBefore.length}자)` : "(비어 있음)"}
              </span>
            </p>
            <p className="whitespace-pre-wrap leading-relaxed text-muted-foreground">
              {uniqueBefore || "아직 입력된 특이사항이 없습니다."}
            </p>
          </div>

          <div className="mt-5 flex gap-2">
            <Button className="flex-1" onClick={handleConfirm}>
              승인
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => {
                setConfirmOpen(false);
                setReflectRejected(true);
              }}
            >
              거절
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
