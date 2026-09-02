/**
 * 실행 상태(run status) — 상담 1건의 확정 수명주기.
 *
 * 값 이름은 프론트에서 만들지 않고 엔진 계약을 그대로 가져온다.
 *   - draft·reviewed·locked : `engine/state.py:43` `ApprovalStatus` (PB 승인 수명주기)
 *   - blocked               : `engine/nodes/manual_review_gate.py:20` `GATE_STATUS_BLOCKED`
 *
 * 엔진에서 두 값은 서로 다른 축이다. 승인 상태는 `approval.status`에,
 * 차단 상태는 `report.governance.manual_review_gate.status`에 기록된다.
 * 프론트는 "지금 이 상담이 어디까지 왔나"를 한 필드로 보여 주므로 둘을 합치되,
 * 이름과 값은 위 정의에서 한 글자도 바꾸지 않는다.
 *
 * 이 파일이 전이·표기 규칙의 유일한 출처다. 화면·문서는 여기를 참조만 하고
 * 문자열을 다시 적지 않는다.
 */

export const RUN_STATUS = {
  /** 작성 중 — 아직 PB 검토 전. 상담 시작 시의 초기 상태. */
  DRAFT: "draft",
  /** PB가 IPS·충돌을 검토했으나 아직 확정 전. */
  REVIEWED: "reviewed",
  /** 확정 — 리스크 계산 승인. 거래 승인이 아니다(`engine/state.py` ApprovalRecord). */
  LOCKED: "locked",
  /** 확정·다운로드 차단 — Judge 미통과로 수동검토 대기. */
  BLOCKED: "blocked",
} as const;

export type RunStatus = (typeof RUN_STATUS)[keyof typeof RUN_STATUS];

/** 상담 시작 시점의 상태. */
export const INITIAL_RUN_STATUS: RunStatus = RUN_STATUS.DRAFT;

/**
 * 허용 전이표. 여기에 없는 전이는 규칙 위반이다.
 *
 * draft    → reviewed              (PB가 IPS 승인 확인)
 * reviewed → locked | blocked      (승인 확정 / Judge 미통과 차단)
 * locked   → blocked               (확정 후 재실행에서 차단된 경우)
 * blocked  → draft                 (차단 해제는 자동 승인이 아니라 처음부터 재실행)
 *
 * `blocked → locked` 직행은 없다. 엔진의 `manual_review_gate`가 사람 검토를
 * 자동 승인하지 않기 때문이다(`docs/engine/hard_stop_contract.md`).
 */
export const RUN_STATUS_TRANSITIONS: Readonly<
  Record<RunStatus, readonly RunStatus[]>
> = {
  [RUN_STATUS.DRAFT]: [RUN_STATUS.REVIEWED],
  [RUN_STATUS.REVIEWED]: [RUN_STATUS.LOCKED, RUN_STATUS.BLOCKED],
  [RUN_STATUS.LOCKED]: [RUN_STATUS.BLOCKED],
  [RUN_STATUS.BLOCKED]: [RUN_STATUS.DRAFT],
} as const;

/** 화면 표기. 문구가 필요한 곳은 문자열을 다시 적지 말고 이 표를 읽는다. */
export const RUN_STATUS_LABEL: Readonly<Record<RunStatus, string>> = {
  [RUN_STATUS.DRAFT]: "작성 중",
  [RUN_STATUS.REVIEWED]: "PB 검토 완료",
  [RUN_STATUS.LOCKED]: "확정",
  [RUN_STATUS.BLOCKED]: "확정 차단 · 수동검토 대기",
} as const;

/**
 * 고객 제공(PDF 등) 허용 여부. `locked` 하나만 true다.
 *
 * 엔진의 `report_is_exportable`(`engine/nodes/assemble_report.py:369`)은 6개
 * 조건을 모두 만족할 때만 true를 돌려주는 실패 폐쇄 계약이며, 프론트의 실행
 * 상태에서는 그 결과가 `locked`로 나타난다. 아직 어느 화면에도 연결하지 않았다.
 */
export const RUN_STATUS_EXPORT_ALLOWED: Readonly<Record<RunStatus, boolean>> = {
  [RUN_STATUS.DRAFT]: false,
  [RUN_STATUS.REVIEWED]: false,
  [RUN_STATUS.LOCKED]: true,
  [RUN_STATUS.BLOCKED]: false,
} as const;

/** 값이 실행 상태인가 (외부 응답·저장값 검증용). */
export function isRunStatus(value: unknown): value is RunStatus {
  return (
    typeof value === "string" &&
    (Object.values(RUN_STATUS) as string[]).includes(value)
  );
}

/** `from`에서 `to`로 가는 전이가 전이표에 있는가. 같은 상태 유지는 항상 허용한다. */
export function canTransition(from: RunStatus, to: RunStatus): boolean {
  return from === to || RUN_STATUS_TRANSITIONS[from].includes(to);
}
