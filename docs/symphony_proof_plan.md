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

- [ ] `case_001`~`case_020` 20건 존재, `GS-EX-*` 접두 0건
- [ ] 라벨링 가이드 §2 경계 사례 규칙 6칸 전부 채워짐 — **이거 없이 라벨링 시작 금지**
- [ ] fail 10건이 6축 전부 커버 (축별 최소 1건)
- [ ] `fail_axes` 값이 허용 6문자열에만 속함 (스키마 테스트 통과)
- [ ] 2인 독립 라벨 일치율이 `initial_agreement`에 기록됨
- [ ] 전 사례에 합성·가상 데이터 명시, LLM 초안 사용 사례에 표기

**산출**: `goldenset/**`, `app/judge/axes.py`, `tests/test_goldenset_schema.py`

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

```bash
python scripts/calibrate_judge.py --prompt-version v1 --out reports/calibration_v1.json
python scripts/calibrate_judge.py --prompt-version v2 --compare-with reports/calibration_v1.json
```

**산출 지표** — "20건 중 17건 일치"보다 아래가 훨씬 설득력 있다.

| 지표 | 정의 |
|---|---|
| 전체 일치율 | pass/fail 판정 일치 건수 / 20 |
| **미탐 (위험)** | 사람 fail → judge pass. 가장 위험한 오류 |
| 오탐 | 사람 pass → judge fail |
| 혼동행렬 | 2×2 (사람 × judge) |
| 축별 일치율 | fail 사례의 `fail_axes` 집합 Jaccard |

**judge 개선 — 범위를 먼저 정해야 한다**

judge 프롬프트는 `rubric.py:290`에 문자열로 박혀 있다 → `app/judge/prompts/v1.py`·`v2.py`로 분리하고 `--prompt-version`으로 선택.

단, 우리 6축 중 **결정론 4축은 프롬프트가 아니라 코드**다(LLM은 환각·위조정밀도 2축뿐). 캘리브레이션에서 나올 미탐 중 상당수는 프롬프트만 고쳐서는 안 잡힌다. 예를 들어 `PROHIBITED_TERMS`에 과제가 지목한 '최적'이 없고, `source_validity`는 `verified=True`가 1건이라도 있으면 통과시킨다.

> **미결 — 8/1 게이트 전까지 팀 결정**
> **(A) 루브릭 6축을 과제 기준으로 정렬** — 금지어 보강, 출처 표기 대조, 표 수치 검사까지. 작업량 크지만 일치율이 실제로 오르고, "검증 레이어 개선"이라 새 기능 금지에 걸리지 않음
> **(B) LLM 2축 프롬프트만 개선** — 가볍지만 결정론 축 미탐은 끝까지 남음
> **(C) 최소 수정 + 한계 공개** — 치명적인 것만 고치고 나머지는 "알지만 안 고쳤다 + 이유"로 발표

**완료 기준 (DoD)**

- [ ] 로더가 견본 3건(GS-EX-01~03)에서 먼저 검증됨 → 20건 확장
- [ ] 로더가 frontmatter 라벨을 state에 넣지 않음을 테스트로 증명 (R1은 `case-format.md` §0으로 경계 명시)
- [ ] 일치율·미탐·오탐·혼동행렬·축별 일치율이 수치로 출력됨
- [ ] **오답 3건 이상** 원인 분석 (사례ID·사람라벨·judge판정·원인가설·수정내용)
- [ ] 프롬프트/루브릭 v1→v2 후 **같은 20건**으로 재측정, 전/후 비교표
- [ ] LangSmith에 실행 기록이 남고 실측 수치를 제출

**산출**: `goldenset/case-format.md`(R1 제공) · 로더는 다경의 `scripts/judge_runner.py`, `scripts/calibrate_judge.py`, `app/judge/prompts/`, `docs/judge_calibration_report.md`

> LangSmith 데이터셋 등록은 기존 `scripts/register_judge_dataset.py`에 dry-run/upload 구조가 이미 있다. 패턴을 복사한다.

---

### R3 — hard stop 규칙

**무엇을.** "judge는 몇 번까지 재시도하고, 끝내 실패하면 어떻게 되는가"를 규칙 문서 한 장으로 못 박고, 규칙마다 테스트를 1:1로 붙인다.

**어떻게.**

> **✅ 상당 부분이 이미 반영돼 있다** — `ab0b64c fix: judge 미통과 리포트를 확정하지 않도록 수정` (7/28, PR #131). 아래는 그 위에서 남은 것만 다룬다.
>
> | 이미 된 것 | 내용 |
> |---|---|
> | 재시도 상한 | `config/config.yaml: judge_max_retries: 3` + `resolve_max_judge_retries()` 순수 함수. 잘못된 값이면 `DEFAULT_MAX_JUDGE_RETRIES=3`으로 폴백 |
> | 통과 없이 확정 금지 | `report.status = pending_manual_review`, `finalized=False`, 제목에 `[미확정 · 수동검토 대기]` 접두, `confirmation_blocked_reason`에 실패 축 기록 |
> | 문서 정합 | `AGENTS.md`·`README.md`가 config 키를 참조하도록 갱신됨 (3회 시도 = 재작성 2회 — 코드와 일치) |
> | 테스트 | 확정/미확정 분기 2건, config 상한 해석 1건(무효값 폴백 포함) |
>
> **→ 무효 조건 ②("실패했는데 리포트가 그대로 확정됨")는 이것으로 방어된다.**

**규칙 ① 숫자는 한 곳에만 — 계층을 문서로 못 박는다.**

값의 SSOT는 `config/config.yaml`의 `judge_max_retries`고, `DEFAULT_MAX_JUDGE_RETRIES`는 그 값이 없거나 무효할 때의 폴백이다. 이 계층이 문서에 없으면 "코드에 3이 두 번 적혀 있는데요?"라는 질문에 답이 궁색해진다. `docs/hard_stop_policy.md`에 명시하고, 문서의 숫자와 config 값을 대조하는 테스트를 붙인다.

> **미갱신 문서 1건 — `발표대비_오케스트레이션_완전해설.md`** (d84ed7e 기준 확인)
>
> `AGENTS.md`·`README.md`·`ui/app.py`는 `ab0b64c`에서 함께 갱신됐지만 이 문서는 빠졌다.
>
> | 행 | 현재 표기 | 실제 |
> |---|---|---|
> | 179 | `MAX_JUDGE_RETRIES=2` · "시도 2회 후 수동검토" · **"왜 3회가 아니라 2회인지" 변론 전체** | 상한 3, 변론 자체가 무효 |
> | 419 | "2회 실패 시 ... 리포트로 진행(경고 병기)" | 3회 실패 시 미확정(`pending_manual_review`) 조립 |
>
> 하필 **감사 답변 준비용 문서**다. 179행은 "3회 미만이라 미달"이라는 지적에 대비한 변론인데, 이제 3회로 맞췄으므로 그대로 두면 오히려 팀이 혼란스러워진다. 규칙 ①이 잡아야 할 바로 그 유형이므로 대조 테스트 범위에 이 문서를 포함시킨다.

**규칙 ② 끝내 실패하면 확정하지 않고 멈춘다 — 남은 간극.**

과제 안내서는 "사람 검토 대기(**`manual_review_gate`**)에서 멈춥니다"라고 정지 지점의 이름까지 지정했다. 현재 구현은 `assemble_report`가 미확정 상태를 붙여 조립하고 정상 종료한다. 결과는 같지만 **그래프상 "멈춘 지점"이 없다.**

> **팀 결정 필요 — 8/1 게이트까지**
> - **(가) `manual_review_gate` 노드 신설 (권장)**: `route_after_judge`가 재시도 소진 시 이 노드로 보내고, 노드는 미확정 리포트 + `hard_stop` 기록을 남기고 END. 안내서 문구와 1:1로 맞고, 감사에서 "이 노드에서 멈췄습니다"라고 그래프를 짚을 수 있다. 기존 `assemble_report` 로직은 재사용하므로 작업량은 작다
> - **(나) 현행 유지 + 규칙 문서로 방어**: "우리는 별도 노드 대신 상태 기반 미확정으로 구현했고 근거는 이것"이라고 문서화. 코드 변경 0이지만 "그래서 뭐가 멈춘 겁니까"에 말로만 답해야 한다

**규칙 ③ 인용은 문장뿐 아니라 출처 표기까지 맞아야 통과.** 현재 `_is_verified_citation`은 `verified` 플래그와 필드 존재 여부만 본다. `quote`가 `chunk_id` 원문에 실제로 포함되는지, `source`가 그 문서와 일치하는지 대조하도록 강화한다. **R3에서 아직 손대지 않은 유일한 규칙이다.**

**규칙 ② 끝내 실패하면 확정하지 않고 멈춘다.**

(가)를 택할 경우:

```python
def route_after_judge(state):
    if judge.get("passed"):                              return "assemble_report"
    if retries >= resolve_max_judge_retries(state):      return "manual_review_gate"
    return "rag_cite"
```

`app/nodes/manual_review_gate.py`는 기존 `assemble_report`로 미확정 리포트를 만든 뒤 `hard_stop` 기록(정지 시각·실패 축·정책 버전·재시도 횟수)을 덧붙이고 END로 간다. 이 `hard_stop` 블록이 R4 번들의 `hard_stop_record.json`이 된다.

**속성 테스트 3건** (`hypothesis` 신규 의존성) — 기존 테스트는 예시 기반이라 특정 입력만 검증한다. 어떤 입력에서도 성립하는지 자동 시험하는 건 아직 없다.

1. 어떤 실패 축 조합·재시도 횟수에서도 `judge.passed is not True` ⇒ `report["finalized"] is False`
2. 어떤 config 값(무효값·음수·bool 포함)에서도 `judge_retries <= resolve_max_judge_retries(state)`
3. 어떤 citation 리스트에서도 quote가 원문에 없거나 source 불일치면 항상 fail

**완료 기준 (DoD)**

- [ ] 정지 지점 구현 방식 (가)/(나) **팀 결정 완료**
- [ ] `docs/hard_stop_policy.md` 한 장 작성 — config SSOT ↔ 코드 폴백 계층 명시
- [ ] `발표대비_오케스트레이션_완전해설.md` 179·419행 정정 (미갱신 잔재 청산)
- [ ] 문서 숫자 = `config.yaml` 값 대조 테스트 통과 (대상에 발표대비 문서 포함)
- [ ] judge 미통과 시 `report.finalized is False` (✅ 이미 통과 — `test_report_is_not_finalized_without_judge_pass`)
- [ ] 인용 출처 표기 대조 강화 + 테스트
- [ ] 규칙 3개에 테스트 1:1 대응
- [ ] 속성 테스트 3건 통과

**산출**: `docs/hard_stop_policy.md`, `tests/test_hard_stop_properties.py`, (가 선택 시) `app/nodes/manual_review_gate.py` + `app/graph.py` 수정

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
├── calibration_before_after.md   개선 전후 비교표 (R2 산출물)
├── llm_audit.json        프롬프트·모델버전·응답 감사기록
└── bundle_hash.txt       번들 루트 해시
```

**설계 시 반영할 점**

- `run_config["audit"]["llm"]`에 컴포넌트별 프롬프트·모델버전·응답·해시가 **이미 쌓이고 있다.** 새로 만들 건 수집기가 아니라 직렬화기다 → 번들의 절반이 사실상 공짜
- 생성은 `run_graph.py` 실행 경로 안에서 **자동 호출**. 사람이 파일을 옮기는 단계가 0이어야 한다
- `summary.md`는 감사 5분 대응용. 이것 하나로 판정 결과·차단 여부·해시가 다 보여야 한다

**완료 기준 (DoD)**

- [ ] 명령 1회로 번들 생성, 수작업 단계 0건
- [ ] `manifest.generated_by`에 스크립트 경로 + git sha 자동 기록
- [ ] 성공 번들과 차단 번들이 각각 정상 생성됨
- [ ] `summary.md`만 보고 30초 안에 상태 파악 가능

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

- [ ] `replay_verify.py`가 2회 실행 해시 일치를 출력
- [ ] 재현 대상 범위가 문서로 **미리** 선언됨
- [ ] 번들 3건(성공 2 · 차단 1) 실물 존재
- [ ] 리허설에서 5분/3분을 **실측 타이머로** 통과

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
| **C** 캘리브레이션 | 로더 연결(다경과 협업), `calibrate_judge.py`, 프롬프트 v1/v2, 오답 분석, LangSmith | 견본 3건으로 선행 가능 |
| **D** hard stop | `hard_stop_policy.md`, 인용 출처 대조 강화, 속성 테스트 3건, (가 선택 시) `manual_review_gate` | 즉시 |
| **E** 증거·재현 | `make_evidence_bundle.py`, `replay_verify.py`, 범위 선언, 번들 3건 | D 후 |

발표는 C(캘리브레이션 숫자)·D(정지 규칙)·E(증거 꺼내기) 3인이 앞에 서고, A·B는 라벨 기준 질문 대기.

| 날짜 | 마일스톤 |
|---|---|
| 7/28 화 | 분담 확정 · **라벨링 가이드 6축 경계 규칙 팀 합의** (이거 없이 라벨링 시작 금지) |
| 7/29~30 | 사례 본문 20건 / 규칙 문서 + 인용 출처 대조 + (가 선택 시) `manual_review_gate` |
| 7/31 금 | **2인 독립 라벨링 → 일치율 → 합의** / 속성 테스트 3건 |
| **8/1 토** | **게이트 1 — R1·R3 DoD 충족.** judge 개선 범위 A/B/C 결정 |
| 8/2~4 | 로더 → v1 측정 → 오답 3건 분석 → v2 재측정 / 번들 배선 |
| **8/5 수** | **게이트 2 — R2·R4 DoD 충족.** 재현성 검증 + 범위 선언 |
| 8/6 목 | **번들 3건 제출** · 리허설 (5분/3분 실측) |
| 8/7 금 | 현장 모의 감사 |

버퍼는 두 게이트다. 밀리면 여기서 잡는다.

---

## 5. 제출 전 최종 확인

**무효 조건 4개 — 말이 아니라 코드/파일로**

- [ ] ① judge가 정답 라벨을 만들지 않았다 — 로더가 라벨을 state에 넣지 않음을 테스트로 증명, `labelers`에 사람 이니셜
- [ ] ② hard stop 있다 — 미통과 시 `report.finalized is False` / `status: pending_manual_review`, 속성 테스트가 보장, 차단 번들 실물 존재
- [ ] ③ 재현 성공 — 해시 일치, 재현 범위를 **미리** 선언
- [ ] ④ 번들 자동 생성 — `manifest.generated_by`, 수작업 0단계

**금지·경계 — 우리 pass 사례 10건 본문에도 그대로 적용됨에 유의**

- [ ] '최적' · 근거 없는 "확률 OO%" · 출처 없는 숫자 → pass 10건에 0건
- [ ] 새 기능·새 화면 없음 (검증 레이어만)
- [ ] 발표 기술스택 = 실제 사용 스택 (`AGENTS.md` 표 기준)

---

### 참조 — 손댈 파일

| 대상 | 경로 |
|---|---|
| 6축 루브릭 · `AXIS_NAMES` | `app/judge/rubric.py:12` |
| 금지어 목록 (R2 개선 후보) | `app/judge/rubric.py:21` |
| `source_validity` (R2 개선 후보) | `app/judge/rubric.py:65` |
| judge LLM 프롬프트 (v1/v2 분리) | `app/judge/rubric.py:290` |
| 라우팅 (R3 수정) | `app/graph.py:29` |
| 재시도 상한 SSOT | `config/config.yaml: judge_max_retries` · `app/nodes/judge_eval.py: resolve_max_judge_retries()` |
| 미확정 상태 조립 | `app/nodes/assemble_report.py` (`STATUS_PENDING_MANUAL_REVIEW`) |
| 리포트 조립 · governance | `app/nodes/assemble_report.py:285` |
| LangSmith 등록 (패턴 복사) | `scripts/register_judge_dataset.py` |
| 실행 CLI (R4 훅 추가) | `scripts/run_graph.py` |
