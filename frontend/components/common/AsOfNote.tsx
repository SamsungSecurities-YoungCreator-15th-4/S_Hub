/**
 * 기준일·출처 표기 — 화면의 수치 묶음마다 "언제 기준의, 어디서 온 값인지"를 붙인다.
 *
 * 표기 톤은 포트폴리오 대시보드 헤더의 "YYYY.MM.DD 기준" 하나를 따른다.
 * 출처는 코드에서 실제로 추적되는 것만 적는다 — 근거를 댈 수 없는 수치에는
 * source 를 넘기지 않고 기준일만 붙인다.
 */

/** 오늘 날짜를 "YYYY.MM.DD" 로. 서버·클라이언트 시각차는 호출부가 suppressHydrationWarning 으로 흡수한다. */
export function asOfToday(): string {
  return new Date()
    .toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replace(/\. /g, ".")
    .replace(/\.$/, "");
}

export default function AsOfNote({
  source,
  className = "",
}: {
  /** 값의 출처·통화 표기. 생략하면 기준일만 나온다. */
  source?: string;
  className?: string;
}) {
  return (
    <span
      className={`text-[11px] font-semibold text-muted-foreground ${className}`}
      suppressHydrationWarning
    >
      {asOfToday()} 기준{source ? ` · ${source}` : ""}
    </span>
  );
}
