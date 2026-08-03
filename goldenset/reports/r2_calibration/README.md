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
- numeric_consistency 축의 관계 검사(F1: 포트폴리오 비중 합계)는 v6 이후 구현했으나(PR #181),
  R2 calibration 로더가 `portfolio`·`confidence_interval`을 전달하지 않아 이 폴더의 측정 범위에는
  반영되지 않는다. 실제 그래프 실행에서는 정상 동작하며, 라이브 데모로 증명한다.
