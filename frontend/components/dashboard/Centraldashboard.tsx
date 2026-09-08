"use client";

import PortfolioSection from "@/components/portfolio/PortfolioSection";
import BacktestChart from "@/components/portfolio/BacktestChart";
import StressTestSection from "@/components/dashboard/StressTestSection";
import TaxSection from "@/components/tax/TaxSection";
import HomeGoalCard from "@/components/home-goal/HomeGoalCard";
import { useDashboardStore } from "@/lib/store";

/**
 * 중앙 대시보드 영역.
 * 분석 결과가 없을 때는 주택 목표 설정을 열어 두고,
 * 기존 분석 섹션은 하나의 회색 빈 화면으로 표시한다.
 */
export default function CentralDashboard() {
  const { portfolioSource, portfolioNote, analyzing } = useDashboardStore();

  // PortfolioSection 의 빈 상태 판정과 동일한 조건(분석 전 = fallback·note 없음·분석 중 아님).
  const isEmpty =
    portfolioSource === "fallback" && portfolioNote === undefined && !analyzing;

  if (isEmpty) {
    return (
      <main className="flex min-w-0 flex-1 flex-col gap-3">
        <HomeGoalCard />
        <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-muted-foreground/20 bg-muted/30">
          <p className="text-[15px] font-semibold text-muted-foreground">
            분석 결과가 존재하지 않습니다
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col gap-3">
      <PortfolioSection />
      {/*
        스트레스 카드는 PB 의 입력 도구가 아니라 고객과 함께 보는 결과다.
        사이드바는 PB 가 직접 접을 수 있어, 카드를 거기 두면 결과를 보여줘야 하는
        순간에 함께 사라진다 — 그래서 중앙에 둔다.
        선택한 포트폴리오 비중을 쓰므로 PortfolioSection 바로 아래가 맞는 자리다.
      */}
      <StressTestSection />
      <HomeGoalCard />
      <BacktestChart />
      <TaxSection />
    </main>
  );
}
