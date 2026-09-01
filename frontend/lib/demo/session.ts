/**
 * 데모 세션 — 쿠키 한 개로 표현한 시연용 로그인 상태.
 *
 * proxy(엣지 미들웨어)는 서버에서 돌기 때문에 sessionStorage·localStorage 를 읽을 수
 * 없다. 그래서 데모 로그인 여부는 반드시 '쿠키'여야 proxy 가 /(대시보드) 진입을
 * 막고 /login 으로 보낼 수 있다. Supabase 세션도 같은 이유로 쿠키에 저장된다.
 *
 * 성질:
 *   - 세션 쿠키(Expires·Max-Age 없음) — 브라우저를 닫으면 사라진다. 리허설을 새로
 *     시작할 때 이전 세션이 남아 첫 장면을 건너뛰는 일을 막는다.
 *   - httpOnly 아님 — 로그인 핸들러가 클라이언트에서 심고 로그아웃이 지우기 때문.
 *     시연용 표식일 뿐 인증 수단이 아니므로 보호할 비밀이 없다.
 *   - 이름에 demo 가 드러난다 — 운영 쿠키와 혼동하지 않게.
 */
import { IS_DEMO } from "@/lib/demo/flag";

/** 데모 로그인 표식 쿠키 이름. proxy 와 로그인·로그아웃 핸들러가 함께 쓴다. */
export const DEMO_SESSION_COOKIE = "s_hub_demo_session";

/** 쿠키 값은 존재 여부만 의미가 있다 — proxy 는 값을 검사하지 않는다. */
const DEMO_SESSION_VALUE = "1";

/** 시연 중 타이핑을 없애기 위해 로그인 입력란에 미리 채워 두는 계정. */
export const DEMO_ACCOUNT = {
  id: "demo@s-hub.dev",
  password: "demo1234",
} as const;

/**
 * 로컬(http://localhost) 시연과 Vercel(https) 배포를 모두 지원하려면 Secure 를
 * 조건부로 붙여야 한다 — http 에서 Secure 쿠키는 아예 저장되지 않는다.
 */
function cookieSuffix(): string {
  const secure =
    typeof location !== "undefined" && location.protocol === "https:"
      ? "; Secure"
      : "";
  return `; Path=/; SameSite=Lax${secure}`;
}

/** 데모 로그인 표식을 심는다. 데모 모드가 아니면 아무것도 하지 않는다. */
export function startDemoSession(): void {
  if (!IS_DEMO || typeof document === "undefined") return;
  document.cookie = `${DEMO_SESSION_COOKIE}=${DEMO_SESSION_VALUE}${cookieSuffix()}`;
}

/** 데모 로그인 표식을 지운다(Max-Age=0). 데모 모드가 아니면 아무것도 하지 않는다. */
export function clearDemoSession(): void {
  if (!IS_DEMO || typeof document === "undefined") return;
  document.cookie = `${DEMO_SESSION_COOKIE}=${cookieSuffix()}; Max-Age=0`;
}
