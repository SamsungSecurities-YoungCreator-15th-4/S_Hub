/**
 * 원화 금액 표기 — 화면·리포트 공용.
 *
 * 매스 고객은 비율보다 금액으로 이해한다는 판단에 따라, 지표 옆에 원화 금액을
 * 병기할 때 쓴다. 만원 단위로 반올림하고 1억 이상은 "억 + 만원"으로 끊는다.
 */

/** 예: 6_900_0000 → "6,900만원", 112_000_0000 → "1억 1,200만원" */
export function formatKrwCompact(krw: number): string {
  const manwon = Math.round(Math.abs(krw) / 10_000);
  if (manwon === 0) return "0원";
  const eok = Math.floor(manwon / 10_000);
  const rest = manwon % 10_000;
  if (eok > 0) {
    return rest > 0
      ? `${eok.toLocaleString("ko-KR")}억 ${rest.toLocaleString("ko-KR")}만원`
      : `${eok.toLocaleString("ko-KR")}억원`;
  }
  return `${manwon.toLocaleString("ko-KR")}만원`;
}

/**
 * 비율(%)을 총자산 대비 금액 문자열로 바꾼다.
 *
 * 지표(변동성·MDD·세후수익률)의 원화 병기는 전부 이 함수를 거친다 —
 * 화면에 뜨는 금액이 "비율 × 총자산"이라는 하나의 식으로만 나오게 해서
 * 값의 출처를 추적할 수 있게 하기 위함이다.
 * 총자산이 0이면(미입력) 병기할 근거가 없으므로 undefined 를 돌려준다.
 */
export function pctOfAumLabel(
  pct: number,
  aumEokwon: number,
  prefix: "±" | "-" | "+" | "" = "",
): string | undefined {
  if (!Number.isFinite(pct) || !Number.isFinite(aumEokwon) || aumEokwon <= 0) {
    return undefined;
  }
  const krw = (Math.abs(pct) / 100) * aumEokwon * 100_000_000;
  return `${prefix}${formatKrwCompact(krw)}`;
}
