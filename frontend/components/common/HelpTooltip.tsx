"use client";

import { useEffect, useRef, useState } from "react";
import { useDashboardStore } from "@/lib/store";

/** 툴팁 폭(px). 아래 className 의 w-64 / w-80 과 같아야 한다. */
const TOOLTIP_WIDTH = 256;
/** wide 일 때의 폭. 제도 설명처럼 문장이 여러 줄인 경우에 쓴다. */
const TOOLTIP_WIDTH_WIDE = 320;
/** 화면 가장자리와의 최소 여백(px). */
const VIEWPORT_MARGIN = 8;

/**
 * 도움말 모드가 ON일 때만 hover 시 툴팁을 표시하는 래퍼.
 * fixed 포지셔닝을 사용해 overflow:hidden 부모에 잘리지 않는다.
 * 항상 children을 렌더링해 helpMode 전환 시 자식 state가 초기화되지 않는다.
 */
export default function HelpTooltip({
  children,
  text,
  placement = "top",
  className = "",
  wide = false,
}: {
  children: React.ReactNode;
  text: string;
  placement?: "top" | "bottom";
  className?: string;
  /** 문장이 긴 설명용. 폭을 320px 로 넓힌다. */
  wide?: boolean;
}) {
  const helpMode = useDashboardStore((s) => s.helpMode);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const handleMouseEnter = () => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    // 툴팁은 x 를 중심으로 좌우로 펼쳐지므로(translateX(-50%)), 대상이 화면
    // 가장자리에 있으면 밖으로 잘린다. 뷰포트 안으로 밀어 넣는다.
    const half = (wide ? TOOLTIP_WIDTH_WIDE : TOOLTIP_WIDTH) / 2;
    const center = r.left + r.width / 2;
    const x = Math.min(
      Math.max(center, half + VIEWPORT_MARGIN),
      window.innerWidth - half - VIEWPORT_MARGIN,
    );
    setPos({ x, y: placement === "bottom" ? r.bottom : r.top });
  };

  const handleMouseLeave = () => setPos(null);

  useEffect(() => {
    if (!pos) return;
    const clear = () => setPos(null);
    window.addEventListener("scroll", clear, true);
    window.addEventListener("resize", clear);
    return () => {
      window.removeEventListener("scroll", clear, true);
      window.removeEventListener("resize", clear);
    };
  }, [pos]);

  return (
    <div
      ref={ref}
      className={`relative ${className}`}
      onMouseEnter={helpMode ? handleMouseEnter : undefined}
      onMouseLeave={helpMode ? handleMouseLeave : undefined}
    >
      {children}

      {helpMode && pos && (
        <span className="pointer-events-none absolute inset-0 rounded-lg bg-brand/[0.07]" />
      )}

      {helpMode && pos && (
        <div
          className={`pointer-events-none fixed z-[9999] ${wide ? "w-80" : "w-64"} rounded-xl bg-foreground px-3 py-2.5 text-[13px] font-semibold leading-relaxed text-background shadow-xl`}
          style={{
            left: pos.x,
            top: placement === "bottom" ? pos.y + 8 : pos.y - 8,
            transform:
              placement === "bottom"
                ? "translateX(-50%)"
                : "translateX(-50%) translateY(-100%)",
          }}
        >
          {text}
          <span
            className={`absolute left-1/2 -translate-x-1/2 border-4 border-transparent ${
              placement === "bottom"
                ? "bottom-full border-b-foreground"
                : "top-full border-t-foreground"
            }`}
          />
        </div>
      )}
    </div>
  );
}
