"use client";

import { Badge } from "@/components/ui/badge";
import { RUN_STATUS, RUN_STATUS_LABEL } from "@/lib/runStatus";
import { useDashboardStore, useRunStatus } from "@/lib/store";

/**
 * 현재 실행 상태 칩 — 읽기 전용. 상태를 바꾸는 조작은 여기 붙이지 않는다
 * (분석 승인은 좌측 게이트, 확정은 리포트 상세 화면에서만 일어난다).
 * 표기는 lib/runStatus.ts 의 RUN_STATUS_LABEL 하나만 쓴다.
 */
export default function RunStatusChip() {
  const status = useRunStatus();
  const reason = useDashboardStore((s) => s.runStatusReason);

  const variant =
    status === RUN_STATUS.LOCKED
      ? "default"
      : status === RUN_STATUS.BLOCKED
        ? "destructive"
        : "secondary";

  return (
    <Badge
      variant={variant}
      title={reason || undefined}
      className="hidden shrink-0 font-bold sm:inline-flex"
    >
      {RUN_STATUS_LABEL[status]}
    </Badge>
  );
}
