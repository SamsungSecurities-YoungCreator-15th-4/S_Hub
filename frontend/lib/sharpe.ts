/**
 * 샤프지수 계산 — 화면·PDF·AI 인사이트가 공유하는 단일 정의.
 *
 * sharpe = (기대수익률 − 무위험수익률) / 변동성
 *
 * 이 함수를 둔 이유는 값을 하드코딩에서 계산으로 옮기기 위함이다. mockData 의
 * 샤프 3건은 원래 손으로 적힌 상수였고, 그중 포트폴리오 A 가 기대수익률·변동성과
 * 맞지 않았다(6.4 / 12.5 = 0.51 인데 0.61 로 적혀 있었다). 화면에 뜨는 숫자는
 * 계산식이 코드에서 추적 가능해야 한다는 원칙에 따라, 샤프만 계산으로 승격한다.
 *
 * 소르티노·MDD·변동성·기대수익률은 여기서 다루지 않는다 — 하방편차와 시계열이
 * 필요한데 프론트 mock 경로에는 수익률 시계열이 없다(`backtest` 는 백엔드 응답
 * 경로에만 채워진다). 근거 없이 계산식을 만들지 않고 하드코딩을 유지한다.
 */

/**
 * 무위험수익률(연 %, 소수 아님 — 4.8% 는 4.8).
 *
 * TODO: 팀 확정 필요. 현재 0 은 "아직 정하지 않았다"는 표시이지 시장값이 아니다.
 * 무위험수익률 선정(국고채 3년 / 1년 / CD91 중 무엇을, 어느 기준일로)은 금융
 * 도메인 판단이라 코드가 정할 수 없다. 0 인 동안 sharpe 는 기대수익률/변동성과
 * 같은 값이 되며, 이는 기존 화면값(현재 0.43 · B 0.43)과 일치한다.
 */
export const RISK_FREE_RATE_PCT = 0;

/**
 * 기대수익률·변동성으로 샤프지수를 계산한다.
 *
 * 두 인자 모두 연율 퍼센트 단위다(4.8% → 4.8). 변동성이 0 이하이거나 값이
 * 유한하지 않으면 정의되지 않으므로 undefined 를 돌려준다 — 0 을 돌려주면
 * "위험 대비 초과수익 0" 이라는 뜻이 되어 없는 값을 지어내는 것이 된다.
 */
export function sharpeRatio(
  expectedReturnPct: number,
  volatilityPct: number,
  riskFreeRatePct: number = RISK_FREE_RATE_PCT,
): number | undefined {
  if (
    !Number.isFinite(expectedReturnPct) ||
    !Number.isFinite(volatilityPct) ||
    !Number.isFinite(riskFreeRatePct) ||
    volatilityPct <= 0
  ) {
    return undefined;
  }
  return (expectedReturnPct - riskFreeRatePct) / volatilityPct;
}

/**
 * 지표 객체에 샤프지수를 붙여 돌려준다.
 *
 * `sharpeRatio(6.4, 12.5)` 처럼 숫자를 다시 적으면, 기대수익률·변동성을 고치고
 * 샤프 인자를 안 고치는 순간 원래 버그(A 가 6.4/12.5=0.51 인데 0.61 로 적혀
 * 있던 것)가 그대로 재발한다. 그래서 같은 객체의 필드에서만 유도한다.
 */
export function withSharpe<
  T extends { expectedReturnPct: number; volatilityPct: number },
>(metrics: T): T & { sharpe: number | undefined } {
  return {
    ...metrics,
    sharpe: sharpeRatio(metrics.expectedReturnPct, metrics.volatilityPct),
  };
}

/**
 * 샤프지수 표시 문자열 — 화면·PDF 공용.
 *
 * 값이 하드코딩이던 동안에는 상수 자체가 이미 소수 2자리(0.43·0.61)라
 * 화면의 `toFixed(2)` 와 PDF 의 `String(v)` 가 우연히 같은 문자열을 냈다.
 * 계산으로 바뀌면 4.8/11.2 = 0.4285714285714286 이 되어 두 경로가 갈라진다.
 * 그래서 표시 규칙도 계산과 같은 곳에 둔다.
 */
export function formatSharpe(value: number | null | undefined): string {
  return value == null ? "-" : value.toFixed(2);
}
