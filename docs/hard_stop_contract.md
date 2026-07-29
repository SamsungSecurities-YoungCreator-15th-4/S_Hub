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
| `governance.manual_review_gate.failed_axes` | 실패한 필수 검사명 목록 |
| `governance.manual_review_gate.decision_hash` | 동일 결정의 재현성 확인용 SHA-256 |
| `governance.manual_review_gate.computation_hash` | 차단된 계산 결과 연결값 |

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
