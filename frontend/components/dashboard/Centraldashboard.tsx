"use client";

import PortfolioSection from "@/components/portfolio/PortfolioSection";
import BacktestChart from "@/components/portfolio/BacktestChart";
import TaxSection from "@/components/tax/TaxSection";
import { selectAnalysisEmpty, useDashboardStore } from "@/lib/store";

/**
 * 상담 전 화면에서 다음에 할 일. 빈 화면이 "미완성"이 아니라 "아직 안 한 것"으로
 * 읽히려면, 무엇을 하면 채워지는지가 그 자리에 있어야 한다. 좌측 사이드바를
 * 위에서 아래로 훑는 순서와 같다.
 */
const NEXT_STEPS = [
  "상담 음성을 업로드하거나 녹음을 시작합니다",
  "전사 결과를 확인하고 IPS 항목을 조정합니다",
  "현재 보유 비중을 입력한 뒤 분석하기를 누릅니다",
];

/**
 * 중앙 대시보드 영역.
 * 분석 결과가 없을 때(상담 전 고객 등)는 섹션을 각각 비우지 않고,
 * 중앙 영역 전체를 하나의 빈 화면으로 덮는다 — 세 군데가 따로 비어 있으면
 * 무엇이 잘못된 것처럼 보인다.
 */
export default function CentralDashboard() {
  const isEmpty = useDashboardStore(selectAnalysisEmpty);

  if (isEmpty) {
    return (
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30 p-6">
          <div className="max-w-[420px]">
            <p className="text-[16px] font-extrabold">분석 전입니다</p>
            <ol className="mt-3 space-y-1.5">
              {NEXT_STEPS.map((step, i) => (
                <li
                  key={step}
                  className="flex gap-2 text-[13px] font-semibold leading-relaxed text-muted-foreground"
                >
                  <span className="shrink-0 tabular-nums font-extrabold text-brand-dark">
                    {i + 1}.
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col gap-3">
      <PortfolioSection />
      <BacktestChart />
      <TaxSection />
    </main>
  );
}
