# R2 judge 캘리브레이션 — v1~v6 추적 기록

R1 골든셋 20건 기준, judge 6축 루브릭의 버전별 공식(official·LangSmith 검증) 측정 결과 요약본.
원본(사람 라벨 근거 `human_rationale` 등 케이스별 상세 포함)은 R2 담당자만 보관하며, 이 폴더에는
`scripts/make_evidence_bundle.py --calibration`으로 민감 필드를 제거한 집계 수치만 커밋한다
(각 파일의 `mismatch_detail_excluded` 필드 참조).

**표기 안내**: 각 파일 내부의 `v1`/`v2` 키는 "비교의 첫 번째/두 번째 자리"를 뜻하는 범용 슬롯 이름이며,
실제 어느 라운드인지는 그 안의 `prompt_version` 값과 `comparison.before_code_sha`/`after_code_sha`
(git merge commit)로 확정된다. 아래 표의 code_sha는 전부 `develop` 브랜치의 실제 merge commit과
대조해 확인했다.

## 요약

| 파일 | 라운드 | mode | code_sha (before→after) | match_rate | 비고 |
|---|---|---|---|---|---|
| `v1_report_summary.json` | v1 (baseline) | official | — | 75.0% (15/20) | 최초 측정 |
| `v2_report_summary.json` | v2 | official | — | 55.0% (11/20) | 오탐 급증 (fp 4→8) |
| `v2_v3_compare_summary.json` | v2→v3 | official | `5d5dfeb`→`ec27d22` (#175→#177) | 55.0%→70.0% | hallucination·false_precision 경계 예외 보강 |
| `v3_v4_compare_summary.json` | v3→v4 | official_code_change | `ec27d22`→`e3b0122` (#177→#178) | 70.0%→70.0% | disclaimer·prohibited_expression 코드 수정(프롬프트 불변). 축별 recall은 개선(면책 2/3→3/3, 금지표현 1/2→2/2)했으나 같은 케이스의 다른 축이 여전히 틀려 전체 confusion matrix는 불변 |
| `v4_v5_compare_summary.json` | v4→v5 | official | `e3b0122`→`bed043e` (#178→#179) | 70.0%→75.0% | false_precision confidence/ci_level 오탐 완화 |
| `v5_v6_compare_summary.json` | v5→v6 | official | `bed043e`→`fbc85f4` (#179→#180) | 75.0%→80.0% | hallucination B1("일반 시장 원리" 예외) 적용 범위 축소 |

## 알려진 한계

- v1→v2는 정식 비교 파일이 없다(단독 측정 두 건만 존재). v2가 왜 크게 나빠졌는지는 이후 라운드(v3)의
  경계 규칙 보강으로 대응했다.
- **입력 어댑터가 계획 대비 좁게 구현됐다.** `docs/symphony_proof_plan.md`의 R2 로더 변환 규칙(§1
  고객 요약 → `run_config`, `portfolio`)은 `portfolio`를 포함하나, 실제 로더는 이를 담지 않는다.
  이후 작성된 `goldenset/case-format.md`가 leakage 경계를 코드로 강제하며 허용 키를
  `metrics`·`explanations`·`citations` 셋으로 좁혔고(`tests/test_goldenset_integrity.py` §8이
  강제), 구현이 그 계약을 따랐기 때문이다. 두 문서의 차이는 구현 시점에 확인되지 않았다. 또한
  `case-format.md` §4는 `metrics.horizons`를 지표별 필드(`var_pct`·`var_krw`·`cvar_pct`·
  `cvar_krw`)로 분리해 담도록 제시하나, 구현은 보유기간별 `values` 배열로 단순화했다(단,
  `confidence_interval`은 스펙상으로도 옵셔널이다). 당시 judge의 `numeric_consistency`가
  membership만 검사해 동작상 문제가 없었고 v1~v6 측정도 이 구조에서 일관되게 수행됐으나, 숫자 간
  관계를 검사하려면 지표 라벨 구분이 필요해 이번 측정 범위에서는 관계 검사(F1·F3·F4·F6·F7)를 수행할
  수 없다. `case-format.md`(승민 소유의 R1 작업 지시서)는 이 기록과 별개로 두며, 수정 여부는 문서
  소유자가 판단한다.
- **F1(포트폴리오 비중 합계) 관계 검사는 구현했으나(PR #181) 두 경로 모두에서 관측되지 않는다.**
  calibration 경로는 위 입력 어댑터 한계(portfolio 미전달) 때문이고, **실제 그래프 실행 경로도
  마찬가지다** — `load_inputs`가 입력 단계에서 자산군 비중 합=100%를 이미 `ValueError`로 강제하고,
  현재 설명문 생성 로직(`rag_cite`)도 "비중" 문맥의 수치를 만들지 않아 F1이 잡을 결함 자체가 두
  경로 모두에서 발생하지 않는다(PR #181 리뷰, 중현 실측). 라이브 데모로 "작동을 증명"할 수 있는
  항목이 아니며, 코드·단위 테스트 수준의 근거로만 존재한다. 라벨 근거(F1으로 확인된 미탐 1건)가
  있어 구현했으나, 시스템 구조상 방어적으로 가려진 상태다.
- F3·F4·F6·F7(수치정합의 나머지 관계 검사)은 구현하지 않았다 — 20건 중 이 유형으로 확인된 사례가
  없어, 확인된 결함만 고친다는 원칙상 구현을 보류했다.
- 이 폴더의 모든 측정은 **judge 1회 판정**(`judge_attempt == 1`) 기준이다. 재작성 루프(judge_retries
  경유) 이후 판정이 달라지는지는 이 측정 범위 밖이다.
