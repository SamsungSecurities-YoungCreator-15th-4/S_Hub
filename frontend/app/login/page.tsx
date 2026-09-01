"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { getSupabase } from "@/lib/supabaseClient";
import { IS_DEMO } from "@/lib/demo/flag";
import { DEMO_ACCOUNT, startDemoSession } from "@/lib/demo/session";

function FloatInput({
  id,
  label,
  type = "text",
  value,
  onChange,
  rightSlot,
}: {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  rightSlot?: React.ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  const lifted = focused || value.length > 0;

  return (
    <div className="relative">
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className={`w-full rounded-[14px] border-[1.5px] px-4 pb-3 pt-7 text-[16px] font-medium text-gray-900 outline-none transition-colors ${
          focused ? "border-symphony-primary" : "border-symphony-border"
        } ${rightSlot ? "pr-11" : ""}`}
      />
      <label
        htmlFor={id}
        className={`pointer-events-none absolute left-3 bg-white px-0.5 font-bold transition-all ${
          lifted
            ? `top-[-0.55rem] text-[11px] ${focused ? "text-symphony-primary" : "text-gray-400"}`
            : "top-[1.05rem] text-[14px] text-gray-400"
        }`}
      >
        {label}
      </label>
      {rightSlot && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {rightSlot}
        </div>
      )}
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  // 데모는 입력란을 미리 채워 둔다 — 발표 중 타이핑은 실패 지점이 된다.
  const [id, setId] = useState(IS_DEMO ? DEMO_ACCOUNT.id : "");
  const [password, setPassword] = useState(IS_DEMO ? DEMO_ACCOUNT.password : "");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    // 데모 모드: Supabase 를 부르지 않고 데모 세션 쿠키만 심고 통과시킨다.
    // getSupabase() 는 env 가 없으면 throw 하는데 이 핸들러에는 try/catch 가 없어,
    // 그냥 두면 setSubmitting(false) 가 실행되지 않아 버튼이 영영 잠긴다.
    // 쿠키를 심어야 proxy(엣지)가 / 진입을 허용한다 — 값은 무엇이든 통과시킨다.
    if (IS_DEMO) {
      startDemoSession();
      setSubmitting(false);
      router.push("/");
      return;
    }

    // ID 입력란을 이메일로 사용한다(Supabase Auth 는 이메일+비밀번호).
    const { error: signInError } = await getSupabase().auth.signInWithPassword({
      email: id.trim(),
      password,
    });
    setSubmitting(false);
    if (signInError) {
      setError("아이디(이메일) 또는 비밀번호가 올바르지 않습니다.");
      return;
    }
    router.push("/");
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white before:pointer-events-none before:absolute before:left-1/2 before:top-1/2 before:size-[640px] before:-translate-x-1/2 before:-translate-y-[62%] before:rounded-full before:bg-[radial-gradient(circle,rgba(74,110,235,0.07)_0%,transparent_70%)] before:content-['']">
      <div className="relative w-full max-w-[340px]">
        {/* 로고 */}
        <div className="mb-[60px] flex flex-col items-center">
          <Image src="/logo.png" alt="S.upervisor" width={72} height={72} className="rounded-3xl object-cover shadow-sm" />
          <h1 className="mt-[36px] text-[52px] font-extrabold leading-none text-symphony-primary">S.upervisor</h1>
          <p className="mt-[36px] text-[19px] text-symphony-text-muted">PB 전용 VVIP Asset Advisor Hub</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {IS_DEMO && (
            <p className="text-center text-[13px] font-medium text-symphony-text-muted">
              시연 모드입니다. 아무 값이나 입력하면 진입합니다.
            </p>
          )}

          <FloatInput id="pb-id" label="ID" value={id} onChange={setId} />

          <FloatInput
            id="pb-pw"
            label="Password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={setPassword}
            rightSlot={
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="text-gray-400 transition-colors hover:text-gray-600"
                tabIndex={-1}
                aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
              >
                {showPassword ? (
                  <EyeOff className="size-5" />
                ) : (
                  <Eye className="size-5" />
                )}
              </button>
            }
          />

          {error && (
            <p className="text-[13px] font-medium text-red-600" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-3 h-[58px] w-full rounded-[29px] bg-[linear-gradient(100deg,var(--color-symphony-primary),var(--color-symphony-gradient-to))] text-[18px] font-semibold text-white shadow-[0_10px_30px_rgba(15,90,224,0.22)] transition-all hover:bg-[linear-gradient(100deg,var(--color-symphony-hover-from),var(--color-symphony-hover-to))] active:opacity-90 disabled:pointer-events-none disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
