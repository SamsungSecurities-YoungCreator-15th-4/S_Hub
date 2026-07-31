# 사례 md 형식 명세 — 로더 작성용

> R1 사례 20건(`goldenset/cases/case_001~020.md`)을 judge 입력으로 바꾸는 로더를 만들 때 참고하는 문서입니다.
> 작성: R1(승민) · 사용: R2 실행·기록(다경)
> **이 문서에는 정답·함정 정보가 없습니다.** 구조만 기술합니다.

---

## 0. 로더가 지켜야 할 경계 — 먼저 읽어주세요

**judge 실행 단계에는 정답(gold label)이 필요 없습니다.** 정답은 실행이 끝난 뒤
**일치율을 계산하는 분석 단계**에서만 씁니다. 저장소에 정답이 공개돼 있더라도
실행 로더는 그것을 읽지 않아야 하며, 이는 테스트로 강제됩니다.

**차단 목록이 아니라 allowlist로 구현하세요.** state에 넣는 키를 아래 셋으로
제한하면, 나중에 frontmatter에 필드가 추가돼도 자동으로 안전합니다.

```python
ALLOWED_STATE_KEYS = {"metrics", "explanations", "citations"}
```

읽어도 되는 frontmatter는 `id` · `variant` · `llm_draft` 셋뿐입니다.
아래는 **정답지이므로 어떤 경로로도 state에 들어가면 안 됩니다.**

```
label · fail_axes · trap_type · rationale · labelers · initial_agreement
```

이 경계는 `case_content_sha256`이 frontmatter를 제외하고 본문만 해시하는 것과
같은 원칙입니다 (`tools/case_hashes.py`).

### 검증

`tests/test_goldenset_integrity.py` §8이 로더를 자동으로 잡습니다.

| 테스트 | 무엇을 막나 |
|---|---|
| `test_loader_does_not_expose_answer_fields` | 정답 필드가 state·직렬화 결과에 남는 것 |
| `test_loader_uses_allowlist_only` | allowlist 밖의 키가 state에 섞이는 것 |

지금은 로더가 없어 **skip** 상태이고, `scripts/judge_runner.py`에 `load_case`가
생기는 순간 자동으로 검사 대상이 됩니다. 함수명을 다르게 쓰실 거면 알려주세요 —
테스트의 탐색 경로에 추가하겠습니다.

### v1 실행 결과에 반드시 기록할 것

v1과 v2가 같은 조건이었음을 감사에서 증명해야 합니다.

| 필드 | 출처 |
|---|---|
| `freeze_commit` | `git rev-parse v1-freeze^{commit}` |
| `case_content_sha256` | `goldenset/case_hashes.json` (사례별) |
| `evalset_hash` | 20건 해시의 집합 해시 |
| `executed_at` | 실행 시각 (UTC) |
| `langsmith_run` | LangSmith run id |

**v1 결과가 기록으로 고정되기 전에는 judge 프롬프트·룰을 수정하지 않습니다.**
순서가 뒤집히면 "고치고 나서 v1을 잰 것 아니냐"를 반박할 수 없습니다.
수명주기 전체는 `.sealed/README.md` §2를 보세요.

---

## 1. 파일 구조

```
---
id: case_001
variant: "…시나리오 설명…"
label:            ← 라벨링 후 채워짐. 로더는 읽지 않음
fail_axes:        ← 〃
trap_type:        ← 〃
rationale:        ← 〃
labelers:         ← 〃
initial_agreement:← 〃
llm_draft: true
---

# 사례 case_001 — HNWI 리스크 리포트

> 합성 데이터 고지 (인용 블록)

## 1. 고객·기준일 요약
## 2. VaR / CVaR
## 3. 스트레스 결과 — …
## 4. 규정 인용
## 5. 면책
## 6. 메타
```

---

## 2. ⚠️ 섹션 번호로 찾으면 안 됩니다

**섹션 개수와 번호가 사례마다 다릅니다.**

| 섹션 개수 | 사례 수 |
|---|---|
| 5개 | 1건 |
| 6개 | 10건 |
| 7개 | 7건 |
| 8개 | 2건 |

같은 `VaR / CVaR`가 어떤 사례는 `## 2.`, 어떤 사례는 `## 3.`입니다. **제목 문자열로 매칭**하세요.

**모든 사례에 있는 섹션 (5개)**

- `고객·기준일 요약`
- `VaR / CVaR`
- `스트레스 결과` — 뒤에 ` — 시나리오명`이 붙습니다. 접두 일치로 찾으세요
- `규정 인용`
- `메타`

**사례에 따라 있을 수도 없을 수도 있는 섹션**

`면책` · `산출 조건` · `보유기간 환산` · `유동성 점검` · `세후 기준 검토` · `시장 동향` · `대응 대안 비교` · `안내` · `손실 발생 가능성 평가`

> **전부 옵셔널로 처리하세요.** 특정 섹션이 없다고 예외를 던지면 안 됩니다. 섹션의 유무 자체가 judge가 판정할 대상일 수 있어서, **로더가 미리 거르면 그 판정 기회가 사라집니다.**

---

## 3. 문체가 3종류입니다

같은 내용이 세 가지 형태로 적혀 있습니다. 파서가 셋 다 처리해야 합니다.

| 문체 | 사례 수 | 형태 |
|---|---|---|
| 표 중심 | 13건 | `\| 지표 \| 1일 \| 10일 \|` |
| 불릿 중심 | 6건 | `- 1일 VaR: 0.00648000 (**32,724,000 KRW**)` |
| 서술 중심 | 1건 | `1일 VaR는 비율 기준 0.00577000, 금액 기준 27,696,000원이며…` |

자산배분 표기도 구분자가 다릅니다.

```
표·불릿  : 국내주식 16% / 해외주식 18% / …     ← 슬래시
서술     : 국내주식 16%, 해외주식 18%, …       ← 쉼표
```

---

## 4. judge에 넘길 3가지

`judge_eval(state)`가 먹는 `RiskState`의 세 키를 채우면 됩니다.

### `metrics`

`VaR / CVaR` 섹션과 `스트레스 결과` 섹션에서 뽑습니다.

```python
{
  "confidence": 0.99,
  "horizons": {
    "1d":  {"var_pct": …, "var_krw": …, "cvar_pct": …, "cvar_krw": …},
    "10d": {…},
  },
  "stress": {"scenario": …, "loss_krw": …, "loss_pct": …},
  "meta": {"data_period": {"end": "2026-07-24"}, "computation_hash": …},
}
```

신뢰구간이 있는 사례는 `confidence_interval`도 채워주시면 좋지만, **없는 사례도 있으니 옵셔널**입니다.

### `citations`

`규정 인용` 섹션(과 본문 곳곳)의 인용 블록에서 뽑습니다. 형식이 고정돼 있어 정규식으로 잡힙니다.

```
> "인용문 전문"
> — 출처: 출처명, chunk_id: internal-rr-007
```

```python
{
  "claim": …,            # 인용이 붙은 주제
  "quote": "인용문 전문",
  "source": "출처명",
  "chunk_id": "internal-rr-007",
  "verified": …,          # verify_citations() 결과
  "extra": {"chunk_text": …},   # ← goldenset/corpus/chunks.json 에서 가져옴
}
```

**`chunk_text`는 반드시 채워주세요.** 이게 없으면 judge의 출처·환각 축이 대조할 원문을 못 갖습니다. `chunks.json`에 없는 `chunk_id`가 나올 수 있는데, **에러 대신 "존재하지 않음"으로 넘기세요.** 그것도 판정 대상입니다.

### `explanations` ★ 여기가 중요합니다

서술 문단들을 `{"topic": …, "text": …}` 리스트로 넘깁니다.

**표 안의 수치도 함께 넣어주세요.** judge의 `numeric_consistency` 축은 `_explanation_text(explanations)`만 스캔합니다. 표만 `metrics`로 보내고 `explanations`에 안 넣으면 **표 안의 숫자는 judge가 아예 못 봅니다.**

```python
# 예: VaR/CVaR 표를 문장으로 펼쳐 explanations에도 추가
{"topic": "VaR 해석",
 "text": "1일 VaR는 0.00612000(31,212,000원), 10일 VaR는 0.01935314(98,701,010원)입니다. …"}
```

`topic`은 judge의 `_ENGINE_METRIC_TOPICS`(`VaR 해석`·`스트레스 시나리오`·`기준일 및 유의사항`)와 맞추면 엔진 수치 문맥으로 인식됩니다.

---

## 5. 참고 자료

| 파일 | 용도 |
|---|---|
| `goldenset/cases/case_001.md` | 표준형 견본. 여기서 시작하세요 |
| `goldenset/corpus/chunks.json` | `chunk_text` 원본 12건 |
| `goldenset/labeling-guide.md` §1 | 6축 한글↔영문 매핑 |
| `app/rag/citations.py` | `verify_citations()` — 인용문이 원문의 부분문자열인지 검증 |

---

## 6. 형식 관련 질문은 승민에게

구조가 애매하면 물어보세요. **다만 "이 사례가 pass인가요"는 묻지 마세요** — 로더 작성에 필요 없고, R2 leakage 경계에 걸립니다.
