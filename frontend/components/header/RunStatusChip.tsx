"use client";

import { RUN_STATUS, RUN_STATUS_LABEL } from "@/lib/runStatus";
import { useRunStatus } from "@/lib/store";

/**
 * 실행 상태 칩 (읽기 전용).
 *
 * "분석이 끝났다"를 완료 문구가 아니라 확정 수명주기의 한 단계로 보여 준다.
 * 값·문구의 출처는 lib/runStatus.ts 하나뿐이라 여기서 문자열을 다시 적지 않는다.
 * 클릭·전이 조작은 없다 — 상태는 화면 조작이 아니라 실행 결과로만 움직인다.
 */
const TONE: Record<string, string> = {
  [RUN_STATUS.DRAFT]: "border-muted-foreground/20 bg-muted text-muted-foreground",
  [RUN_STATUS.REVIEWED]: "border-brand/25 bg-brand/5 text-brand-dark",
  [RUN_STATUS.LOCKED]: "border-positive/30 bg-positive/10 text-positive",
  [RUN_STATUS.BLOCKED]: "border-destructive/30 bg-destructive/10 text-destructive",
};

export default function RunStatusChip() {
  const status = useRunStatus();

  return (
    <span
      title="포트폴리오 분석 상태: 표시 전용"
      className={`shrink-0 rounded-lg border px-2 py-0.5 text-[10px] font-bold ${TONE[status]}`}
    >
      {RUN_STATUS_LABEL[status]}
    </span>
  );
}
