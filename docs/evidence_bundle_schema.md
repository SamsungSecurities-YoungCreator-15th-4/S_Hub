# 감사 증거 번들 스키마 (Evidence Bundle Schema)

> 계약 SSOT: [`app/evidence/schema.py`](../app/evidence/schema.py)
> 이 문서는 그 파일에서 추출한 서술이며, 값이 갈리면 코드가 우선한다.

---

## 1. 목적 — 실행 1회 = 서류철 1개

무효 조건 ④는 **수동 조립**이다. 감사 서류를 사람이 파일을 모으고 값을 옮겨 적어 만들면, 그 서류철은 실행의 증거가 아니라 사람의 진술이 된다. 옮겨 적는 순간 원본과 어긋날 수 있고, 어긋났는지 확인할 방법도 없기 때문이다. 증거 번들은 이 조건을 방어하기 위해 존재한다 — **실행이 끝난 자리에서 최종 state 하나를 읽어 서류철 한 벌을 결정론적으로 찍어낸다.** 사람이 값을 채우는 칸은 어디에도 없고, 번들의 모든 값은 state의 어느 경로에서 왔는지 되짚을 수 있다. `app/evidence/state_dump.py`가 "state를 사람이 손으로 만들면 서류철을 손으로 조립하는 셈"이라고 적은 것이 이 문서의 전제다.

---

## 2. 생성 방법

```
python scripts/run_graph.py --auto-approve --evidence-bundle
```

이 한 줄이면 그래프가 완주하고, 종료 직후 번들 디렉터리가 생긴다. **수작업 단계는 0이다.**

- `--evidence-bundle`은 인자를 생략할 수 있고, 생략하면 출력 루트는 `evidence/`다(`scripts/run_graph.py`의 `DEFAULT_EVIDENCE_ROOT`). `--evidence-bundle DIR`로 다른 루트를 지정할 수 있다.
- 번들은 **in-process로 생성**된다. `scripts/make_evidence_bundle.py`를 subprocess로 다시 부르지 않는데, 명령과 번들 사이에 사람이 파일을 옮기거나 경로를 지정하는 단계가 끼면 "명령 한 번이면 자동 생성"이 성립하지 않기 때문이다.
- **정상 확정과 수동검토 차단 양쪽 모두에서 생성된다.** 차단 사례도 제출물이다.
- 생성 후 `BUNDLE_FILENAMES` 전체가 실제로 존재하는지 확인하고, 하나라도 없으면 `SystemExit`으로 실패한다. 번들 없이 성공 종료하면 서류철이 빈 채로 제출되기 때문이다.

### run_id 부여 규칙

`run-YYYYMMDD-NNN` 형식으로 자동 부여된다(`allocate_run_id`). 출력 루트를 훑어 같은 날짜 접두를 가진 디렉터리의 일련번호를 모으고, 비어 있는 가장 작은 번호를 `%03d`로 잡는다. **같은 날 재실행해도 기존 번들을 덮어쓰지 않는다.**

`generated_at`과 `run_id`의 날짜는 `datetime.now(timezone.utc)`를 **한 번만** 읽어 함께 쓴다. 두 번 호출하면 자정 경계에서 둘의 날짜가 갈린다.

### 관련 플래그

| 플래그 | 동작 |
| --- | --- |
| `--evidence-bundle [DIR]` | 실행 종료 후 번들 자동 생성. 기본 루트 `evidence/` |
| `--dump-state PATH` | 최종 state를 결정론적 JSON으로 저장 (번들 입력과 같은 내용) |
| `--calibration PATH` | R2 calibration 리포트를 번들에 실음. 생략하면 §4.8 자리가 `available:false`로 나간다 |

`scripts/make_evidence_bundle.py`를 직접 부르는 경로도 남아 있다(`--state`/`--out`/`--run-id`/`--calibration`). 이 경로에서 `--run-id`를 생략하면 `state.trace_id`를, 그마저 없으면 `unknown-run`을 쓴다.

`evidence/`는 실행 산출물이라 git이 추적하지 않는다(`.gitignore`). 실행마다 `run-YYYYMMDD-NNN`이 쌓이고 `trace_id`·LangSmith URL 같은 실행 식별자가 들어가므로, 감사 제출본은 레포가 아니라 제출 경로로 따로 전달한다.

---

## 3. 디렉터리 구조

`BUNDLE_FILENAMES` 기준. 여기 있는 파일은 번들 디렉터리에 **반드시** 생성된다.

```
<출력 루트>/run-YYYYMMDD-NNN/
├── manifest.json                 # 파일별 sha256 + 생성 주체
├── summary.md                    # 1페이지 요약 (§7)
├── trace.json                    # 실행 추적
├── judge_rationale.json          # judge 판정과 사유
├── citation_verification.json    # 인용 검증 결과
├── hard_stop_record.json         # 차단 기록
├── replay_diff.json              # 재실행 해시 대조
├── llm_audit.json                # LLM 감사
├── calibration_summary.json      # R2 캘리브레이션 요약·개선 전후 비교 (§4.8)
└── bundle_hash.txt               # manifest의 sha256
```

`HASHED_FILENAMES`는 위에서 `manifest.json`과 `bundle_hash.txt`를 뺀 나머지다. manifest는 해시를 담는 그릇이고 bundle_hash는 manifest의 해시라서, 자기 자신을 넣으면 순환한다.

**이 문서는 파일 종수를 숫자로 적지 않는다.** 숫자를 적으면 파일이 늘 때마다 상수와 갈라지고, 그 drift를 잡아 줄 장치가 없다. `tests/test_evidence_bundle.py`의 `test_bundle_creates_every_contract_file`도 같은 이유로 숫자를 박지 않고 `BUNDLE_FILENAMES == HASHED_FILENAMES + {manifest, bundle_hash}`라는 구조를 검사한다. 위 목록이 어긋나면 그 테스트가 아니라 이 문서를 고친다 — SSOT는 `app/evidence/schema.py:50` (BUNDLE_FILENAMES)다.

---

## 4. 파일별 계약

각 표의 "출처"는 state의 원본 경로다. 값이 없을 때의 표기는 §5를 따른다.

### 4.1 `manifest.json` — `MANIFEST_REQUIRED_KEYS`

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `schema_version` | str | `BUNDLE_SCHEMA_VERSION` 상수 |
| `run_id` | str | 호출자가 넘긴 run_id (§2 규칙) |
| `generated_at` | str | 생성 시각 (UTC ISO 8601, 초 단위) |
| `generated_by` | dict | `script`(고정 문자열) · `git_sha`(`git rev-parse HEAD`) |
| `files` | dict[str, str] | `HASHED_FILENAMES` 각각의 파일 sha256 |

### 4.2 `trace.json` — `TRACE_REQUIRED_KEYS`

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `trace_id` | str | `state.trace_id` |
| `langsmith_trace_url` | str | `report.governance.langsmith_trace_url` (없으면 `run_config.observability`) |
| `langsmith_trace_urls` | list | `report.governance.langsmith_trace_urls` |
| `langsmith_project` | str | `report.governance.langsmith_project` (없으면 `run_config.observability`) |
| `node_execution_order` | — | **state에 없다** — §8 참조 |

### 4.3 `judge_rationale.json` — `JUDGE_RATIONALE_REQUIRED_KEYS`

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `passed` | bool | `state.judge.passed` |
| `reason` | str | `state.judge.reason` |
| `score` | num | `state.judge.score` |
| `judge_retries` | int | `state.judge_retries` |
| `judge_max_retries` | int | `state.run_config.judge_max_retries` |
| `checks` | list | `state.judge.checks` — 항목별 `passed`·`required`·`detail` + 축 이름 병기 |
| `rubric` | dict | `state.judge.rubric` — 축별 `passed`·`reason` + 축 이름 병기 |
| `manual_review_flags` | list | `state.judge.manual_review_flags` |
| `judge_feedback` | str | `state.judge_feedback` |

**축 이름 병기** — `app/judge/axes.py`가 6축 한글↔영문 매핑의 SSOT다. 번들은 `axis_en`과 `axis_ko`를 함께 싣는다.

| `axis_en` | `axis_ko` |
| --- | --- |
| `source_validity` | 출처 |
| `numeric_consistency` | 수치 정합 |
| `hallucination` | 환각 |
| `false_precision` | 위조정밀도 |
| `disclaimer` | 면책 |
| `prohibited_expression` | 금지표현 |

한글 표기는 과제 스타터킷 라벨링 가이드 §4의 규정값이라 공백·철자를 바꾸지 않는다. 6축 루브릭이 **아닌** 사전 검사(`citation_content_contract` 등)는 한글 규정 표기가 없으므로 지어내지 않고 `axis_ko=None`에 사유(`axis_ko_note`)를 남긴다.

### 4.4 `citation_verification.json` — `CITATION_VERIFICATION_REQUIRED_KEYS`

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `citation_count` | int | `state.citations` 길이 |
| `verified_citation_count` | int | `state.citations` 중 `verified is True` 개수 |
| `citations` | list | `state.citations` — `claim`·`quote`·`source`·`chunk_id`·`verified`·`provenance`·`chunk_text_present`·`evidence_role`·`category`·`published_at` |
| `rejected_citations` | list | `state.citation_rejections` |

`rejected_citations` 항목별 필드는 `attempt`·`topic`·`chunk_id`·`cited_source`·`cited_locator`·`quote`·`reason`·`original_comparison`이다. `attempt`는 judge 재작성 루프에서 시도별로 누적되므로 어느 시도의 탈락인지 구분하기 위해 함께 싣는다. 상세 계약은 [`docs/hard_stop_contract.md`](hard_stop_contract.md)의 인용 검증 계약 절을 따른다.

`chunk_text_present`는 원문을 그대로 싣지 않고 존재 여부만 bool로 남긴다.

### 4.5 `hard_stop_record.json` — `HARD_STOP_RECORD_REQUIRED_KEYS`

> **[※]** 이 파일의 키 이름은 **우리가 정하지 않는다.** `app/nodes/manual_review_gate.py`가 `report.governance.manual_review_gate`에 실제로 기록하는 이름을 그대로 옮긴다(`MANUAL_REVIEW_GATE_KEYS`). 담당이 다른 산출물이므로 번들이 이름을 새로 만들면 원본과 어긋난다.

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `blocked` | bool | **번들 파생값** — 아래 설명 |
| `blocked_derived_from` | str | 파생 근거 경로 (`BLOCKED_DERIVED_FROM`) |
| `report_status` | str | `report.status` |
| `report_finalized` | bool | `report.finalized` |
| `confirmation_allowed` | bool | `report.governance.confirmation_allowed` |
| `export_allowed` | bool | `report.governance.export_allowed` |
| `manual_review_required` | bool | `report.governance.manual_review_required` |
| `confirmation_blocked_reason` | str | `report.governance.confirmation_blocked_reason` |
| `manual_review_gate` | dict | `report.governance.manual_review_gate` 전문 |
| `source_paths` | dict | `HARD_STOP_SOURCE_PATHS` — 위 7개 값의 원본 경로표 |

`blocked`는 state에 존재하는 키가 **아니다.** 성공 실행에서도 파일을 반드시 만들기 위해 번들이 파생시킨 값이며, 그래서 근거 경로를 `blocked_derived_from`에 함께 적는다. 판정식은 `report.governance.manual_review_gate.status == 'blocked'`다.

`manual_review_gate` 전문의 키는 12개이며 `MANUAL_REVIEW_GATE_KEYS`의 순서를 그대로 따른다 — `status`·`trigger`·`policy_version`·`trace_id`·`stopped_at`·`stopped_at_basis`·`judge_passed`·`judge_retries`·`judge_max_retries`·`failed_axes`·`computation_hash`·`decision_hash`.

**`decision_hash`는 같은 차단 판단 내용에 대한 조건부 재현 지문이다** —
[`docs/reproducibility_scope.md`](reproducibility_scope.md) §2.1을 따른다. 해시 입력은
차단 판단 내용(`status`·`trigger`·`policy_version`·`judge_passed`·`judge_retries`·`judge_max_retries`·`failed_axes`·`computation_hash`)뿐이고, 실행마다 달라지는
`trace_id`와 `stopped_at`은 제외된다. 다만 LLM Judge의 `failed_axes`가 바뀌면
다른 판단이므로 해시가 달라지는 것이 정상이다.

`policy_version`은 `config/hard_stop_policy.yaml`의 `version`에서 오며 해시 입력에 포함된다. 정책이 바뀌면 같은 판단이라도 지문이 갈리는 것이 의도된 동작이다.

`stopped_at`은 승인 잠금일 또는 기준일에서 산출한 **논리적 기준시각**이지 차단이 실제로 일어난 벽시계 시각이 아니다. 감사자가 이를 혼동하지 않도록 `stopped_at_basis`가 원본 경로(`approval.locked_as_of` 또는 `run_config.as_of_date`)를 함께 밝힌다. 원본이 없거나 ISO 8601이 아니면 `stopped_at`은 §5의 "없음" 표기(`{"available": false, "reason": ...}`)로 나가고 `stopped_at_basis`는 `null`이 된다 — Hard Stop은 이 경우에도 예외 없이 차단으로 끝난다.

`source_paths`를 파일에 함께 싣는 이유는 감사자가 번들의 모든 값을 원본 state 키로 되짚을 수 있게 하기 위해서다.

### 4.6 `replay_diff.json` — `REPLAY_DIFF_REQUIRED_KEYS`

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `status` | str | `REPLAY_DIFF_PLACEHOLDER_STATUS` — 현재 자리표시 |
| `hashes` | dict | `config_hash`·`computation_hash`·`approval_hash` |
| `note` | str | `REPLAY_DIFF_PLACEHOLDER_NOTE` |

`hashes`는 `report.reproducibility`에서 읽고, 없으면 `run_config.config_hash` / `metrics.meta.computation_hash`로 되짚는다. 이 세 해시는 재현 범위 선언의 "재현 지문"과 정확히 일치한다.

현재 상태는 §8을 참조한다.

### 4.7 `llm_audit.json` — `LLM_AUDIT_REQUIRED_KEYS`

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `prompt_hash` | dict | `state.run_config.audit.llm.*.latest.prompt_hash` (컴포넌트별) |
| `model_version` | dict | `state.run_config.audit.llm.*.latest.model_version` (컴포넌트별) |
| `ips_extraction_meta` | dict | `state.ips_extraction_meta` |
| `raw_prompt_and_response` | — | **미저장** — §8 참조 |

### 4.8 `calibration_summary.json` — `CALIBRATION_FILE_REQUIRED_KEYS`

> **[※]** calibration 필드도 **다른 담당자의 산출물**이다. 번들은 이름을 정하지 않고 `app/evaluation/`의 구현을 그대로 참조한다. 특히 파생 지표의 필드명은 `match`·`match_rate`이며 **`agreement`가 아니다** — 병합된 코드가 SSOT이기 때문이다.

| 키 | 타입 | 출처 |
| --- | --- | --- |
| `source` | dict | **실행 등급** (`CALIBRATION_GRADE_KEYS`) 또는 §5의 "없음" 표기 |
| `v1` | dict | 개선 전 측정. `calibration_summary()` 결과 또는 §5의 "없음" 표기 |
| `v2` | dict | 개선 후 재측정. 같은 형태 |
| `comparison` | dict | v1·v2 비교. `CALIBRATION_COMPARISON_REQUIRED_KEYS` 또는 §5의 "없음" 표기 |
| `mismatch_detail_excluded` | str | 오판 사례 상세를 싣지 않는 이유 (`CALIBRATION_MISMATCH_EXCLUSION_REASON`) |

#### `source` — 수치보다 먼저 봐야 하는 값

같은 일치율이라도 **개발용 mock에서 나온 수치와 공식 실행 수치는 증거로서 값이 다르다.** 등급이 안 보이면 감사자가 리허설 숫자를 공식 실측으로 읽는다. 그래서 일치율보다 앞에 둔다.

| 키 | 의미 |
| --- | --- |
| `schema_version` | 리포트 스키마 버전 |
| `mode` | `dev_mock` · `offline_rehearsal` · `official` 중 하나 |
| `official_validation_passed` | `--official` 검증을 통과했는가 |
| `langsmith_required` | LangSmith run ID 요건을 적용했는가 |

- **`langsmith_required=false`는 공식 등급이 아니다.** R2는 LangSmith 실행 기록 제출이 과제 요구사항이라 `validate_official_case_set`의 `require_langsmith` 기본값이 True다. `--no-langsmith`로 이를 낮춰 돌린 실행은 `mode=offline_rehearsal`이 되며, 번들은 그 사실을 감추지 않는다.
- **등급을 아는 한, 등급이 낮아도 수치는 그대로 싣는다.** `dev_mock`이든 `offline_rehearsal`이든 수치는 나가고 등급이 그 옆에 붙는다. 감추는 것이 아니라 밝히는 것이 이 블록의 목적이다.

**등급을 모르면 수치도 싣지 않는다 — fail-closed.** 아래 세 경우 `v1`·`v2`·`comparison`이 **전부** "없음" 표기로 나간다. 등급만 "없음"으로 적고 일치율은 그대로 내보내면, 감사자가 등급 줄을 지나쳤을 때 출처를 알 수 없는 수치를 공식 결과로 읽는다.

| 경우 | `source` | `v1`·`v2`·`comparison` |
| --- | --- | --- |
| 리포트를 안 넘김 | 없음 | 없음 |
| 등급 키(`CALIBRATION_GRADE_KEYS`) 중 하나라도 누락 | 없음 (누락 키를 사유에 명시) | 없음 (등급 미확인이 사유) |
| `schema_version`이 `CALIBRATION_REPORT_SCHEMA_VERSION`과 다름 | **남김** (무엇을 받았는지는 기록) | 없음 (버전 불일치가 사유) |

세 경우의 사유 문구는 섞지 않는다 — "안 줬다" · "등급을 모른다" · "줬는데 못 읽는다"는 감사에서 각각 다른 사실이다.

모르는 `schema_version`에서 수치를 버리는 이유는 필드 이름이 같아도 뜻이 달라졌을 수 있어서다. 조용히 옮기면 감사 증거에 다른 의미의 숫자가 실린다. 어댑터가 아는 버전은 `CALIBRATION_REPORT_SCHEMA_VERSION`이고, `tests/test_evidence_bundle.py`가 생산자(`scripts/calibration_report.py`의 `SCHEMA_VERSION`)와 대조한다.

**네 자리는 R2 진행 상태와 무관하게 항상 존재한다.** 채울 값이 없으면 자리를 비우는 게 아니라 `{"available": false, "reason": ...}`이 들어간다 — `hard_stop_record`가 성공 실행에서도 `blocked=false`로 반드시 생성되는 것과 같은 원칙이다(§8.5). 파일이 없는 것과 "아직 측정하지 않았다"는 감사에서 전혀 다른 의미다.

**입력은 state가 아니다.** calibration은 실행 1회분 state가 아니라 사례집 전체를 judge에 돌린 결과의 집계라, 그래프 한 번의 최종 state에는 존재할 수 없다. `scripts/calibration_report.py --out` 산출물을 아래 플래그로 넘긴다.

```bash
python scripts/run_graph.py --auto-approve --evidence-bundle --calibration out/calibration_report.json
python scripts/make_evidence_bundle.py --state run_state.json --out evidence/run-001 --calibration out/calibration_report.json
```

#### `v1`·`v2` 한쪽의 계약 — `CALIBRATION_SUMMARY_REQUIRED_KEYS`

계약은 `app/evidence/schema.py`의 `calibration_summary()`와 `CALIBRATION_SUMMARY_REQUIRED_KEYS`에 정의돼 있다. 필수 키는 `prompt_version`·`evalset_hash`·`evalset_case_count`·`total`·`confusion_matrix`·`derived`·`per_axis`다.

리포트에 이미 `overall`·`axis_metrics`가 들어 있지만 번들은 **그것을 옮겨 적지 않는다.** `app/evidence/schema.py:455` (calibration_summary_from_report)가 리포트의 `records`를 `CalibrationRecord`로 되돌려 `calibration_summary()`에 그대로 태운다. 옮겨 적으면 집계 로직이 두 벌이 되어 한쪽만 고쳐지는 순간 번들과 리포트가 갈리는데, 그 상황이 이 문서가 처음부터 막으려던 것이다.

#### `comparison`의 계약 — `CALIBRATION_COMPARISON_REQUIRED_KEYS`

필드명은 `app/evaluation/judge_calibration.py`의 `VersionComparison`을 그대로 옮긴다: `before`·`after`·`match_rate_delta`·`false_negative_delta`·`false_positive_delta`·`axis_before`·`axis_after`·`before_code_sha`·`after_code_sha`.

- **계약 키가 하나라도 없으면 부분 결과를 만들지 않는다.** 일부만 실으면 감사자가 "비교했는데 값이 빈 칸"으로 읽는다. 통째로 "없음" 표기로 나가고 누락 키를 사유에 적는다.
- `before_code_sha`·`after_code_sha`를 함께 싣는 이유는 v1·v2의 `code_sha` 동일성을 요구하지 않기 때문이다. judge LLM축 프롬프트가 코드에 하드코딩돼 있어 진짜 개선이면 `code_sha`가 바뀌는 것이 정상이지만, 그렇다고 "프롬프트만 바뀌었다"는 보장은 없다. 두 값을 그대로 남겨 증거를 검토하는 사람이 직접 판단하게 한다.

#### 오판 사례 상세는 싣지 않는다

`find_mismatches()`가 만드는 `Mismatch`에는 `human_rationale` — 사람이 라벨에 적은 근거 원문 — 이 들어 있다. 번들에 실으면 답안지가 증거물로 새어 나간다. 그래서 번들은 **집계값만** 싣고, 사유를 `mismatch_detail_excluded`에 명시한다. 오답 원인 분석(평가 포인트 2)은 `scripts/calibration_report.py --out` 산출물이 담당한다.

- `confusion_matrix`가 **유일한 원본**이고(`true_positive`·`true_negative`·`false_positive`·`false_negative`), `CALIBRATION_DERIVED_KEYS`(`match`·`match_rate`·`false_negative`·`false_positive`)는 전부 거기서 계산된 파생값이다. 두 곳에 손으로 적으면 한쪽만 고쳐져 어긋날 수 있어, 감사 증거에서는 사람이 채우는 칸을 남기지 않는다.
- `per_axis`는 축별로 같은 구조를 갖고, 여기에 `human_fail_support`와 `defect_recall`이 추가된다. 결함이 드문 축은 `match_rate`가 과장되기 때문이다 — 20건 중 결함 1건을 놓치면 `match_rate` 95%인데 `defect_recall`은 0%다.
- `prompt_version`이 필요한 이유는 일치율이 프롬프트에 종속된 수치라서다. 버전이 없으면 개선 전후 비교와 LangSmith `prompt_hash` 대조가 성립하지 않는다.
- `evalset_hash`가 필요한 이유는 일치율이 (프롬프트 × 평가셋)의 함수라서다. 평가셋 정체성이 없으면 사례 추가·라벨 변경으로 인한 변동을 judge 성능 변화로 오진한다. 수동 버전 문자열은 drift가 생기므로 내용 해시로 고정한다. 해시 대상에는 사례 본문과 **사람 라벨**이 함께 들어간다 — 본문만 고정하면 같은 본문을 다시 라벨링해 정답을 바꾼 경우를 못 잡는다.

**이 계약은 `calibration_summary.json`으로 번들에 실린다.** 아직 채워지지 않은 자리의 현재 상태는 §8.4를 참조한다.

---

## 5. 누락 표기 규칙

값이 없을 때 조용히 비우지 않는다. `unavailable()`이 유일한 통로이며 형식은 다음과 같다.

```json
{ "available": false, "reason": "<원본 키 경로> 없음" }
```

필요하면 `note`·`recovery` 같은 키가 덧붙는다.

**왜 구분하는가** — "없는 것"과 "안 채운 것"은 감사에서 전혀 다른 의미다. 값이 비어 있을 때 그것이 *원래 없어서*인지 *번들이 채우다 만 것*인지 구분되지 않으면, 서류철 전체의 신뢰가 무너진다. 그래서 없으면 없다고 **사유와 원본 경로를 함께** 적는다.

한 가지 더 중요한 구분이 있다. **빈 문자열·빈 리스트를 "없음"으로 적으면 안 된다.** 확정 리포트의 `confirmation_blocked_reason=""`이나 통과 실행의 `manual_review_flags=[]`는 값이 빠진 게 아니라 "차단 사유가 없다"는 정보 그 자체다. 그래서 판정은 **키가 없거나 값이 `None`일 때만** "없음"으로 간다.

번들이 조립한 파생 섹션은 기준이 다르다 — `None`·`{}`·`[]`·`""` 어느 쪽이든 비면 "없음"으로 적는다. 원본 값이 아니라 번들이 만든 값이므로, 비어 있다는 것 자체가 조립 실패를 뜻하기 때문이다.

---

## 6. 해시 체계

세 단계로 쌓인다.

```
① 파일별 sha256  →  ② manifest.json  →  ③ bundle_hash.txt
```

1. **파일별 sha256** — `HASHED_FILENAMES` 각각의 파일 내용 해시(`sha256_of_file`). manifest의 `files`에 파일명→해시로 들어간다.
2. **manifest.json** — 위 해시표에 `schema_version`·`run_id`·`generated_at`·`generated_by`를 더한 문서.
3. **bundle_hash.txt** — manifest 파일 자체의 sha256. 한 줄로 저장된다.

따라서 **bundle_hash 하나가 번들 전체를 봉인한다.** 어느 파일이든 한 바이트가 바뀌면 그 파일의 해시가 바뀌고, manifest가 바뀌고, bundle_hash가 바뀐다.

해시가 재현되려면 직렬화가 결정론이어야 한다. 번들의 모든 JSON은 `ensure_ascii=False`·`indent=2`·`sort_keys=True`에 끝 개행 하나를 붙여 쓴다.

### `generated_by` 구성

| 키 | 값 |
| --- | --- |
| `script` | `"scripts/make_evidence_bundle.py"` |
| `git_sha` | `git rev-parse HEAD`의 출력 |

`git_sha`는 조회에 실패하거나 출력이 비면 §5의 `unavailable(...)` 형태가 된다. 이 값이 있어야 "어느 코드가 이 번들을 만들었나"가 고정되고, LLM 프롬프트 원문 복원 경로(§8)도 여기에 걸린다.

### state 덤프의 결정론

번들 입력이 되는 state 덤프도 같은 원칙을 따른다(`app/evidence/state_dump.py`). `sort_keys=True`로 키 순서를 고정하고 `ensure_ascii=False`로 한글을 원문 유지하며, **타임스탬프·`trace_id`를 제외하면 같은 입력에서 바이트가 동일하다.** 재현 비교용으로 그 키들을 걷어낸 사본을 만드는 `canonical_for_replay()`가 따로 있다.

JSON이 표현하지 못하는 타입(datetime·Decimal·set·Path·bytes·numpy 등)은 조용히 `str()`로 뭉개지 않는다. 타입별로 명시적으로 다루고, 무엇을 어느 경로에서 어떻게 바꿨는지 `_serialization_notes`에 남긴다.

| `_serialization_notes` 키 | 의미 |
| --- | --- |
| `converted` | 변환이 하나라도 있었는가 (bool) |
| `conversions` | 변환 내역 목록 — 항목별 `path`·`original_type`·`converted_to`·`original_repr` |
| `note` | 이 구조의 의미 설명 |

`conversions`는 `path` 기준으로 정렬된다. 리스트는 `sort_keys=True`로도 정렬되지 않아, 순회 순서에 기대면 내용이 같아도 덤프 바이트가 흔들리기 때문이다.

모르는 타입은 추측해서 바꾸지 않고 `_unserializable` 표식(타입명·repr)으로 남긴다 — 조용히 통과시키는 것보다 눈에 띄는 편이 낫다. Decimal은 float으로 바꾸면 값이 달라지므로 문자열로 원형을 보존하고, set은 순서가 없어 정렬해야 결정론이 된다.

현재 그래프의 최종 state에는 변환 대상이 없다(`app/engine/`이 경계에서 전부 `float()`로 캐스팅한다). 그래서 `conversions`는 보통 빈 리스트이며, **비어 있다는 사실 자체가 "원형 그대로 실렸다"는 증거**가 된다.

---

## 7. 5분 감사 대응 — `summary.md`

`summary.md`는 **1페이지**다. 감사자가 처음 5분에 물을 것만 담고, 그 이상은 나머지 파일로 넘긴다. 서류철을 다 읽어야 판단이 서면 그건 5분 대응이 아니다.

실리는 항목은 다음과 같다.

| 절 | 내용 |
| --- | --- |
| 머리말 | run_id · 스키마 버전 · 기준일(`as_of_date`) |
| 판정 | `judge.passed` · `report.finalized` · `report.status` |
| 차단 | 차단 여부(예/아니오) · `export_allowed` |
| 실패 축 | 필수 검사 중 미통과 축을 한글(영문)로 병기. 없으면 "없음 (필수 검사 전부 통과)" |
| 차단 사유 | `confirmation_blocked_reason` |
| 주요 해시 | `config_hash` · `computation_hash` · `approval_hash` · `report_hash` |
| 추적 | `trace_id` · LangSmith trace URL |

세 가지를 눈여겨볼 만하다.

- **실패 축은 두 경로로 찾는다.** `judge.checks`에서 `required=True`인데 통과하지 못한 축을 먼저 모으고, 거기서 안 나오면 `manual_review_gate.failed_axes`로 되짚는다. 차단 실행에서도 실패 축이 비지 않게 하기 위해서다.
- **앞의 세 해시가 재현 지문이다.** [`docs/reproducibility_scope.md`](reproducibility_scope.md) §2가 `config_hash`·`computation_hash`·`approval_hash`를 재현 보장 대상으로 선언한다. 셋이 한 화면에 모여 있어야 감사자가 `summary.md` 한 장으로 재현 범위를 확인할 수 있다 — 하나라도 빠지면 `replay_diff.json`을 따로 열어야 한다.
- **`report_hash`는 재현 지문이 아니다.** state에서 읽는 값이 아니라 번들이 `report` 전문에서 계산한 값이며, summary에 그 사실과 함께 "재현 지문 아님"을 괄호로 적는다.

값이 §5의 "없음" 형태이면 `없음 (사유)`로 풀어 쓰고, `None`이나 빈 문자열이면 `-`로 적는다.

---

## 8. 알려진 공백

현재 `available: false`로 나가거나 아직 채워지지 않은 항목이다. **감추지 않고 번들 안에 사유와 함께 싣는다.**

### 8.1 `llm_audit.raw_prompt_and_response` — LLM 프롬프트·응답 원문 미저장

state에 원문이 없다. 이것은 결함이 아니라 `app/llm/audit.py`의 **의도된 설계**다("비밀값 없이 기록"). 감사는 해시 기반으로 이뤄지며, 번들은 그 사실과 함께 복원 경로를 명시한다.

| 키 | 내용 |
| --- | --- |
| `reason` | `RAW_LLM_UNAVAILABLE_REASON` — 미저장 사실 |
| `recovery.git_sha` | 이 커밋에서 프롬프트 원문을 복원할 수 있다 |
| `recovery.prompt_hash_items` | 컴포넌트별 프롬프트 해시 항목 |
| `observability` | 응답 원문 관측은 LangSmith trace 담당 |

### 8.2 `trace.node_execution_order` — 노드 실행 순서 미기록

노드 실행 순서는 `scripts/run_graph.py`가 스트리밍 중 **지역 변수로만** 수집하고 state에 기록하지 않는다. 따라서 state를 입력으로 받는 번들에서는 채울 수 없고, `available: false`로 사유와 함께 나간다.

### 8.3 `replay_diff` — 1회 실행분만

`status`는 `single_run_only` 자리표시다. 번들은 1회 실행분의 해시만 싣고 **동일 입력 2회 실행 대조는 수행하지 않는다.** `--evidence-bundle` 배선은 번들을 자동 생성할 뿐 재실행 대조를 하지 않기 때문이다.

**이 번들은 재현성이 증명되었음을 뜻하지 않는다.** 표시는 R5 재현 검증에서 채워질 때까지 유지한다. 재현 범위 자체의 선언은 [`docs/reproducibility_scope.md`](reproducibility_scope.md)를 따른다.

### 8.4 `calibration_summary.json` — 측정 전 실행

**파일은 편입됐다.** `BUNDLE_FILENAMES`에 들어 있어 모든 실행에서 생성된다(§4.8).

다만 R2가 측정을 끝내기 전까지, 또는 `--calibration`을 넘기지 않은 실행에서는 `source`·`v1`·`v2`·`comparison` 네 자리가 `available: false`로 나간다. 이것은 감추는 것이 아니라 §5 규약대로 **못 잰 것을 못 쟀다고 적는 것**이다. 사유에는 원본 경로(`R2 calibration 리포트 입력`)와 복원 방법(`scripts/calibration_report.py --out` 산출물을 `--calibration`으로 전달)이 함께 실린다.

R4 최종 DoD는 **`source.mode=official`인 v1·v2가 채워진 번들**이 제출될 때 닫힌다. `offline_rehearsal` 등급으로 채워진 번들은 파일은 완성돼 보여도 R2 제출 요건을 만족하지 않는다 — `source` 블록이 그 구분을 드러내라고 있는 것이다. 배선은 이제 R2 산출물을 기다릴 뿐이다.

### 8.5 `hard_stop_record.manual_review_gate` — 차단되지 않은 실행

정상 확정 실행에서는 `manual_review_gate` 노드가 실행되지 않으므로 이 키가 `available: false`가 된다. 이는 공백이 아니라 **정상 동작**이며, 번들은 그 사유를 `note`에 적는다. 같은 파일의 `blocked=false`가 같은 사실을 파생값으로 확인해 준다.

---

## 9. 관련 문서

- [`docs/reproducibility_scope.md`](reproducibility_scope.md) — 무엇이 재현 대상이고 무엇이 아닌지의 선언. `replay_diff`의 세 해시와 `decision_hash`의 재현 보장 근거가 여기에 있다.
- [`docs/hard_stop_contract.md`](hard_stop_contract.md) — Judge Hard Stop 계약과 인용 검증 계약. `hard_stop_record.json`과 `citation_verification.json`의 원본 계약이다.
- [`app/evidence/schema.py`](../app/evidence/schema.py) — 이 문서의 SSOT. 파일명·필수 키·"없음" 표기가 전부 여기서 온다.
