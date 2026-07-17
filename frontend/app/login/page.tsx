"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { getSupabase } from "@/lib/supabaseClient";

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
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
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
