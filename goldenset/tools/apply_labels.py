"""합의된 최종 라벨을 사례 frontmatter에 기입한다.

흐름
  1. `--init` — 답안지와 봉인 매핑을 읽어 `final_labels.yaml` 골격을 만든다.
     라벨러 이름과 `initial_agreement`(합의 전 일치 여부)는 자동으로 채워지고,
     `label`·`fail_axes`·`trap_type`·`rationale`은 **사람이 직접 채운다**.
  2. 사람이 합의 결과를 그 파일에 적는다.
  3. 인자 없이 실행 — 스키마를 검증하고 `cases/*.md`에 기입한다.

⚠️ 이 스크립트는 라벨을 **만들지 않는다.** 사람이 정한 값을 옮겨 적고 검증할 뿐이다
   (무효 조건 ① — 자동화가 정답 라벨을 만들면 과제 무효).

사용:
  python goldenset/tools/apply_labels.py --init
  python goldenset/tools/apply_labels.py            # 검증만 (dry-run)
  python goldenset/tools/apply_labels.py --write    # 실제 기입
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES, SEALED = ROOT / "cases", ROOT / ".sealed"
FINAL = ROOT / "final_labels.yaml"
AXES = ("출처", "수치 정합", "환각", "위조정밀도", "면책", "금지표현")
FM_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)

# 라벨 산출 방식 — 20건 전부에 동일하게 기록한다.
# 출제자(승민)는 함정 설계를 인지한 상태이므로 **라벨러에서 배제**했고,
# 불일치 조정과 축 일관성 판단만 담당했다. 이 한 줄이 없으면 frontmatter는
# 라벨 구성을 실제보다 두텁게 주장하는 셈이 되어 사실과 어긋난다.
LABELING_METHOD = (
    "2인 라벨러(중현·준호) 전건 독립 라벨 · "
    "출제자는 라벨링에서 배제하고 불일치 조정·축 일관성만 담당 · "
    "3건(case_003·008·010)은 본문 수정 후 재라벨"
)


def load_sheets() -> dict[str, dict[str, str]]:
    """답안지에서 {blind_id: {labeler: verdict}} 를 모은다."""
    out: dict[str, dict[str, str]] = {}
    d = ROOT / "labels"
    for f in sorted(d.glob("*.md")) if d.exists() else []:
        m = re.search(r"^#\s*라벨링 답안지\s*—\s*(.+)$", f.read_text(encoding="utf-8"), re.M)
        name = m.group(1).strip() if m else f.stem
        for cid, rest in re.findall(r"^\|\s*(B\d+)\s*\|(.*)\|\s*$", f.read_text(encoding="utf-8"), re.M):
            v = rest.split("|")[0].strip().lower()
            if v in ("pass", "fail"):
                out.setdefault(cid, {})[name] = v
    return out


def do_init() -> int:
    bm = SEALED / "blind_map.json"
    if not bm.exists():
        print(f"봉인 매핑이 없다: {bm}")
        return 1
    mapping = json.loads(bm.read_text(encoding="utf-8"))["map"]
    sheets = load_sheets()
    if not sheets:
        print("⚠️ goldenset/labels/ 에 채워진 답안지가 없다 — 라벨러 정보 없이 골격만 만든다.")

    lines = [
        "# 최종 라벨 — 합의 결과를 사람이 직접 채운다",
        "#",
        "# label      : pass | fail",
        "# fail_axes  : fail만. 허용값 그대로 — " + " · ".join(AXES),
        "# trap_type  : fail만. pass는 none",
        "# rationale  : 판정 사유 2~3줄. **기준표 항목 번호를 인용**할 것 (예: 출처-F2, 면책-B7)",
        "#",
        "# labelers / initial_agreement 는 답안지에서 자동 기입됐다. 틀리면 고칠 것.",
        "",
    ]
    for bid in sorted(mapping):
        cid = mapping[bid]
        votes = sheets.get(bid, {})
        names = sorted(votes)
        if len(votes) >= 2:
            vals = set(votes.values())
            agree = len(vals) == 1
            n = sum(1 for v in votes.values() if v == max(vals, key=list(votes.values()).count))
            ia = f"{n}/{len(votes)} ({'독립 라벨 일치' if agree else '불일치 → 합의'})"
        else:
            ia = ""
        lines += [
            f"{cid}:",
            f"  # blind={bid}" + (f"  votes={votes}" if votes else ""),
            "  label:",
            "  fail_axes: []",
            "  trap_type: none",
            '  rationale: ""',
            f"  labelers: {json.dumps(names, ensure_ascii=False)}",
            f'  initial_agreement: "{ia}"',
            "",
        ]
    FINAL.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 골격 생성: {FINAL}")
    print("   label · fail_axes · trap_type · rationale 을 사람이 채운 뒤 --write 로 기입한다.")
    return 0


def validate(data: dict) -> list[str]:
    errs = []
    ids = {p.stem for p in CASES.glob("case_*.md")}
    if set(data) != ids:
        errs.append(f"사례 id 불일치: 누락 {sorted(ids - set(data))} / 잉여 {sorted(set(data) - ids)}")
    covered = set()
    for cid, d in sorted(data.items()):
        d = d or {}
        lab, axes = d.get("label"), d.get("fail_axes") or []
        trap, rat = d.get("trap_type"), (d.get("rationale") or "").strip()
        if lab not in ("pass", "fail"):
            errs.append(f"{cid}: label 미기입 또는 오류 ({lab!r})")
            continue
        if not rat:
            errs.append(f"{cid}: rationale 비어 있음")
        if lab == "fail":
            if not axes:
                errs.append(f"{cid}: fail인데 fail_axes 비어 있음")
            for a in axes:
                if a not in AXES:
                    errs.append(f"{cid}: 허용되지 않은 축 {a!r}")
            if not trap or trap == "none":
                errs.append(f"{cid}: fail인데 trap_type 미기입")
            if not re.search(r"[가-힣]+-[FPB]\d", rat):
                errs.append(f"{cid}: rationale에 기준표 항목 번호가 없다 (예: 출처-F2)")
            covered |= set(axes)
        else:
            if axes:
                errs.append(f"{cid}: pass인데 fail_axes가 비어 있지 않음")
            if trap not in (None, "none"):
                errs.append(f"{cid}: pass인데 trap_type이 none이 아님")
    missing = [a for a in AXES if a not in covered]
    if missing:
        errs.append(f"6축 커버리지 미달 — 어느 fail 사례에서도 안 나온 축: {missing}")
    return errs


def do_apply(write: bool) -> int:
    if not FINAL.exists():
        print(f"{FINAL} 이 없다. 먼저 --init 으로 골격을 만들 것.")
        return 1
    data = yaml.safe_load(FINAL.read_text(encoding="utf-8")) or {}
    errs = validate(data)
    if errs:
        print(f"❌ 검증 실패 {len(errs)}건 — 기입하지 않는다\n")
        for e in errs:
            print(f"  · {e}")
        return 1

    labs = sum(1 for d in data.values() if d["label"] == "fail")
    print(f"✅ 검증 통과 — pass {len(data)-labs}건 / fail {labs}건")
    if not write:
        print("   (dry-run) 실제 기입하려면 --write")
        return 0

    for cid, d in sorted(data.items()):
        p = CASES / f"{cid}.md"
        front, body = FM_RE.match(p.read_text(encoding="utf-8")).groups()
        fm = yaml.safe_load(front) or {}
        fm.update(
            {
                "label": d["label"],
                "fail_axes": d.get("fail_axes") or [],
                "trap_type": d.get("trap_type") or "none",
                "rationale": d["rationale"].strip(),
                "labelers": d.get("labelers") or [],
                "initial_agreement": d.get("initial_agreement") or "",
                "labeling_method": LABELING_METHOD,
            }
        )
        out = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000)
        p.write_text(f"---\n{out}---\n\n{body.lstrip()}", encoding="utf-8")
    print(f"✅ {len(data)}건 frontmatter 기입 완료")
    print("\n다음: git commit — **이 커밋이 라벨 동결 시점**이다. 커밋 후에 judge를 돌린다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="final_labels.yaml 골격 생성")
    ap.add_argument("--write", action="store_true", help="실제로 frontmatter에 기입")
    a = ap.parse_args()
    return do_init() if a.init else do_apply(a.write)


if __name__ == "__main__":
    sys.exit(main())
