# R2 Judge 실행용 무라벨 입력본

이 디렉터리는 `goldenset/cases/case_*.md`에서 정답성 frontmatter를 제거한
Judge 실행 전용 입력입니다. R2 실행 담당자는 원본 정답 사례집을 열거나 파싱하지
않고 이 디렉터리만 사용합니다.

- 유지: `id`, `variant`, `llm_draft`, 사례 본문
- 제거: 사람 정답, 실패 축, 함정 유형, 판정 사유 및 라벨링 이력
- 생성: `python goldenset/tools/export_judge_inputs.py`
- 검증: `python goldenset/tools/export_judge_inputs.py --check`

`manifest.json`의 사례별 SHA-256은 frontmatter를 제외한 본문 해시이며,
`goldenset/case_hashes.json`의 R1 동결 해시와 일치해야 합니다.

`input_set_hash`는 **사람 라벨을 포함하지 않은 20건 본문 집합의 해시**입니다.
`app/evidence/schema.py`의 공식 `evalset_hash`와 다릅니다. 공식 값은 사례 본문과
사람 라벨을 함께 고정하므로 calibration summary에는 반드시 그 값을 사용합니다.
