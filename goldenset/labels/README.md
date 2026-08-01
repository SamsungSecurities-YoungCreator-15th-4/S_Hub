# 라벨러 답안지 (최종)

최종 라벨의 근거가 된 답안지입니다.

| 파일 | 라벨러 | 범위 |
|---|---|---|
| `answer_sheet_중현.md` | 중현 | B01~B20 전건 |
| `answer_sheet_준호.md` | 준호 | B01~B20 전건 |

두 라벨러가 **20건을 겹쳐서** 독립으로 판정했습니다. 공통 구간이 20/20이라
사람 간 일치율(IAA)이 측정됩니다. 이 값은 **라벨의 난이도·모호성**을 나타내며,
judge 일치율의 상한이 아닙니다 — judge는 조정된 gold label과 비교되기 때문입니다.

**출제자는 라벨러에서 배제했습니다.** 어느 사례에 어떤 결함을 심었는지 아는 상태의
판정은 사람 라벨로 셀 수 없습니다. 출제자의 역할은 불일치 조정과 축 일관성 판단뿐입니다.

재라벨링 3건(`R01`~`R03`)의 답안지는 `../dist_relabel/`에 있습니다.

## 산출 결과

- 사람 간 일치율 **18/20** (IAA) → `reports/agreement_before.md` §7
- 최종 라벨 **pass 10 / fail 10** → `../cases/case_*.md` frontmatter

## 재현 절차

```bash
# 1. 합의 전 일치율
python goldenset/tools/score_labels.py --labels goldenset/labels \
       --out reports/agreement_before.md

# 2. 불일치 건을 기준표 항목 번호 근거로 조정 (사람이 논의)

# 3. 최종 라벨 골격 생성 → 사람이 채움
python goldenset/tools/apply_labels.py --init

# 4. 검증 후 기입
python goldenset/tools/apply_labels.py            # dry-run
python goldenset/tools/apply_labels.py --write

# 5. git commit + git tag v1-freeze ← 라벨 동결. 이후에 judge를 돌린다
```

> ⚠️ 5번 커밋 **전에는 judge를 돌리지 않습니다.** 커밋 순서가 "라벨 먼저, judge 나중"을
> 증명하는 유일한 증거입니다.
