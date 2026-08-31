"""재현 대조 범위가 문서 선언과 갈리지 않는지 검사한다.

`scripts/replay_verify.py`가 "재현됐다"고 말하려면 **선언한 것을 대조했다**는 게
먼저 성립해야 한다. 코드 상수와 `docs/reproducibility_scope.md`의 표가 갈리면
"선언과 다른 것을 대봤다"가 되어 R5 주장 자체가 무너진다. 그래서 이 대조를
사람 눈이 아니라 테스트로 고정한다.

**이 대조의 한계** — 문서 표의 "대상" 칸은 사람이 읽는 라벨이지 state 경로가
아니다(`metrics` 전체 · `trace_id` · `run_id` · 타임스탬프 …). 그래서 자동으로
확인되는 것은 **선언 항목의 집합이 같다**는 것까지이고, 각 항목을 어느 경로로
번역했는지(`ScopeItem.paths`)는 문서가 적어 두지 않아 기계 대조가 불가능하다.
경로 번역의 오타는 대신 `test_every_declared_path_exists_in_a_real_dump`가
잡는다 — 실제 덤프 모양에서 모든 경로가 실제로 해석되는지 확인해, 오타 난 경로가
"양쪽 다 없으니 일치"로 조용히 통과하는 것을 막는다.

예외는 §3의 「파생 경로」 표다. 이쪽은 문서가 state 경로를 직접 적어 두어
`test_ips_derived_paths_match_doc_table`이 경로까지 대조한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.evidence.replay_scope import (
    ABSENT,
    CONDITIONAL,
    EXCLUDED,
    FINGERPRINT_LABELS,
    GUARANTEED,
    IPS_DERIVED_PATHS,
    MATCH,
    MAX_REPORTED_PATHS,
    MISMATCH,
    compare_all,
    compare_item,
    resolve,
)

ROOT = Path(__file__).resolve().parents[1]

# 통합 레포에서 엔진 문서는 대시보드 문서와 섞이지 않도록 `docs/engine/` 아래 둔다.
DOCS = ROOT / "docs" / "engine"
SCOPE_DOC = DOCS / "reproducibility_scope.md"

SECTION_HEADINGS = {
    "guaranteed": "## 2. 재현 보장 대상",
    "conditional": "### 2.1 조건부 재현·반복 실측 대상",
    "excluded": "## 3. 재현 제외 대상",
}


def _table_targets(heading: str, header: str = "| 대상 |") -> list[str]:
    """해당 절에서 `header`로 시작하는 **첫 표**의 첫 칸을 순서대로 뽑는다.

    §3에는 「파생 경로」 표가 하나 더 있으므로 헤더로 표를 특정한다.
    """
    lines = SCOPE_DOC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    targets: list[str] = []
    seen_header = False
    index = start + 1
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("#"):
            break
        if line.startswith(header):
            seen_header = True
            index += 2  # 헤더 줄 + 구분선
            continue
        if seen_header:
            if not line.startswith("|"):
                break
            targets.append(line.split("|")[1].strip())
        index += 1
    return targets


def _passing_dump() -> dict:
    """§2·§2.1 경로가 모두 존재하는 성공 실행 덤프의 최소 형태."""
    return {
        "trace_id": "run-aaaaaaaaaaaa",
        "run_config": {
            "audit": {
                "llm": {
                    "rag_cite": {"latest": {"prompt_hash": {"aggregate_sha256": "rag-hash"}}},
                    "judge_eval": {"latest": {"prompt_hash": {"aggregate_sha256": "judge-hash"}}},
                }
            }
        },
        "ips": {"Unique": "고금리·강달러 충격"},
        "ips_extraction_meta": {"output_hash": "out-1", "extraction_hash": "ext-1"},
        "metrics": {"var": 1.5, "meta": {"computation_hash": "comp-1"}},
        "explanations": [{"topic": "VaR", "text": "설명"}],
        "citations": [{"chunk_id": "a.pdf::1"}],
        "judge": {
            "passed": True,
            "rubric": {
                "source_validity": {"passed": True, "reason": "근거 문구 v1"},
                "hallucination": {"passed": True, "reason": "근거 문구 v1"},
            },
        },
        "report": {
            "status": "confirmed",
            "finalized": True,
            "client_summary": {"ips": {"Unique": "고금리·강달러 충격"}},
            "governance": {
                "export_allowed": True,
                "langsmith_trace_url": "https://smith.example/a",
            },
            "reproducibility": {
                "config_hash": "cfg-1",
                "computation_hash": "comp-1",
                "approval_hash": "appr-1",
                "ips_extraction": {"output_hash": "out-1", "extraction_hash": "ext-1"},
            },
        },
    }


def _blocked_dump() -> dict:
    """차단 실행 — `decision_hash`가 있는 유일한 경우."""
    dump = _passing_dump()
    dump["judge"]["passed"] = False
    dump["report"].update({"status": "pending_manual_review", "finalized": False})
    dump["report"]["governance"].update(
        {
            "export_allowed": False,
            "manual_review_gate": {"decision_hash": "dec-1"},
        }
    )
    return dump


# ---------------------------------------------------------------------------
# 문서 ↔ 코드 선언 대조
# ---------------------------------------------------------------------------
def test_doc_tables_are_parsed_not_vacuously():
    """파서가 퇴화하면 아래 대조들이 조용히 전부 통과한다. 안전장치."""
    for key, heading in SECTION_HEADINGS.items():
        assert _table_targets(heading), f"{key}: 문서에서 '대상' 표를 읽지 못했습니다."


@pytest.mark.parametrize(
    ("key", "declared"),
    [("guaranteed", GUARANTEED), ("conditional", CONDITIONAL), ("excluded", EXCLUDED)],
)
def test_declared_labels_match_the_scope_doc(key, declared):
    """코드의 선언 목록이 문서 표와 **한 글자도 다르지 않아야** 한다.

    항목이 늘거나 줄거나 표기가 바뀌면 여기서 잡힌다. 문서를 고쳤으면
    `app/evidence/replay_scope.py`도 같이 고쳐야 한다는 뜻이다.
    """
    doc_labels = _table_targets(SECTION_HEADINGS[key])
    code_labels = [item.label for item in declared]

    assert code_labels == doc_labels, (
        f"{key}: 코드 선언과 docs/reproducibility_scope.md가 갈립니다.\n"
        f"  문서: {doc_labels}\n  코드: {code_labels}"
    )


def test_ips_derived_paths_match_doc_table():
    """§3 「파생 경로」 표는 문서가 state 경로를 직접 적어 둔 유일한 자리다."""
    doc_paths = [
        target.strip("`") for target in _table_targets(SECTION_HEADINGS["excluded"], "| 파생 경로 |")
    ]
    # 문서 표의 마지막 행은 바로 위 경로와 같은 생산 지점을 뜻하는 〃 표기라
    # 경로 자체는 5개가 모두 다르다.
    assert doc_paths == list(IPS_DERIVED_PATHS)


def test_fingerprint_labels_are_declared_in_guaranteed():
    """재현 지문 3종은 §2 안에 있어야 한다 — §3의 「제외 대상에 대한 원칙」."""
    guaranteed_labels = {item.label for item in GUARANTEED}
    assert set(FINGERPRINT_LABELS) <= guaranteed_labels
    assert len(FINGERPRINT_LABELS) == 3


def test_every_declared_path_exists_in_a_real_dump():
    """선언한 경로가 실제 덤프 모양에서 전부 해석돼야 한다.

    경로에 오타가 나면 양쪽 덤프 모두에서 안 잡혀 `ABSENT`가 되고, 그러면
    불일치로 세지 않아 **오타가 곧 통과**가 된다. 그걸 막는 검사다.
    성공 덤프와 차단 덤프의 합집합으로 본다 — `decision_hash`는 차단 실행에만 있다.
    """
    dumps = (_passing_dump(), _blocked_dump())
    unresolved: list[str] = []
    for item in GUARANTEED + CONDITIONAL + EXCLUDED:
        for path in item.paths:
            if not any(resolve(dump, path) for dump in dumps):
                unresolved.append(f"{item.label} → {path}")

    assert not unresolved, (
        "아래 경로가 어느 덤프에서도 해석되지 않습니다. 오타이거나 state 구조가 "
        "바뀐 것입니다:\n" + "\n".join(f"  {row}" for row in unresolved)
    )


# ---------------------------------------------------------------------------
# 대조 동작
# ---------------------------------------------------------------------------
def test_identical_dumps_match_everything():
    results = compare_all(_passing_dump(), _passing_dump())

    for result in results["guaranteed"]:
        assert result.status == MATCH, result.item.label
    for result in results["conditional"]:
        # decision_hash는 성공 실행에 없으므로 ABSENT가 정상이다.
        assert result.status in (MATCH, ABSENT), result.item.label


def test_absent_on_both_sides_is_not_a_mismatch():
    """차단되지 않은 실행의 `decision_hash`는 없는 게 정상이다."""
    results = compare_all(_passing_dump(), _passing_dump())
    gate = next(
        r for r in results["conditional"] if "decision_hash" in r.item.label
    )
    assert gate.status == ABSENT


def test_present_on_one_side_only_is_a_mismatch():
    """한쪽에만 있으면 구조가 달라진 것이므로 불일치다 — 비교 불가로 넘기지 않는다."""
    result = compare_item(
        next(i for i in CONDITIONAL if "decision_hash" in i.label),
        _passing_dump(),
        _blocked_dump(),
    )
    assert result.status == MISMATCH
    assert result.diverged == ("report.governance.manual_review_gate.decision_hash",)


def test_rubric_reason_is_not_compared_but_passed_is():
    """§3이 제외한 `reason` 문구 때문에 §2.1 판정이 흔들리면 안 된다."""
    right = _passing_dump()
    right["judge"]["rubric"]["source_validity"]["reason"] = "근거 문구 v2 — 전혀 다른 산문"

    results = compare_all(_passing_dump(), right)
    judge_item = next(r for r in results["conditional"] if "6축" in r.item.label)
    excluded_reason = next(r for r in results["excluded"] if "reason" in r.item.label)

    assert judge_item.status == MATCH
    assert excluded_reason.status == MISMATCH


def test_fingerprint_value_is_carried_for_display():
    results = compare_all(_passing_dump(), _passing_dump())
    config_hash = next(r for r in results["guaranteed"] if r.item.label == "`config_hash`")

    assert config_hash.value == "cfg-1"


def test_dict_mismatch_reports_leaf_path_not_just_the_root():
    """`metrics` 전체처럼 dict를 통째로 대조하는 항목은 leaf까지 짚어야 한다.

    "metrics가 다르다"만 보고하면 현장에서 원인을 못 찾는다.
    """
    right = _passing_dump()
    right["metrics"]["meta"]["computation_hash"] = "comp-CHANGED"

    result = compare_item(
        next(i for i in GUARANTEED if i.label == "`metrics` 전체"),
        _passing_dump(),
        right,
    )

    assert result.status == MISMATCH
    assert result.diverged == ("metrics.meta.computation_hash",)


def test_leaf_diff_report_is_capped_but_total_is_kept():
    """불일치 leaf가 수백 개여도 화면이 무너지면 안 된다 — 상한을 두되 총계는 남긴다.

    문서 §4.1은 모드 A에서 갈린 leaf가 760개였다고 기록한다. 그걸 다 쏟으면
    결론이 안 읽힌다.
    """
    right = _passing_dump()
    right["metrics"] = {f"key_{i}": i for i in range(50)}

    result = compare_item(
        next(i for i in GUARANTEED if i.label == "`metrics` 전체"),
        _passing_dump(),
        right,
    )

    assert result.status == MISMATCH
    assert len(result.diverged) == MAX_REPORTED_PATHS
    assert result.diverged_total > MAX_REPORTED_PATHS


def test_absent_item_has_no_diverged_paths():
    """`ABSENT`는 실패가 아니므로 어긋난 경로를 만들지 않는다."""
    result = compare_item(
        next(i for i in CONDITIONAL if "decision_hash" in i.label),
        _passing_dump(),
        _passing_dump(),
    )

    assert result.status == ABSENT
    assert result.diverged == ()
    assert result.diverged_total == 0
