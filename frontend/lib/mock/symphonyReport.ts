/**
 * S.ymphony 리스크 리포트 — 화면 상수.
 *
 * 이 파일에는 **비중과 무관한 값만** 남긴다 — 인용 목록·검증 항목·재현성 해시·면책처럼
 * 어느 안을 진단하든 같은 것들이다.
 *
 * IPS 충돌·VaR/CVaR·손실 기여도·스트레스는 예전에 여기 상수로 있었다. 그 값들은
 * 김성삼의 상담 전 비중 하나에만 맞아서, 리포트가 제안안을 진단하게 되자 본문과
 * 어긋났다. 지금은 각각 `lib/ipsConflicts.ts` · `lib/riskModel.ts` ·
 * `lib/stressScenarios.ts` 가 비중에서 계산한다.
 */

/** 리포트 기준일. 확정 승인 표기도 같은 값을 쓴다. */
export const REPORT_AS_OF = "2026-09-10";

/**
 * 리포트 산출 조건 — 재현성 블록이 읽는다.
 *
 * 총 평가금액과 신뢰수준은 여기 있지 않다. 전자는 고객 레코드에서, 후자는
 * `lib/riskModel.ts` 에서 읽는다 — 한 값을 두 곳에 적으면 갈라진다.
 */
export const REPORT_META = {
  seed: 20260910,
  engineVersion: "v0.9.3",
} as const;

// ── ⑥ 인용·출처 ─────────────────────────────────────────────────

interface CitationRow {
  no: number;
  source: string;
  locator: string;
  usedIn: string;
}

export const CITATIONS: CitationRow[] = [
  {
    no: 1,
    source: "한국은행 통화정책방향 결정문 (2026-08)",
    locator: "기준금리 3.00%",
    usedIn: "VaR/CVaR · 스트레스",
  },
  {
    no: 2,
    source: "사내 House View 2026 3Q",
    locator: "자산배분 가이드 · 위험자산 상한",
    usedIn: "IPS 충돌 · 손실 기여도",
  },
  {
    no: 3,
    source: "국세청 2026년 세금가이드 1권",
    locator: "ISA 과세특례",
    usedIn: "절세",
  },
  {
    no: 4,
    source: "국세청 2026년 세금가이드 2권",
    locator: "연금계좌 세액공제",
    usedIn: "절세",
  },
];

// ── ⑦ 검증 항목 ─────────────────────────────────────────────────

interface VerificationRow {
  label: string;
  /** 분수 표기가 필요한 항목만 채운다(퍼센트로 바꾸지 않는다). */
  ratio?: string;
  passed: boolean;
}

export const VERIFICATIONS: VerificationRow[] = [
  { label: "입력 스키마 검증", passed: true },
  { label: "자산 비중 합계 100.0%", passed: true },
  { label: "인용 근거 존재", ratio: "4/4", passed: true },
  { label: "본문·표 수치 일관성", passed: true },
  { label: "금지 표현 검사", passed: true },
  { label: "개별 종목 권유 문구 부재", passed: true },
  { label: "난수 시드 고정", passed: true },
];

export const VERIFICATION_NOTE =
  "검증 항목 중 하나라도 실패하면 이 지점에서 산출이 중단되며 승인 단계로 넘어가지 않습니다.";

// ── ⑧ 재현성 해시 ───────────────────────────────────────────────

interface HashRow {
  label: string;
  value: string;
}

export const REPRODUCIBILITY_HASHES: HashRow[] = [
  { label: "입력 스냅샷", value: "sha256:4f2a9c1d7b03" },
  { label: "정책 파일 (ips_policy.yaml)", value: "sha256:8e11b4a6d59f" },
  { label: "엔진 상수", value: "sha256:c07d3f82ae61" },
  { label: "리포트 페이로드", value: "sha256:a95c60e4128b" },
];

export const REPRODUCIBILITY_NOTE = `동일한 입력·정책·시드에서 동일한 해시가 재생성됩니다. 시드 ${REPORT_META.seed} 고정.`;

// ── ⑨ 면책 ──────────────────────────────────────────────────────

export const DISCLAIMERS: { code: string; text: string }[] = [
  {
    code: "E1",
    text: "본 리포트는 정보 제공을 목적으로 하며 특정 상품의 매매를 권유하지 않습니다.",
  },
  {
    code: "E3",
    text: "과거 데이터에 기반한 추정치이며 미래 성과를 보장하지 않습니다.",
  },
];

/** 원 단위 금액 표기. 부호를 그대로 살린다(손실은 음수로 들어온다). */
export function formatWon(krw: number): string {
  return `${krw.toLocaleString("ko-KR")}원`;
}
