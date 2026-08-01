# Judge Hard Stop·인용 검증 계약

## 1. 목적

Judge 필수 검사를 통과하지 못한 리포트가 확정본 또는 다운로드 가능한 자료로
노출되는 경로를 차단한다. 인용은 `verified=true` 플래그만 신뢰하지 않고
인용문·문서명·조항/주장·청크 원문을 결정론적으로 다시 대조한다.

## 2. 재시도 상한 SSOT

- 단일 설정값: `config/config.yaml`의 `judge_max_retries`
- 해석: 최초 Judge 평가를 포함한 최대 **시도 횟수**
- 코드 접근점: `app.nodes.judge_eval.resolve_max_judge_retries`
- 환경변수나 그래프 상수로 별도 상한을 만들지 않는다.
- 누락·불리언·0 이하·비정수 값은 코드 기본값으로 대체하지 않고 즉시 실패한다.

## 3. 그래프 분기

```text
judge_eval
  ├─ judge.passed=true
  │    → assemble_report → END
  ├─ judge.passed=false AND judge_retries < judge_max_retries
  │    → rag_cite → judge_eval
  └─ judge.passed=false AND judge_retries >= judge_max_retries
       → manual_review_gate → END
```

`manual_review_gate`는 자동 승인 노드가 아니다. 실패 상태를 잠그고 사람 검토
대기 증거를 남기는 terminal Hard Stop이다. 수동 검토 이후 확정하는 별도 업무
절차는 이번 계약의 범위 밖이며, 이 노드에서 우회 승인하지 않는다.

## 4. R2 Judge 반환 계약

R2 담당자와 아래 필드를 합의한다. 철자와 타입을 바꾸면 그래프와 R4 증거 수집이
깨지므로 함께 변경한다.

| 필드 | 타입 | Hard Stop 사용 방식 |
|---|---|---|
| `judge.passed` | `bool` | `true`일 때만 정상 리포트 조립 |
| `judge.reason` | `str` | 차단 사유 원문 |
| `judge.checks` | `list[dict]` | `required=true`, `passed!=true`인 검사명을 실패 축으로 기록 |
| `judge.manual_review_flags` | `list[str]` | 수동 검토 경고 |
| `judge_retries` | `int` | SSOT 상한과 비교 |
| `judge_feedback` | `str` | 재작성 가능한 동안 `rag_cite`에 전달 |

필수 검사는 하나라도 명시적으로 `passed=true`가 아니면 실패로 취급한다.

## 5. 인용 검증 계약

### 검색 직후 검증

`app.rag.citations.verify_citations`가 다음을 확인한다.

1. `chunk_id`가 이번 검색 결과에 실제로 존재한다.
2. 표시한 문서명이 청크 metadata의 `source`와 일치한다.
3. 공백 정규화한 인용문이 청크 원문의 실제 부분문자열이다.
4. `article`, `clause`, `section`, `locator` metadata가 제공된 문서는 조항
   표기를 생략할 수 없고, 표시한 조항·절·항이 청크 metadata와 일치해야 한다.
5. provenance에 문서명·청크·조항/주장을 고정하고, 인용문과 청크 원문은
   SHA-256 지문으로 남긴다.

### Judge 직전 재검증

`citation_content_contract` 필수 검사가 최종 State에 저장된 인용을 다시 확인한다.
엄격 인용 게이트에서는 `extra.chunk_text`가 없거나 인용문이 원문과 다르면
실패한다. 검색 이후 문서명·청크·인용문·조항/주장 또는 원문이 변조되면
provenance 지문 대조에서 실패한다.

법령처럼 조항 metadata가 있는 문서는 조항까지 일치해야 한다. 일반 방법론 PDF처럼
조항 metadata가 없는 문서는 문서명·청크 ID·인용문·claim(topic)을 검사한다.

### 탈락 인용 기록 — `state.citation_rejections`

검증에서 **떨어진** 인용의 감사 기록이다. 통과한 인용은 `state.citations`에만
실리고, 탈락분은 여기에만 남는다. 탈락분을 `citations`로 되살리면 judge 판정이
달라지므로 두 키는 절대 섞지 않는다.

| 구분 | 내용 |
|---|---|
| 생산자 | `app/nodes/rag_cite.py` (`rag_cite`) |
| 소비자 | R4 증거 번들 — `citation_verification.json`의 `rejected_citations` |
| 재시도 규칙 | **누적**(덮어쓰기 아님). 시도별 기록을 `attempt` 오름차순으로 보존 |

레코드 필드:

| 필드 | 의미 |
|---|---|
| `attempt` | 몇 번째 RAG 시도의 탈락인가 (`judge_retries + 1`) |
| `topic` | 인용이 뒷받침하려던 설명 topic |
| `chunk_id` | 인용이 속한다고 표기한 청크 |
| `cited_source` | 인용이 "이 문서"라고 표기한 문서명 |
| `cited_locator` | 인용이 표기한 조항/절/항 |
| `quote` | 표기한 인용문 |
| `reason` | 탈락 사유 (`verify_citations` 판정) |
| `original_comparison` | 원문이 실제로 무엇이었나 — `chunk_found`, `chunk_source`, `chunk_locator`, `quote_found_in_chunk` |

**누적하는 이유** — judge 재작성 루프에서 `rag_cite`는 여러 번 방문된다. LangGraph는
리듀서가 없는 키를 덮어쓰므로 이번 시도분만 반환하면 최종 state와 번들에 마지막
시도의 탈락만 남는다. 감사에서 묻는 것은 "무엇이 왜 떨어졌나"의 전체 이력이라
시도별로 보존해야 추적이 끊기지 않는다.

같은 `attempt`의 기존 기록은 버리고 새로 쓴다 — 체크포인트 재생으로 같은 시도가
두 번 실행돼도 기록이 중복되지 않아야 한다(재현성).

`citation_rejections` 키가 아예 없는 과거 실행의 state로도 번들 생성은 성공하며,
그 경우 `rejected_citations`는 `available:false`로 표시된다.

## 6. R4 차단 증거 계약

`manual_review_gate`는 `report.governance`에 아래 값을 제공한다.

| 경로 | 값/의미 |
|---|---|
| `report.status` | `pending_manual_review` |
| `report.finalized` | `false` |
| `governance.confirmation_allowed` | `false` |
| `governance.export_allowed` | `false` |
| `governance.manual_review_required` | `true` |
| `governance.confirmation_blocked_reason` | Judge 실패 사유 |
| `governance.manual_review_gate.status` | `blocked` |
| `governance.manual_review_gate.trigger` | `judge_retries_exhausted` |
| `governance.manual_review_gate.policy_version` | 적용한 Hard Stop 정책 버전 |
| `governance.manual_review_gate.trace_id` | 해당 실행을 LangSmith·번들과 연결하는 식별자 |
| `governance.manual_review_gate.stopped_at` | 승인 잠금일 또는 기준일에서 산출한 논리적 차단 기준시각(ISO 8601) |
| `governance.manual_review_gate.stopped_at_basis` | 논리적 기준시각의 원본 경로(`approval.locked_as_of` 또는 `run_config.as_of_date`) |
| `governance.manual_review_gate.judge_passed` | 차단 당시 Judge 통과 여부(`false`) |
| `governance.manual_review_gate.judge_retries` | 차단 당시 누적 Judge 시도 횟수 |
| `governance.manual_review_gate.judge_max_retries` | 적용한 재시도 상한 SSOT 값 |
| `governance.manual_review_gate.failed_axes` | 실패한 필수 검사명 목록 |
| `governance.manual_review_gate.decision_hash` | 동일 결정의 재현성 확인용 SHA-256 |
| `governance.manual_review_gate.computation_hash` | 차단된 계산 결과 연결값 |

`decision_hash`는 차단 판단 내용(`status`, `trigger`, `policy_version`, Judge 판정·
시도 횟수·실패 축, `computation_hash`)만 해시한다. 실행마다 달라질 수 있는
`trace_id`와 시각 메타데이터 `stopped_at`은 표시·추적에는 보존하지만 해시 입력에서는
제외한다. 따라서 같은 계산과 같은 정책 판단이면 실행이 달라도 동일한 결정 지문이
생성된다.

`stopped_at`은 노드가 벽시계를 직접 읽지 않도록 `approval.locked_as_of` 또는
`run_config.as_of_date`에서 결정론적으로 산출한 논리적 기준시각이다. 실제 실행·번들
생성 시각은 LangSmith trace와 R4 `manifest.generated_at`이 담당한다. 감사자가 이를
실제 차단 발생 시각으로 오해하지 않도록 `stopped_at_basis`에 원본 경로를 함께 싣는다.
두 원본이 모두 없거나 ISO 8601 형식이 아니어도 Hard Stop은 예외로 중단되지 않으며,
`stopped_at={"available": false, "reason": ...}`로 부재 사유를 명시한다.

UI와 향후 다운로드 기능은 `report_is_exportable(report)`가 `true`일 때만 고객 제공
동작을 허용한다. 단순히 `report.finalized=true` 한 필드만 보고 허용하지 않는다.

## 7. 규칙-테스트 1:1 대응

| R3 규칙 | 대응 테스트 |
|---|---|
| 규칙 ① 상한 숫자 SSOT | `test_rule_1_retry_limit_requires_config_ssot` |
| 규칙 ② 상한 소진 실패는 사람 검토 대기 | `test_graph_e2e_exhausted_judge_stops_at_manual_review_gate` |
| 규칙 ③ 문장뿐 아니라 출처 표기도 일치 | `test_rule_3_starter_kit_source_marking_mismatch_is_rejected` |
| 조항 표기 누락·불일치 차단 | `test_verify_citations_rejects_real_quote_with_wrong_source_and_article` |
| 속성 ① 모든 유효 상한의 경계 | `test_property_retry_limit_routes_every_exhausted_failure_to_gate` |
| 속성 ② 어떤 선행 상태에서도 Hard Stop | `test_property_manual_review_gate_is_always_fail_closed` |
| 속성 ③ 인용 identity 변조 전부 차단 | `test_property_citation_identity_tampering_never_passes` |
| 결정 지문에서 실행 식별자 제외 | `test_decision_hash_excludes_trace_id` |
| 정책 버전·논리적 차단시각 기록 | `test_manual_review_gate_records_policy_and_logical_stop_time` |
| 시각 근거 누락·오류에도 fail-closed | `test_missing_or_invalid_stop_metadata_never_breaks_hard_stop` |

## 8. R1 사례집 20건 의존성

R1 사례집은 `case_001`~`case_020`의 사람 라벨 20건(정상 10·결함 10)이며,
R2가 동일한 사례집으로 Judge 개선 전·후를 평가해야 한다. 기존
`tests/test_judge_eval_evalset.py`의 `EC-01`~`EC-20`은 7월 시스템 회귀용
코드 생성 평가셋으로, R1 사례집을 대신하지 않는다.

현재 저장소에는 스타터킷 견본 3건만 있고 R1 실제 20건은 아직 없다. 따라서 R3는
제공된 FAIL 견본을 직접 사용하는 출처 회귀 테스트까지 수행하며, 실제 20건 기반
Judge 테스트·일치율·혼동행렬은 R1 사례집 병합 후 R2 파이프라인에서 수행한다.
R3 Hard Stop 테스트는 그 결과의 `judge.passed`, `judge.checks`,
`judge_feedback`, `judge_retries` 계약을 소비한다.

실행:

```bash
pytest tests/test_hard_stop_contract.py
```
