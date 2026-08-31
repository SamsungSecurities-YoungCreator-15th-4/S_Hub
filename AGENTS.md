# AGENTS.md — S_Hub (S.upervisor × S.ymphony)

이 문서는 Codex·Claude Code 등 AI 코딩 에이전트가 세션 시작 시 읽는 공용 컨텍스트다.
이 레포에서 일하는 모든 에이전트는 새 작업을 시작하기 전 이 문서를 먼저 읽고,
아래 불변 규칙을 위반하지 않는다.

## 프로젝트 한 줄 소개

삼성증권 영크리에이터 15기 4조 — 두 산출물을 한 레포에 합친 것이다.

- **S.upervisor** (`frontend/` + `backend/`) — PB가 VVIP 고객 상담 시 사용하는 AI 자산관리 대시보드. **화면·UX의 기준이자 진입점**이다.
- **S.ymphony** (`engine/` + `console/` + `scripts/`) — LangGraph 기반 재현가능·설명가능 리스크 리포트 엔진. 대시보드가 보여 줄 숫자의 **근거와 감사 추적을 생산**한다.

## 불변 규칙 (위반 금지)

1. **재현성** — 노드는 결정론적으로 동작한다. 무작위성이 있으면 시드를 고정하고,
   같은 입력이면 같은 결과가 나와야 한다. 계산 결과에는 computation_hash를 남긴다.
2. **설명가능(화이트박스)** — 모든 수치·주장에는 근거(citations/evidence)를 첨부한다.
   최종 판단은 사람이 한다(HITL, `approval_gate` 직전 인터럽트).
3. **계층 경계** — `engine/engine/`(결정론 계층) 안에서는 langchain·openai import를 금지한다.
   수치 계산은 순수 파이썬/numpy로만 한다. LLM 호출은 `engine/llm/` + 노드 계층에서만 한다.
4. **데이터 계약** — `engine/state.py`(`RiskState`/`IPSProfile`)는 팀 합의 없이 수정하지 않는다.
   변경이 필요하면 먼저 팀에 공유한다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 프론트엔드 | Next.js (pnpm), TypeScript, TailwindCSS, shadcn/ui, recharts, Zustand |
| 백엔드 | FastAPI (Python), yfinance |
| DB·인증 | Supabase (PostgreSQL + pgvector) — 접근 방식 A: supabase-py(RPC 전용) / B: psycopg3(직접 SQL) |
| 오케스트레이션 | LangGraph (StateGraph, MemorySaver, HITL 인터럽트) |
| LLM | Azure OpenAI (LangChain, temperature=0) — IPS 추출·RAG 인용·Judge |
| 결정론 엔진 | numpy/scipy — historical VaR/CVaR, 스트레스 테스트 |
| RAG 검색 | Chroma(langchain-chroma) + AzureOpenAIEmbeddings — 코퍼스 21건 인용·검증 |
| 관측성 | LangSmith 트레이싱 |
| 엔진 콘솔 | Streamlit |
| 배포 | 프론트엔드 Vercel · 백엔드 Render · 엔진 콘솔 Streamlit Cloud |
| 협업 | GitHub, Notion, Slack |

## 레포 구조

```
S_Hub/
├── frontend/          # [S.upervisor] Next.js 프론트엔드 (PB 상담 대시보드 UI)
├── backend/           # [S.upervisor] FastAPI 백엔드
│   ├── app/
│   │   ├── routers/   # API 엔드포인트 (consultations, rag 등)
│   │   ├── stt/       # STT·화자 매핑·RRTTLLU 추출
│   │   ├── rag/       # RAG 검색부 (Azure 임베딩 + pgvector)
│   │   ├── services/  # STT 파이프라인·IPS 추출 등 비즈니스 로직
│   │   ├── schemas/   # Pydantic 모델
│   │   ├── core/      # 설정(config)
│   │   └── db/        # Supabase 클라이언트
│   └── requirements.txt   # 대시보드 런타임 (엔진과 분리 고정)
├── supabase/          # [S.upervisor] DB 마이그레이션·시드 (PostgreSQL + pgvector)
├── engine/            # [S.ymphony] 리스크 리포트 엔진
│   ├── state.py       # RiskState/IPSProfile — 팀 데이터 계약(SSOT), 임의 수정 금지
│   ├── graph.py       # StateGraph 조립 (9노드 + 조건부 분기 2개)
│   ├── hard_stop_policy.py      # Hard Stop 정책 버전 로더·검증(SSOT 접근점)
│   ├── deployment_validation.py # 실제 배포 계약 검증(--validate-deployment)
│   ├── nodes/         # 그래프 노드 (순수 함수, 바꾼 키만 반환)
│   ├── engine/        # 결정론 계층 — langchain/llm import 금지
│   ├── llm/           # AzureChatOpenAI 팩토리·프롬프트 체인
│   ├── rag/           # 검색·인용 검증·인덱스 배포
│   ├── judge/         # judge 6축 루브릭 (런타임 판정)
│   ├── evaluation/    # judge 캘리브레이션 (사람 라벨 대조 — 판정이 아니라 판정의 평가)
│   ├── evidence/      # R4 증거 번들 스키마·state 덤프
│   ├── observability/ # LangSmith 트레이싱
│   └── utils/         # 해시 등 공용 유틸
├── console/           # [S.ymphony] Streamlit 엔진 콘솔 (구 ui/)
├── config/            # [S.ymphony] config.yaml · ips_policy.yaml · hard_stop_policy.yaml · rag_sources.json
├── corpus/            # [S.ymphony] RAG 근거 문서 (21건, 원문 PDF는 gitignore·로컬 전용 / manifest.md 참조)
├── data/              # [S.ymphony] 시장 데이터 (gitignore 대상 산출물 포함)
├── goldenset/         # [S.ymphony] R1 사례집·라벨·평가 도구 (dist/는 생성물이라 gitignore)
├── scripts/           # [S.ymphony] CLI 진입점 (run_graph.py)
├── tests/             # [S.ymphony] pytest
├── requirements.txt   # [S.ymphony] 엔진 런타임 (대시보드와 분리 고정)
├── docs/
│   └── engine/        # [S.ymphony] 계약·계획 문서 (mermaid.mmd 포함)
└── .github/           # PR 템플릿·CI(대시보드/엔진 2종)·커뮤니티 문서
```

디렉터리를 새로 만들기 전에 위 목록에 이미 맞는 자리가 있는지 먼저 본다.
파일 한두 개를 위해 최상위 디렉터리를 만들지 않는다.

### 통합 레포에서 특히 조심할 것

- **`backend/app/`(대시보드)과 `engine/`(엔진)은 다른 코드베이스다.** 둘 다 과거에
  `app.*`로 import 됐기 때문에, 일괄 치환·경로 리팩터링은 반드시 한쪽만 대상으로 한다.
- **엔진의 경로 상수는 레포 루트 기준이다** (`config/`, `data/`, `goldenset/`, `corpus/`).
  엔진을 하위 디렉터리로 옮기면 `data/` 같은 이름이 대시보드 쪽 디렉터리와 겹쳐
  **에러 없이 잘못된 파일을 읽는다.** 옮기지 않는다.
- **런타임 의존성은 둘로 나뉘어 있다.** 루트 `requirements.txt`(엔진)와
  `backend/requirements.txt`(대시보드)를 합치지 않는다. 두 곳의 pandas·numpy·openai
  핀이 서로 다르고, 합치면 해소 불가능한 충돌이 난다.

## 그래프 노드 흐름

`engine/graph.py`의 실제 조립 기준. 노드 9개, 조건부 분기 2개, HITL 인터럽트 1개.

아래 ①②③은 분기 번호가 아니라 **제어 지점 번호**다 — ① 충돌 재추출 분기 ·
② HITL 인터럽트 · ③ judge 재작성 분기. 조건부 분기는 ①·③ 둘이고 ②는 인터럽트라
번호가 ①·③으로 건너뛴다. `scripts/run_graph.py`의 실행 요약 출력과 같은 표기다.

```
START
  → load_inputs
  → extract_ips  ◄──────────────┐  (분기① 충돌 재추출 루프)
  → conflict_check ──────────────┘
        │  route_after_conflict_check:
        │   conflicts 있고 conflict_retries < MAX_CONFLICT_RETRIES(=1) → extract_ips 회귀
        │   그 외 → approval_gate
        ▼
  → approval_gate        ★ HITL: interrupt_before=["approval_gate"] (사람 승인 대기)
  → var_engine
  → rag_cite  ◄──────────────────┐  (분기③ judge 재작성 루프)
  → judge_eval ───────────────────┘
        │  route_after_judge:
        │   judge.passed → assemble_report → END
        │   미통과이고 judge_retries < judge_max_retries → rag_cite 재작성
        │   미통과이고 judge_retries >= judge_max_retries → manual_review_gate → END
```

- 컴파일: `g.compile(checkpointer=MemorySaver(), interrupt_before=["approval_gate"])`
- 노드는 순수 함수로, 바꾼 키만 반환한다(레포 구조의 `nodes/` 규약과 동일).
- 재시도 상한 SSOT는 `config/config.yaml`의 `judge_max_retries`이며
  `resolve_max_judge_retries`를 통해서만 읽는다.
  **폴백 기본값은 없다** — 설정이 없거나 1 이상의 정수가 아니면 코드 기본값으로
  대체하지 않고 `ValueError`로 실행을 거부한다. 그래프를 직접 호출하는 스크립트도
  `run_config`에 이 값을 반드시 넣어야 한다.
  judge가 규칙 기반이라 실패 사유가 구조적이므로 재시도를 늘려도 해결 확률이
  크게 오르지는 않으며, 상한을 소진하면 수동검토로 전환한다.
  문서에 적힌 횟수가 설정과 갈라지지 않도록 `tests/test_docs_config_consistency.py`가
  대조한다.
- **통과 없이 확정·다운로드하지 않는다** — 재시도 소진 실패는
  `manual_review_gate`에서 종료한다. `report.status=pending_manual_review`,
  `report.finalized=False`, `governance.export_allowed=False`이며 차단 사유와
  결정 지문을 기록한다. 상세 계약은 `docs/engine/hard_stop_contract.md`를 따른다.

## RiskState 데이터 계약 키

`engine/state.py`의 정의를 철자·타입 그대로 옮긴 것. **이 표는 SSOT가 아니라 요약 참조이며,
실제 계약은 항상 `engine/state.py`가 우선한다.** 키를 추가·변경하려면 state.py를 먼저 고치고 팀에 공유한다.

### `RiskState` (`TypedDict, total=False`)

| 키 | 타입 | 생산/소비 노드 (graph.py 근거) |
| --- | --- | --- |
| `run_config` | `dict` | TBD (노드 구현 범위) |
| `demo_options` | `dict` | UI/CLI의 세션별 충돌·judge·오프라인 시연 옵션 |
| `trace_id` | `str` | TBD |
| `raw_input` | `str` | TBD |
| `portfolio` | `list` | TBD |
| `liquidity_required_krw` | `float \| None` | `extract_ips`가 자연어의 명시적 유동성 필요 금액을 원 단위로 저장 |
| `market_data_ref` | `dict` | TBD |
| `ips` | `dict` | TBD |
| `ips_extraction_meta` | `dict` | `extract_ips`의 모델·seed·프롬프트·입출력 해시 |
| `conflicts` | `list` | `route_after_conflict_check`가 읽어 분기① 판단 |
| `conflict_policy` | `dict` | `conflict_check`가 정책 버전·해시·근거 ID 저장 |
| `conflict_retries` | `int` | `route_after_conflict_check`가 읽어 분기① 판단 (MAX=1) |
| `approval` | `ApprovalRecord` | `load_inputs` draft → UI/CLI reviewed → `approval_gate` locked |
| `metrics` | `dict` | TBD |
| `explanations` | `list` | TBD |
| `citations` | `list` | TBD |
| `citation_rejections` | `list` | `rag_cite` 생산 → R4 증거 번들 소비 (시도별 **누적**, [인용 검증 계약](docs/engine/hard_stop_contract.md#5-인용-검증-계약) 참조) |
| `judge` | `dict` | `route_after_judge`가 `judge.passed`를 읽어 분기③ 판단 |
| `judge_retries` | `int` | `route_after_judge`가 읽어 분기③ 판단 (상한 SSOT=`config/config.yaml: judge_max_retries`) |
| `judge_feedback` | `str` | TBD |
| `report` | `dict` | TBD |

> "생산/소비 노드"는 `engine/graph.py`로 증명되는 것만 표기했다. TBD는 각 노드 구현
> (`engine/nodes/*.py`)에서 정해지며, 이 문서에서 추정하지 않는다. 정확한 소유 노드는 해당 노드 코드를 확인한다.

### `IPSProfile` (pydantic `BaseModel`)

고객 상담용 공개 IPS JSON은 `Name`, `Age`, `Job`, `Goal`, `Asset`, `Return`, `Risk`,
`Time`, `Tax`, `Liquidity`, `Legal`, `Unique` 12개 필드로 구성한다. `Age="50"`,
`Job="자영업자"`, `Goal="시장리스크 진단·대응안을 엔진으로 산출·검증"`, `Asset=50.0`(억 원),
`Risk="균형형"`은 과제 시나리오 고정값이다. `Unique`는 항상
`"고금리·강달러 충격"`으로 시작한다.

### 승인·충돌 정책

- `conflict_check`는 `config/ips_policy.yaml`의 버전된 내부 기준과 공식 근거를 사용한다.
- `severity=block`은 예외 승인할 수 없고, `severity=review`만 사유가 있는 PB 예외 승인을 허용한다.
- 승인은 `draft → reviewed → locked` 순서이며, locked는 리스크 계산 승인이지 거래 승인이 아니다.
- 상세 기준과 근거는 [`docs/engine/ips_conflict_policy.md`](docs/engine/ips_conflict_policy.md)를 따른다.

## 코퍼스 규격

RAG 근거 문서는 `corpus/`에 카테고리별로 둔다. 상세 목록은 [`corpus/manifest.md`](corpus/manifest.md) 참조.

- 카테고리 4종: `house_view`(삼성증권 하우스뷰), `macro`(거시·통화정책),
  `tax`(세무), `methodology`(리스크 계량·스트레스 테스트 방법론).
- 총 **21건** (house_view 6 · macro 7 · tax 6 · methodology 2).
- **원문 PDF는 저작권상 로컬 전용**이며 git에 포함하지 않는다
  (`.gitignore: /corpus/**/*.pdf`, 단 `!/corpus/**/.gitkeep`로 폴더 구조는 유지).
- git이 추적하는 것은 **폴더 구조(`.gitkeep`)와 `corpus/manifest.md`뿐**이다.
  manifest는 원문이 아닌 문서 목록이라 커밋 가능하다.

## 작업 규칙

- **디렉터리 경계**: 변경은 한 영역 안에서 끝내는 것을 우선한다. 영역은 셋이다 —
  `frontend/` · `backend/` · 엔진(`engine/`·`console/`·`scripts/`·`tests/`·`config/`).
  두 영역을 동시에 건드리는 변경은 PR을 분리하는 것을 먼저 고려하고,
  나눌 수 없으면 PR 본문에 이유를 적는다.
- **계층 경계**: `engine/engine/`(결정론 계층)에는 langchain/openai 등 LLM 관련 import를 절대 추가하지 않는다. LLM 호출은 `engine/llm/` + 노드 계층에서만 한다.
- **데이터 계약**: `engine/state.py`의 `RiskState`/`IPSProfile`은 팀 합의 없이 수정하지 않는다.
- **재현성**: 노드는 결정론적으로 동작해야 하며(랜덤 시드 고정), 계산 결과에는 computation_hash를 남긴다.
- **커밋 메시지**: 한국어로, `타입: 설명` 형식. 타입은 `feat`, `fix`, `docs`, `chore`, `refactor`, `test` 중 하나.
  - 예) `feat: 스트레스 시나리오 금리 충격 추가`
  - `Co-Authored-By`, 모델명, 세션 링크 등 AI 도구 attribution·trailer를 커밋과 PR에 넣지 않는다.
    CI(`Commit metadata policy`)가 이를 검사하며 위반 시 실패한다.
- **빌드/실행 확인**: 푸시 전 반드시 건드린 영역을 로컬에서 확인한다.

  프론트엔드는 `pnpm build`, 백엔드는 최소 `uvicorn app.main:app`이 떠야 한다.
  엔진은 아래 정상·차단 경로와 `pytest`, `ruff check engine tests scripts console`을 모두 통과한다.

  ```bash
  # 정상 확정 경로: assemble_report 종료
  python scripts/run_graph.py --auto-approve

  # Judge 재시도 소진 경로: manual_review_gate 종료·다운로드 차단
  python scripts/run_graph.py --auto-approve --force-judge-fail 3
  ```
- **덮어쓰기 알림**: 기존 파일을 지우거나 덮어쓰기 전 사용자에게 먼저 알리고 동의를 받는다.
- **비밀 정보 금지**: `.env` 파일과 모든 비밀키는 절대 커밋하지 않는다. `.env.example`만 추적 대상이다.

## 프론트엔드 작업 시 주의 (Next.js 16.x)

이 프로젝트가 사용하는 Next.js는 학습 데이터 시점 이후의 버전(16.x)이라 API·관례·파일 구조가 다를 수 있다. 코드를 쓰기 전 `frontend/node_modules/next/dist/docs/`에서 관련 가이드를 먼저 읽고, 사용 중단(deprecation) 경고는 그때그때 반영한다.

## 금융 도메인 주의사항

이 프로젝트는 PB가 실제 VVIP 상담에 사용하는 **금융 의사결정 보조 도구**다. 그래서 다음을 반드시 지킨다.

- **세금·법률 계산 로직은 함부로 추정하지 않는다.** 근거(법령·국세청 안내·논문·교과서 등 명확한 출처)가 있는 수식만 구현하고, 코드 주석으로 출처를 남긴다.
- **정량 지표(샤프지수·MDD·변동성 등)는 가짜/더미 데이터가 아니라 실제 수식과 실제 시장 데이터로 계산한다.** "일단 동작하게" 임의 값을 박아두지 않는다. 데이터가 없으면 함수 자체를 만들지 말고, 데이터 소스부터 연결한 뒤 작성한다.
- **숫자가 화면에 표시되면 그 숫자의 출처와 계산식이 코드에서 추적 가능해야 한다.**
- **AI는 미드필더다.** IPS 추출·설명·Judge는 AI가 하지만, 비중·세율·VaR 결정은 AI가 하지 않는다.

## 보안

- API 키, 팀 계정 정보, 비밀번호를 코드·커밋·이슈·PR 본문 어디에도 포함하지 않는다.
- 외부 API 호출 시 키는 환경변수로만 읽는다. 하드코딩 금지.
- 사용자(고객) 정보를 다루는 코드는 로깅 시 PII 마스킹을 고려한다.

## 브랜치 전략

- 통합 레포는 `main` 단일 브랜치로 운영한다. `feature/*` · `fix/*` · `chore/*` 등
  목적별 브랜치에서 작업하고 **PR로만** `main`에 넣는다.
  `main` 직접 push 금지 — ruleset이 승인 1건을 요구한다.
- 원본 두 레포(`VVIP_PB_Advisor`, `Orchestration`)의 GitFlow(`develop` 경유)는
  **여기에 적용하지 않는다.** S_Hub에는 `develop`이 없다.
- 상세 규약은 [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md)를 따른다.
