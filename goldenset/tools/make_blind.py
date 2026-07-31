"""라벨링 배포 패키지 생성 — blind 사례집 · 답안지 · 봉인.

하는 일
  1. `cases/` 20건에서 라벨 필드를 제거하고 **불투명 ID**(B01~B20)로 바꿔 `cases_blind/`에 쓴다
  2. 원본 id ↔ blind id 매핑을 `.sealed/blind_map.json`에 봉인한다
  3. `case-plan.md`(출제 의도)를 `.sealed/`로 옮겨 봉인한다
  4. 라벨러별 답안지(`dist/answer_sheet_*.md`)와 배포 패키지를 만든다

왜 불투명 ID인가
  출제자 본인(라벨러 #1)이 `case_003`을 보면 무슨 함정을 심었는지 떠오른다.
  ID를 끊어야 blind가 성립한다. 조원 라벨러에게도 동일 ID를 쓴다.

⚠️ 이 스크립트는 pass/fail을 판정하지 않는다. 라벨은 사람이 매긴다(무효 조건 ①).

사용: python goldenset/tools/make_blind.py [--seed 문구]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES, BLIND, SEALED, DIST = (ROOT / n for n in ("cases", "cases_blind", ".sealed", "dist"))

# 라벨러에게 보이면 안 되는 frontmatter 필드
LABEL_FIELDS = ("label", "fail_axes", "trap_type", "rationale", "labelers", "initial_agreement")

BLIND_HEADER = """---
id: {bid}
---

> **라벨링 대상 사례입니다.** 아래 본문만 읽고 판정하세요.
> 인용 원문 대조가 필요하면 함께 받은 `chunks.json`을 참고하세요.
> 판정 기준은 `labeling-guide.md` §2이며, 사유에 **규칙 번호**를 적어 주세요.

"""


def strip_labels(text: str) -> str:
    """frontmatter에서 라벨 필드를 제거하고 본문만 남긴다."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("frontmatter를 찾지 못했습니다")
    front, body = m.groups()
    kept = [
        line
        for line in front.split("\n")
        if not any(line.strip().startswith(f"{f}:") for f in LABEL_FIELDS)
    ]
    leaked = [f for f in LABEL_FIELDS if re.search(rf"^\s*{f}:\s*\S", "\n".join(kept), re.M)]
    if leaked:
        raise AssertionError(f"라벨 필드가 남았습니다: {leaked}")
    return body.lstrip("\n")


# 배포용 가이드에서 남길 절 — 판정 기준 그 자체만 남긴다.
#
# ⚠️ §4(규칙 갱신 로그)를 여기에 넣지 말 것.
#    §4는 라벨링이 진행되면서 "어느 사례에서 무엇이 갈렸는지"가 사례 ID와 함께
#    누적된다. 1회차 배포 시점에는 비어 있어 안전해 보이지만, 라벨링 후 생성기를
#    다시 돌리면 그때는 정답표가 된다. 절 목록으로 막지 않고 아래 누출 검사로
#    이중 방어한다.
KEEP_SECTIONS = ("0.", "1.", "2.")

# 배포본에 있으면 안 되는 것 — 하나라도 걸리면 생성을 중단한다.
LEAK_PATTERNS = (
    r"pass\s*\d+건",           # pass/fail 건수 배분
    r"fail\s*\d+건",
    r"case[-_]plan",           # 구성표 파일명
    r"manifest\.md",
    r"case_\d+",               # 원본 사례 ID (블라인드 ID만 노출돼야 한다)
    r"\.sealed",               # 봉인 경로
    r"함정",                    # 출제 의도 어휘
    r"trap[-_]?type",
    r"규칙 갱신 로그",           # §4 제목 — 절 필터가 뚫렸다는 신호
)
# `fail_axes`는 라벨러가 직접 채우는 필드명이라 §1 안내에 정당하게 등장한다.
# 누출 패턴에 넣지 말 것 — 오탐으로 생성이 막힌다.


def build_labeler_guide(text: str) -> str:
    """라벨러 배포용 가이드 — 답을 흘리는 절을 제거한다.

    제거 대상
      §3 라벨링 절차 — 배포 패키지 표가 '어떤 파일에 답이 있는지' 알려준다
      §4 규칙 갱신 로그 — **사례 ID와 판정 이력이 누적된다** (위 주석 참조)
      §5 파일 규격  — 라벨러가 쓸 일 없다
      §6 체크리스트 · §7 설계 근거 — **pass/fail 건수 배분이 적혀 있다**
    헤더의 총 건수 표기도 지운다. 균형을 알면 답을 맞춰버릴 수 있다.

    재실행 안전성: 원본 가이드가 라벨링 이후로 갱신됐더라도 이 함수는 같은
    결과를 내야 한다. 절 목록(화이트리스트) + 누출 패턴 검사로 보장한다.
    """
    head, *rest = re.split(r"\n(?=## )", text)
    head = re.sub(r"> 대상:.*\n", "> 대상: 4조 · 정답 사례집 라벨링\n", head)
    head = re.sub(r"> \*\*상태:.*\n", "> **상태: 라벨링용 배포본**\n", head)
    kept = [s for s in rest if s[3:].lstrip().startswith(KEEP_SECTIONS)]
    guide = head + "\n" + "\n".join(kept)

    leaks = {m for p in LEAK_PATTERNS for m in re.findall(p, guide)}
    if leaks:
        raise AssertionError(f"배포용 가이드에 누출이 남았습니다: {sorted(leaks)}")
    return guide.rstrip() + "\n"


def answer_sheet(name: str, ids: list[str]) -> str:
    rows = "\n".join(
        f"| {b} |  |  |  |  |" for b in ids
    )
    return f"""# 라벨링 답안지 — {name}

**작성 전 반드시 읽어 주세요**

1. `labeling-guide.md` §2(축별 판정 기준)를 먼저 읽습니다. 이 문서가 유일한 판정 근거입니다.
2. 🚫 **AI에 판정을 묻지 마세요 — 과제 무효 사유입니다(무효 조건 ①).**
   우리 시스템 judge뿐 아니라 **ChatGPT · Claude · Gemini 등 어떤 AI도 안 됩니다.**
   "이거 pass야 fail이야?", "어느 축이 틀렸어?" 류의 질문 일체 금지입니다.
   *왜 —* R2에서 재는 것이 "judge가 **사람** 판단과 얼마나 맞는가"입니다. 사람 라벨을 AI가 만들면
   "AI와 judge가 얼마나 비슷한가"를 재는 셈이 되어 숫자가 통째로 무의미해집니다.
3. **다른 라벨러나 출제자에게 답을 묻지 마세요.** 독립 판정이어야 일치율이 의미를 갖습니다.
4. 판정이 안 되는 사례는 비워 두고 `비고`에 "규칙 미비"라고 적어 주세요. **찍지 마세요.**
5. 계산 확인(예: 10일 값이 1일×√10인지)은 계산기·엑셀로 하세요. 산술은 도구를 써도 되지만
   **판정은 본인이** 합니다.

**기재 방법**

- `판정`: `pass` 또는 `fail`
- `실패 축`: fail일 때만. 허용값 그대로 — `출처` `수치 정합` `환각` `위조정밀도` `면책` `금지표현` (복수면 쉼표)
- `근거`: 기준표 항목 번호 (예: `출처-F2`, `면책-B7`)
- `사유`: 한 줄이면 충분합니다

| 사례 | 판정 | 실패 축 | 근거 | 사유 |
|---|---|---|---|---|
{rows}

**비고**

-
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="symphony-proof-r1", help="blind ID 셔플 시드 문구")
    ap.add_argument(
        "--overlap",
        type=int,
        default=8,
        help=(
            "조원 두 명이 **공통으로** 보는 사례 수 (기본 8). "
            "출제자(라벨러#1)는 함정 설계를 알고 있어 라벨이 오염돼 있다. "
            "겹치는 구간이 있어야 '오염 없는 사람-사람 일치율'을 잴 수 있다 — "
            "그 숫자로 사람 간 일치율(IAA)을 낸다. 0이면 겹침 없음."
        ),
    )
    ap.add_argument(
        "--names",
        default="승민,중현,준호",
        help="라벨러 실명 3개, 쉼표 구분. 첫 번째가 출제자(#1)다. 예: 승민,중현,준호",
    )
    args = ap.parse_args()
    names = [n.strip() for n in args.names.split(",")]
    if len(names) != 3:
        ap.error("--names 는 라벨러 3명이어야 한다")

    files = sorted(CASES.glob("case_*.md"))
    if len(files) != 20:
        print(f"⚠️ 사례가 {len(files)}건입니다 (20건 예상)")

    seed = int(hashlib.sha256(args.seed.encode()).hexdigest()[:8], 16)
    order = list(files)
    random.Random(seed).shuffle(order)

    for d in (BLIND, SEALED, DIST):
        d.mkdir(exist_ok=True)
    for old in BLIND.glob("*.md"):
        try:
            old.unlink()
        except OSError:
            pass  # 일부 마운트는 삭제를 막는다 — 아래에서 덮어쓴다

    mapping = {}
    for i, src in enumerate(order, 1):
        bid = f"B{i:02d}"
        body = strip_labels(src.read_text(encoding="utf-8"))
        body = re.sub(r"사례 case_\d+", f"사례 {bid}", body)
        (BLIND / f"{bid}.md").write_text(BLIND_HEADER.format(bid=bid) + body, encoding="utf-8")
        mapping[bid] = src.stem

    ids = sorted(mapping)
    n = len(ids)
    half, ov = n // 2, max(0, min(args.overlap, n // 2))
    # 앞 절반 + 겹침 / 겹침 + 뒤 절반 — 가운데 ov건을 두 조원이 공통으로 본다
    a_ids, b_ids = ids[: half + ov // 2], ids[half - ov + ov // 2 :]
    shared = sorted(set(a_ids) & set(b_ids))
    assign = {
        f"{names[0]}(#1)": ids,
        f"{names[1]}(#2)": a_ids,
        f"{names[2]}(#3)": b_ids,
    }
    for raw, (name, subset) in zip(names, assign.items()):
        (DIST / f"answer_sheet_{raw}.md").write_text(answer_sheet(name, subset), encoding="utf-8")

    (SEALED / "blind_map.json").write_text(
        json.dumps(
            {
                "sealed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "seed_phrase": args.seed,
                "note": "라벨 확정 전 열람 금지. 개봉은 최종 라벨 확정 후.",
                "map": mapping,
                "assignment": {k: v for k, v in assign.items()},
                "clean_pair": shared,
                "clean_pair_note": (
                    "조원 2인이 공통으로 라벨한 사례. 출제자 오염이 없어 "
                    "사람 간 일치율(IAA) 산출에 쓴다. judge 일치율의 상한이 아니다."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    plan = ROOT / "case-plan.md"
    if plan.exists():
        (SEALED / "case-plan.md").write_text(plan.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            plan.unlink()
            print("🔒 case-plan.md → .sealed/ 로 봉인")
        except OSError:
            print("🔒 case-plan.md → .sealed/ 복사 완료 — 원본은 직접 삭제하세요")

    guide_src = ROOT / "labeling-guide.md"
    (DIST / "labeling-guide.md").write_text(
        build_labeler_guide(guide_src.read_text(encoding="utf-8")), encoding="utf-8"
    )
    shutil.copy(ROOT / "corpus" / "chunks.json", DIST / "chunks.json")
    dist_blind = DIST / "cases_blind"
    dist_blind.mkdir(exist_ok=True)
    for f in BLIND.glob("*.md"):
        (dist_blind / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"✅ blind 사례 {len(mapping)}건 → cases_blind/")
    print(f"✅ 답안지 {len(assign)}건 → dist/")
    print(
        f"   중현 {len(a_ids)}건 · 준호 {len(b_ids)}건 · "
        f"공통 {len(shared)}건 {shared[:3]}{'…' if len(shared) > 3 else ''}"
    )
    if not shared:
        print("   ⚠️ 겹치는 구간이 없다 — 오염 없는 사람-사람 일치율을 잴 수 없다")
    print(f"✅ 배포 패키지 → dist/ (labeling-guide.md · chunks.json · cases_blind/ · 답안지)")
    print(f"🔒 매핑 봉인 → .sealed/blind_map.json")
    print("\n⚠️ dist/ 만 조원에게 전달하세요. corpus/manifest.md 와 .sealed/ 는 절대 금지.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
