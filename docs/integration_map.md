# S.ymphony 엔진 × S.upervisor 대시보드 통합 지도

작성일 2026-09-02 · 기준 커밋 `2467eaa` (main)

이 문서는 **조사·측정 결과만** 담는다. 코드는 한 줄도 바꾸지 않았다.
근거가 코드에 없는 항목은 추정하지 않고 **"확인 필요"**로 남겼다.

## 0. 한 줄 요약

**엔진과 대시보드 사이에 데이터 경로가 없다.** `frontend/`·`backend/` 어디에도
`engine/`을 import하거나 호출하는 코드가 없고, 엔진 노드 9개의 산출물 중
대시보드 화면에 표시되는 것은 **0개**다. 두 쪽은 같은 개념(VaR·스트레스·IPS·자산군)을
각자 따로 정의해 각자 계산한다. 그래서 이 문서의 대부분은 "무엇을 어디에 붙일까"가
아니라 **"붙이기 전에 무엇을 먼저 맞춰야 하는가"**에 관한 것이다.

확인 방법:

```
grep -rn "^from engine|import engine" backend/            → 0건
grep -rni "symphony|engine" frontend/**/*.ts(x)           → runStatus.ts의 주석 6줄뿐
                                                            (실행 코드 아님)
```

---

## Part 1. 엔진 파이프라인 인벤토리

`engine/graph.py`의 조립 순서대로. 계층 판정 기준은 AGENTS.md의 불변 규칙 3
(`engine/engine/` 안 = 결정론 계층, LLM 호출은 `engine/llm/` + 노드 계층에서만).

| # | 노드 · 파일 | 하는 일 | 입력 (읽는 state) | 출력 (쓰는 state) | 계층 | 대시보드 표시 |
|---|---|---|---|---|---|---|
| 1 | `load_inputs`<br>`engine/nodes/load_inputs.py:77` | config.yaml 로드 + 상담 원문·포트폴리오 정규화, 승인 레코드 draft 생성 | `demo_options`, `run_config`, `trace_id`, `raw_input`, `portfolio` | `run_config`, `trace_id`, `raw_input`, `portfolio`, `market_data_ref`, `approval` | 결정론 (노드) | **없음** |
| 2 | `extract_ips`<br>`engine/nodes/extract_ips.py:32` | 상담 자연어 → IPS 구조화 추출 (+ 유동성 필요금액) | `demo_options`, `raw_input`, `conflicts`, `conflict_retries` | `ips`, `liquidity_required_krw`, `ips_extraction_meta`, `conflict_retries` | **LLM** (`engine/llm/extract_ips_chain.py`) | **없음** |
| 3 | `conflict_check`<br>`engine/nodes/conflict_check.py:71` | `config/ips_policy.yaml` 임계값으로 적합성 충돌을 block/review로 판정 | `ips`, `portfolio`, `liquidity_required_krw` | `conflicts`, `conflict_policy` | 결정론 (노드) | **없음** |
| 4 | `approval_gate`<br>`engine/nodes/approval_gate.py:14` | PB 검토 결과 검증 후 승인을 locked로 전이 (HITL 인터럽트 지점) | `approval`, `conflicts`, `run_config` | `approval` (+`approval_hash`) | 결정론 (노드) | **없음** |
| 5 | `var_engine`<br>`engine/nodes/var_engine.py:30` | VaR·CVaR·스트레스·기여도 일괄 계산 | `run_config`, `portfolio` | `metrics` | **결정론 계층** (`engine/engine/metrics.py`) | **없음** |
| 6 | `rag_cite`<br>`engine/nodes/rag_cite.py:830` | 수치별 설명문 생성 + Chroma 검색 인용 후보 → 결정론 검증 통과분만 채택 | `metrics`, `run_config`, `judge_retries`, `citation_rejections`, `judge_feedback`, `ips` | `run_config`, `explanations`, `citations`, `citation_rejections` | **LLM + 결정론 검증 혼합** | **없음** |
| 7 | `judge_eval`<br>`engine/nodes/judge_eval.py:375` | 형태 검사(결정론) + 6축 루브릭으로 통과/재작성/차단 판정 | `run_config`, `metrics`, `explanations`, `citations`, `approval`, `portfolio`, `judge_retries`, `demo_options` | `run_config`, `judge`, `judge_retries`, `judge_feedback` | **혼합** — 6축 중 4축 결정론, `hallucination`·`false_precision` 2축만 주입 LLM (`engine/judge/rubric.py:354`) | **없음** |
| 8 | `assemble_report`<br>`engine/nodes/assemble_report.py:294` | 최종 리포트 조립 + 확정/미확정 상태·거버넌스 기록 | `metrics`, `run_config`, `portfolio`, `citations`, `explanations`, `judge`, `approval`, `conflicts`, `ips`, `ips_extraction_meta`, `conflict_policy`, `trace_id`, `raw_input`, `judge_retries` | `report` | 결정론 (노드) | **없음** |
| 9 | `manual_review_gate`<br>`engine/nodes/manual_review_gate.py:115` | judge 재시도 소진 시 확정·다운로드 차단, 차단 사유·결정 지문 기록 | `approval`, `run_config`, `judge`, `judge_retries`, `judge_feedback`, `metrics`, `trace_id` | `report` (status=`pending_manual_review`, `export_allowed=False`) | 결정론 (노드) | **없음** |

### Part 1에서 "확인 필요"로 남긴 것

| 항목 | 왜 확정하지 못했나 |
|---|---|
| `rag_cite`의 실제 인용 산출 개수·품질 | Azure 키·Chroma 인덱스가 이 환경에 없다. `rag_cite.py:16-18`의 폴백 경로(빈 인용)로만 동작하므로 실인용 경로를 관측하지 못했다 |
| `judge_eval` LLM 2축의 판정 분포 | 위와 같은 이유. 결정론 4축만 관측 가능 |
| `metrics` 딕셔너리의 전체 키 목록 | `compute_metrics`(`engine/engine/metrics.py:264`)가 horizon별로 키를 동적 생성한다. 실행해 확인한 것은 `meta.computation_hash` 경로뿐이며, 전체 스키마는 실행 산출물로 확정해야 한다 |
| `report` 딕셔너리를 소비하는 UI 계약 | 소비자가 `console/`(Streamlit)뿐이고 대시보드 쪽 계약이 존재하지 않는다 |

---

## Part 2. 갭 표 — 붙일 자리와 난이도

Part 1이 전부 "없음"이므로 9개 노드 산출물 전체가 갭이다. 산출물 단위로 쪼개
붙일 자리를 찾았다. **줄 번호는 기준 커밋 `2467eaa` 기준이다.**

| 엔진 산출물 | 새 UI 필요? | 붙일 자리 (파일:줄) | 난이도 | 근거 |
|---|---|---|---|---|
| `metrics` VaR·CVaR | **필드 추가** | `frontend/components/portfolio/PortfolioSection.tsx:201` 지표 그리드 | **중** | 타일 2개 추가는 단순하나, 이 그리드는 `grid-cols-3`에 지표 6개다. 8개가 되면 마지막 줄이 비므로 열 수 또는 배치를 함께 조정해야 한다 |
| `metrics` 스트레스 시나리오 A·B·C | **필드 추가** | `frontend/components/right-panel/StressTestSection.tsx:23` `SCENARIO_PRESETS` | **상** | 프리셋 배열에 항목을 더하는 것 자체는 쉽다. 그러나 대시보드 프리셋은 `{ratePct, fxKrw}` 2축 슬라이더 값이고 엔진 시나리오는 자산군별 충격 벡터라 **자료형이 호환되지 않는다**. Part 3-④ 참조 |
| `citations` (검증 통과 인용) | **필드 추가** | 화면 `frontend/components/right-panel/InsightSection.tsx:186` · PDF `frontend/components/pdf/PbPdfTemplate.tsx:1892` | **중** | 양쪽에 이미 "출처 / 인용 목록" 렌더가 있다. 엔진 인용 스키마와 `InsightCitation` 타입의 필드 대조가 선행 작업 |
| `explanations` (수치별 설명문) | **필드 추가** | `frontend/components/right-panel/InsightSection.tsx:130` 결과 영역 | **하** | 문자열 목록 렌더라 기존 영역에 그대로 들어간다 |
| `report.status` / `governance.export_allowed` | **필드 추가** | `frontend/components/header/PdfExportButton.tsx:112` `disabled={!!exporting}` | **하** | 스토어에 `runStatus`·`RUN_STATUS_EXPORT_ALLOWED`가 이미 있다(`frontend/lib/runStatus.ts`). 현재 disabled 조건이 하나뿐이라 붙일 자리가 명확하다 |
| `approval` (draft→reviewed→locked) | **새 UI** | 없음 (스토어 필드만 존재) | **중** | 승인 상태를 보여 주는 화면 요소가 대시보드에 없다. `frontend/components/sidebar/Sidebar.tsx:728` IPS 조율기 헤더가 후보지만 확정된 자리는 아니다 |
| `conflicts` (block/review 충돌) | **새 UI** | 없음 | **상** | 표시할 자리도, 예외 승인 사유를 입력받을 자리도 없다. `severity=review`는 10자 이상 사유 입력이 필수라(`approval_gate.py:39`) 입력 폼이 함께 필요하다 |
| `judge` (6축 판정·재시도) | **새 UI** | 없음 | **중** | 판정 결과를 표시할 자리가 없다. 판정 자체는 읽기 전용이라 폼은 불필요 |
| `citation_rejections` (탈락 인용 이력) | **새 UI** | 없음 | **중** | 감사 추적용 누적 목록이라 기존 "출처 목록"과 성격이 다르다(채택분 vs 탈락분) |
| `metrics.meta.computation_hash`, `trace_id`, `approval_hash`, `decision_hash` | **새 UI** | 없음 | **하** | 대시보드에 해시·추적 ID를 표시하는 요소가 **하나도 없다**(`grep -rn "hash\|trace"` → UI 0건). 다만 문자열 한 줄 표시라 구현 자체는 가볍다 |
| `market_data_ref` (데이터 출처·기준일) | **필드 추가** | `frontend/components/common/DataSourceBadge.tsx` | **하** | 출처 배지 체계가 이미 있다. `source`/`note` 두 필드에 매핑된다 |
| `report` 전체 (리포트 본문) | **새 UI** | 없음 | **확인 필요** | 리포트를 화면에 띄울지, PDF에만 실을지 정해진 바가 없다. 결정 전에는 난이도를 판정할 수 없다 |

---

## Part 3. 계약 불일치

이미 알려진 3건(VaR·IPS 필드·RAG) 외에 **7건을 새로 찾았다.** 심각한 순서로 정렬했다.

### ① 자산군 분류 체계가 다르다 — 6종 vs 12종 *(새로 찾음)*

| | 엔진 | 백엔드·대시보드 |
|---|---|---|
| 정의 위치 | `engine/engine/returns.py:122` `REAL_ASSET_TICKERS` | `backend/app/portfolio/assets.py:27` `ASSET_TICKERS` |
| 개수 | 6 (`domestic_equity`, `global_equity`, `domestic_bond`, `global_bond`, `alternatives`, `cash`) | 12 (`domestic_equity`, `overseas_blue_chip`, `overseas_growth`, `overseas_dividend`, `general_bond`, `separate_tax_bond`, `low_coupon_bond`, `reit`, `gold`, `commodity`, `dollar`, `cash`) |

세부 대조:

| 자산군 키 | 엔진 티커 | 백엔드 티커 | 판정 |
|---|---|---|---|
| `domestic_equity` | `^KS11` | `^KS11` | **일치** |
| `cash` | 티커 없음 — `rf_annual/252` 상수로 생성 (`returns.py:169`) | `"CASH"` (`assets.py:39`) | **같은 이름 다른 생성 방식** |
| `alternatives` | `GLD` (금 단독) | 대응 키 없음. `ALTERNATIVE_ASSETS = [reit, gold, commodity, dollar]` (`assets.py:132`) | **같은 이름 다른 의미** — 엔진의 "대체투자"는 실제로는 금 하나다 |
| `global_equity` | `ACWI` | 대응 키 없음 (`SPY`/`QQQ`/`SCHD` 3종으로 분리) | 같은 의미 다른 이름 |
| `global_bond` | `IGOV` | 대응 키 없음 | 같은 의미 다른 이름 |
| `domestic_bond` | `114260.KS` | `471230.KS`·`439870.KS`·`484790.KS` 3종 | 같은 의미 다른 이름·다른 상품 |

**이것이 최상위 병목이다.** 자산군 키가 맞지 않으면 포트폴리오를 그대로 넘길 수 없고,
엔진의 `portfolio_returns`는 매핑 없는 자산군을 만나면 조용히 넘어가지 않고
`ValueError`로 실패한다(`engine/engine/metrics.py:51`).

### ② IPS `Return` 필드의 단위가 다르다 — % vs 억 원 *(새로 찾음)*

| | 정의 | 근거 |
|---|---|---|
| 엔진 | **억 원 금액** | `engine/state.py` `Return: float = Field(default=0.0, ge=0, description="목표 수익 금액, 단위 억 원")` |
| 백엔드 STT 추출 | **%** | `backend/app/stt/stt_record.py:60` `"목표 수익률. 단위는 %. 예: 연 5%면 5."` · 같은 파일 `:370` |
| 대시보드 표시 | **%** | `frontend/components/sidebar/Sidebar.tsx:749` `{ips.returnPct}%` |

같은 키 이름 `Return`으로 한쪽은 5(=5억), 다른 쪽은 5(=5%)를 담는다.
**값이 유효 범위 안에 있어 타입 검증에 걸리지 않고 조용히 통과한다.**

### ③ IPS 필드 개수가 다르다 — 9 vs 12 *(알려진 것의 정정)*

"IPS 7필드"로 공유돼 있으나 코드는 셋 다 다르다.

| | 필드 | 근거 |
|---|---|---|
| 백엔드 | **9** — Goal, Asset, Return, Risk, Time, Tax, Liquidity, Legal, Unique | `backend/app/services/ips.py:5` `IPS_KEYS` |
| 대시보드 | **9** — 위와 동일 (IpsRow 9행) | `frontend/components/sidebar/Sidebar.tsx:733~803` |
| 엔진 | **12** — 위 9개 + Name, Age, Job | `engine/state.py` `IPSProfile` |

추가로 엔진 쪽 5개 필드는 `Literal` 고정값이라 대시보드 값이 들어오면 검증에서 거부된다:
`Age="50"`, `Job="자영업자"`, `Goal=`(고정 문장), `Asset=50.0`, `Risk="균형형"`.
대시보드의 `risk`는 안정형·균형형·공격형 3종이므로(`frontend/lib/store.ts` `IpsState`)
**균형형이 아닌 고객은 엔진에 그대로 넣을 수 없다.**

### ④ 스트레스 시나리오의 정의·단위·계산 방식이 다르다 *(새로 찾음)*

| | 엔진 | 백엔드·대시보드 |
|---|---|---|
| 정의 위치 | `engine/engine/stress.py:13,29,45` | `backend/app/portfolio/metrics.py:622` `CRISIS_SCENARIO_SHOCKS` |
| 시나리오 | A 고금리(+250bp) · B 강달러(+15%) · C 코로나 | `crisis_2008` · `crisis_ru_war` + 금리·환율 2축 슬라이더 |
| 충격의 의미 | **즉시 가격 충격** — `loss = -(value × shock)` (`stress.py:104`) | **연간 수익률 충격을 관측기간 전체에 일별 드리프트로 주입** 후 지표 재계산 (`metrics.py:664` `apply_return_shocks`) |
| 산출물 | `loss_krw`, `loss_pct` (+ 밴드 상·하한) | 재계산된 기대수익률·변동성·MDD·세후수익률 |
| 겹치는 국면 | 코로나(2020) | 2008 금융위기, 2022 러우전쟁 |

두 쪽에 **공통으로 있는 시나리오가 하나도 없다.** 이름이 겹치는 것도 없고,
같은 국면을 다룬 것도 없다. 게다가 충격 값의 의미가 "즉시 가격 하락률"과
"기간 전체에 분산 주입되는 연간 드리프트"로 달라, 같은 `-0.25`도 다른 결과를 낸다.

### ⑤ 기준일(as_of_date)이 다르다 — 고정일 vs 오늘 *(새로 찾음)*

| | 기준일 | 관측기간 | 근거 |
|---|---|---|---|
| 엔진 | **고정 `2026-07-03`** | 1,250 거래일 | `config/config.yaml` `as_of_date`·`var_lookback_days` |
| 백엔드 | **호출 시점(오늘) 기준 상대 기간** | `"5y"` | `backend/app/portfolio/models.py:56`·`:189` `period: str = Field("5y")` |

엔진은 재현성을 위해 기준일을 못박았고 대시보드는 실시간을 따른다.
**두 화면에 나란히 숫자를 띄우면 관측 구간이 서로 다르다.**
관측 길이는 약 5년으로 같으나 끝점이 다르다.

### ⑥ 무위험이자율이 다르다 — 3.25% vs 3.5% *(새로 찾음)*

| | 값 | 쓰임 | 근거 |
|---|---|---|---|
| 엔진 | **0.0325** | `cash` 자산군의 일별 수익률 생성(`rf/252`) | `engine/engine/returns.py:134` · `config/config.yaml` `rf_rate` |
| 백엔드 | **0.035** (미국 기준 가정) | 샤프·소르티노의 분모 | `backend/app/portfolio/constants.py:105-106` `DEFAULT_RISK_FREE_RATE` |

같은 이름의 상수가 값도 다르고 역할도 다르다(수익률 생성 vs 지표 분모).

### ⑦ 런타임 의존성 핀이 다르다 — pandas 2.3 vs 3.0 *(새로 찾음)*

| | numpy | pandas | scipy |
|---|---|---|---|
| 엔진 (`requirements.txt`) | 2.2.6 | **2.3.3** | 1.15.3 |
| 대시보드 (`backend/requirements.txt`) | 2.4.6 | **3.0.5** | 핀 없음 |

AGENTS.md가 "합치지 않는다"고 명시한 의도된 분리다. 다만 **pandas 메이저 버전이
다른 두 환경에서 같은 수치를 계산한다**는 사실은 통합 논의에서 전제로 알고 있어야 한다.
Part 4-⑤에서 분위수 계산 자체는 두 구현이 동일한 값을 내는 것을 확인했다.

### ⑧ VaR — 기본 신뢰수준·음수 처리·반올림·라벨 *(알려진 것 + 확장)*

Part 4에서 수치로 대조한다. 코드 차이는 네 가지다.

| 항목 | 엔진 `historical_var` | 백엔드 `calculate_historical_var` |
|---|---|---|
| 기본 신뢰수준 | `0.99` (`engine/engine/metrics.py:16`) | `0.95` (`backend/app/portfolio/metrics.py:300`) |
| 음수 결과 | 그대로 반환 — `float(-q)` (`metrics.py:25`) | `max(-q, 0.0)`로 0에 고정 (`metrics.py:313`) |
| 반올림 | 없음 (float 그대로) | `safe_round(..., 6)` 6자리 (`metrics.py:318-320`) |
| method 라벨 | 없음 | `"historical_5_percentile"` 고정 (`metrics.py:321`) — **신뢰수준을 0.99로 넘겨도 라벨은 5 percentile 그대로다** |
| 시간 스케일링 | horizon별 `√h` (h=1,10) | `daily_loss × √252` 연환산 1종 (`metrics.py:314`) |
| CVaR | `historical_cvar` 있음 (`metrics.py:28`) | **대응 함수 없음** |

### ⑨ IPS 추출 — 대시보드 RRTTLLU vs 엔진 IPSProfile *(알려진 것)*
### ⑩ RAG — pgvector 고객문서 검색 vs Chroma 인용검증 *(알려진 것, 합치지 않기로 결정됨)*

### 화면에 없는 것 하나 더

`historical_var_95`는 프론트 타입에 존재하지만(`frontend/lib/api/types.ts:392`)
그 필드는 `RejectionCountsResponse`(포트폴리오 탐색 시 탈락 건수 카운터)의 일부이고,
**이 값을 읽는 컴포넌트가 없다.** 즉 **VaR은 현재 대시보드 어디에도 표시되지 않는다.**

---

## Part 4. VaR 두 함수 실측 대조

### 측정 조건

| 항목 | 값 |
|---|---|
| 입력 시계열 | `data/returns_dummy.parquet` — 레포에 이미 있는 산출물 (1,250행 × 6자산, 2021-09-20 ~ 2026-07-03) |
| 시계열 성격 | `engine/engine/returns.py`의 고정 수식 더미. 무작위성 없음 → 시드 불필요 |
| 포트폴리오 | `engine/nodes/load_inputs.py:14` `DUMMY_PORTFOLIO` (50억 원, 6자산) |
| 포트폴리오 수익률 | `engine.engine.metrics.portfolio_returns`로 생성 (n=1250, mean −0.00005419, std 0.00349700) |
| 실행 함수 | 두 함수를 **실제로 import해서 호출**했다. 재구현·복사 없음 |
| 실행 환경 | numpy 2.5.2 / pandas 3.0.5 (레포 핀과 다름 — Part 3-⑦) |
| 예외 | Part 4-③의 클램프 측정만 시드 고정 난수 사용. **시드 42** (`numpy.random.default_rng(42)`) |

`data/returns_dummy.parquet`는 `.gitignore` 대상이라 다른 사람 로컬에는 없을 수 있다.
`engine.engine.returns.load_returns()`를 한 번 호출하면 같은 파일이 결정론적으로 재생성된다.

### ① 신뢰수준을 맞췄을 때 — 사실상 동일

| 신뢰수준 | 엔진 `historical_var` | 백엔드 `daily_loss` | 차이 |
|---|---|---|---|
| 0.90 | 0.0046889008 | 0.0046890000 | −9.92e−08 |
| 0.95 | 0.0053808368 | 0.0053810000 | −1.63e−07 |
| 0.99 | 0.0060030502 | 0.0060030000 | +5.02e−08 |

**남은 차이는 계산식이 아니라 백엔드의 6자리 반올림뿐이다.** 50억 원 기준 금액으로는
0.90에서 −496원, 0.95에서 −816원, 0.99에서 +251원이다.

### ② 각자의 기본값일 때 — 여기서 갈린다

| | 값 | 50억 원 기준 |
|---|---|---|
| 엔진 `historical_var(r)` (기본 0.99) | 0.0060030502 | **30,015,251원** |
| 백엔드 `calculate_historical_var(s)` (기본 0.95) | 0.0053810000 | **26,905,000원** |
| 차이 | 0.0006220502 | **3,110,251원** |

엔진 기본값이 백엔드 기본값의 **1.1156배**다.
같은 데이터·같은 포트폴리오인데 함수 기본값만으로 일간 VaR이 311만 원 벌어진다.

또한 백엔드를 0.99로 호출해도 응답의 `method` 라벨은 `'historical_5_percentile'`
그대로였다(`backend/app/portfolio/metrics.py:321`이 문자열 상수로 고정). 라벨을 믿고
읽으면 신뢰수준을 잘못 알게 된다.

### ③ 음수 클램프가 결과를 바꾸는 정도

**레포 데이터에서는 발동하지 않는다.**

| 포트폴리오 | 0.90 / 0.95 / 0.99에서 VaR<0 | 클램프 발동 |
|---|---|---|
| 6자산 기본 | 없음 | 없음 (차이 0원) |
| 현금 100% | 없음 (일별 수익률이 음수를 포함) | 없음 (차이 0원) |

발동 경계를 찾아 내려가 보면, 6자산 기본 포트폴리오는 신뢰수준 **약 0.49**,
현금 100%는 **약 0.41** 아래에서야 엔진 VaR이 음수가 된다. 실제로 쓰는
0.90~0.99 구간과는 거리가 있다.

클램프가 실제로 갈리는 경우를 보기 위해, **일별 수익률이 항상 양수인 시계열**
(시드 42, `default_rng(42).uniform(0.0001, 0.0005, 1250)`)로 측정했다:

| 신뢰수준 | 엔진 | 백엔드 | 차이 | 50억 원 기준 |
|---|---|---|---|---|
| 0.90 | −0.0001420993 | 0.0 | −0.0001420993 | −710,496원 |
| 0.95 | −0.0001201170 | 0.0 | −0.0001201170 | −600,585원 |
| 0.99 | −0.0001039916 | 0.0 | −0.0001039916 | −519,958원 |

즉 클램프는 **현재 데이터에서는 0원 차이, 손실이 없는 구간에서만 최대 71만 원 차이**를 만든다.
신뢰수준 기본값 차이(311만 원)가 클램프보다 큰 요인이다.

### ④ 시간 스케일링 규약이 다르다

| | 산출 | 값 |
|---|---|---|
| 백엔드 | `daily_loss × √252` (연환산) | 0.0854180000 |
| 엔진 | `1일 VaR × √10` (10일) | 0.0189833116 |

두 숫자는 **비교 대상이 아니다.** 백엔드는 연환산 1종, 엔진은 `horizons: [1, 10]`
(`config/config.yaml`)의 1일·10일 2종을 낸다. 화면에 나란히 놓으려면 기간을 먼저 통일해야 한다.

### ⑤ 분위수 자체는 동일 — 차이의 원인을 분리

| 신뢰수준 | `np.quantile` | `pd.Series.quantile` | 동일? |
|---|---|---|---|
| 0.95 | −0.005380836833 | −0.005380836833 | **예** |
| 0.99 | −0.006003050209 | −0.006003050209 | **예** |

numpy와 pandas의 분위수는 비트 단위로 같다. **따라서 두 함수의 차이는 수치 라이브러리나
보간 방식 때문이 아니라, 전적으로 코드에 적힌 네 가지(기본 신뢰수준·클램프·반올림·라벨)
때문이다.**

### ⑥ 어느 쪽이 왜 다른가 — 코드 인용

```python
# engine/engine/metrics.py:16-25
def historical_var(returns: np.ndarray, confidence: float = 0.99) -> float:
    ...
    q = np.quantile(np.asarray(returns, dtype=float), 1.0 - confidence)
    return float(-q)                       # 클램프 없음. 음수는 의미가 있어 그대로 둔다
```

```python
# backend/app/portfolio/metrics.py:298-321
def calculate_historical_var(
    portfolio_daily_returns: pd.Series,
    confidence_level: float = 0.95,        # 기본값이 다르다
) -> Dict[str, Any]:
    ...
    daily_quantile = float(portfolio_daily_returns.quantile(q))
    daily_loss = max(-daily_quantile, 0.0)  # 음수를 0으로 고정
    annualized_loss = daily_loss * np.sqrt(TRADING_DAYS)
    return {
        ...
        "daily_loss": safe_round(daily_loss, 6),        # 6자리 반올림
        "method": "historical_5_percentile",            # 신뢰수준과 무관한 고정 라벨
    }
```

엔진 쪽 주석(`metrics.py:19-22`)은 음수 VaR을 **버그가 아니라 "해당 신뢰수준에서 손실이
발생하지 않는다"는 정보**로 규정한다. 백엔드는 화면 표시용으로 손실을 0 아래로 내리지
않는다. 어느 쪽도 계산이 틀린 것이 아니라 **규약이 다르다.**

### 회의에서 5분 안에 정할 것 두 가지

1. **신뢰수준을 하나로 정한다.** 0.95와 0.99 중 무엇이든, 정하면 두 구현의 차이는
   50억 기준 1,000원 미만(반올림)으로 줄어든다. 정하지 않으면 311만 원이 벌어진다.
2. **기간 규약을 정한다.** 연환산 1종인지, 1일·10일 2종인지. 이건 신뢰수준을 맞춰도
   자동으로 해결되지 않는다.

클램프와 라벨은 현재 데이터에서 화면 숫자를 바꾸지 않으므로 뒤로 미뤄도 된다.

---

## Part 5. 통합 순서 제안

의존 관계상 앞의 것이 풀리지 않으면 뒤의 것을 시작할 수 없다.

| 순서 | 할 일 | 막고 있는 것 |
|---|---|---|
| 1 | **자산군 매핑 확정** (Part 3-①) | 포트폴리오를 엔진에 넘기는 모든 경로 |
| 2 | **VaR 신뢰수준·기간 규약 확정** (Part 4) | 화면에 VaR을 띄우는 작업 |
| 3 | **IPS `Return` 단위와 필드 수 확정** (Part 3-②③) | 상담 IPS를 엔진에 넘기는 경로 |
| 4 | **엔진 호출 경로 신설** | 위 셋이 정해진 뒤에야 인터페이스를 그릴 수 있다 |
| 5 | 표시 작업 — 난이도 "하"부터 (`explanations`, `export_allowed`, 해시 표시) | 4번 |
| 6 | 새 UI 작업 (`conflicts`, `approval`, `judge`) | 4번 |

스트레스 시나리오(Part 3-④)는 1~4와 독립적으로 논의할 수 있으나,
두 정의 중 하나를 고르는 것이 아니라 **둘 다 유지하고 화면에서 구분해 표기할지**를
먼저 정해야 한다. 계산 방식이 달라 한쪽으로 흡수되지 않는다.

---

## 재현 방법

Part 4의 수치는 아래로 재현된다. 레포 코드는 건드리지 않는다.

```bash
# 의존성: numpy, pandas, pyarrow, pydantic, fastapi, pyyaml, scipy
python - <<'PY'
import sys; sys.path.insert(0, "backend"); sys.path.insert(0, ".")
import pandas as pd
from app.portfolio.metrics import calculate_historical_var
from engine.engine.metrics import historical_var, portfolio_returns
from engine.nodes.load_inputs import DUMMY_PORTFOLIO

df = pd.read_parquet("data/returns_dummy.parquet")   # 없으면:
                                                     # from engine.engine.returns import load_returns
                                                     # df = load_returns()
r = portfolio_returns(df, DUMMY_PORTFOLIO); s = pd.Series(r)
print("engine  0.99:", historical_var(r))
print("backend 0.95:", calculate_historical_var(s)["daily_loss"])
PY
```
