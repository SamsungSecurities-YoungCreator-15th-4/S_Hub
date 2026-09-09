/**
 * S.ymphony 시작 화면 — 로그인 앞에 서는 브랜드 관문.
 *
 * 색·배치는 엔진 콘솔의 시작 화면(`console/start_page.py`)을 따른다.
 *
 * 여기서는 인증을 하지 않는다. 진입 흐름은 시작화면 → 로그인 → 대시보드이며,
 * 로그인은 `app/login/page.tsx` 가 그대로 담당한다. 이 화면은 그 앞의 한 장이다.
 * 상태가 없어 클라이언트 컴포넌트로 둘 이유도 없다.
 */

import Image from "next/image";
import Link from "next/link";

export default function StartPage() {
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

        <Link
          href="/login"
          className="flex h-[58px] w-[240px] items-center justify-center rounded-[29px] bg-[linear-gradient(100deg,#0F5AE0_0%,#3D84FF_100%)] text-[18px] font-semibold text-white shadow-[0_10px_32px_rgba(27,109,255,0.42)] transition-all hover:bg-[linear-gradient(100deg,#1B6DFF_0%,#5C98FF_100%)] focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-[#9DBAFF] active:opacity-90"
        >
          시작하기
        </Link>
      </div>
    </div>
  );
}
