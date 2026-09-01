/**
 * 데모 모드 플래그.
 *
 * `NEXT_PUBLIC_DEMO=1` 이면 프론트가 백엔드(FastAPI·Supabase)를 호출하지 않고
 * 고정 데이터를 반환한다. 9/11 시연은 PPT 없이 화면만 띄우므로, Render 무료 티어
 * 스핀다운과 Supabase 연결을 시연 경로에서 제거하는 것이 목적이다.
 *
 * 레포 관례는 `process.env.NEXT_PUBLIC_*` 직접 참조지만, 이 값은 api 계층·
 * AuthGuard·배너 등 여러 곳에서 읽으므로 한 곳에서 해석해 둔다.
 * 값이 정확히 "1" 일 때만 켜진다 — "0"·"false"·빈 문자열은 모두 꺼짐이다.
 */
export const IS_DEMO = process.env.NEXT_PUBLIC_DEMO === "1";
