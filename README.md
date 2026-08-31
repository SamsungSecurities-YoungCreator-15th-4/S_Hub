# S_Hub

> 삼성증권 영크리에이터 15기 4조 — 두 산출물을 한 레포에 합친 통합 저장소.

PB가 VVIP 고객 상담에 쓰는 **대시보드**와, 그 화면이 보여 줄 숫자의 **근거·감사 추적을 생산하는 엔진**을 함께 둔다.

| | **S.upervisor** | **S.ymphony** |
| --- | --- | --- |
| 하는 일 | 상담 녹취 → IPS 구조화 → 세후 포트폴리오 제안 대시보드 | LangGraph 기반 재현가능·설명가능 리스크 리포트 엔진 |
| 코드 | `frontend/` · `backend/` · `supabase/` | `engine/` · `console/` · `scripts/` · `config/` |
| 상세 문서 | [docs/dashboard/README.md](docs/dashboard/README.md) | [docs/engine/README.md](docs/engine/README.md) |
| 배포 | Vercel (프론트) · Render (백엔드) | Streamlit Cloud (엔진 콘솔) |

두 시스템은 **IPS 7필드(RRTTLLU — Return · Risk · Time · Tax · Liquidity · Legal · Unique)** 라는
같은 데이터 계약을 공유한다. 이것이 연결의 접합면이다.

## 레포 구조

```
S_Hub/
├── frontend/        # [S.upervisor] Next.js 대시보드 UI
├── backend/         # [S.upervisor] FastAPI + requirements.txt (대시보드 런타임)
├── supabase/        # [S.upervisor] DB 마이그레이션·시드
│
├── engine/          # [S.ymphony] 리스크 리포트 엔진 (그래프·노드·결정론 계층)
├── console/         # [S.ymphony] Streamlit 엔진 콘솔
├── scripts/         # [S.ymphony] CLI 진입점 (run_graph.py)
├── tests/           # [S.ymphony] pytest
├── config/          # [S.ymphony] config.yaml · ips_policy.yaml · hard_stop_policy.yaml
├── corpus/          # [S.ymphony] RAG 근거 문서 21건 (원문 PDF는 로컬 전용)
├── goldenset/       # [S.ymphony] 사례집·라벨·평가 도구
├── data/            # [S.ymphony] 시장 데이터 캐시
├── requirements.txt # [S.ymphony] 엔진 런타임
│
├── docs/
│   ├── dashboard/   # S.upervisor 상세 문서
│   └── engine/      # S.ymphony 계약·계획 문서
└── .github/         # CI 2종 (대시보드·엔진) · 커뮤니티 문서 · Dependabot
```

> **`config/` · `corpus/` · `data/` · `goldenset/` 는 레포 루트에 있어야 한다.**
> 엔진이 이 경로들을 루트 기준으로 찾는다. 하위 디렉터리로 옮기면 이름이 대시보드 쪽과
> 겹쳐 **에러 없이 잘못된 파일을 읽는다.**

## 빠른 시작

```bash
# 엔진 — 정상 확정 경로
pip install -r requirements.txt
python scripts/run_graph.py --auto-approve --offline
pytest tests

# 대시보드 백엔드
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload

# 대시보드 프론트 (pnpm 통일, npm/yarn 혼용 금지)
cd frontend && pnpm install && pnpm dev
```

**두 `requirements.txt` 를 합치지 않는다.** pandas·numpy·openai 핀이 서로 다르고,
합치면 해소 불가능한 의존성 충돌이 난다.

## 작업 규칙

- 에이전트·사람 공통 규칙: [AGENTS.md](AGENTS.md)
- 협업·브랜치·PR 규약: [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)
- 보안·비밀 관리: [SECURITY.md](SECURITY.md)

`main` 단일 브랜치로 운영하며, 직접 push 없이 PR로만 반영한다.

## 라이선스

[MIT](LICENSE)
