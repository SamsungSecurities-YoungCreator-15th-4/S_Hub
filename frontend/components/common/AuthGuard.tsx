"use client";

/**
 * 최소 인증 가드. 보호된 페이지를 감싸 Supabase 인증 상태를 구독하고,
 * 세션이 없으면 /login 으로 보낸다. 세션 확인 전에는 보호 콘텐츠를 렌더하지 않는다.
 *
 * onAuthStateChange 는 구독 즉시 현재 세션으로 한 번 호출되므로 초기 확인을 겸하고,
 * 이후 다른 탭 로그아웃·토큰 만료 등 런타임 상태 변화도 함께 반영한다.
 * (의도적으로 단순하게 유지 — 미들웨어/SSR 세션까지는 다루지 않는다.)
 *
 * 데모 모드(NEXT_PUBLIC_DEMO=1)에서는 Supabase Auth 를 아예 호출하지 않고 통과시킨다.
 * 9/11 시연 경로에서 로그인과 네트워크 왕복을 제거하는 것이 목적이다.
 * 기존 Supabase 경로는 그대로 두고 분기만 앞에 세웠다 — 플래그를 끄면 원래대로 동작한다.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabase } from "@/lib/supabaseClient";
import { IS_DEMO } from "@/lib/demo/flag";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  // 데모 모드는 처음부터 통과 상태로 시작한다 — effect 안에서 동기 setState 를 하면
  // 렌더가 연쇄된다(react-hooks 규칙 위반).
  const [ready, setReady] = useState(IS_DEMO);

  useEffect(() => {
    // 데모 모드: Supabase 클라이언트를 생성조차 하지 않는다.
    // (getSupabase() 는 NEXT_PUBLIC_SUPABASE_* 가 없으면 throw 한다 —
    //  시연 배포에 Supabase 키를 넣지 않아도 화면이 뜨게 하려면 여기서 끊어야 한다.)
    if (IS_DEMO) return;

    const {
      data: { subscription },
    } = getSupabase().auth.onAuthStateChange((_event, session) => {
      if (!session) {
        setReady(false);
        router.replace("/login");
      } else {
        setReady(true);
      }
    });
    return () => {
      subscription.unsubscribe();
    };
  }, [router]);

  if (!ready) return null;
  return <>{children}</>;
}
