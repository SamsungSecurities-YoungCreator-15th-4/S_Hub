import { Inbox, MonitorPlay, Wifi } from "lucide-react";
import type { DataSource } from "@/lib/api";

/**
 * 데이터 출처 배지 — 화면 값이 실데이터인지 데모(폴백)인지 명시한다.
 * 우리 거버넌스: 폴백 값을 실데이터인 척 보여주지 않는다.
 *  - live    : 실데이터(보통 배지 생략)
 *  - demo    : 시연 모드 고정 데이터 — 선택한 것이므로 사고(fallback)와 구분해 표시한다
 *  - empty   : 정상 빈결과(데이터 없음)
 *  - fallback: 호출 실패 → 데모 데이터 표시 중 ⚠️
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
  if (source === "live" || source === "fallback") return null;

  // 위에서 live·fallback 은 null → 여기 도달하는 값은 "demo" 와 "empty" 둘뿐이다.
  const { Icon, label, cls } =
    source === "demo"
      ? {
          Icon: MonitorPlay,
          label: "시연 고정 데이터",
          cls: "border-sky-200 bg-sky-50 text-sky-700",
        }
      : {
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
