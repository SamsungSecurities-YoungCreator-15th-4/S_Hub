"use client";

import { Pie, PieChart, ResponsiveContainer } from "recharts";

interface Props {
  allocation: { label: string; weight: number; color: string }[];
}

/** 포트폴리오 카드 자산배분 원형 차트 + 우측 1열 범례
 *  - 원형 차트는 항상 h-64 고정 → 아이템 수 무관하게 같은 크기
 *  - 범례는 차트 오른쪽에 배치해 자산 비중을 한눈에 비교한다.
 */
export default function AssetDonut({ allocation }: Props) {
  const data = allocation
    .filter((d) => d.weight > 0)
    .map((d) => ({ ...d, fill: d.color }));

  return (
    <div className="grid w-full grid-cols-[minmax(0,1.15fr)_minmax(150px,0.85fr)] items-center gap-4 py-1">
      {/* 원형 차트: 항상 고정 높이 */}
      <div className="h-64 min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="weight"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={0}
              outerRadius="86%"
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* 범례: 항상 오른쪽 */}
      <div className="flex min-w-0 flex-col gap-1.5 pr-2">
        {data.map((d) => {
          const rounded = Math.round(d.weight * 10) / 10;
          const displayWeight = rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1);
          return (
            <div key={d.label} className="flex min-w-0 items-center gap-1.5">
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: d.fill }}
              />
              <span className="flex-1 truncate text-[11px] font-semibold text-muted-foreground">
                {d.label}
              </span>
              <span className="shrink-0 text-[11px] font-bold tabular-nums">
                {displayWeight}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
