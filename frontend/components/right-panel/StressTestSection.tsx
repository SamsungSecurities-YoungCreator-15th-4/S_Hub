"use client";

import { Card } from "@/components/ui/card";
import HelpTooltip from "@/components/common/HelpTooltip";

import {
  STRESS_SCENARIOS,
  formatKrwLoss,
  runStress,
  type StressScenario,
} from "@/lib/stressScenarios";
import { useDashboardStore } from "@/lib/store";

const STRESS_TEST_HELP =
  "과거에 실제로 있었던 시장 충격 국면을 참조해, 지금 포트폴리오가 그런 상황을 다시 만나면 " +
  "얼마를 잃을 수 있는지 보여줍니다. 충격 크기는 미리 정해져 있어 매번 같은 결과가 나옵니다. " +
  "정밀한 재현이 아니라 방향과 크기를 맞춘 대표 시나리오입니다.";

/** 우측 상단: Stress Test — 시나리오 카드 3장 */
export default function StressTestSection() {
  const {
    customers,
    selectedCustomerId,
    portfolios,
    selectedPortfolioId,
    stressScenarioKey,
    setStressScenarioKey,
    helpMode,
  } = useDashboardStore();

  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
  // 총자산: 억원 단위 입력을 원 단위로 환산한다.
  const totalKrw = (customer?.aumEokwon ?? 0) * 100_000_000;

  const portfolio =
    portfolios.find((p) => p.id === selectedPortfolioId) ?? portfolios[0];

  return (
    <Card className="gap-0 p-3.5">
      <div className="mb-0.5">
        <HelpTooltip text={STRESS_TEST_HELP} placement="bottom">
          <p className="cursor-default text-[14px] font-bold">
            <span
              className={
                helpMode
                  ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                  : ""
              }
            >
              Stress Test
            </span>
          </p>
        </HelpTooltip>
      </div>
      <p className="mb-3 text-[11px] font-medium text-muted-foreground">
        과거 충격 국면을 참조한 세 가지 시나리오
      </p>

      {!portfolio || totalKrw <= 0 ? (
        <p className="py-3 text-center text-[12px] font-semibold text-muted-foreground">
          고객 자산과 포트폴리오가 정해지면 계산됩니다.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {STRESS_SCENARIOS.map((scenario) => (
            <ScenarioCard
              key={scenario.key}
              scenario={scenario}
              weights={portfolio.weights}
              totalKrw={totalKrw}
              selected={stressScenarioKey === scenario.key}
              onSelect={() =>
                setStressScenarioKey(
                  stressScenarioKey === scenario.key ? null : scenario.key,
                )
              }
            />
          ))}
        </div>
      )}
    </Card>
  );
}

function ScenarioCard({
  scenario,
  weights,
  totalKrw,
  selected,
  onSelect,
}: {
  scenario: StressScenario;
  weights: Parameters<typeof runStress>[0];
  totalKrw: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const loss = runStress(weights, totalKrw, scenario);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`rounded-xl border p-2.5 text-left transition-colors ${
        selected
          ? "border-brand bg-brand/[0.04]"
          : "border-border hover:border-brand/40"
      }`}
    >
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] font-extrabold">{scenario.label}</span>
        <span className="text-[11px] font-semibold text-muted-foreground tabular-nums">
          자산의 {(loss.lossPct * 100).toFixed(1)}%
        </span>
      </div>
      <p className="mt-0.5 text-[11px] font-medium leading-snug text-muted-foreground">
        {scenario.blurb}
      </p>
      <p className="mt-1.5 text-[17px] font-extrabold text-down tabular-nums">
        &minus;{formatKrwLoss(loss.lossKrw)}
      </p>
      <p className="text-[10.5px] font-semibold text-muted-foreground tabular-nums">
        {formatKrwLoss(loss.lossKrwLow)} ~ {formatKrwLoss(loss.lossKrwHigh)}
      </p>
      {selected && (
        <p className="mt-1.5 border-t border-border pt-1.5 text-[10px] font-medium leading-snug text-muted-foreground">
          {scenario.reference}
        </p>
      )}
    </button>
  );
}
