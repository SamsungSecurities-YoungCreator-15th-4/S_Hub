import { Inbox, Wifi } from "lucide-react";
import type { DataSource } from "@/lib/api";

/**
 * 데이터 출처 배지 — 화면 값이 실데이터인지 데모(폴백)인지 명시한다.
 * 우리 거버넌스: 폴백 값을 실데이터인 척 보여주지 않는다.
 *  - live    : 실데이터(배지 생략)
 *  - demo    : 고정 데이터 — 화면에는 표시하지 않는다(live 와 동일하게 통과).
 *              source 값과 isTrusted() 판정은 그대로라 배지만 되살리면 원복된다.
 *  - empty   : 정상 빈결과(데이터 없음)
 *  - fallback: 호출 실패 → 배지 없음(경고는 각 섹션이 note 로 직접 띄운다)
 */
export default function DataSourceBadge({
  source,
  note,
  className = "",
}: {
  source: DataSource;
  note?: string;
  className?: string;
}) {
  if (source !== "empty") return null;

  // 여기 도달하는 값은 "empty" 하나뿐이다.
  const { Icon, label, cls } = {
    Icon: Inbox,
    label: "데이터 없음",
    cls: "border-muted-foreground/15 bg-muted/30 text-muted-foreground/60",
  };

  return (
    <span
      title={note}
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${cls} ${className}`}
    >
      <Icon className="size-2.5" />
      {label}
    </span>
  );
}

/** 실데이터 표시용 작은 라벨(원하면 사용). */
export function LiveBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 ${className}`}
    >
      <Wifi className="size-3" />
      실데이터
    </span>
  );
}
