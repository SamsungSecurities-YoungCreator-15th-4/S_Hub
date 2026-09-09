"use client";

/**
 * S.ymphony 시작 화면 — 대시보드 진입 전의 관문.
 *
 * 색·배치는 엔진 콘솔의 시작 화면(`console/start_page.py`)을 따른다.
 * 아이디·비밀번호 입력란은 두지 않는다 — 심사위원이 무엇을 칠지 고민하는 순간이
 * 시연에서는 실패 지점이 된다.
 *
 * 인증 경로는 그대로다. 데모 모드는 기존과 같이 데모 세션 쿠키를 심고, 그 외에는
 * 기존과 같은 signInWithPassword 를 부른다 — 입력란에 미리 채워 두던 계정
 * (`lib/demo/session.ts`의 DEMO_ACCOUNT)을 그대로 쓸 뿐 로직을 바꾸지 않았다.
 */

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getSupabase } from "@/lib/supabaseClient";
import { IS_DEMO } from "@/lib/demo/flag";
import { DEMO_ACCOUNT, startDemoSession } from "@/lib/demo/session";

export default function StartPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleStart() {
    setError(null);
    setSubmitting(true);

    // 데모 모드: Supabase 를 부르지 않고 데모 세션 쿠키만 심는다.
    // 쿠키를 심어야 proxy(엣지)가 / 진입을 허용한다.
    if (IS_DEMO) {
      startDemoSession();
      setSubmitting(false);
      router.push("/");
      return;
    }

    const { error: signInError } = await getSupabase().auth.signInWithPassword({
      email: DEMO_ACCOUNT.id,
      password: DEMO_ACCOUNT.password,
    });
    setSubmitting(false);
    if (signInError) {
      setError("로그인에 실패했습니다. 다시 시도해 주세요.");
      return;
    }
    router.push("/");
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-[radial-gradient(1300px_900px_at_50%_40%,#16225F_0%,#0C1447_48%,#070C33_100%)] px-4">
      {/* 로고 뒤 정적 글로우 */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[36%] size-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(74,110,235,0.3)_0%,rgba(74,110,235,0)_65%)]"
      />

      <div className="relative flex flex-col items-center text-center">
        <Image
          src="/symphony-clef-white.png"
          alt="S.ymphony"
          width={200}
          height={200}
          priority
          className="h-auto w-[clamp(120px,22vw,200px)] drop-shadow-[0_0_28px_rgba(140,170,255,0.4)]"
        />
        <h1 className="mt-9 text-[clamp(2.6rem,9vw,5rem)] font-extrabold leading-[1.1] tracking-[-0.01em] text-white">
          S.ymphony
        </h1>
        <p className="mt-9 mb-[60px] text-[clamp(1rem,3vw,1.25rem)] leading-[1.75] text-[#B9C4EE]">
          PB 상담 대시보드
        </p>

        <button
          type="button"
          onClick={handleStart}
          disabled={submitting}
          className="h-[58px] w-[240px] rounded-[29px] bg-[linear-gradient(100deg,#0F5AE0_0%,#3D84FF_100%)] text-[18px] font-semibold text-white shadow-[0_10px_32px_rgba(27,109,255,0.42)] transition-all hover:bg-[linear-gradient(100deg,#1B6DFF_0%,#5C98FF_100%)] focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-[#9DBAFF] active:opacity-90 disabled:pointer-events-none disabled:opacity-50"
        >
          {submitting ? "여는 중…" : "시작하기"}
        </button>

        {error && (
          <p className="mt-5 text-[13px] font-medium text-[#FFB4B4]" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
