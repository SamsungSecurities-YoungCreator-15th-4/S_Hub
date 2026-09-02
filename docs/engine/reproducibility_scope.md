# 재현성 범위 선언 (Reproducibility Scope)

> 대상: S.ymphony Proof · R5
> 최초 선언 2026-08-01 · 최종 갱신 2026-08-02 · 근거: 아래 §4 실측
> 측정 기준 커밋 `d865307` (`develop`, #148·#150 반영)
> **이 문서는 재실행 검증 전에 선언된다.** 결과를 보고 범위를 조정하지 않는다.

---

## 1. 왜 범위를 선언하는가

과제 무효 조건 ③은 "같은 입력인데 결과가 달라짐 **(선언한 대상 기준)**"이다. 이 단서는 봐주기가 아니라 요구다 — LLM이 포함된 파이프라인에서 전 필드 재현은 불가능하며, **무엇이 결정론이고 무엇이 아닌지 아는가**를 묻는 것이다. 범위를 선언하지 못하면 그 자체가 시스템을 모른다는 뜻이 된다.

따라서 우리는 재현 대상을 먼저 못박고, 제외 대상은 제외 이유와 함께 공개한다.

---

## 2. 재현 보장 대상

동일 입력·동일 결정론 설정으로 재실행할 때 아래 항목은 코드 구조상
**완전히 일치해야 한다.** 이 목록에는 실제 LLM 판정이나 그 파생 상태를
포함하지 않는다.

| 대상 | 근거 |
| --- | --- |
| `config_hash` | `sha256_of_dict(run_config)` — 설정 파일에서만 유래 |
| `computation_hash` | `engine/deterministic/metrics.py` — 수익률·가중치·파라미터 payload, seed 고정 |
| `approval_hash` | HITL 승인 입력의 결정론 해시 |
| `metrics` 전체 | 순수 numpy 계산 계층 |
| `explanations` 전체 | 고정 골격 + metrics 값 조립 (LLM 생성 아님) |
| `prompt_hash.rag_cite` | 검색 결과가 아닌 topic 골격에서 조립 |

**이 목록이 무조건적인 "같은 결과"의 정의다.** 재현 데모와 증거 번들의
재현 지문은 이 항목들로 대조한다.

### 2.1 조건부 재현·반복 실측 대상

아래 항목은 §4.1의 반복 실행에서 일치했지만, LLM 판정이 포함되어 **항상 같다고
보장하지 않는다.** 분리된 감사 지표로 관찰하고 불일치를 숨기지 않는다.

| 대상 | 정확한 성질 |
| --- | --- |
| Judge 6축 판정·`judge.passed` | 4축은 결정론이지만 환각·위조정밀도 2축은 LLM 판정이므로 반복 실측 대상 |
| `report.status`·`report.finalized`·`export_allowed` | `judge.passed`의 결정론 파생이지만 upstream LLM 판정이 바뀌면 함께 바뀔 수 있음 |
| `manual_review_gate.decision_hash` | 동일한 정책·계산·Judge 판정 내용에는 같지만, `failed_axes`가 바뀌면 의도적으로 달라짐 |

> #150은 `decision_hash`에서 `trace_id`·`stopped_at`을 제외해 **동일한 차단
> 판단 내용**에 대한 조건부 재현성을 회복했다. 이는 전체 LLM 파이프라인의
> 무조건적 재현 보장을 뜻하지 않는다.

---

## 3. 재현 제외 대상 (명시적 선언)

| 대상 | 제외 사유 |
| --- | --- |
| `citations` 집합·순서 | LLM 응답 비결정성 (§5 참조). retriever는 결정론이나 인용 선택 단계가 갈린다 |
| `judge.rubric.*.reason` 문구 | LLM 산문. 판정(pass/fail)도 §2.1의 반복 실측 대상이며 무조건 보장은 아님 |
| `prompt_hash.judge_eval` | judge 프롬프트 payload에 `citations`가 포함되어 위 항목의 파생으로 변동 |
| `trace_id` · `run_id` · 타임스탬프 | 실행마다 다른 것이 정상. LangSmith 추적이 켜져 있으면 `trace_id`가 매 실행 새 UUID에서 파생된다 |
| LangSmith trace URL | 위 파생 |
| `ips` 추출 산출물 (`ips.Unique` 및 파생 5개 경로) | IPS 추출이 LLM 산출물이라 `citations`와 같은 사유다 — Azure 응답 비결정성(§5). `--offline`은 고정 프로필을 돌려주므로(§6) 모드 A·C에서는 갈리지 않는다 |

`ips.Unique`는 `IPSProfile`의 필드이고(`state.py:32` (Unique)), 함께 움직이는 파생 5개는
아래와 같다. 모두 §4.1 모드 B에서 실제로 갈린 leaf 경로다.

| 파생 경로 | 생산 지점 |
| --- | --- |
| `ips_extraction_meta.output_hash` | `extract_ips.py:52` (output_hash) |
| `ips_extraction_meta.extraction_hash` | `extract_ips.py:58` (extraction_hash) |
| `report.client_summary.ips.Unique` | `assemble_report.py:326` (ips) |
| `report.reproducibility.ips_extraction.output_hash` | `assemble_report.py:359` (ips_extraction) |
| `report.reproducibility.ips_extraction.extraction_hash` | 〃 |

### 이 항목은 선언의 공백을 메운 것이다

**`ips`는 §2에 있다가 내려온 항목이 아니다.** 최초 선언에서 §2에도 §3에도 없었고,
§4.1의 N=10 재측정에서 모드 B의 문구가 갈리는 것이 드러나면서 그 공백이 보였다.
따라서 이 추가는 **보장 범위를 좁힌 것이 아니라 빠져 있던 선언을 채운 것**이다.

§9는 "§2 항목에서 불일치가 발견되면 범위를 조정하지 말고 원인을 찾아 고친다"고
정한다. 그 규칙은 **보장한 적 있는 항목**에 적용된다. `ips`는 보장한 적이 없으므로
그 규칙의 대상이 아니며, 오히려 §9 첫 줄("범위를 넓히거나 좁힐 때는 재실행 검증
전에 이 문서를 먼저 고친다")이 요구하는 선언을 뒤늦게 이행하는 쪽에 해당한다.
같은 일이 반복되지 않도록, 새 state 키를 만들 때 §2·§3 중 어디에 속하는지를
함께 정하는 것을 §9에 규칙으로 두는 편이 낫다.

### 제외 대상에 대한 원칙

**"재현 지문"으로 제시하는 해시는 `computation_hash` · `config_hash` · `approval_hash` 세 개로 한정한다.** `prompt_hash.judge_eval`을 재현 증거로 내세우면 자기모순이 된다.

`decision_hash`는 §2.1의 조건부 지문이며 이 세 개에는 넣지 않는다. 차단
실행에서만 존재하고 Judge 판정 내용에 따라 달라질 수 있다. **같은 차단
판단의 감사 지문**으로는 쓰되, 모든 실행에 공통인 재현 지문으로는 제시하지 않는다.

---

## 4. 실측 근거

**아래 모든 측정은 커밋 `d865307` 기준이다.**

### 4.1 3개 모드 필드 대조 (2026-08-02 재측정)

동일 입력·동일 thread로 3개 모드를 실행하고 `--dump-state` 덤프를 필드 단위로 대조했다. 각 모드의 **1회차를 기준으로 2회차 이후를 대조**한다.

- **A**: `--auto-approve --offline` — N=10
- **B**: `--auto-approve` (실 Azure·실 RAG) — N=10
- **C**: `--auto-approve --offline --force-judge-fail 3` (차단 경로) — N=5

각 행이 어느 선언에 속하는지 함께 적는다. 이 표는 측정값이고, 무엇을 보장으로
내세우는지는 §2·§2.1·§3이 정한다.

| 대상 | 선언 | A (N=10) | B (N=10) | C (N=5) |
| --- | --- | --- | --- | --- |
| `config_hash` · `computation_hash` · `approval_hash` | §2 | 동일 | 동일 | 동일 |
| `metrics` 전체 | §2 | 차이 0건 | 차이 0건 | 차이 0건 |
| `explanations` 전체 | §2 | 차이 0건 | 차이 0건 | 차이 0건 |
| `prompt_hash.rag_cite` | §2 | 동일 | 동일 | 동일 |
| **judge 6축 판정** | §2.1 | **10회 6/6 동일** | **10회 6/6 동일** | **5회 6/6 동일** |
| `judge.passed` | §2.1 | 10회 True | 10회 True | 5회 False |
| `report.status` · `finalized` · `export_allowed` | §2.1 | 동일 | 동일 | 동일 |
| `manual_review_gate.decision_hash` | §2.1 | 해당 없음 | 해당 없음 | 5회 동일 |
| `citations` 건수 | §3 | 20~30 (중앙값 22.5) | 19~23 (중앙값 19.5) | 19~28 (중앙값 20) |
| `citations` chunk_id 집합·순서 | §3 | 상이 | 상이 | 상이 |
| `judge.rubric.*.reason` | §3 | 상이 | 상이 | 상이 |
| `prompt_hash.judge_eval` | §3 | 상이 | 상이 | 상이 |
| `ips.Unique` 등 IPS 추출 산출물 | §3 | 동일 | **상이** | 동일 |

차이 건수는 leaf 경로 단위이며, 1회차와 갈린 적이 있는 경로의 **합집합**이다. A 760 · B 609 · C 570이고, 쌍별로는 A 291~594 · B 21~585 · C 178~362다. 분류하면 검색 결과 파생(A 735 · B 578 · C 544), LLM 산문(12·12·12), 시각·ID(13·13·14), IPS 추출 LLM(0·6·0)이다. 미분류 경로는 0건이다. **§2의 무조건 보장 대상과 §2.1의 조건부 대상 모두에서 어느 모드·어느 실행에서도 차이가 발생하지 않았다(불일치 0건).**

`ips.Unique`와 파생 5개 경로는 이 측정에서 미선언 상태로 드러났고, **§3에 제외 대상으로 편입했다.** 편입 사유와 경로 목록은 §3을 따른다.

실행 시간: A 평균 36.8초(34.8~39.8) · B 평균 32.4초(31.6~33.7) · C 평균 116.0초(74.2~131.4).

### 4.2 `decision_hash` — #150 이후 재측정 (2026-08-02, 커밋 `d865307`)

`decision_hash`를 §3에서 §2.1로 옮긴 근거다. 차단 경로(모드 C)를 **LangSmith 추적 off/on 각 2회, 총 4회** 실행했다. 추적 on을 따로 돌린 이유는 **off에서는 `trace_id`가 애초에 갈리지 않기 때문**이다 — 추적이 꺼지면 `load_inputs`가 `run-{config_hash[:12]}`로 되짚어(`load_inputs.py:100` (trace_id)) 매 실행 같은 값이 나오고, 켜져 있어야 `run-{uuid4().hex[:12]}`로 실행마다 달라진다(`observability/langsmith.py:133`). off만 측정하면 "`trace_id`가 달라도 지문이 같다"를 증명한 것이 아니라 `trace_id`가 같은 경우를 본 것에 불과하다.

| 대상 | 추적 off 2회 | 추적 on 2회 |
| --- | --- | --- |
| `trace_id` | 동일 (`run-89c73320a15a`) | **상이** (`run-a888f05a2d8d` / `run-a3e2b387e11d`) |
| `decision_hash` | 동일 | **동일** |
| `manual_review_gate` 나머지 11개 키 | 차이 0건 | 차이 0건 |
| `citations` chunk_id 집합·순서 | 상이 | 상이 |

`decision_hash`는 **4회 실행 전부** `dd776bffcbf1a539acdf5566ddbea74e5be9bef8d7c3adfb5876bf021c675227`로 일치했다. `trace_id`가 갈린 실행 쌍에서도 같았고, 추적 on/off 사이에서도 같았다. 같은 실행에서 `citations`는 여전히 갈렸으므로(§3) 이 일치는 실행 전체가 결정론이어서가 아니라 **해시 입력이 결정론 산출물로만 구성되어서**다.

측정 조건: `--auto-approve --offline --force-judge-fail 3`, `as_of_date=2026-07-03`, `policy_version=2026-08-01.v1`, `computation_hash=41c27a5c…3b120b08`, `failed_axes=["forced_failure"]`.

### 4.3 통합 레포 머지 이후 재확인 (2026-09-01, 커밋 `b7286fe`)

pydantic 2.13.5·yfinance 1.7.0 머지 이후 §4.2의 기준선이 유지되는지 확인한 기록이다.
**결론부터: §4.2의 기준선 `dd776bff…`는 유지된다.** 아래 측정에서 나온 다른 값은
기준선을 대체하지 않는다 — 측정 환경이 §4.2와 다르기 때문이다.

측정 환경: Python 3.10.21(CI와 동일한 마이너), 루트 `requirements.txt` 핀 그대로
(pydantic 2.13.5 · numpy 2.2.6 · scipy 1.15.3 · yfinance 1.7.0 · langgraph 1.2.10).
조건은 §4.2와 같다 — `--auto-approve --offline --force-judge-fail 3`,
`as_of_date=2026-07-03`, `policy_version=2026-08-01.v1`. 3회 반복했다.

| 대상 | §4.2 (2026-08-02) | 이번 측정 (3회) |
| --- | --- | --- |
| `computation_hash` | `41c27a5c…3b120b08` | **동일** (`41c27a5c…3b120b08`) |
| `trace_id` (추적 off) | `run-89c73320a15a` | **동일** |
| `decision_hash` | `dd776bff…c675227` | 3회 모두 `b9572518…c5d696f6` (상이) |
| `failed_axes` | `["forced_failure"]` | 5건 (아래 참조) |

**머지가 깨뜨린 것은 없다.** 머지가 건드릴 수 있었던 결정론 수치 계층은
`computation_hash`가 §4.2와 **바이트 단위로 같다**. `decision_hash`도 3회 실행에서
전부 일치해 결정론 자체는 유지된다.

**값이 갈린 이유는 해시 입력인 `failed_axes`가 달라서다.** §2.1이 밝힌 대로
`decision_hash`는 `failed_axes`가 바뀌면 의도적으로 달라진다. 이번 측정기는
Azure OpenAI 키도, 로컬 RAG 코퍼스·인덱스도 없는 환경이라 4축이 추가로 실패했다.

| 추가 실패 축 | judge가 남긴 사유 | 원인 |
| --- | --- | --- |
| `false_precision` · `hallucination` | "판정을 위한 LLM Judge를 구성하지 못했습니다" | Azure OpenAI 키 없음 |
| `source_validity` · `verified_citations_present` | "strict citation gate에서 검증 통과 인용이 0건입니다" | 로컬 코퍼스·Chroma 인덱스 없음 (`corpus/**/*.pdf`는 저작권상 gitignore) |

즉 `b9572518…`은 **"키도 코퍼스도 없는 환경"이라는 다른 조건의 관측값**이며,
§4.2 기준선의 재현 실패가 아니다. 기준선을 갱신하려면 §4.2와 같은 환경
(Azure 키 + 로컬 코퍼스 인덱스)에서 `failed_axes=["forced_failure"]`가 재현되는
상태로 다시 측정해야 한다. **그 재측정은 아직 하지 않았다.**

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

> **부수 확인 — `seed` 전달이 비일관적이다.** `get_llm(temperature, *, seed)` 호출부 3곳 중 `extract_ips_chain.py:78`만 seed를 넘기고 `rag_cite.py:879`·`judge_eval.py:380`는 넘기지 않는다. 위 측정상 이를 고쳐도 재현되지 않지만, 일관성 차원에서 정리할 가치는 있다. 단 `judge_eval`의 seed 전달 변경은 judge 출력 분포를 바꾸므로 R2 v1/v2 캘리브레이션 측정이 끝나기 전에는 수정하지 않는다.
>
> **두 번째 실사례 — seed를 넘겨도 갈렸다.** `extract_ips_chain.py:78` (EXTRACTION_SEED)는 세 호출부 중 **유일하게 `seed=EXTRACTION_SEED`를 넘기는데도** §4.1 모드 B에서 `ips.Unique`가 실행마다 갈렸다. 위 ③의 rag_cite 프롬프트 실험과 별개로, 실제 파이프라인에서 seed 지정이 재현을 보장하지 못한다는 것을 다시 보여준다.

---

## 6. `--offline`에 대한 정정

**`--offline`은 재현성 모드가 아니다.** docstring이 밝히듯 "외부 키 없이 CI smoke를 돌리기 위한 것"이며, 실제로 대체하는 범위는 다음과 같다.

| 대상 | offline이 대체하는가 | 근거 |
| --- | --- | --- |
| 시장 데이터 | **예** — `data_source="dummy"` → 고정 수식 + parquet 캐시 | `load_inputs.py:86` (demo_options) |
| IPS 추출 LLM | **예** — 고정 `_offline_profile()` 반환 | `extract_ips.py:34` |
| RAG 검색 | 아니오 — 실제 Chroma 검색 | `rag_cite.py`에 offline 분기 없음 |
| rag_cite LLM | 아니오 — 실제 Azure 호출 | 〃 |
| judge_eval LLM | 아니오 — 실제 Azure 호출 | `judge_eval.py`에 offline 분기 없음 |

발표·문서에서 "offline이라 재현된다"고 서술하지 않는다. 재현되는 이유는 offline 여부가 아니라 **§2 항목이 결정론 계층 산출물이기 때문**이다.

---

## 7. 모의 감사 대응

**재현 데모는 §2의 결정론 항목과 §2.1의 반복 실측 항목을 분리해
보인다.** `replay_verify` 대조 출력에서 어떤 항목이 보장이고 어떤 항목이 관찰값인지
표기해, LLM 판정의 일치를 결정론 보장으로 과장하지 않는다. §3 항목은 "재현 대상
아님"으로 함께 표기한다.

주의할 점 두 가지.

1. **화면에 인용 목록이 보이면 심사자가 육안으로 차이를 잡는다.** 인용을 화면에 띄운다면 "인용 집합은 재현 대상이 아니다"를 먼저 말한다.
2. **차단 경로는 평균 116.0초·최대 131.4초가 걸린다** (judge 재시도 상한 소진, §4.1 N=5). 3분 제한에 남는 여유가 최대치 기준 48.6초뿐이므로, 차단 시연을 라이브로 한다면 시간을 다시 실측하고 대비책을 정해 둔다.

---

## 8. 향후 옵션 — LLM 응답 캐시 (미채택)

완전 일치를 원한다면 `prompt_sha256 → 응답` 캐시를 파일로 두고 캐시 히트 시 LLM을 호출하지 않는 방식이 유일한 현실적 수단이다(신규 모듈 약 80~120줄 + `get_llm` 래핑 1곳). `--replay` 플래그로 분리하면 통상 실행 경로를 오염시키지 않고 실행 시간도 수 초로 단축된다.

**현재 미채택이다.** §2 선언만으로 무효 조건 ③이 방어되며, 도입 시에는 발표에서 **"LLM 응답을 고정 재생하는 재현 모드"**라고 정확히 밝혀야 한다. "같은 입력이라 같은 결과가 나왔다"와 "캐시된 응답을 재생했다"는 다른 주장이기 때문이다.

---

## 9. 이 문서의 갱신 규칙

- 재현 범위를 넓히거나 좁힐 때는 **재실행 검증 전에** 이 문서를 먼저 고친다.
- 측정값이 바뀌면 §4를 갱신하고 측정 일자를 남긴다.
- §2 항목에서 불일치가 발견되면 범위를 조정하지 말고 **원인을 찾아 고친다.** 그것이 결정론 계층의 결함이기 때문이다.
- §2.1 항목이 달라지면 보장 범위를 조용히 넓히거나 좁히지 말고 불일치 사례와
  LLM 모델·프롬프트 버전을 같이 기록한다.
