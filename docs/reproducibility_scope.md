# 재현성 범위 선언 (Reproducibility Scope)

> 대상: S.ymphony Proof · R5
> 최초 선언 2026-08-01 · 근거: 아래 §4 실측
> **이 문서는 재실행 검증 전에 선언된다.** 결과를 보고 범위를 조정하지 않는다.

---

## 1. 왜 범위를 선언하는가

과제 무효 조건 ③은 "같은 입력인데 결과가 달라짐 **(선언한 대상 기준)**"이다. 이 단서는 봐주기가 아니라 요구다 — LLM이 포함된 파이프라인에서 전 필드 재현은 불가능하며, **무엇이 결정론이고 무엇이 아닌지 아는가**를 묻는 것이다. 범위를 선언하지 못하면 그 자체가 시스템을 모른다는 뜻이 된다.

따라서 우리는 재현 대상을 먼저 못박고, 제외 대상은 제외 이유와 함께 공개한다.

---

## 2. 재현 보장 대상

동일 입력·동일 thread로 2회 실행 시 아래 항목은 **완전히 일치한다.**

| 대상 | 근거 |
| --- | --- |
| `config_hash` | `sha256_of_dict(run_config)` — 설정 파일에서만 유래 |
| `computation_hash` | `app/engine/metrics.py` — 수익률·가중치·파라미터 payload, seed 고정 |
| `approval_hash` | HITL 승인 입력의 결정론 해시 |
| `metrics` 전체 | 순수 numpy 계산 계층 |
| `explanations` 전체 | 고정 골격 + metrics 값 조립 (LLM 생성 아님) |
| `prompt_hash.rag_cite` | 검색 결과가 아닌 topic 골격에서 조립 |
| **judge 6축 판정(pass/fail)** | 결정론 4축은 순수 파이썬, LLM 2축도 판정 자체는 안정 |
| `judge.passed` | 위 6축의 집계 |
| `report.status` · `report.finalized` | 판정 결과의 결정론 함수 |
| `governance.export_allowed` | 〃 |

**이 목록이 "같은 결과"의 정의다.** 재현 데모와 증거 번들의 대조는 이 항목들로 수행한다.

---

## 3. 재현 제외 대상 (명시적 선언)

| 대상 | 제외 사유 |
| --- | --- |
| `citations` 집합·순서 | LLM 응답 비결정성 (§5 참조). retriever는 결정론이나 인용 선택 단계가 갈린다 |
| `judge.rubric.*.reason` 문구 | LLM 산문. **판정(pass/fail)은 재현 대상이며 사유 문장만 제외한다** |
| `prompt_hash.judge_eval` | judge 프롬프트 payload에 `citations`가 포함되어 위 항목의 파생으로 변동 |
| `manual_review_gate.decision_hash` | 계산에 `trace_id`가 포함됨 (`manual_review_gate.py:62-74`). 구성 요소는 전부 일치 |
| `trace_id` · `run_id` · 타임스탬프 | 실행마다 다른 것이 정상 |
| LangSmith trace URL | 위 파생 |

### 제외 대상에 대한 원칙

**"재현 지문"으로 제시하는 해시는 `computation_hash` · `config_hash` · `approval_hash` 세 개로 한정한다.** `prompt_hash.judge_eval`이나 `decision_hash`를 재현 증거로 내세우면 자기모순이 된다.

---

## 4. 실측 근거 (2026-08-01)

동일 입력·동일 thread로 3개 모드를 각 2회 실행하고 `--dump-state` 덤프를 필드 단위로 대조했다.

- **A**: `--auto-approve --offline`
- **B**: `--auto-approve` (실 Azure·실 RAG)
- **C**: `--auto-approve --offline --force-judge-fail 3` (차단 경로)

| 대상 | A | B | C |
| --- | --- | --- | --- |
| `config_hash` · `computation_hash` · `approval_hash` | 동일 | 동일 | 동일 |
| `metrics` 전체 | 차이 0건 | 차이 0건 | 차이 0건 |
| `explanations` 전체 | 차이 0건 | 차이 0건 | 차이 0건 |
| `prompt_hash.rag_cite` | 동일 | 동일 | 동일 |
| **judge 6축 판정** | **6/6 동일** | **6/6 동일** | **6/6 동일** |
| `judge.passed` | True/True | True/True | False/False |
| `report.status` · `finalized` · `export_allowed` | 동일 | 동일 | 동일 |
| `citations` 건수 | 28/28 | 20/20 | 20/20 |
| `citations` chunk_id 집합·순서 | 상이 | 상이 | 상이 |
| `judge.rubric.*.reason` | 상이 | 상이 | 상이 |
| `prompt_hash.judge_eval` | 상이 | 상이 | 상이 |

전체 차이 건수는 A 171 · B 72 · C 148이며, 분류하면 검색 결과 파생(A 145 · B 46 · C 111), LLM 산문(8·8·12), 시각·ID(10·10·11)이다. **§2의 보장 대상에서는 어느 모드에서도 차이가 발생하지 않았다.**

실행 시간: A 23.8초 · B 20.8초 · C 107.6초.

---

## 5. 변동 원인 — 3단계로 좁힘

**① retriever는 완전한 결정론이다.** 7개 topic 전부 2회 호출해 chunk_id 집합과 순서까지 동일함을 확인했다.

**② rag_cite가 LLM에 넘기는 프롬프트도 동일하다.** `prompt_hash.rag_cite`가 전 모드에서 일치한다.

**③ 따라서 원인은 Azure OpenAI 응답의 비결정성이다.** 실제 rag_cite 프롬프트(21,963자·청크 12건)를 그대로 3회 호출한 결과:

```
seed 미지정   3회 동일 = False   고유 응답 2종
seed = 42     3회 동일 = False   고유 응답 2종
```

**`seed`를 지정해도 해결되지 않는다.** 짧은 프롬프트에서는 3회 동일했으므로, 프롬프트가 길고 후보가 많을수록 갈리는 것으로 보인다. `temperature=0`은 벤더 측 비결정성을 제거하지 못한다.

> **부수 확인 — `seed` 전달이 비일관적이다.** `get_llm(temperature, *, seed)` 호출부 3곳 중 `extract_ips_chain.py:78`만 seed를 넘기고 `rag_cite.py:839`·`judge_eval.py:379`는 넘기지 않는다. 위 측정상 이를 고쳐도 재현되지 않지만, 일관성 차원에서 정리할 가치는 있다.

---

## 6. `--offline`에 대한 정정

**`--offline`은 재현성 모드가 아니다.** docstring이 밝히듯 "외부 키 없이 CI smoke를 돌리기 위한 것"이며, 실제로 대체하는 범위는 다음과 같다.

| 대상 | offline이 대체하는가 | 근거 |
| --- | --- | --- |
| 시장 데이터 | **예** — `data_source="dummy"` → 고정 수식 + parquet 캐시 | `load_inputs.py:82` |
| IPS 추출 LLM | **예** — 고정 `_offline_profile()` 반환 | `extract_ips.py:34` |
| RAG 검색 | 아니오 — 실제 Chroma 검색 | `rag_cite.py`에 offline 분기 없음 |
| rag_cite LLM | 아니오 — 실제 Azure 호출 | 〃 |
| judge_eval LLM | 아니오 — 실제 Azure 호출 | `judge_eval.py`에 offline 분기 없음 |

발표·문서에서 "offline이라 재현된다"고 서술하지 않는다. 재현되는 이유는 offline 여부가 아니라 **§2 항목이 결정론 계층 산출물이기 때문**이다.

---

## 7. 모의 감사 대응

**재현 데모는 §2 항목의 일치를 보인다.** `replay_verify` 대조 출력에 §2 항목만 싣고, §3 항목은 "재현 대상 아님"으로 함께 표기해 심사자가 화면에서 차이를 발견하기 전에 우리가 먼저 밝힌다.

주의할 점 두 가지.

1. **화면에 인용 목록이 보이면 심사자가 육안으로 차이를 잡는다.** 인용을 화면에 띄운다면 "인용 집합은 재현 대상이 아니다"를 먼저 말한다.
2. **차단 경로는 107.6초가 걸린다** (judge 3회 재시도). 3분 제한에 여유가 크지 않으므로, 차단 시연을 라이브로 할 경우 시간을 실측해 두어야 한다.

---

## 8. 향후 옵션 — LLM 응답 캐시 (미채택)

완전 일치를 원한다면 `prompt_sha256 → 응답` 캐시를 파일로 두고 캐시 히트 시 LLM을 호출하지 않는 방식이 유일한 현실적 수단이다(신규 모듈 약 80~120줄 + `get_llm` 래핑 1곳). `--replay` 플래그로 분리하면 통상 실행 경로를 오염시키지 않고 실행 시간도 수 초로 단축된다.

**현재 미채택이다.** §2 선언만으로 무효 조건 ③이 방어되며, 도입 시에는 발표에서 **"LLM 응답을 고정 재생하는 재현 모드"**라고 정확히 밝혀야 한다. "같은 입력이라 같은 결과가 나왔다"와 "캐시된 응답을 재생했다"는 다른 주장이기 때문이다.

---

## 9. 이 문서의 갱신 규칙

- 재현 범위를 넓히거나 좁힐 때는 **재실행 검증 전에** 이 문서를 먼저 고친다.
- 측정값이 바뀌면 §4를 갱신하고 측정 일자를 남긴다.
- §2 항목에서 불일치가 발견되면 범위를 조정하지 말고 **원인을 찾아 고친다.** 그것이 결정론 계층의 결함이기 때문이다.
