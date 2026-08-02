# 모의 감사 런북 — 5분 증거 제시 · 3분 재실행

> 대상: 8/7 모의 감사 현장 진행 · 담당: 발표자 1명 + 보조 1명
> 이 문서는 대본이 아니라 **체크리스트**다. 팀 누구나 이 순서를 그대로 밟을 수 있어야 한다.
> 시간 수치는 전부 [`docs/reproducibility_scope.md`](reproducibility_scope.md) §4.1·§4.2·§7의 실측 인용이며,
> 이 문서에서 새로 측정한 값은 없다(§7 참조).

---

## 1. 전제 — 감사자가 무엇을 지정하고 무엇을 보는가

**감사자가 하는 것**: 제출된 번들 3건 중 **1건을 지목**한다. 그 뒤 5분간 증거를 제시받고, 3분간 라이브 재실행을 본다.

**번들 3건의 구성** ([`docs/symphony_proof_plan.md`](symphony_proof_plan.md) §2 R5 「모의 감사 대응」 기준):

| 번들 | 내용 | 덧붙이는 플래그 | state 덤프 경로 |
| --- | --- | --- | --- |
| 성공① | 정상 실행 (judge 첫 시도 통과) | 없음 | `evidence/state_dumps/success_1.json` |
| 성공② | judge 실패 → 재작성 → 통과 (루프 시연) | `--force-judge-fail N` (N은 `judge_max_retries`**보다 작은** 값) | `evidence/state_dumps/success_2.json` |
| 차단 | 재시도 소진 → `manual_review_gate` 정지 | `--force-judge-fail N` (N은 `judge_max_retries` **이상**) | `evidence/state_dumps/blocked.json` |

세 번들 모두 아래 형태로 만든다. `--dump-state`가 붙어 있는 것이 §3.4 대조의 전제다 — 이유는 §1.1.

```bash
python scripts/run_graph.py --auto-approve --offline \
  --evidence-bundle --dump-state evidence/state_dumps/<위 표의 이름>.json \
  [--force-judge-fail N]
```

- 출력 루트는 `--evidence-bundle`에 인자를 주지 않으면 `evidence/`다 — `scripts/run_graph.py:127` (DEFAULT_EVIDENCE_ROOT).
- 재시도 상한 숫자는 이 문서에 적지 않는다. 유일한 원천은 `config/config.yaml`의 `judge_max_retries`이고
  코드는 `app/nodes/judge_eval.py:28` (resolve_max_judge_retries)로만 읽는다.
- 강제 실패 횟수는 `demo_options.force_judge_fail`로 들어간다 — `scripts/run_graph.py:155` (force_judge_fail).

**감사자가 보는 것**: 번들 디렉터리 안의 파일 전체. 목록의 원천은 `app/evidence/schema.py:50` (BUNDLE_FILENAMES)이며,
이 문서는 종수를 숫자로 적지 않는다 — 파일이 늘면 문서가 상수와 갈라진다.
성공 번들이든 차단 번들이든 **`BUNDLE_FILENAMES`가 전부 생성된다** — 차단 사례도 제출물이다.

### 1.1 `submitted.json`은 번들 안에 없다 — 만들 때 같이 만들어 둔다

**번들에는 state 덤프가 들어 있지 않다.** `BUNDLE_FILENAMES`(`app/evidence/schema.py:50`)에 없기 때문이다.
§3.4의 `submitted.json`은 현장에서 번들을 열어 꺼내는 파일이 아니라 **번들을 만들 때 `--dump-state`로
함께 만들어 보관해 둔 파일**이다 — `scripts/run_graph.py:261` (dump_state).
이 절차 없이 현장에서 `replay_verify.py submitted.json …`을 치면 파일이 없어 **종료 코드 `2`로 끝난다**(§3.4).

**보관 위치는 번들 디렉터리 밖이다.** 번들 안에 넣으면 "번들 구성의 원천은 `BUNDLE_FILENAMES`뿐"이라는
위 설명과 갈린다. `evidence/state_dumps/`에 둔다 — `run_id` 채번은 `run-`으로 시작하는 디렉터리만 세므로
같은 루트에 둬도 번호가 밀리지 않는다 (`scripts/run_graph.py:47` (allocate_run_id)).

**지목된 번들과 덤프의 대응은 파일명이 아니라 `trace_id`로 확인한다.** 이름은 사람이 붙인 것이라 근거가 못 된다.

- 번들 쪽: `summary.md` §추적의 `trace_id` (= `trace.json`의 같은 값, `scripts/make_evidence_bundle.py:141` (trace_id))
- 덤프 쪽: 최상위 `trace_id`
- 두 값이 같은 덤프를 `submitted.json`으로 쓴다. 감사자가 번들을 지목하면 이 확인을 먼저 하고 명령을 친다.

**재실행은 원본과 같은 플래그로 돈다.** "같은 입력"이 계약이므로 다음 두 개를 원본에 맞춘다.

- **`--offline`은 제출 번들 생성과 재실행 양쪽에 똑같이 건다.** 한쪽만 걸면 시장 데이터와 IPS 추출 입력이
  달라져 "같은 입력"이 성립하지 않는다(§4 마지막 줄). 재현 데모를 `--offline`으로 돌리고 이유를 먼저 밝히는 것은
  `docs/symphony_proof_plan.md` §2 R5의 방침이기도 하다.
- **`--force-judge-fail N`의 N도 원본과 같은 값을 쓴다.** 기억에 의존하지 않는다 — 원본 값은 덤프 자신에
  `demo_options.force_judge_fail`로 남아 있다 (`scripts/run_graph.py:155` (force_judge_fail)).

```bash
python -c "import json;print(json.load(open('submitted.json'))['demo_options'])"
```

이건 대조가 아니라 **재실행 인자를 읽는 것**이라 §3.4의 "손으로 대조하지 않는다"에 걸리지 않는다.

---

## 2. 5분 증거 제시 동선 (합 300초)

지목받은 번들 디렉터리에서 시작한다. 아래 순서를 바꾸지 않는다.

| # | 구간 | 목표 | 무엇을 연다 | 무엇을 짚는다 |
| --- | --- | --- | --- | --- |
| ① | 번들 정체 확인 | 30초 | `manifest.json` | `run_id` · `schema_version` · `generated_by.script` · `generated_by.git_sha` |
| ② | 판정 7줄 | 60초 | `summary.md` 머리말 | 아래 7줄을 위에서 아래로 그대로 읽는다 |
| ③ | 실패 축·차단 사유 | 45초 | `summary.md` §실패 축 · §차단 사유 | 성공 번들이면 "없음 (필수 검사 전부 통과)" 한 줄로 끝낸다 |
| ④ | 재현 지문 3종 | 45초 | `summary.md` §주요 해시 | 3종이 한 절에 모여 있다 — 파일 하나만 연다 |
| ⑤ | 지목 번들 심화 1건 | 60초 | 성공 → `judge_rationale.json` / 차단 → `hard_stop_record.json` | 아래 참조 |
| ⑥ | `available:false` 선제 설명 | 30초 | 해당 파일 | 아래 §2.3 |
| — | 예비 | 30초 | — | 질문 흡수용 |

**합계 300초.**

### 2.1 ② 구간 — `summary.md` 머리말 7줄

`scripts/make_evidence_bundle.py:510` (build_summary_md)가 찍는 순서 그대로다. 순서를 바꾸지 않는다.

```
- 스키마 버전:
- 기준일(as_of_date):
- judge 통과:
- 리포트 확정(finalized):
- 리포트 상태:
- 차단(hard stop):            ← 예 / 아니오
- 고객 제공·다운로드 허용(export_allowed):
```

마지막 두 줄이 무효 조건 ②의 답이다. 차단 번들이면 `차단: 예` · `export_allowed: False`가 한 화면에 같이 보인다.

### 2.2 ④ 구간 — 재현 지문 3종을 어디서 보여주는가

**`summary.md` §주요 해시 한 곳에 3종이 다 있다.** 이 구간에서는 파일을 하나만 연다.

| 지문 | 위치 | 근거 |
| --- | --- | --- |
| `config_hash` | `summary.md` §주요 해시 | `scripts/make_evidence_bundle.py:510` (build_summary_md) |
| `computation_hash` | 〃 | 〃 |
| `approval_hash` | 〃 | 〃 |

- `summary.md`의 `report_hash`는 재현 지문이 **아니다.** 번들이 `report` 전문에서 계산한 값이며, 화면에 "재현 지문 아님"이라고 적혀 있다.
- 같은 값이 `replay_diff.json`의 `hashes`에도 있다 — `scripts/make_evidence_bundle.py:329` (build_replay_diff). 감사자가 "summary가 옮겨 적은 것 아니냐"고 물으면 그쪽을 열어 대조한다.
- 왜 3종뿐인지 묻거든 `docs/reproducibility_scope.md` §3 「제외 대상에 대한 원칙」을 연다.
- `replay_diff.json`을 열면 `status: single_run_only`가 같이 보인다. **먼저 말한다** — 이 번들은 1회 실행분 해시만 싣고 있고 2회 대조는 3분 재실행에서 지금 한다고 예고한다.

### 2.3 ⑥ 구간 — `available:false`가 나왔을 때 말할 것

표기 규약의 원천은 `app/evidence/schema.py:53` (unavailable)이고, `summary.md`에서는 `없음 (사유)` 형태로 풀려 나온다.

| 화면에 뜨는 것 | 말할 것 | 근거 |
| --- | --- | --- |
| `llm_audit.raw_prompt_and_response` | 결함이 아니라 "비밀값 없이 기록"이라는 설계. 복원 경로는 `manifest.generated_by.git_sha` | `docs/evidence_bundle_schema.md` §8.1 |
| `trace.node_execution_order` | state에 없는 값이라 채울 수 없음. CLI 출력에만 존재 | 〃 §8.2 |
| `hard_stop_record.manual_review_gate` (성공 번들) | 공백이 아니라 **정상**. 같은 파일 `blocked=false`가 같은 사실을 파생값으로 확인 | 〃 §8.5 |
| `LangSmith trace URL: 없음 (...)` | 추적이 꺼진 실행. `trace_id`는 그대로 있고 원본 키 경로가 사유에 적혀 있음 | 〃 §5 |
| `calibration_summary.json`의 `source`·`v1`·`v2`·`comparison` | R2 측정 전이라 비어 있음. **파일은 항상 생성되고** 사유와 복원 방법(`--calibration`)이 실려 있음 | 〃 §8.4 |

핵심 문장은 하나다 — **"없는 것"과 "안 채운 것"을 구분해 사유와 원본 키 경로를 함께 적었다** (`docs/evidence_bundle_schema.md` §5).

**calibration이 채워진 번들이라면 `source.mode`를 먼저 짚는다.** 허용 모드는 `dev_mock`·`offline_rehearsal`·`official`·`official_code_change`·`official_offline_code_change`이며, 공식 제출 가능 모드는 LangSmith까지 검증한 `official`·`official_code_change`뿐이다. 감사자가 일치율을 먼저 읽기 전에 등급을 말한다. 알 수 없는 mode나 모순된 검증 플래그에서는 수치도 함께 비워지므로(fail-closed), "수치는 있는데 등급을 모르는" 상태는 나오지 않는다 — `docs/evidence_bundle_schema.md` §4.8.

### 2.4 ⑤ 구간 — 지목 번들별 심화 파일

- **성공 번들** → `judge_rationale.json`: `rubric` 6축의 `passed`/`reason`, 각 축에 `axis_en`·`axis_ko` 병기. 6축 명칭 SSOT는 `app/judge/axes.py`.
- **차단 번들** → `hard_stop_record.json`: `blocked`·`blocked_derived_from`·`manual_review_gate` 12키·`source_paths`.
  `decision_hash`는 `app/nodes/manual_review_gate.py:147` (decision_hash)가 만든다. 계약 표는 `docs/hard_stop_contract.md` §6.
- 어느 쪽이든 `source_paths`를 짚어 **번들의 모든 값이 원본 state 키로 되짚힌다**는 것을 보인다.

---

## 3. 3분 재실행 동선 (합 180초)

### 3.1 실행 명령

```bash
python scripts/run_graph.py --auto-approve --offline \
  --dump-state replay.json --evidence-bundle
```

번들은 그래프 종료 직후 in-process로 생성된다 — `scripts/run_graph.py:66` (generate_evidence_bundle). 사람이 파일을 옮기는 단계는 없다.

차단 경로를 재실행하려면 위 명령에 `--force-judge-fail N`을 붙인다. **N은 임의로 고르는 값이 아니라
지목된 번들이 쓴 값 그대로다** — 확인 방법은 §1.1. 그리고 **이 플래그가 무엇을 시연하는지는 §3.5에서
먼저 읽는다** — judge가 결함을 판별하는 실연이 아니다.

`submitted.json`은 이 실행이 만드는 것이 아니라 제출 번들을 만들 때 함께 만들어 둔 덤프다(§1.1).
`replay.json`만 이 명령이 새로 만든다.

### 3.2 구간 배분

대조가 `scripts/replay_verify.py` 한 줄로 끝나면서 예전 ③④⑤(110초)가 한 구간으로 합쳐졌다.

**성공 경로 (기본)**

| # | 구간 | 목표 | 내용 |
| --- | --- | --- | --- |
| ① | 먼저 밝히기 | 20초 | §4의 4줄을 **명령을 치기 전에** 말한다 |
| ② | 실행 | 45초 | §3.1 명령 1줄. 진행 중 노드 실행 순서가 화면에 흐른다 |
| ③ | 대조 | 60초 | `replay_verify.py` 1회. §2·§2.1·§3이 한 화면에 나온다 (§3.4) |
| — | 예비 | 55초 | 질문 흡수용 |

**합계 180초.**

**차단 경로 (§3.3에서 가능하다고 판단)**

| # | 구간 | 목표 | 내용 |
| --- | --- | --- | --- |
| ① | 먼저 밝히기 | 20초 | §4의 4줄 + §3.5의 시연 구분 1줄 |
| ② | 실행 | **131초** | 실측 최대치를 그대로 잡는다 (§3.3) |
| ③ | 대조 | 20초 | `replay_verify.py` 1회 — 결론 줄과 §3 줄만 짚는다 |
| — | 예비 | 9초 | — |

**합계 180초.** 예비가 9초뿐이다 — 이 값의 의미는 §3.3을 따른다.

### 3.3 각 경로의 소요 (실측 인용)

| 경로 | 명령 | 실측 | 출처 |
| --- | --- | --- | --- |
| 성공 (오프라인) | `--auto-approve --offline` | 평균 36.8초 (34.8~39.8, N=10) | `reproducibility_scope.md` §4.1 모드 A |
| 성공 (실 Azure) | `--auto-approve` | 평균 32.4초 (31.6~33.7, N=10) | 〃 모드 B |
| 차단 | `--auto-approve --offline --force-judge-fail` (상한 이상) | 평균 116.0초 (**최대 131.4초**, N=5) | 〃 모드 C |

#### 차단 경로 라이브 재실행 — 결론이 바뀌었다

이 문서의 이전 판은 "차단 경로는 라이브로 못 돌린다"고 결론 냈다. 근거는 대조 구간이
110초라 최대 131.4초 실행과 합치면 241.4초로 3분을 넘긴다는 것이었다.
**`scripts/replay_verify.py`가 생기면서 그 전제가 사라졌다.**

최대치 기준으로 다시 계산한다. 평균(116.0초)으로 계산하면 절반의 실행에서 넘치므로 쓰지 않는다.

```
3분 제한                        180.0초
─ ① 먼저 밝히기                  20.0초
─ ② 차단 경로 실행 (실측 최대)    131.4초
                              ─────────
  대조·예비에 남는 시간            28.6초
```

대조 명령 자체는 사실상 시간을 쓰지 않으므로(§3.4), 28.6초는 **화면을 읽고 짚는 시간**이다.
결론 줄 1개 + §3 제외 대상 줄을 짚는 데 20초를 잡으면 **예비 8.6초**가 남는다.

**들어간다. 다만 여유가 얇다.** 예비 8.6초로는 질문 1건도 받을 수 없다. 그래서:

- **차단 경로를 라이브로 돌리는 것은 감사자가 차단 번들을 지목했을 때의 선택지**이지 기본값이 아니다.
- 실행이 시작되고 **140초가 지나도 안 끝나면 중단한다.** 실측 최대치를 넘긴 것이므로 정상 범위 밖이다.
  **이때 성공 경로로 갈아타지 않는다** — 그 시점에 이미 160초를 썼고, 남은 20초에는 성공 경로 실측 상한
  39.8초가 들어가지 않는다. 전환 대상은 §6.2의 오프라인 무결성 검증이다(§6.3).
- 위 계산에 들어간 값 중 실측이 아닌 것(①·③의 사람이 말하는 시간)과 표본이 작은 것(모드 C는 N=5)은 §7에 남겼다. **리허설에서 타이머로 재기 전까지 이 판단은 계산일 뿐이다.**

**성공 경로는 대안으로 유지하되, 선택은 타이머가 돌기 전에 끝낸다.** 여유가 없다고 판단되면 §3.2 성공 경로
배분으로 시작하고, 차단 재현은 `decision_hash` 동일성으로 갈음한다(§6.3). 시작한 뒤에는 경로를 바꾸지 않는다.

### 3.4 대조에서 무엇을 보여주는가

```bash
python scripts/replay_verify.py submitted.json replay.json
```

인자는 state 덤프 2개뿐이다 — `scripts/replay_verify.py:160` (left). 무엇을 대조할지는 이
스크립트가 정하지 않는다. `docs/reproducibility_scope.md` §2·§2.1·§3의 선언을
`app/evidence/replay_scope.py:38` (GUARANTEED)가 옮겨 적고, 그 대조는 테스트가 고정한다.

출력은 §2 무조건 보장 · §2.1 조건부 · §3 재현 대상 아님을 **한 화면에** 낸다.
§3은 대조하지 않되 함께 보인다 — 감사자가 차이를 먼저 발견하기 전에 밝히는 것이
§4의 원칙이라, 숨겨서 통과가 아니라 보여 주면서 통과여야 한다.

#### 종료 코드 — 현장에서 1과 3을 구분하지 못하면 원인을 못 찾는다

| 코드 | 뜻 | 현장 대응 |
| --- | --- | --- |
| `0` | §2·§2.1 전부 일치 | 정상. 결론 줄을 읽고 §3 줄로 넘어간다 |
| `1` | **불일치** — 재현 보장 대상이 어긋남 | 어긋난 경로가 `↳`로 찍힌다. 범위를 조정하지 말고 원인을 찾는다 (`reproducibility_scope.md` §9) |
| `2` | **입력 문제** — 파일 없음·JSON 깨짐·최상위가 객체 아님 | 판정 실패가 아니다. 덤프 경로를 확인한다. 사유는 stderr로 나온다 |
| `3` | **대조 불가** — 선언 항목이 어느 덤프에도 없음 | 빈 덤프를 넘겼을 때다. `1`과 달리 "틀렸다"가 아니라 "대볼 게 없었다"는 뜻 |

원천은 `scripts/replay_verify.py:34` (EXIT_MATCH)다. **`2`·`3`을 `1`과 뭉개면 안 되는 이유**는
`1`이 "재현이 깨졌다"는 발표 대응이 필요한 상황인 반면 `2`·`3`은 파일을 잘못 넘긴
운영 실수라서다 — 현장에서 둘을 혼동하면 있지도 않은 재현 실패를 설명하게 된다.

#### 손으로 대조하지 않는다

이전 판은 `python -c`로 직접 키를 꺼내 비교했다. 지금은 쓰지 않는다 — 선언 목록을 손으로
옮겨 적으면 문서와 갈릴 수 있고, 갈리면 "선언한 것과 다른 것을 대봤다"가 되어 재현 주장
자체가 무너진다.

`canonical_for_replay`도 쓰지 않는다. `trace_id`만 걷어내므로
(`app/evidence/state_dump.py:159` (canonical_for_replay)) 전체 비교는 §3 제외 대상 때문에
실패하는 것이 정상이다.

### 3.5 차단 번들 재실행이 시연하는 것 — 두 요구를 구분한다

감사에는 성격이 다른 두 요구가 있다. **먼저 구분해 말하고, 그다음 한 번의 실행으로 둘 다
되는 이유를 말한다.** 합쳐서 말하면 "재현 시연을 안 했다"로 읽힌다.

| 요구 | 무엇을 보여야 하나 | 무효 조건 |
| --- | --- | --- |
| **A. Hard Stop 실연** | 판정이 실패했을 때 리포트가 확정되지 않고 멈추는 것, 그리고 그 사실이 증거로 남는 것 | ② 실패했는데 리포트가 그대로 확정됨 |
| **B. R5 재현 대조** | 같은 입력을 다시 넣었을 때 선언 범위(§2·§2.1)가 같다는 것 | ③ 같은 입력인데 결과가 달라짐 (선언한 대상 기준) |

**한 번의 차단 경로 재실행이 둘 다 충족한다.** 실행이 끝나면 A는 `report.status`·
`export_allowed`·`hard_stop_record.json`으로, B는 `replay_verify.py` 출력으로 확인된다.
같은 실행에서 나온 두 산출물이라 따로 돌릴 필요가 없다.

#### ★ `--force-judge-fail`은 judge의 판별을 시연하지 않는다

**이 구분을 놓치면 발표에서 사실과 다른 주장을 하게 된다.**

`--force-judge-fail N`은 judge의 실제 판정 결과를 **덮어쓴다**. 6축이 전부 통과했더라도
`failed_axes=["forced_failure"]`로 강제 실패시킨다 — `app/nodes/judge_eval.py:403` (force_fail_n).
`reproducibility_scope.md` §4.2의 측정 조건에도 `failed_axes=["forced_failure"]`가 그대로 적혀 있다.

따라서 차단 번들 라이브 재실행이 보이는 것은:

- ✅ **Hard Stop 기구가 작동한다** — 실패 신호가 들어오면 확정·다운로드가 막히고 결정 지문이 남는다
- ❌ **judge가 결함 리포트를 판별한다** — 이건 보이지 않는다. 판정을 우회했기 때문이다

**"결함 리포트를 즉석에서 태워 judge가 잡는 것"을 보이려면 다른 경로가 필요하다.**
R1 사례집 20건을 judge에 돌리는 `scripts/judge_runner.py --r1`이 그 판별의 증거이고,
결과는 R2 캘리브레이션(일치율·혼동행렬)로 제출된다. 이건 그래프 실행이 아니라 정적 리포트
채점이라 3분 라이브 동선에 넣지 않는다.

질문이 나오면 §5의 15번을 연다.

---

## 4. 먼저 밝힐 것 — 감사자가 화면에서 발견하기 전에 말한다

재실행 명령을 치기 **전에** 4줄로 말한다. 근거는 전부 `docs/reproducibility_scope.md` §3이다.

- [ ] **인용 집합·순서는 재현 대상이 아니다.** retriever는 결정론이지만 인용 선택 단계가 LLM이라 갈린다 (§3, §5).
- [ ] **`judge.rubric.*.reason` 문구는 재현 대상이 아니다.** LLM 산문이다. 판정(pass/fail)도 §2.1의 반복 실측 대상이지 무조건 보장이 아니다.
- [ ] **`prompt_hash.judge_eval`은 재현 대상이 아니다.** judge 프롬프트 payload에 `citations`가 들어가 위 항목의 파생으로 움직인다.
- [ ] **IPS 추출 산출물(`ips.Unique` 및 파생 5개 경로)은 재현 대상이 아니다.** Azure 응답 비결정성이며, §4.1 모드 B에서 실제로 갈렸다. `--offline`은 고정 프로필을 돌려주므로 이번 데모에서는 갈리지 않는다 (§6).

추가로 한 줄 더 말한다 — **`--offline`은 재현성 모드가 아니다.** 시장 데이터와 IPS 추출만 스텁으로 바꾸고
RAG 검색·rag_cite·judge_eval은 실제 Azure를 호출한다 (`reproducibility_scope.md` §6).
"offline이라 재현된다"고 말하지 않는다. 재현되는 이유는 §2 항목이 결정론 계층 산출물이기 때문이다.

---

## 5. 예상 질문과 답변 근거 위치

**답변 문안은 쓰지 않는다.** 아래는 "어느 문서 어느 절을 여는가"만 적는다.

| # | 겨냥 | 질문 | 근거 위치 |
| --- | --- | --- | --- |
| 1 | 무효 조건 ① | judge가 정답 라벨을 미리 본 것 아닌가 | `goldenset/judge_inputs/README.md` · `tests/test_goldenset_judge_inputs.py` · `docs/symphony_proof_plan.md` §2 R1 |
| 2 | 무효 조건 ② | 실패했는데 확정된 리포트가 있나 | `docs/hard_stop_contract.md` §6 · 번들 `hard_stop_record.json` · `app/nodes/assemble_report.py:369` (report_is_exportable) |
| 3 | 무효 조건 ③ | 같은 입력인데 결과가 다르면 | `docs/reproducibility_scope.md` §2 · §2.1 · §3 |
| 4 | 무효 조건 ④ | 이 서류철을 사람이 조립한 것 아닌가 | `docs/evidence_bundle_schema.md` §1 · §2 · `manifest.generated_by` |
| 5 | 평가 포인트 1 | 라벨 기준이 사람마다 다르지 않나 | `goldenset/labeling-guide.md` · `goldenset/reports/agreement_before.md` |
| 6 | 평가 포인트 2 | judge가 틀린 건 몇 건이고 원인은 무엇인가 | `docs/symphony_proof_plan.md` §2 R2 · `docs/evidence_bundle_schema.md` §4.8 · §8.4 |
| 7 | 평가 포인트 3 | 문서에 적은 규칙이 코드에 그대로 있나 | `docs/hard_stop_contract.md` §7 · `tests/test_docs_config_consistency.py` · `tests/test_docs_line_anchors.py` |
| 8 | 평가 포인트 4 | 명령 몇 번으로 만들어지나 | `docs/evidence_bundle_schema.md` §2 · `scripts/run_graph.py:66` (generate_evidence_bundle) |
| 9 | 평가 포인트 5 | 재현 지문이 왜 3개뿐인가 | `docs/reproducibility_scope.md` §3 「제외 대상에 대한 원칙」 |
| 10 | 인용 검증 | 인용문이 실제 원문에 있는지 어떻게 아나 | `docs/hard_stop_contract.md` §5 · 번들 `citation_verification.json` |
| 11 | 재시도 상한 | 재시도는 몇 번까지이고 그 숫자는 어디 있나 | `docs/hard_stop_contract.md` §2 · `app/nodes/judge_eval.py:28` (resolve_max_judge_retries) |
| 12 | 차단 지문 | 차단 지문이 실행마다 같나 | `docs/reproducibility_scope.md` §4.2 · `docs/evidence_bundle_schema.md` §4.5 |
| 13 | 누락 표기 | "없음"으로 나온 칸은 안 채운 것 아닌가 | `docs/evidence_bundle_schema.md` §5 · §8 |
| 14 | 탈락 인용 | 떨어진 인용은 어디에 남나 | `docs/hard_stop_contract.md` §5 「탈락 인용 기록」 · `scripts/make_evidence_bundle.py:249` (_rejected_citations) |
| 15 | 시연 범위 | 방금 차단된 건 judge가 결함을 잡은 건가 | 이 문서 §3.5 · `app/nodes/judge_eval.py:403` (force_fail_n) · R2 판별 증거는 `scripts/judge_runner.py` + `docs/evidence_bundle_schema.md` §4.8 |
| 16 | 재현 해시 검증 | R2 사례집 채점에서 `computation_hash_present`가 전부 통과한 건 무슨 뜻인가 | `app/evaluation/goldenset_loader.py:190` (_synthesize_hash) · `docs/reproducibility_scope.md` §2 |

---

## 6. 실패 대비

### 6.1 재실행이 3분을 넘길 때

- **판단 시점**: 실행 시작 후 60초. 성공 경로 실측 상한이 39.8초(§4.1 모드 A)이므로 이 시점에 안 끝나면 정상 범위 밖이다.
  **차단 경로로 시작한 경우의 판단 시점은 140초다**(§6.3) — 실측 상한 자체가 131.4초라 60초는 기준이 되지 않는다.
- **대응**: 실행을 끊지 않고 두되, 대조 구간을 **지문 3종 1개 구간(40초)으로 줄인다.** §2 항목 대조와 제외 대상 공개는 버린다.
- **그래도 안 끝나면**: 재실행을 중단하고 §6.2의 오프라인 무결성 검증으로 전환한다. 중단했다는 사실을 먼저 말한다.

### 6.2 네트워크가 끊길 때

`--offline`이어도 RAG·judge는 Azure를 호출하므로(§4의 마지막 줄) **재실행 자체가 성립하지 않는다.**
네트워크가 없으면 인용이 0건이 되고, `config/config.yaml`의 `strict_citation_gate`가 켜져 있으면 출처 축이 실패해
정상적으로 차단된다 — `app/judge/rubric.py:63` (source_validity). 결함이 아니라 설계된 fail-closed 동작이지만,
**재현 데모로는 쓸 수 없다.**

대응 — 제출된 번들 파일만으로 되는 **오프라인 무결성 검증 2종**으로 전환한다. 둘 다 네트워크가 필요 없다.

```bash
# ① bundle_hash 재계산 — manifest.json의 sha256과 bundle_hash.txt가 같아야 한다
sha256sum manifest.json | cut -d' ' -f1
cat bundle_hash.txt

# ② manifest.files 전건 재계산 — HASHED_FILENAMES 각각의 해시가 manifest 기록과 같아야 한다
python -c "
import json, hashlib, pathlib
m = json.load(open('manifest.json'))
bad = [f for f, h in m['files'].items()
       if hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() != h]
print('불일치:', bad or '없음', f\"({len(m['files'])}건 검사)\")
"
```

말할 것 — **bundle_hash 하나가 번들 전체를 봉인한다.** 어느 파일이든 1바이트가 바뀌면 그 파일 해시가 바뀌고,
manifest가 바뀌고, bundle_hash가 바뀐다 (`docs/evidence_bundle_schema.md` §6).

### 6.3 차단 번들이 지정될 때

- **5분 구간은 그대로 간다.** ⑤ 구간만 `hard_stop_record.json`으로 바꾼다(§2.4). 차단 번들도 `BUNDLE_FILENAMES`가 전부 있다.
- **3분 재실행은 차단 경로로 돌릴 수 있다.** `replay_verify.py`가 대조 구간을 없애면서 계산상 들어간다(§3.3). §3.2의 차단 경로 배분을 쓰고, §3.5의 시연 구분을 **먼저 밝히고** 시작한다.
- **경로 선택은 타이머 시작 전에 끝낸다.** 차단 경로로 갈지 성공 경로로 갈지는 명령을 치기 전에 정한다. 한 번 시작하면 3분 안에서는 다른 경로로 갈아탈 수 없다 — 아래 전환 기준 참조.
- **예비가 9초뿐이라는 것을 알고 들어간다.** 질문을 받을 여유가 없으므로, 감사자가 실행 중에 물으면 "끝나고 답하겠다"고 미룬다.
- **전환 기준**: 실행 시작 후 140초가 지나도 안 끝나면 중단한다. 실측 최대치(131.4초)를 넘긴 것이라 정상 범위 밖이다.
  **성공 경로 재실행으로 바꾸지 않는다** — 그 시점에 사전 설명 20초 + 실행 140초로 160초를 썼고, 남는 20초에
  성공 경로 실측 상한 39.8초(§4.1 모드 A)와 대조 시간이 들어가지 않는다. 산술적으로 3분 안에 끝나지 않는다.
- **140초 시점의 대응**: 중단했다는 사실을 **먼저 말하고**, §6.2의 오프라인 무결성 검증 2종과 제출 번들에
  이미 들어 있는 `decision_hash`로 전환한다. 라이브 재실행 대신 제출물로 답하는 것이며, §6.1의 마지막 항목과 같은 경로다.
- **차단의 재현을 `decision_hash`로 갈음할 때** — `reproducibility_scope.md` §4.2가 추적 off/on 4회 실행 전부 동일함을 기록하고 있고, `trace_id`가 갈린 실행 쌍에서도 같았다. 성공 경로로 시작하기로 정한 경우에도 이 근거를 쓴다.
- UI까지 묻거든 `ui/report_export.py:18` (pdf_export_state)를 연다. `report_is_exportable`이 `false`면 PDF 저장 버튼이 비활성이고, 안내문이 "Judge 미통과 또는 수동검토 대기"로 분기한다.

---

## 7. 미검증 항목 — 이 문서가 측정하지 않은 것

- **구간별 목표 시간(30초·60초 등)은 배분안이지 실측이 아니다.** 총합만 300초·180초에 맞춰 놓았다.
  구간 실측은 리허설에서 타이머로 해야 하며, 이는 `docs/symphony_proof_plan.md` §2 R5 DoD의 미체크 항목이다.
- **§3.3의 차단 경로 판단은 계산이지 실측이 아니다.** 남는 예비 8.6초는 두 가정 위에 있다 —
  ① 먼저 밝히기 20초와 ③ 대조 20초가 **사람이 말하는 시간이라 실측된 적이 없고**,
  ② 실행 상한 131.4초는 **N=5 표본의 최대값**이라 6회차가 더 걸릴 수 있다.
  리허설에서 이 둘을 타이머로 재기 전까지 "차단 경로가 3분에 들어간다"는 계산상 결론이다.
  실측 결과 8.6초가 음수가 되면 §6.3의 기본 경로를 성공 경로로 되돌린다.
- **§3.3 표의 초 단위 수치는 전부 인용이다.** 이 문서 작성 시 그래프를 실행하지 않았다.
  출처는 `reproducibility_scope.md` §4.1(모드 A·B·C)과 §7이며, 측정 기준 커밋은 그 문서 머리말이 밝힌다.
- **`replay_verify.py`의 대조 시간을 실물 번들 덤프로 재보지 않았다.** §3.3의 계산은 대조가
  사실상 시간을 쓰지 않는다는 전제 위에 있는데, 그 근거인 실측은 **합성 덤프 기준**이다.
  실제 실행 state 덤프는 `citations` 20여 건과 감사 기록이 붙어 더 크다. 번들 3건을 만든 뒤
  실물 덤프로 다시 재고, 유의미하게 느리면 §3.2 차단 경로 배분을 고쳐야 한다.
- **번들 3건의 실물이 아직 없다.** 현재 레포에 `evidence/` 디렉터리가 없다. 8/6 제출 전에 3건을 만들고,
  만든 뒤 이 런북의 파일명·키 이름을 실물로 한 번 더 대조한다. **§1.1의 state 덤프 3건도 이때 같이 만든다** —
  번들만 만들고 덤프를 빠뜨리면 3분 재실행이 종료 코드 `2`로 끝난다. 만든 뒤 번들 `trace_id`와 덤프 `trace_id`가
  실제로 맞물리는지 3쌍 모두 확인한다.
- **§6.2의 검증 명령 2종은 합성 state로 만든 번들에서만 확인했다.** 그래프를 돌리지 않고
  `make_bundle`(직렬화기)만 호출해 만든 번들이라 파일 구조·해시 체계는 같지만, 실행 산출물이 들어간
  실물 번들에서 다시 한 번 돌려 봐야 한다.
- **UI 시연 동선은 이 문서 범위 밖이다.** §6.3의 `pdf_export_state` 1건만 확인했고,
  Streamlit 화면의 다른 위치는 확인하지 않았다.
