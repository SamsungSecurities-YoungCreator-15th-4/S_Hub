"""judge 신뢰 지표를 화면용 표로 바꾸는 순수 UI 헬퍼.

9월 과제 요구:

    이 신뢰 지표가 폴더 깊숙이만 있지 않고, Hub 화면 또는 전용 패널에서
    팀·리뷰어가 볼 수 있을 것

핸드아웃이 덧붙인 말이 이 모듈의 성격을 정한다.

    "100% 일치" 과신보다, 불일치를 정직하게 분석한 쪽이 이 과제 취지에 맞다

그래서 이 모듈은 **잘 나온 숫자를 크게 보여주는** 대신 미탐·오탐을 분리하고
어긋난 사례를 이름으로 나열한다.

표기 규약 두 가지
-----------------
1. **일치율은 분수로 적는다.** 20건에서 1건은 5%p 라, 퍼센트로 적으면
   `80.0%` 같은 표기가 실제보다 정밀해 보인다 — 우리 6축 중 하나가
   위조정밀도인데 지표 화면이 그걸 어기면 안 된다.
2. **미탐(FN)과 오탐(FP)을 절대 하나로 합치지 않는다.** 성격이 다르다.
   미탐은 불량이 나가는 것이고 오탐은 멀쩡한 걸 막는 것이다.

`rag_evidence.py` 와 같이 streamlit 을 import 하지 않는다 — 화면 없이
테스트할 수 있어야 한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

#: v1-freeze 동결본. 신규 사례와 섞어 집계하면 v1↔v7 비교가 무효가 된다.
FROZEN_CASE_IDS = tuple(f"case_{i:03d}" for i in range(1, 21))

_COMPARE_RE = re.compile(r"^(v\d+)_(v\d+)_compare_summary\.json$")

#: 6축 영문 키 → 한글. engine/judge/axes.py 의 SSOT 와 같은 표기여야 한다.
AXIS_KO_FALLBACK = {
    "source_validity": "출처",
    "numeric_consistency": "수치 정합",
    "hallucination": "환각",
    "false_precision": "위조정밀도",
    "disclaimer": "면책",
    "prohibited_expression": "금지표현",
}


def format_fraction(matched: object, total: object) -> str:
    """일치 건수를 `16/20` 형태로 적는다. **퍼센트로 바꾸지 않는다.**

    20건 평가셋에서 1건은 5%p 다. 퍼센트 표기는 없는 정밀도를 만든다.
    """
    if not isinstance(matched, int) or not isinstance(total, int) or total <= 0:
        return "—"
    return f"{matched}/{total}"


def _derived(block: object) -> dict:
    if not isinstance(block, dict):
        return {}
    derived = block.get("derived")
    return derived if isinstance(derived, dict) else {}


def load_version_trend(reports_dir: Path | str) -> list[dict]:
    """프롬프트 버전별 일치 추이. `vN_vM_compare_summary.json` 들을 모은다.

    파일 안의 `v1`/`v2` 키는 버전 이름이 아니라 **before/after** 자리표시다
    (파일명이 실제 버전을 담는다). 헷갈리기 쉬워 여기서 이름을 붙여 돌려준다.
    """
    directory = Path(reports_dir)
    if not directory.exists():
        return []

    rows: dict[str, dict] = {}
    for path in sorted(directory.glob("*_compare_summary.json")):
        m = _COMPARE_RE.match(path.name)
        if m is None:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # 파일명이 아니라 블록 안의 prompt_version 을 신뢰한다 — 파일명은
        # 사람이 붙인 것이고 prompt_version 은 실행이 기록한 값이다.
        for key, fallback in (("v1", m.group(1)), ("v2", m.group(2))):
            block = payload.get(key)
            name = (block or {}).get("prompt_version") or fallback
            d = _derived(block)
            total = (block or {}).get("evalset_case_count")
            if not d or not isinstance(total, int):
                continue
            rows[name] = {
                "version": name,
                "match": d.get("match"),
                "total": total,
                "fraction": format_fraction(d.get("match"), total),
                "false_negative": d.get("false_negative"),
                "false_positive": d.get("false_positive"),
                "evalset_hash": (block or {}).get("evalset_hash"),
            }

    def _order(name: str) -> int:
        digits = re.sub(r"\D", "", name)
        return int(digits) if digits else 0

    return [rows[k] for k in sorted(rows, key=_order)]


def confusion_rows(summary_block: object) -> list[dict]:
    """혼동행렬을 화면용 4행으로. **미탐·오탐을 합치지 않는다.**"""
    block = summary_block if isinstance(summary_block, dict) else {}
    cm = block.get("confusion_matrix")
    cm = cm if isinstance(cm, dict) else {}
    total = block.get("evalset_case_count")
    labels = (
        ("true_positive", "결함 적중", "사람 fail · judge fail"),
        ("true_negative", "정상 통과", "사람 pass · judge pass"),
        ("false_negative", "미탐 (FN)", "사람 fail · judge pass — 불량이 나간다"),
        ("false_positive", "오탐 (FP)", "사람 pass · judge fail — 멀쩡한 걸 막는다"),
    )
    return [
        {
            "key": key,
            "label": label,
            "meaning": meaning,
            "count": cm.get(key),
            "fraction": format_fraction(cm.get(key), total if isinstance(total, int) else 0),
        }
        for key, label, meaning in labels
    ]


def axis_rows(summary: object, *, which: str = "axis_after") -> list[dict]:
    """축별 결함 재현율. 6축 전부를 돌려준다(값이 없으면 None)."""
    payload = summary if isinstance(summary, dict) else {}
    comparison = payload.get("comparison")
    axes = (comparison or {}).get(which) if isinstance(comparison, dict) else None
    axes = axes if isinstance(axes, dict) else {}

    rows = []
    for key, ko in AXIS_KO_FALLBACK.items():
        a = axes.get(key)
        a = a if isinstance(a, dict) else {}
        rows.append(
            {
                "axis": key,
                "axis_ko": a.get("axis_ko") or ko,
                "match": a.get("match"),
                "total": a.get("total"),
                "fraction": format_fraction(a.get("match"), a.get("total")),
                "false_negative": a.get("false_negative"),
                "false_positive": a.get("false_positive"),
                # 사람이 fail 로 본 사례가 몇 건인지 — 재현율의 분모다.
                # 이게 작으면 재현율 1.0 도 근거가 약하다는 뜻이라 함께 보여준다.
                "human_fail_support": a.get("human_fail_support"),
            }
        )
    return rows


def mismatch_rows(judge_results: object, human_labels: object) -> list[dict]:
    """사람 라벨과 judge 판정이 어긋난 사례. **왜 틀렸는지까지 낸다.**

    핸드아웃이 "어긋난 사례 목록과 왜 틀렸는지"를 요구한다. 요약 JSON 은
    `mismatch_detail_excluded` 로 이 상세를 뺀다(사람 라벨 원문 누출 방지).
    화면은 분석 단계이므로 여기서 다시 합친다 — **실행 단계와 다르다.**
    """
    results = judge_results if isinstance(judge_results, list) else []
    labels = human_labels if isinstance(human_labels, dict) else {}

    rows = []
    for record in results:
        if not isinstance(record, dict):
            continue
        case_id = record.get("case_id")
        human = labels.get(case_id)
        if not isinstance(human, dict):
            continue
        human_pass = human.get("label") == "pass"
        judge_pass = bool(record.get("passed"))
        if human_pass == judge_pass:
            continue
        rows.append(
            {
                "case_id": case_id,
                "kind": "미탐 (FN)" if (not human_pass and judge_pass) else "오탐 (FP)",
                "human_label": human.get("label"),
                "judge_label": "pass" if judge_pass else "fail",
                "human_fail_axes": human.get("fail_axes") or [],
                "trap_type": human.get("trap_type"),
                "judge_failed_checks": sorted(
                    {
                        c.get("name")
                        for c in (record.get("checks") or [])
                        if isinstance(c, dict) and not c.get("passed") and c.get("name")
                    }
                ),
                "frozen": case_id in FROZEN_CASE_IDS,
            }
        )
    # 미탐을 먼저 보여준다 — 불량이 나가는 쪽이 더 급하다.
    return sorted(rows, key=lambda r: (r["kind"] != "미탐 (FN)", str(r["case_id"])))


def split_frozen_and_added(judge_results: object, human_labels: object) -> dict:
    """동결 20건과 신규 사례를 **따로** 집계한다.

    섞으면 v1↔v7 비교의 조건이 달라져 8월에 쌓은 근거가 무효가 된다.
    """
    results = judge_results if isinstance(judge_results, list) else []
    labels = human_labels if isinstance(human_labels, dict) else {}

    def tally(records):
        counts = {"true_positive": 0, "true_negative": 0,
                  "false_positive": 0, "false_negative": 0}
        for record in records:
            human = labels.get(record.get("case_id"))
            if not isinstance(human, dict):
                continue
            human_pass = human.get("label") == "pass"
            judge_pass = bool(record.get("passed"))
            if human_pass and judge_pass:
                counts["true_negative"] += 1
            elif not human_pass and not judge_pass:
                counts["true_positive"] += 1
            elif human_pass and not judge_pass:
                counts["false_positive"] += 1
            else:
                counts["false_negative"] += 1
        total = sum(counts.values())
        match = counts["true_positive"] + counts["true_negative"]
        return {
            **counts,
            "total": total,
            "match": match,
            "fraction": format_fraction(match, total),
        }

    valid = [r for r in results if isinstance(r, dict)]
    return {
        "frozen": tally([r for r in valid if r.get("case_id") in FROZEN_CASE_IDS]),
        "added": tally([r for r in valid if r.get("case_id") not in FROZEN_CASE_IDS]),
    }


def load_human_labels(cases_dir: Path | str) -> dict[str, dict]:
    """골든셋 사례의 사람 라벨을 읽는다(분석 단계 전용).

    ⚠️ judge **실행** 경로에서는 절대 부르지 않는다 — leakage 경계다.
    화면은 실행이 끝난 뒤 결과를 대조하는 자리라 읽어도 된다.
    """
    import yaml

    directory = Path(cases_dir)
    if not directory.exists():
        return {}
    labels: dict[str, dict] = {}
    for path in sorted(directory.glob("case_*.md")):
        text = path.read_text(encoding="utf-8")
        parts = text.split("---")
        if len(parts) < 3:
            continue
        try:
            meta = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        if isinstance(meta, dict) and meta.get("id"):
            labels[meta["id"]] = meta
    return labels
