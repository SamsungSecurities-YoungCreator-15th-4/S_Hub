import { MonitorPlay } from "lucide-react";
import { IS_DEMO } from "@/lib/demo/flag";

/**
 * 시연 모드 표시 배너.
 *
 * 우리 거버넌스: 고정 데이터를 실데이터인 척 보여주지 않는다.
 * 데모 모드에서는 화면의 모든 숫자가 고정값이므로, 필드별 배지에 앞서
 * 화면 전체에 한 번 명시한다. NEXT_PUBLIC_DEMO=1 일 때만 렌더링된다.
 *
 * 레이아웃을 밀지 않도록 하단 고정(fixed)이며 클릭을 가로채지 않는다.
 */
export default function DemoBanner() {
  if (!IS_DEMO) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center pb-2">
      <span className="pointer-events-auto inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50/95 px-3 py-1 text-[11px] font-semibold text-sky-700 shadow-sm backdrop-blur">
        <MonitorPlay className="size-3.5" />
        시연 고정 데이터
      </span>
    </div>
  );
}
