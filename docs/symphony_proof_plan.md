# S.ymphony Proof 실행 계획서

> 4조 · 2026.08.07 현장 모의감사 · 대상 레포 `Orchestration` (develop)
> 작성 2026-07-28 · **팀 논의용 초안** — 분담·일정은 5인 합의로 확정

---

## 1. 무엇을 만드는가

7월 S.ymphony는 "잘 돌아간다"까지 왔다. 이번엔 그 위에 **자기 자신을 증명하는 레이어**를 얹는다. 새 기능·새 화면은 만들지 않고, 기존 8노드 파이프라인은 그대로 둔다.

만들 것은 5개고, **서로 물려 돌아가는 하나의 사슬**이다.

```
R1 사람이 만든 정답 20건
       │  (기준선)
       ▼
R2 judge에게 채점시켜 대조 → 일치율·미탐·오탐 → 원인 분석 → judge 개선 → 재측정
       │  (판정 능력이 숫자로 확정됨)
       ▼
R3 그 judge가 끝내 실패하면 확정 없이 정지 (manual_review_gate)
       │  (실행할 때마다 성공/차단 기록이 발생)
       ▼
R4 실행 1회 = 증거 서류철 1개 자동 생성
       │
       ▼
R5 같은 입력 2회 = 같은 해시. 서류철 3건으로 모의 감사 대응
```

R1이 흔들리면 R2 숫자가 전부 무의미해지고, R3가 없으면 R4의 차단 기록이 존재할 수 없다. **순서대로 쌓아야 한다.**

---

### 읽기 가이드 — 담당별 중점

**전원 필독**: §1 사슬 그림 · §3 평가 포인트 대응표 · §5 무효 조건 4개

| 담당 | 반드시 읽을 것 | 읽을 때 던질 질문 |
|---|---|---|
| A 사례집 | R1 전체 + 스타터킷 라벨링 가이드 §2 | "이 함정을 다른 조원이 봐도 같은 축으로 판정할까?" |
| B 라벨·검증 | R1 + 라벨링 절차 4단계 | "내 판정 근거가 기준표 어느 줄에 있나?" |
| C 캘리브레이션 | R2 전체, 특히 로더 ★ 표시 | "이 수치가 judge에게 실제로 전달되나?" |
| D hard stop | R3 + '이미 반영된 것' 표 | "이 규칙을 깨는 입력을 만들 수 있나?" |
| E 증거·재현 | R4·R5 + 5분/3분 제약 | "감사인이 이것만 열어도 판단이 되나?" |

**읽고 나서 답할 수 있어야 하는 것**: 내 산출물이 평가 포인트 5개 중 어느 것을 담보하는가.

---

## 2. 요구사항별 설계

각 항목은 **무엇을 / 어떻게 / 완료 기준 / 산출 파일** 순이다. 완료 기준(DoD)을 만족해야 다음 단계로 넘어간다.

---

### R1 — 정답 사례집 20건

**무엇을.** judge를 시험할 모의고사 문제집. 잘 쓴 리포트 10건 + 결함을 심은 리포트 10건. 합격/불합격과 이유는 **사람이 먼저** 매긴다. RAG 자료창고와 다르다 — 이건 채점관을 평가하는 기준지다.

**어떻게.**

```
goldenset/
├── labeling-guide.md        스타터킷 템플릿의 [팀 작성] 빈칸을 채운 최종본
├── cases/case_001.md ~ case_020.md
└── corpus/                  사례 전용 가상 규정 청크 (internal-rr-*)
```

| 구성 | 규칙 |
|---|---|
| pass 10건 | 결함 0. **문체·길이·시나리오를 다양하게** — judge가 겉모습으로 맞히지 못하게 |
| fail 10건 | 6축을 축당 최소 1건씩 커버. 복합 함정 포함 |
| 난이도 | 한눈에 보이는 함정 : 정독해야 보이는 함정 ≈ **1:2** |

**라벨링 절차** (가이드 §3 권장안 채택)

1. 팀원 2인이 서로 결과를 보지 않고 독립 라벨 (pass/fail + 실패 축 + 사유)
2. 합의 전 일치율 계산 → 기준 품질 자가 점검
3. 불일치 건만 논의, 기준표를 근거로 최종 확정 (다수결 아님)
4. 합의 논거를 `rationale`에 반영, 필요 시 경계 규칙 갱신

**설계 시 반영할 점**

- **축 이름 SSOT 필요.** 가이드는 한글(`"수치 정합"`)을 글자 그대로 쓰라 하고 우리 코드는 영문(`numeric_consistency`)이다. 띄어쓰기 하나 어긋나면 R2 집계가 조용히 깨진다 → `app/judge/axes.py`에 매핑을 고정하고 `rubric.py`의 `AXIS_NAMES`와 값 집합이 같은지 테스트
- 본문 초안은 LLM 사용 가능(가이드 §5 허용). 단 **사용 사실을 사례에 표기**하고, `label`·`fail_axes`·`rationale`은 반드시 사람이 부여
- 본문은 자기완결적이어야 한다 — judge가 판정에 쓸 입력 수치와 인용 원문이 사례 안에 있어야 함 (견본 §1·§4 구성 참조)

**완료 기준 (DoD)**

- [x] `case_001`~`case_020` 20건 존재, `GS-EX-*` 접두 0건
- [x] 라벨링 가이드 §2 경계 사례 규칙 6칸 전부 채워짐 — 축별 7·7·7·16·10·7칸
- [x] fail 10건이 6축 전부 커버 — 출처3 · 수치정합3 · 환각3 · 면책3 · 위조정밀도2 · 금지표현2
- [x] `fail_axes` 값이 허용 6문자열에만 속함 — `tests/test_goldenset_integrity.py` 31 passed
- [x] 2인 독립 라벨 일치율이 `initial_agreement`에 기록됨 — 20건 전부, 사람 간 일치율 18/20
- [x] 전 사례에 합성·가상 데이터 명시, LLM 초안 사용 사례에 표기 — 누락 0건

**산출**: `goldenset/**`, `app/judge/axes.py`, `tests/test_goldenset_schema.py`·`tests/test_goldenset_integrity.py`

**완료** — 라벨 확정 후 `v1-freeze`(`58d5e2b`)로 동결. 사례 본문은 `goldenset/case_hashes.json`으로 고정되며, R2 v1~v7 전 라운드가 같은 `freeze_commit`·`input_set_hash`를 기록한다. 산출 경위는 `goldenset/reports/agreement_before.md`.

---

### R2 — judge 캘리브레이션

**무엇을.** 20건을 judge에게 채점시켜 사람 정답과 대조. 일치율을 뽑고, 어긋난 건을 미탐/오탐으로 나눠 세고, 원인을 3건 이상 분석해 judge를 고친 뒤, **같은 문제집으로 전/후를 비교**한다.

**어떻게.**

사례집은 리포트 md 전문인데 `judge_eval(state)`는 `RiskState`를 먹는다. 이 사이를 잇는 변환기가 이번 과제 코드의 심장이다.

> **소유권 확정** — R3가 `goldenset/tools/export_judge_inputs.py`로 R1 원본에서 정답 메타데이터를 제거하고, R2 실행 담당(다경)은 `goldenset/judge_inputs/`만 읽는 **로더**를 `scripts/judge_runner.py`에 연결한다. R2는 정답이 든 `goldenset/cases/`를 열거나 파싱하지 않는다. 계획서 초안의 `app/goldenset/adapter.py`는 이 러너와 중복이므로 만들지 않는다.

```python
# 다경의 러너 안에 들어갈 로더 (아래는 변환 규칙)
case_00X.md
  frontmatter → 정답 라벨 (judge에 절대 노출 금지)
  §1 고객 요약  → run_config, portfolio
  §2 VaR/CVaR표 → metrics.horizons  +  표 수치를 explanations에도 투입 ★
  §3 스트레스   → metrics.stress
  §4 규정 인용  → citations[]
  서술 문단     → explanations[]
```

★ `numeric_consistency`는 `explanations` 텍스트만 스캔한다. 견본의 핵심 함정(1일 VaR × √10 ≠ 10일 VaR)은 **표 안**에 있으므로, 표 수치를 explanations로 옮겨주지 않으면 이 축이 무력화된다.

계획 단계에서는 `calibrate_judge.py` 하나로 잡았으나, **실제 구현은 judge 실행과
집계를 두 스크립트로 나눴다** — 실행(Azure 호출)과 분석(순수 집계)을 분리해야
같은 판정 결과로 집계만 다시 돌릴 수 있기 때문이다.

```bash
# ① judge 실행 — 사례를 judge에 돌려 JudgeResult JSON으로 기록
python scripts/judge_runner.py --prompt-version v1 --out out/v1.json
python scripts/judge_runner.py --prompt-version v2 --out out/v2.json

# ② 집계·비교 — 사람 라벨과 합쳐 일치율·혼동행렬·v1↔v2 비교를 뽑는다
python scripts/calibration_report.py --judge-results out/v1.json \
    --judge-results-v2 out/v2.json --human-labels-dir goldenset/cases \
    --official --out out/calibration_report.json
```

`--out` 산출물은 R4 증거 번들이 `--calibration`으로 받아 그대로 싣는다. 허용
mode는 `dev_mock`·`offline_rehearsal`·`official`·`official_code_change`·
`official_offline_code_change`이며, 공식 증거는 LangSmith 요건까지 적용한
`official`·`official_code_change`다 — 상세는
[`docs/evidence_bundle_schema.md`](evidence_bundle_schema.md) §4.8.

**산출 지표** — "20건 중 17건 일치"보다 아래가 훨씬 설득력 있다.

| 지표 | 정의 |
|---|---|
| 전체 일치율 | pass/fail 판정 일치 건수 / 20 |
| **미탐 (위험)** | 사람 fail → judge pass. 가장 위험한 오류 |
| 오탐 | 사람 pass → judge fail |
| 혼동행렬 | 2×2 (사람 × judge) |
| 축별 일치율 | fail 사례의 `fail_axes` 집합 Jaccard |

**judge 개선 — 범위를 먼저 정해야 한다**

judge 프롬프트는 `rubric.py:359`에 문자열로 박혀 있다 → `app/judge/prompts/v1.py`·`v2.py`로 분리하고 `--prompt-version`으로 선택.

단, 우리 6축 중 **결정론 4축은 프롬프트가 아니라 코드**다(LLM은 환각·위조정밀도 2축뿐). 캘리브레이션에서 나올 미탐 중 상당수는 프롬프트만 고쳐서는 안 잡힌다. 예를 들어 `PROHIBITED_TERMS`에 과제가 지목한 '최적'이 없고, `source_validity`는 `verified=True`가 1건이라도 있으면 통과시킨다.

> **미결 — 8/1 게이트 전까지 팀 결정**
> **(A) 루브릭 6축을 과제 기준으로 정렬** — 금지어 보강, 출처 표기 대조, 표 수치 검사까지. 작업량 크지만 일치율이 실제로 오르고, "검증 레이어 개선"이라 새 기능 금지에 걸리지 않음
> **(B) LLM 2축 프롬프트만 개선** — 가볍지만 결정론 축 미탐은 끝까지 남음
> **(C) 최소 수정 + 한계 공개** — 치명적인 것만 고치고 나머지는 "알지만 안 고쳤다 + 이유"로 발표

> **결정 기록 (해소됨) — (A)와 (C)를 함께 택했다.**
> 결정론 축은 코드로 고쳤고(v4 면책·금지표현, v7 `source_validity` 사각지대),
> LLM 2축은 프롬프트로 조정했다(v2·v3·v5·v6). 고치지 않은 것은 숨기지 않고
> `goldenset/reports/r2_calibration/README.md`의 「알려진 한계」에 원인과 함께 적었다
> — 수치정합 관계 검사 F2·F3·F4·F6·F7 미구현, F1은 구현했으나 두 경로 모두에서
> 미관측, F5는 이 실행 형태에서 발생 불가. 최종 v7 일치율 16/20.

**완료 기준 (DoD)**

- [ ] 로더가 견본 3건(GS-EX-01~03)에서 먼저 검증됨 → 20건 확장
      — **미충족.** 견본 단계를 거치지 않고 `case_001`~`case_020` 20건에 바로 붙였다.
      로더 테스트(`tests/test_goldenset_loader.py`)도 20건을 대상으로 한다. 계획한 단계적
      확장을 건너뛴 것이며, 20건 검증 자체는 `test_loads_all_twenty_cases` 외 9건이 담당한다.
- [x] 로더가 frontmatter 라벨을 state에 넣지 않음을 테스트로 증명 (R1은 `case-format.md` §0으로 경계 명시)
      — `ALLOWED_STATE_KEYS`(metrics·explanations·citations) + `test_state_uses_allowlist_only`
      ·`test_no_answer_fields_anywhere_in_state`
- [x] 일치율·미탐·오탐·혼동행렬·축별 일치율이 수치로 출력됨
      — `v*_report_summary.json`의 `derived`·`confusion_matrix`·`per_axis`
- [x] **오답 3건 이상** 원인 분석 (사례ID·사람라벨·judge판정·원인가설·수정내용)
      — 원인가설·수정내용은 `goldenset/reports/r2_calibration/README.md`에 3건 이상
      (v2 오탐 급증→v3 경계 보강 · v4 면책/금지표현 코드 수정 · v7 `source_validity`
      사각지대 수정). **사례ID·사람라벨은 라벨 방화벽 때문에 커밋하지 않는다** —
      `human_rationale`가 답안지라 번들·레포에 싣지 않고 제외 사유를
      `mismatch_detail_excluded`에 명시한다.
- [x] 프롬프트/루브릭 v1→v2 후 **같은 20건**으로 재측정, 전/후 비교표
      — v1~v7 전 라운드 `evalset_hash` 동일(`70a75abc…`), 비교표는 `*_compare_summary.json`
- [x] LangSmith에 실행 기록이 남고 실측 수치를 제출
      — `docs/r2_calibration_runs/*.manifest.json`의 `langsmith_run`, 전 라운드 20/20

**산출**: `goldenset/case-format.md`(R1 제공) · 무라벨 입력본 `goldenset/judge_inputs/` · 다경의 `scripts/judge_runner.py`(실행) + `scripts/calibration_report.py`(집계)

> LangSmith 데이터셋 등록은 기존 `scripts/register_judge_dataset.py`에 dry-run/upload 구조가 이미 있다. 패턴을 복사한다.

---

### R3 — hard stop 규칙

**무엇을.** "judge는 몇 번까지 재시도하고, 끝내 실패하면 어떻게 되는가"를 규칙 문서 한 장으로 못 박고, 규칙마다 테스트를 1:1로 붙인다.

**어떻게 — 구현 완료 상태.**

| 규칙 | 현재 구현 |
|---|---|
| 재시도 상한 SSOT | `config/config.yaml: judge_max_retries`를 `resolve_max_judge_retries()`로만 읽는다. 누락·bool·0 이하·잘못된 타입은 코드 기본값으로 대체하지 않고 `ValueError`로 실행을 거부한다. |
| 통과 없이 확정 금지 | `route_after_judge`가 상한 소진 실패를 독립 노드 `manual_review_gate`로 보내고, `pending_manual_review`·`finalized=False`·`export_allowed=False`를 기록한 뒤 END로 종료한다. |
| 결정 지문 | `decision_hash`는 판단 내용과 정책 버전·`computation_hash`를 해시하며, 실행마다 달라지는 `trace_id`·`stopped_at`은 제외한다. |
| 인용 identity 검증 | 인용문뿐 아니라 `chunk_id`·문서명·조항/locator가 원문 청크와 모두 일치해야 `verified=true`가 된다. 탈락 인용은 `citation_rejections`에 시도별로 누적된다. |
| UI 차단 | `report_is_exportable()`이 false면 PDF 저장 버튼을 비활성화한다. |

**규칙 ① 숫자는 한 곳에만.** 값의 유일한 원천은 `config/config.yaml`이며 폴백
기본값은 없다. 문서에 숫자를 복제하지 않고 키를 참조하며,
`tests/test_docs_config_consistency.py`가 문서와 설정을 대조한다.

**규칙 ② 끝내 실패하면 확정하지 않고 멈춘다.** 그래프는 별도
`manual_review_gate` 노드를 사용한다. 노드는 미확정 리포트와 정책 버전·실패 축·
재시도 횟수·논리적 차단시각·결정 지문을 `report.governance.manual_review_gate`에
남긴다. R4는 이 원본 계약을 `hard_stop_record.json`에 이름 그대로 싣는다.

**규칙 ③ 인용은 문장뿐 아니라 출처 표기까지 맞아야 통과한다.** `rag_cite`는
quote가 청크 원문에 존재하는지와 source·locator가 청크 provenance와 일치하는지를
함께 확인한다. 문장만 맞거나 출처만 맞는 인용은 통과하지 않는다.

**완료 기준 (DoD)**

- [x] 독립 `manual_review_gate` 노드 및 실패 경로 E2E 구현
- [x] `docs/hard_stop_contract.md`에 상한·인용·차단·R4 상태 계약 문서화
- [x] 문서의 재시도 상한 = `config.yaml` 대조 테스트
- [x] Judge 미통과 시 `finalized=False`·`export_allowed=False`
- [x] 인용문·문서명·조항·청크 일치 검증과 탈락 이력 누적
- [x] 규칙별 1:1 테스트 및 속성 테스트 3건 이상

**산출**: `docs/hard_stop_contract.md` · `app/nodes/manual_review_gate.py` ·
`app/graph.py` · `tests/test_hard_stop_contract.py`

---

### R4 — evidence bundle

**무엇을.** 명령 한 번이면 감사 서류철이 자동으로 만들어진다. 사람이 스크린샷을 모아 만든 서류철은 인정되지 않는다.

**어떻게.**

```bash
python scripts/run_graph.py --auto-approve --evidence-bundle
```

```
evidence/<run_id>/
├── manifest.json         스키마버전 · generated_by(스크립트@git_sha) · 각 파일 sha256
├── summary.md            ★ 1페이지 요약 — 5분 안에 이것만 열면 다 보이게
├── trace.json            LangSmith trace_id + 노드 실행 순서
├── judge_rationale.json  judge.checks / rubric 축별 판정 사유 전문
├── hard_stop_record.json ★ 멈춘 기록 (없으면 성공 번들임을 명시)
├── replay_diff.json      같은 입력 2회 실행 해시 대조
├── citation_verification.json  인용 검증 결과·탈락 인용 이력
├── calibration_summary.json    R2 실행 등급·일치율·개선 전후 비교
├── llm_audit.json        프롬프트·모델버전·응답 감사기록
└── bundle_hash.txt       번들 루트 해시
```

> 위는 계획 시점 스케치이며 **실제 목록의 SSOT는 `app/evidence/schema.py`의
> `BUNDLE_FILENAMES`**다. 계약 상세는
> [`docs/evidence_bundle_schema.md`](evidence_bundle_schema.md)를 따른다.

**설계 시 반영할 점**

- `run_config["audit"]["llm"]`에 컴포넌트별 프롬프트·모델버전·응답·해시가 **이미 쌓이고 있다.** 새로 만들 건 수집기가 아니라 직렬화기다 → 번들의 절반이 사실상 공짜
- 생성은 `run_graph.py` 실행 경로 안에서 **자동 호출**. 사람이 파일을 옮기는 단계가 0이어야 한다
- `summary.md`는 감사 5분 대응용. 이것 하나로 판정 결과·차단 여부·해시가 다 보여야 한다

**완료 기준 (DoD)**

- [x] 명령 1회로 번들 생성, 수작업 단계 0건
      — `run_graph.py --evidence-bundle --dump-state` 1회. 제출 번들 3건 모두 이 경로로 생성
- [x] `manifest.generated_by`에 스크립트 경로 + git sha 자동 기록
      — 제출 번들 3건 전부 `git_sha=6112cb4`(동결 커밋)로 재확인
- [x] 성공 번들과 차단 번들이 각각 정상 생성됨
      — 성공 2 · 차단 1, `bundle_hash`와 `manifest.files` 전건 해시 재계산 일치
- [ ] `summary.md`만 보고 30초 안에 상태 파악 가능
      — **미충족(측정 안 함).** 머리말 7줄 형식은 갖췄으나(`audit_demo_runbook.md` §2.1),
      30초 안에 읽히는지는 사람이 재야 하고 아직 타이머로 재지 않았다. 런북 §2 배분은
      이 구간에 60초를 잡아 두었다 — 배분안이지 실측이 아니다(런북 §7 첫 항목).

**산출**: `scripts/make_evidence_bundle.py`, `evidence/**`, `docs/evidence_bundle_schema.md`

---

### R5 — 재현성 + 모의 감사

**무엇을.** 같은 입력 2회 = 같은 결과임을 해시로 증명한다. 발표는 발표가 아니라 모의 감사다.

**어떻게.**

```bash
python scripts/replay_verify.py --thread demo-001
# 2회 실행 → computation_hash / config_hash / report_hash 대조
```

**재현 대상을 먼저 선언한다.** 무효 조건 ③은 "**선언한 대상 기준**" 재현 실패다. 즉 무엇을 재현 대상으로 삼는지 우리가 먼저 못박아야 방어된다. `docs/reproducibility_scope.md`:

| 대상 | 보장 | 근거 |
|---|---|---|
| `computation_hash` · `config_hash` | ✅ | seed=42, numpy 결정론 |
| judge 결정론 4축 판정 | ✅ | 순수 파이썬 규칙 |
| judge LLM 2축(환각·위조정밀도) | ⚠️ 캐시 봉인 | temperature=0이나 벤더 비결정성 잔존 |
| `trace_id` · 타임스탬프 | ❌ 제외 | 실행마다 다른 것이 정상 |

LLM 2축이 유일한 약점이다. **재현 데모는 `--offline` 또는 캐시된 judge 응답으로 돌리고 이유를 먼저 밝힌다.** 숨기다 찔리면 무효 조건 ③이지만, 먼저 선언하면 오히려 성숙도 점수다.

**모의 감사 대응**

| 단계 | 내용 |
|---|---|
| 8/6까지 | 서류철 3건 제출 — **성공 2 · 차단 1** |
| 성공① | 정상 실행 (judge 1회 통과) |
| 성공② | judge 1회 실패 → 재작성 → 통과 (루프 시연) |
| 차단 | 사례집 fail 케이스 투입 → 재시도 소진 → `manual_review_gate` 정지 |
| 당일 | 심사자가 1건 지목 → **5분** 증거 제시 → **3분** 라이브 재실행 |
| 시연 | 오류 리포트 1건을 골라 judge 레이어가 어느 축에서 어떻게 판별하는지 (강사 명시 요구) |

**완료 기준 (DoD)**

- [x] `replay_verify.py`가 2회 실행 해시 일치를 출력
      — 제출물 `replay_verification.txt`. 재현 보장 대상 8건 전부 일치, 두 실행의
      `trace_id`가 달라 별개 실행임도 확인
- [x] 재현 대상 범위가 문서로 **미리** 선언됨
      — `docs/reproducibility_scope.md`. 범위 변경은 재실행 검증보다 먼저 한다(§9)
- [x] 번들 3건(성공 2 · 차단 1) 실물 존재
      — 제출 완료. `trace_id`가 state 덤프 3쌍과 모두 맞물림
- [ ] 리허설에서 5분/3분을 **실측 타이머로** 통과
      — **미충족.** 기계가 재는 값(재실행 시간·대조 시간)은 확인했으나
      **사람이 말하는 시간을 아직 타이머로 재지 않았다.** 상세는
      `audit_demo_runbook.md` §7·§7.1 마지막 문단.

**산출**: `scripts/replay_verify.py`, `docs/reproducibility_scope.md`, 번들 3건, 발표 대본

---

## 3. 평가 포인트 ↔ 무엇으로 증명하는가

과제 안내의 평가 포인트 5개에 각각 증거를 붙인다. **"했습니다"가 아니라 "이 파일이 증거입니다"로 답할 수 있어야 한다.**

| 평가 포인트 | 증명 수단 | 담보하는 요구사항 |
|---|---|---|
| **1. 사람 판정의 일관성** | 라벨링 가이드 §2 경계 규칙 6칸 + **2인 독립 라벨 일치율**(`initial_agreement`) | R1 |
| **2. 검증의 정직성** | 미탐/오탐을 숫자로 공개 + 오답 3건 원인 분석 + 전/후 비교표. **개선 후 나빠진 축도 그대로 제출** | R2 |
| **3. 규칙-구현 일치** | 정책 상수 SSOT + 문서-코드 대조 테스트 + 규칙별 테스트 1:1 + 속성 테스트 3건 | R3 |
| **4. 증거 자동화** | `manifest.generated_by`(스크립트@git sha) + 수작업 0단계 | R4 |
| **5. 재현성** | 해시 대조 + **재현 범위 사전 선언** + 라이브 3분 재실행 | R5 |

**포인트 2가 이번 과제의 함정이다.** 일치율이 높은 팀이 아니라 **틀린 걸 드러내고 원인까지 판 팀**이 점수를 받는다. 캘리브레이션 결과가 나쁘게 나와도 숫자를 손보지 않는다 — 낮은 일치율 + 정확한 원인 분석 + 개선 시도가 만점 시나리오다.

---

## 4. 분담 (5인) · 일정

**A·B(사례집)와 D(hard stop)는 서로 독립이라 1일차 동시 착수.** C는 A·B를, E는 D를 기다린다. 이 둘이 전체 일정을 좌우한다.

| 담당 | 산출물 | 착수 |
|---|---|---|
| **A** 사례집 | `goldenset/cases/` 20건 본문, 라벨링 가이드 최종본, 사례 코퍼스 | 즉시 |
| **B** 라벨·검증 | 독립 라벨 20건, A와 합의, `initial_agreement`, 스키마 테스트 | A 본문 후 |
| **C** 캘리브레이션 | 로더 연결(다경과 협업), `judge_runner.py`(실행)+`calibration_report.py`(집계), 프롬프트 v1/v2, 오답 분석, LangSmith | 견본 3건으로 선행 가능 |
| **D** hard stop | `hard_stop_contract.md`, 인용 identity 검증, 속성 테스트 3건 이상, `manual_review_gate` | 구현 완료 |
| **E** 증거·재현 | `make_evidence_bundle.py`, `replay_verify.py`, 범위 선언, 번들 3건 | D 후 |

발표는 C(캘리브레이션 숫자)·D(정지 규칙)·E(증거 꺼내기) 3인이 앞에 서고, A·B는 라벨 기준 질문 대기.

| 날짜 | 마일스톤 |
|---|---|
| 7/28 화 | 분담 확정 · **라벨링 가이드 6축 경계 규칙 팀 합의** (이거 없이 라벨링 시작 금지) |
| 7/29~30 | 사례 본문 20건 / 규칙 문서 + 인용 출처 대조 + `manual_review_gate` 구현 |
| 7/31 금 | **2인 독립 라벨링 → 일치율 → 합의** / 속성 테스트 3건 |
| **8/1 토** | **게이트 1 — R1·R3 DoD 충족.** judge 개선 범위 A/B/C 결정 |
| 8/2~4 | 로더 → v1 측정 → 오답 3건 분석 → v2 재측정 / 번들 배선 |
| **8/5 수** | **게이트 2 — R2·R4 DoD 충족.** 재현성 검증 + 범위 선언 |
| 8/6 목 | **번들 3건 제출** · 리허설 (5분/3분 실측) |
| 8/7 금 | 현장 모의 감사 |

버퍼는 두 게이트다. 밀리면 여기서 잡는다.

---

## 5. 제출 전 최종 확인

> **확인 시점: 동결 커밋 `6112cb4` · 2026-08-05.** 아래는 제출물 실물과 코드를 대조한
> 결과다. 이 절의 체크는 "했다고 생각한다"가 아니라 **그 자리에서 파일을 열어 확인한 것**만
> 켠다. 검증 명령은 §5.1.

**무효 조건 4개 — 말이 아니라 코드/파일로**

- [x] ① judge가 정답 라벨을 만들지 않았다 — 로더가 라벨을 state에 넣지 않음을 테스트로 증명, `labelers`에 사람 이니셜
      — `ALLOWED_STATE_KEYS` 3키 + 코드 레벨 재확인(`goldenset_loader.py`),
      `tests/test_goldenset_integrity.py` 31 passed, `final_labels.yaml`의
      `labelers: ["중현", "준호"]`(출제자 승민은 라벨러에서 배제). 제출물 9건 JSON 키
      스캔에서도 라벨 유출 0건.
- [x] ② hard stop 있다 — 미통과 시 `report.finalized is False` / `status: pending_manual_review`, 속성 테스트가 보장, 차단 번들 실물 존재
      — `blocked_state.json` 실측: `status=pending_manual_review` · `finalized=False` ·
      `export_allowed=False` · `confirmation_allowed=False`. 속성 테스트 3건 실재
      (`test_property_*`, `docs/hard_stop_contract.md` §7 표).
- [x] ③ 재현 성공 — 해시 일치, 재현 범위를 **미리** 선언
      — 재현 보장 대상 8건 전부 일치(`replay_verification.txt`), 범위 선언은
      `docs/reproducibility_scope.md`.
- [x] ④ 번들 자동 생성 — `manifest.generated_by`, 수작업 0단계
      — 3건 전부 `generated_by.git_sha=6112cb4`, `bundle_hash == sha256(manifest.json)`
      재계산 일치.

**금지·경계 — 우리 pass 사례 10건 본문에도 그대로 적용됨에 유의**

- [x] '최적' · 근거 없는 "확률 OO%" · 출처 없는 숫자 → pass 10건에 0건
      — `final_labels.yaml`의 pass 10건 본문 스캔 결과 적발 0건. `최적`이 등장하는 곳은
      금지어 목록(`app/judge/rubric.py`)과 **의도적 결함 사례**뿐이다.
- [x] 새 기능·새 화면 없음 (검증 레이어만)
      — 8월 `ui/` 변경은 기존 분석 화면에 감사 번들 다운로드와 Hard Stop 시연 옵션을
      **노출**한 것이고 새 화면은 없다. 신규 파일은 `ui/evidence_export.py` 1개이며
      리포트 생성 9노드는 손대지 않았다. R3의 `manual_review_gate`는 과제가 요구한
      검증 레이어 노드다.
- [x] 발표 기술스택 = 실제 사용 스택 (`AGENTS.md` 표 기준)
      — 발표자료 기술스택 7행을 `requirements.txt`와 실제 import로 전건 대조 완료.
      `AGENTS.md` 표의 RAG 검색 계층 누락은 #204에서 보강했다.

### 5.1 재확인 명령

레포만 있으면 아래로 위 항목 대부분이 재현된다. 네트워크·LLM 호출 없다.

```bash
pytest                                   # 977 passed / 20 skipped 기준
ruff check .
python scripts/replay_verify.py <제출 state> <재실행 state>
```

---

### 참조 — 손댈 파일

| 대상 | 경로 |
|---|---|
| 6축 루브릭 · `AXIS_NAMES` | `app/judge/rubric.py:12` |
| 금지어 목록 (R2 개선 후보) | `app/judge/rubric.py:21` |
| `source_validity` (R2 개선 후보) | `app/judge/rubric.py:65` |
| judge LLM 프롬프트 (v1/v2 분리) | `app/judge/rubric.py:359` |
| Hard Stop 라우팅 | `app/graph.py:30` (`route_after_judge`) |
| 재시도 상한 SSOT | `config/config.yaml: judge_max_retries` · `app/nodes/judge_eval.py: resolve_max_judge_retries()` |
| 미확정 상태·차단 기록 | `app/nodes/manual_review_gate.py` |
| 리포트 조립 · governance | `app/nodes/assemble_report.py:285` |
| LangSmith 등록 (패턴 복사) | `scripts/register_judge_dataset.py` |
| 실행 CLI (R4 훅 추가) | `scripts/run_graph.py` |
