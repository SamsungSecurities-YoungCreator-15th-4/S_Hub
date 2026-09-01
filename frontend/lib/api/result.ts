/**
 * 데이터 출처 상태 — 화면이 "지금 보는 값이 어디서 왔는지" 명시하기 위한 공통 타입.
 *
 * 우리 거버넌스: 폴백(mock) 값을 실데이터인 척 보여주지 않는다. 호출 결과는 항상
 * source 를 달고 돌려, UI 가 배지로 사용자에게 알리도록 한다.
 *  - "live"     : 백엔드 실데이터
 *  - "demo"     : 시연 모드(NEXT_PUBLIC_DEMO=1)의 고정 데이터 — 의도적으로 선택한 값
 *  - "empty"    : 정상 응답이지만 결과 없음(예: RAG 404 — 관련 문서 없음)
 *  - "fallback" : 호출 실패(네트워크/타임아웃/5xx)로 mock 표시 중 ⚠️
 *
 * "demo" 와 "fallback" 은 같은 mock 값을 쓰지만 뜻이 다르다. fallback 은 사고이고
 * demo 는 선택이다. 둘을 한 값으로 합치면 시연 중에 백엔드가 실제로 죽어도 알 수 없다.
 */
export type DataSource = "live" | "demo" | "empty" | "fallback";

export interface ApiResult<T> {
  data: T;
  source: DataSource;
  /** 폴백·빈결과 사유(사용자 안내·디버깅용). live 일 땐 보통 비움. */
  note?: string;
}

export function live<T>(data: T): ApiResult<T> {
  return { data, source: "live" };
}

export function empty<T>(data: T, note?: string): ApiResult<T> {
  return { data, source: "empty", note };
}

export function fallback<T>(data: T, note?: string): ApiResult<T> {
  return { data, source: "fallback", note };
}

export function demo<T>(data: T, note = "시연 고정 데이터"): ApiResult<T> {
  return { data, source: "demo", note };
}

/**
 * "이 값을 신뢰하고 화면·store 에 반영해도 되는가."
 *
 * 호출부가 `source === "live"` 로 직접 비교하면 "demo" 가 실패로 취급돼
 * 시연에서 에러 상태로 빠진다. 그래서 판정을 여기 한 곳에 둔다.
 * 데모 모드가 꺼져 있으면 "demo" 는 발생하지 않으므로
 * 기존 `=== "live"` 와 **완전히 동일하게** 동작한다.
 */
export function isTrusted(source: DataSource): boolean {
  return source === "live" || source === "demo";
}
