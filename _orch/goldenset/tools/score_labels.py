"""라벨러 간 일치율 산출 — 합의 **전** 숫자를 낸다.

이 스크립트가 내는 숫자
  1. 라벨러 쌍별 pass/fail 일치율
  2. **사람 간 일치율(IAA)** — 합의 **전** 독립 판정끼리의 일치율.
     라벨 난이도·모호성의 지표이자 사람 판정 신뢰도의 기준선이다.
  3. 축별 일치도 — 둘 다 fail로 본 사례에서 fail_axes 집합의 Jaccard
  4. 불일치 건 목록 — 기준표 어느 항목에서 갈렸는지
  5. 판정 불능(빈칸) 건수 — 기준표 미비 신호

⚠️ **이 값은 judge 일치율의 상한이 아니다.** judge는 개별 라벨러가 아니라
   조정을 거친 **최종 gold label**과 비교된다. 조정은 불일치를 해소한 결과이므로
   gold는 어느 한 사람의 원본보다 깨끗하고, 따라서 judge는 IAA를 넘을 수 있다
   (이론상 20/20도 가능하다). 두 숫자는 **서로 다른 것을 재는 별개 지표**이며,
   발표에서도 `사람-사람 N/20`과 `judge-gold M/20`을 나란히, 그러나 따로 제시한다.

   다만 진단에는 쓴다 — **사람이 갈렸던 사례에서 judge가 유독 잘 맞으면**
   그것은 실력이 아니라 누출 신호일 수 있다.

⚠️ 합의 후 일치율은 당연히 100%라 의미가 없다. **합의 전에 돌려서 기록**할 것.
⚠️ 이 스크립트는 최종 라벨을 정하지 않는다. 사람이 정한다(무효 조건 ①).

사용:
  python goldenset/tools/score_labels.py --labels goldenset/labels
  python goldenset/tools/score_labels.py --labels goldenset/labels --out goldenset/reports/agreement.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AXES = ("출처", "수치 정합", "환각", "위조정밀도", "면책", "금지표현")
ROW_RE = re.compile(r"^\|\s*(B\d+)\s*\|(.*)\|\s*$", re.M)
NAME_RE = re.compile(r"^#\s*라벨링 답안지\s*—\s*(.+)$", re.M)


class Sheet:
    def __init__(self, path: Path):
        text = path.read_text(encoding="utf-8")
        m = NAME_RE.search(text)
        self.name = m.group(1).strip() if m else path.stem
        self.rows: dict[str, dict] = {}
        self.blank: list[str] = []
        self.bad_axes: list[str] = []
        for cid, rest in ROW_RE.findall(text):
            cells = [c.strip() for c in rest.split("|")]
            cells += [""] * (4 - len(cells))
            verdict, axes_raw, basis, reason = cells[:4]
            verdict = verdict.lower()
            if verdict not in ("pass", "fail"):
                self.blank.append(cid)  # 판정 불능 — 기준표 미비 신호
                continue
            axes = [a.strip() for a in re.split(r"[,·/]", axes_raw) if a.strip()]
            for a in axes:
                if a not in AXES:
                    self.bad_axes.append(f"{cid}: {a!r}")
            self.rows[cid] = {
                "verdict": verdict,
                "axes": {a for a in axes if a in AXES},
                "basis": basis,
                "reason": reason,
            }

    def __repr__(self):
        return f"<{self.name} {len(self.rows)}건>"


def jaccard(a: set, b: set) -> float:
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def compare(x: Sheet, y: Sheet) -> dict:
    shared = sorted(set(x.rows) & set(y.rows))
    if not shared:
        return {"pair": f"{x.name} × {y.name}", "n": 0}
    agree, disagree, jac = [], [], []
    matrix = {"pass_pass": 0, "pass_fail": 0, "fail_pass": 0, "fail_fail": 0}
    for cid in shared:
        a, b = x.rows[cid], y.rows[cid]
        matrix[f"{a['verdict']}_{b['verdict']}"] += 1
        if a["verdict"] == b["verdict"]:
            agree.append(cid)
            if a["verdict"] == "fail":
                jac.append((cid, jaccard(a["axes"], b["axes"])))
        else:
            disagree.append(
                {
                    "case": cid,
                    x.name: f"{a['verdict']} {sorted(a['axes'])} [{a['basis']}]",
                    y.name: f"{b['verdict']} {sorted(b['axes'])} [{b['basis']}]",
                }
            )
    return {
        "pair": f"{x.name} × {y.name}",
        "n": len(shared),
        "agree": len(agree),
        "rate": f"{len(agree)}/{len(shared)}",
        "matrix": matrix,
        "axis_jaccard": jac,
        "axis_jaccard_mean": round(sum(v for _, v in jac) / len(jac), 3) if jac else None,
        "disagreements": disagree,
    }


def render(sheets: list[Sheet], pairs: list[dict], clean: dict | None) -> str:
    L = ["# 라벨러 간 일치율 (합의 전)", ""]
    L += ["> 이 숫자는 **합의 전** 독립 판정 기준이다. 합의 후 일치율은 100%라 의미가 없다.", ""]
    L += ["## 1. 라벨러", "", "| 라벨러 | 판정 건수 | 판정 불능 | 축 표기 오류 |", "|---|---|---|---|"]
    for s in sheets:
        L.append(f"| {s.name} | {len(s.rows)} | {len(s.blank)} | {len(s.bad_axes)} |")
    if clean:
        L += ["", "## 2. 사람 간 일치율(IAA) — 라벨 신뢰도 기준선", ""]
        L += [f"라벨러 2인이 공통으로 본 **{clean['n']}건** 기준. 출제자는 라벨링에서 배제.", ""]
        L += [f"### **{clean['rate']}**  ({clean['pair']})", ""]
        L += [
            "이 값은 **라벨의 난이도·모호성**을 나타낸다. 낮으면 기준표에 빈칸이 있다는 뜻이다.",
            "",
            "> ⚠️ **judge 일치율의 상한이 아니다.** judge는 개별 라벨러가 아니라 조정을 거친",
            "> 최종 gold label과 비교되며, gold는 불일치가 해소돼 어느 한 사람의 원본보다",
            "> 깨끗하다. 따라서 judge가 이 값을 넘는 것은 정상이다.",
            "",
            "`사람-사람` 과 `judge-gold` 는 **별개 지표로 나란히** 제시한다.",
            "다만 **사람이 갈렸던 사례에서 judge가 유독 잘 맞으면 누출을 의심**한다.",
            "",
        ]
    else:
        L += ["", "## 2. ⚠️ 오염 없는 사람-사람 일치율 — **미측정**", ""]
        L += [
            "조원 2인이 **같은 사례를 본 구간이 없다.** 따라서 아래 일치율은 전부",
            "`출제자 × 조원` 쌍이며, 한쪽에 출제 기억 오염이 섞여 있어 **과대평가될 수 있다.**",
            "",
            "이 한계를 캘리브레이션 리포트와 발표에 그대로 적는다.",
            '"judge가 사람 수준에 근접했다"는 해석은 하지 않는다 — 비교 기준 자체가 오염돼 있다.',
            "",
        ]
    L += ["## 3. 쌍별 상세", ""]
    for p in pairs:
        if not p["n"]:
            continue
        L += [f"### {p['pair']} — {p['rate']}", ""]
        m = p["matrix"]
        L += [
            "| | 상대 pass | 상대 fail |",
            "|---|---|---|",
            f"| **pass** | {m['pass_pass']} | {m['pass_fail']} |",
            f"| **fail** | {m['fail_pass']} | {m['fail_fail']} |",
            "",
        ]
        if p["axis_jaccard_mean"] is not None:
            L += [
                f"둘 다 fail로 본 {len(p['axis_jaccard'])}건의 **축 일치도(Jaccard) 평균 "
                f"{p['axis_jaccard_mean']}**",
                "",
            ]
            low = [c for c, v in p["axis_jaccard"] if v < 1.0]
            if low:
                L += [f"- 축이 갈린 사례: {', '.join(low)}", ""]
        if p["disagreements"]:
            L += ["**판정이 갈린 건**", ""]
            for d in p["disagreements"]:
                L.append(f"- `{d['case']}`")
                for k, v in d.items():
                    if k != "case":
                        L.append(f"  - {k}: {v}")
            L += [
                "",
                "> 갈린 건은 **누가 틀렸는지가 아니라 기준표 어느 항목이 모호했는지**를 따진다.",
                "> 기준표로 판정되지 않으면 규칙 미비이므로 `labeling-guide.md` §4에 기록하고",
                "> 규칙을 보강한 뒤 같은 축 사례를 소급 재검토한다.",
                "",
            ]
    blanks = {s.name: s.blank for s in sheets if s.blank}
    if blanks:
        L += ["## 4. 판정 불능 (기준표 미비 신호)", ""]
        for n, b in blanks.items():
            L.append(f"- {n}: {', '.join(b)}")
        L += ["", "> 찍지 않고 비워둔 건이다. **기준표를 고칠 지점**을 알려주는 정보다.", ""]
    bad = {s.name: s.bad_axes for s in sheets if s.bad_axes}
    if bad:
        L += ["## 5. ⚠️ 축 표기 오류 — 집계가 깨진다", ""]
        for n, b in bad.items():
            L.append(f"- {n}: {'; '.join(b)}")
        L += ["", f"> 허용값: {' · '.join(AXES)}", ""]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(ROOT / "labels"), help="채워진 답안지 폴더")
    ap.add_argument("--out", default=None, help="리포트 저장 경로 (.md)")
    args = ap.parse_args()

    d = Path(args.labels)
    # README 등 답안이 아닌 md가 라벨러로 잡히지 않도록 파일명을 제한한다
    files = sorted(d.glob("answer_sheet_*.md")) if d.exists() else []
    if len(files) < 2:
        print(f"답안지가 부족하다 ({len(files)}건). {d} 에 채워진 답안지를 넣고 다시 실행.")
        return 1

    sheets = [Sheet(f) for f in files]
    pairs = [compare(x, y) for x, y in combinations(sheets, 2)]

    # clean 쌍 = 출제자(#1)를 뺀 조원끼리
    peers = [s for s in sheets if "#1" not in s.name and "승민" not in s.name]
    clean = compare(*peers) if len(peers) == 2 and compare(*peers)["n"] else None

    report = render(sheets, pairs, clean)
    print(report)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(report, encoding="utf-8")
        p.with_suffix(".json").write_text(
            json.dumps({"pairs": pairs, "clean": clean}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"저장: {p} · {p.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
