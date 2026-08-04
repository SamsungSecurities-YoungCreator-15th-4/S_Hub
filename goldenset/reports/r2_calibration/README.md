# R2 judge 캘리브레이션 — v1~v6 추적 기록

R1 골든셋 20건 기준, judge 6축 루브릭의 버전별 official 계열(official·official_code_change,
전부 LangSmith 검증) 측정 결과 요약본. 원본(사람 라벨 근거 `human_rationale` 등 케이스별 상세
포함)은 **R2 분석 담당자만** 보관한다 — R2 실행·기록 담당은 사람 라벨에 접근하지 않는 것이 이
프로젝트의 leakage 경계이며(`goldenset/case-format.md` §0, `tests/test_goldenset_integrity.py`
§8), 무라벨 입력본(`goldenset/judge_inputs/`)만 사용한다. 이 폴더에는
`scripts/make_evidence_bundle.py --calibration`으로 민감 필드를 제거한 집계 수치만 커밋한다
(각 파일의 `mismatch_detail_excluded` 필드 참조).

**표기 안내**: 각 파일 내부의 `v1`/`v2` 키는 "비교의 첫 번째/두 번째 자리"를 뜻하는 범용 슬롯 이름이며,
실제 어느 라운드인지는 그 안의 `prompt_version` 값과 `comparison.before_code_sha`/`after_code_sha`
(git merge commit)로 확정된다. 아래 표의 code_sha는 전부 `develop` 브랜치의 실제 merge commit과
대조해 확인했다.

## 요약

| 파일 | 라운드 | mode | code_sha (before→after) | match_rate | 비고 |
|---|---|---|---|---|---|
| `v1_report_summary.json` | v1 (baseline, 단독) | official | `b035600` (단독) | 75.0% (15/20) | 최초 측정 |
| `v1_v2_compare_summary.json` | v1→v2 | official | `b035600`→`5d5dfeb` (#169→#175) | 75.0%→55.0% | 오탐 급증 (fp 4→8) |
| `v2_report_summary.json` | v2 (단독) | official | `5d5dfeb` (단독) | 55.0% (11/20) | v1_v2_compare와 동일 결과, 단독 참조용 |
| `v2_v3_compare_summary.json` | v2→v3 | official | `5d5dfeb`→`ec27d22` (#175→#177) | 55.0%→70.0% | hallucination·false_precision 경계 예외 보강 |
| `v3_v4_compare_summary.json` | v3→v4 | official_code_change | `ec27d22`→`e3b0122` (#177→#178) | 70.0%→70.0% | disclaimer·prohibited_expression 코드 수정(프롬프트 불변). 축별 recall은 개선(면책 2/3→3/3, 금지표현 1/2→2/2)했으나 같은 케이스의 다른 축이 여전히 틀려 전체 confusion matrix는 불변 |
| `v4_v5_compare_summary.json` | v4→v5 | official | `e3b0122`→`bed043e` (#178→#179) | 70.0%→75.0% | false_precision confidence/ci_level 오탐 완화 |
| `v5_v6_compare_summary.json` | v5→v6 | official | `bed043e`→`fbc85f4` (#179→#180) | 75.0%→80.0% | hallucination B1("일반 시장 원리" 예외) 적용 범위 축소 |
| `v6_report_summary.json` | v6 (최종, 단독) | official | `fbc85f4` (단독) | **80.0% (16/20)** | 최종 라운드 단독 요약 — 이 파일이 v6 공식 최종 성능의 단일 참조점 |

## 계획 대비 변경

- **프롬프트 버전 관리 방식.** `docs/symphony_proof_plan.md`의 R2 섹션은 judge 프롬프트를
  `app/judge/prompts/v1.py`·`v2.py`로 분리하고 `--prompt-version`으로 런타임 선택하는 방식을
  제시했다. 실제로는 이 방식을 채택하지 않고, **프롬프트를 `app/judge/rubric.py`에 유지한 채 라운드마다
  develop에 병합하고 각 실행을 그 시점 커밋에서 수행**했다. `--prompt-version`은 런타임 선택자가
  아니라 실행 라벨이며, 어느 프롬프트로 측정했는지는 결과의 `code_sha`(위 요약 표의 merge commit)가
  확정한다. 런타임 파일 선택은 실행 시점에 달라질 수 있지만 커밋은 사후에 바꿀 수 없어 재현 근거가 더
  강하고, 프롬프트 불변·코드만 변경한 라운드(v3→v4)를 `official_code_change` 등급으로 구분해 기록할
  수 있는 것도 이 방식 덕이다.

## 알려진 한계

- v2가 왜 크게 나빠졌는지(75.0%→55.0%, 오탐 급증)는 `v1_v2_compare_summary.json`에 정식 비교로
  남아 있고, 이후 라운드(v3)의 경계 규칙 보강으로 대응했다.
- **입력 어댑터가 계획 대비 좁게 구현됐다.** `docs/symphony_proof_plan.md`의 R2 로더 변환 규칙(§1
  고객 요약 → `run_config`, `portfolio`)은 `portfolio`를 포함하나, 실제 로더는 이를 담지 않는다.
  이후 작성된 `goldenset/case-format.md`가 leakage 경계를 코드로 강제하며 허용 키를
  `metrics`·`explanations`·`citations` 셋으로 좁혔고(`tests/test_goldenset_integrity.py` §8이
  강제), 구현이 그 계약을 따랐기 때문이다. 두 문서의 차이는 구현 시점에 확인되지 않았다. 또한
  `case-format.md` §4는 `metrics.horizons`를 지표별 필드(`var_pct`·`var_krw`·`cvar_pct`·
  `cvar_krw`)로 분리해 담도록 제시하나, 구현은 보유기간별 `values` 배열로 단순화했다(단,
  `confidence_interval`은 스펙상으로도 옵셔널이다). 당시 judge의 `numeric_consistency`가
  membership만 검사해 동작상 문제가 없었고 v1~v6 측정도 이 구조에서 일관되게 수행됐으나, 숫자 간
  관계를 검사하려면 지표 라벨 구분이 필요해 이번 측정 범위에서는 관계 검사(F1~F7 중 F1·F2·F3·F4·
  F6·F7)를 수행할 수 없다. `case-format.md`(승민 소유의 R1 작업 지시서)는 이 기록과 별개로 두며, 수정 여부는 문서
  소유자가 판단한다.
- **F1(포트폴리오 비중 합계) 관계 검사는 구현했으나(PR #181) 두 경로 모두에서 관측되지 않는다.**
  calibration 경로는 위 입력 어댑터 한계(portfolio 미전달) 때문이고, **실제 그래프 실행 경로도
  마찬가지다** — `load_inputs`가 입력 단계에서 자산군 비중 합=100%를 이미 `ValueError`로 강제하고,
  현재 설명문 생성 로직(`rag_cite`)도 "비중" 문맥의 수치를 만들지 않아 F1이 잡을 결함 자체가 두
  경로 모두에서 발생하지 않는다(PR #181 리뷰, 중현 실측). 라이브 데모로 "작동을 증명"할 수 있는
  항목이 아니며, 코드·단위 테스트 수준의 근거로만 존재한다. 라벨 근거(F1으로 확인된 미탐 1건)가
  있어 구현했으나, 시스템 구조상 방어적으로 가려진 상태다.
- **수치정합의 나머지 관계 검사(F2·F3·F4·F5·F6·F7)는 구현하지 않았다.** `numeric_consistency`가
  실제로 수행하는 검사는 ⑴ 비중 합계(F1) ⑵ 날짜의 metrics 소속 ⑶ 숫자의 metrics 소속 셋뿐이며
  (`app/judge/rubric.py:numeric_consistency`), 숫자 사이의 관계를 보는 코드는 없다. 20건 중 이
  유형으로 확인된 사례가 없어 확인된 결함만 고친다는 원칙상 보류했다. 다만 **미구현 사유가 축마다
  같지 않다**:
  - F2(`비율 × 평가액 ≠ 금액`)·F3(1일↔10일 관계)·F4(`VaR > CVaR` 등 대소)·F6(신뢰구간이 점추정치를
    품지 않음)·F7(신뢰구간의 √t 규약)은 **관계 검사 자체가 없고**, 설령 구현해도 위 입력 어댑터
    한계(지표 라벨 없이 `values` 배열) 때문에 이 경로에서는 동작할 수 없다.
  - F5(같은 지표가 표와 본문에서 다른 값)는 **이 경로에서 발생 자체가 불가능하다** — 로더가 표를
    그대로 문장으로 펼쳐 explanations를 만들기 때문에(`_flatten_tables`) 표와 본문이 구조적으로 항상
    같아진다. 즉 "검사했으나 못 잡았다"가 아니라 "이 실행 형태에서는 성립하지 않는 결함 유형"이다.
- **계획서의 ★(표 수치를 explanations에 투입)는 구현했으나 그것만으로는 목적이 달성되지 않는다.**
  `docs/symphony_proof_plan.md` §R2는 핵심 함정(1일 VaR × √10 ≠ 10일 VaR, 라벨링 가이드 수치정합
  `F3`)이 표 안에만 있어 judge 눈에 띄지 않으므로 표 수치를 explanations로 옮겨야 이 축이 작동한다고
  봤고, 로더는 이를 구현했다(`_flatten_tables`). 그러나 이 축의 엔진 수치 검사는 **소속 검사**이고
  √t 관계를 검사하는 코드는 judge에 없다. metrics와 explanations를 같은 표에서 만들기 때문에 어긋난
  10일 값도 양쪽에 동일하게 들어가 소속 검사를 **항상 통과한다**. ★와 F3 관계 검사는 둘 다 있어야
  작동하는 한 쌍인데 후자가 없어, 이 함정 유형은 v1~v6 전 구간에서 이 축으로 검출되지 않는다. ★를
  하지 않았어도 결과는 같으며, ★는 검출을 돕는 방향이 아니라 소속 일치를 자동으로 성립시키는 방향으로
  작용한다.
- **`source_validity` 축은 v1~v6 전 구간에서 실패 판정이 0건이다 — 구조적 사각지대다.** 이 축은
  검증 통과 인용이 **1건이라도 있으면 통과**한다(`app/judge/rubric.py:source_validity`). 나머지
  인용이 위조·불일치여도 축 자체는 pass다. 실제로 6개 버전 모두에서 "인용 결함이 있는데 출처 축은
  통과"가 1건씩 관측된다. 인용 결함을 실제로 잡은 것은 이 축이 아니라 preflight 필수 검사
  (`citations_all_verified`·`citation_content_contract`, 6개 버전 모두 각 1건 실패)다.
  - **전체 pass/fail 판정과 일치율에는 영향이 없다** — preflight가 `required=True`라 judge는
    어차피 불합격을 냈다.
  - 다만 **축별 일치율에서 출처 축은 사실상 측정되지 않았다.** 사람은 출처 축 결함으로 라벨하지만
    judge는 그 축을 pass로 두고 다른 이름의 검사로 실패시키므로, 이 축의 `fail_axes` 대조는
    judge의 검출력을 반영하지 못한다(집계는 `fail_axes`와 `failed_required_checks`를 분리해
    기록한다 — `app/evaluation/calibration_schema.py`).
  - **PR #196에서 수정했다** — 제시된 인용이 있으면 전부 검증돼야 통과하도록 바꿨다(v7부터 적용).
    다만 이 수정이 실제로 작동하는 것은 **calibration 경로뿐이다.** 라이브 그래프 실행에서는
    `rag_cite`가 검증 통과분만 `state["citations"]`에 넣고(`citations=[citation.to_dict() for
    citation in unique_verified]` — `app/nodes/rag_cite.py:1004`) 탈락분은 `citation_rejections`로
    분리하므로, 미검증 인용이 애초에 이 축에 도달하지 않는다. F1(PR #181)이 두 경로 모두에서
    관측되지 않았던 것과 달리, 이번 건은 **calibration 경로에서만 작동**한다(PR #196 리뷰, 다경).
- **LLM 2축(`hallucination`·`false_precision`)의 라운드 간 변화는 프롬프트 개선 효과와 벤더
  비결정성을 분리하지 못한다.** 이 두 축만 LLM 판정이고, 각 버전을 **1회씩만** 실행했다.
  `docs/reproducibility_scope.md`는 judge 6축 판정을 무조건 보장 대상이 아닌 **반복 실측 대상**으로
  선언하고(§2.1), `temperature=0`·`seed` 지정으로도 Azure 응답 비결정성이 제거되지 않음을 실측으로
  기록했으며(§5), 응답 캐시는 미채택이다(§8). 러너도 `seed`를 지정하지 않는다. 따라서 예컨대
  v5→v6(75%→80%, `hallucination` 축 규칙 축소)의 개선폭이 전부 프롬프트 덕이라고는 이 측정만으로
  주장할 수 없다. 결정론 4축(`source_validity`·`numeric_consistency`·`disclaimer`·
  `prohibited_expression`)의 라운드 간 변화에는 이 한계가 없다.
- **`numeric_consistency`의 소속 검사 후보 집합이 넓다.** 사례당 metrics에서 파생되는 후보 숫자가
  23~49개다(절댓값·×100 환산·보유기간 키·신뢰수준 파생값을 모두 포함 —
  `app/judge/rubric.py:_metric_numbers`). 설명문의 숫자가 이 중 **아무 것과라도** 근사 일치하면
  통과하므로, 위 ★ 항목과 같은 뿌리에서 이 축은 미검출 방향으로 관대하다.
- 이 폴더의 모든 측정은 **judge 1회 판정**(`judge_attempt == 1`) 기준이다. 재작성 루프(judge_retries
  경유) 이후 판정이 달라지는지는 이 측정 범위 밖이다.
- **`computation_hash_present` 검사는 실질적으로 무측정이다.** R1 사례집 본문의 `computation_hash`는
  `<실행 시 자동 기록 — 자리표시>` 플레이스홀더이며 실제 해시가 없다. 로더는 이 값을 metrics 수치
  내용에서 결정론적으로 합성해 채운다(`app/evaluation/goldenset_loader.py:_synthesize_hash`). 그
  결과 judge의 형태 검사 `computation_hash_present`는 20건 전부 통과하지만, 이는 엔진이 산출한 재현
  해시를 검증한 것이 아니라 로더가 합성한 값의 존재를 확인한 것이다. 합성하지 않으면 20건 전부가 이
  검사에서 실패해 다른 축을 측정할 수 없어 합성을 택했다. 앞의 관계 검사(F1·F3·F4·F6·F7)는 checks
  목록에 아예 포함되지 않아 "해당 없음"으로 읽히는 반면, 이 검사는 **`passed: true`로 기록되어
  일치율 산출에 들어간다** — 감사 시 "재현 해시 검사를 통과했다"로 읽힐 수 있으므로 이 차이를 함께
  본다.
- **조건부 검사 2건은 checks 목록에 포함되지 않는다.** judge preflight의 `citation_routing_contract`
  와 `citation_publication_freshness`는 `run_config.audit.llm.rag_cite.latest`에 라이브 `rag_cite`
  실행 기록이 있을 때만 목록에 추가된다(`app/nodes/judge_eval.py:_build_checks`). calibration은 정적
  리포트를 재생하므로 그 기록이 없고, 두 검사는 **건너뛴 것이 아니라 조건 미성립으로 목록에 포함되지
  않는다**("스킵"과 달리 이 실행 형태에서는 성립하지 않는 검사라는 뜻이다). 판정에는 영향이 없다 —
  라우팅 검사는 목록에 없어 집계에 들어가지 않고, 최신성 검사는 `required=False`인 비차단 항목이다.
