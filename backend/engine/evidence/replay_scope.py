"""재현 대조 범위의 코드 측 SSOT — `docs/reproducibility_scope.md`의 선언을 옮긴 것.

**이 파일은 선언의 주인이 아니다.** 무엇을 재현 대상으로 삼는가는
`docs/reproducibility_scope.md` §2·§2.1·§3이 정하고, 여기는 그 표를 기계가 읽을 수
있는 형태로 옮겨 적은 것뿐이다. 둘이 갈리면 재현 대조가 "선언한 것과 다른 것을
대봤다"가 되어 R5 주장 자체가 무너지므로, `tests/test_replay_scope.py`가 매 실행
문서 표와 대조한다.

`label`은 문서 표의 "대상" 칸을 **한 글자도 바꾸지 않고** 옮긴다 — 그래야 기계
대조가 성립한다. `paths`는 그 선언을 실제 state 경로로 옮긴 엔지니어링 번역이며,
문서가 경로까지 적어 두지 않으므로 이쪽은 자동 대조 대상이 아니다(한계는
`tests/test_replay_scope.py`의 docstring에 적었다).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

#: 경로에서 dict 전체를 훑는 자리. `judge.rubric.*.passed`처럼 축 이름을 모르는
#: 채로 "각 축의 passed만" 집어내야 할 때 쓴다. §3이 `judge.rubric.*.reason`을
#: 제외 대상으로 선언했으므로 rubric을 통째로 비교하면 안 된다.
WILDCARD = "*"


@dataclass(frozen=True)
class ScopeItem:
    """재현 선언 1건."""

    #: `docs/reproducibility_scope.md` 표의 "대상" 칸 원문. 바꾸면 테스트가 잡는다.
    label: str
    #: 실제로 대조할 state 경로들. 점으로 잇고 `*`는 dict 전체를 뜻한다.
    paths: tuple[str, ...]


# --- §2 무조건 보장 -----------------------------------------------------------
#: 동일 입력·동일 결정론 설정이면 **완전히 일치해야 한다.** 하나라도 어긋나면
#: 범위를 조정하지 말고 원인을 찾는다(문서 §9).
GUARANTEED: tuple[ScopeItem, ...] = (
    ScopeItem("`config_hash`", ("report.reproducibility.config_hash",)),
    ScopeItem("`computation_hash`", ("report.reproducibility.computation_hash",)),
    ScopeItem("`approval_hash`", ("report.reproducibility.approval_hash",)),
    ScopeItem("`metrics` 전체", ("metrics",)),
    ScopeItem("`explanations` 전체", ("explanations",)),
    ScopeItem(
        "`prompt_hash.rag_cite`",
        ("run_config.audit.llm.rag_cite.latest.prompt_hash",),
    ),
)

#: 재현 "지문"으로 제시하는 세 해시. 문서 §3 「제외 대상에 대한 원칙」이 이 셋으로
#: 한정했다. 출력에서 값까지 보여 주는 대상이다.
FINGERPRINT_LABELS: tuple[str, ...] = (
    "`config_hash`",
    "`computation_hash`",
    "`approval_hash`",
)


# --- §2.1 조건부 --------------------------------------------------------------
#: 반복 실측에서 일치했으나 LLM 판정이 포함되어 **항상 같다고 보장하지 않는다.**
#: 대조는 하되, 불일치가 곧 결함은 아니라는 것을 출력에서 구분해 보인다.
CONDITIONAL: tuple[ScopeItem, ...] = (
    ScopeItem(
        "Judge 6축 판정·`judge.passed`",
        # rubric을 통째로 비교하면 §3이 제외한 reason 문구까지 걸린다. passed만 본다.
        ("judge.rubric.*.passed", "judge.passed"),
    ),
    ScopeItem(
        "`report.status`·`report.finalized`·`export_allowed`",
        ("report.status", "report.finalized", "report.governance.export_allowed"),
    ),
    ScopeItem(
        "`manual_review_gate.decision_hash`",
        ("report.governance.manual_review_gate.decision_hash",),
    ),
)


# --- §3 재현 제외 -------------------------------------------------------------
#: 대조하지 않는다. 다만 **화면에는 함께 낸다** — 감사자가 차이를 먼저 발견하기
#: 전에 우리가 밝히는 것이 모의 감사 런북 §4의 원칙이다.
EXCLUDED: tuple[ScopeItem, ...] = (
    ScopeItem("`citations` 집합·순서", ("citations",)),
    ScopeItem("`judge.rubric.*.reason` 문구", ("judge.rubric.*.reason",)),
    ScopeItem(
        "`prompt_hash.judge_eval`",
        ("run_config.audit.llm.judge_eval.latest.prompt_hash",),
    ),
    # run_id는 번들이 부여하는 값이라 state에 없다. state에 있는 것만 적는다.
    ScopeItem("`trace_id` · `run_id` · 타임스탬프", ("trace_id",)),
    ScopeItem("LangSmith trace URL", ("report.governance.langsmith_trace_url",)),
    ScopeItem(
        "`ips` 추출 산출물 (`ips.Unique` 및 파생 5개 경로)",
        (
            "ips.Unique",
            # 아래 5개는 문서 §3의 「파생 경로」 표를 그대로 옮긴 것이다.
            "ips_extraction_meta.output_hash",
            "ips_extraction_meta.extraction_hash",
            "report.client_summary.ips.Unique",
            "report.reproducibility.ips_extraction.output_hash",
            "report.reproducibility.ips_extraction.extraction_hash",
        ),
    ),
)

#: 문서 §3의 「파생 경로」 표에 실린 state 경로. 대상 표와 달리 이쪽은 문서가
#: 경로를 직접 적어 두어 자동 대조가 가능하다.
IPS_DERIVED_PATHS: tuple[str, ...] = (
    "ips_extraction_meta.output_hash",
    "ips_extraction_meta.extraction_hash",
    "report.client_summary.ips.Unique",
    "report.reproducibility.ips_extraction.output_hash",
    "report.reproducibility.ips_extraction.extraction_hash",
)


# --- 경로 해석 ----------------------------------------------------------------
#: 값을 못 찾았음을 뜻하는 표식. `None`을 쓰면 "값이 None"과 구분되지 않는다.
MISSING = object()


def _walk(node: Any, parts: tuple[str, ...], prefix: str) -> Iterator[tuple[str, Any]]:
    if not parts:
        yield prefix, node
        return
    head, rest = parts[0], parts[1:]
    if head == WILDCARD:
        if not isinstance(node, dict):
            return
        for key in sorted(node):
            yield from _walk(node[key], rest, f"{prefix}.{key}" if prefix else key)
        return
    if not isinstance(node, dict) or head not in node:
        return
    yield from _walk(node[head], rest, f"{prefix}.{head}" if prefix else head)


def resolve(dump: dict, path: str) -> dict[str, Any]:
    """경로가 가리키는 값들을 `{실제경로: 값}`으로 돌려준다.

    와일드카드가 없으면 항목 0개(못 찾음) 또는 1개다. 빈 dict는 "그 경로가 이
    덤프에 없다"는 뜻이며, 값이 `None`인 것과 구분된다 — 없는 것과 비어 있는 것을
    섞으면 오타 난 경로가 "양쪽 다 없으니 일치"로 조용히 통과한다.
    """
    return dict(_walk(dump, tuple(path.split(".")), ""))


# --- 대조 --------------------------------------------------------------------
#: 항목 하나의 대조 결과.
MATCH = "match"          # 양쪽에 있고 같다
MISMATCH = "mismatch"    # 값이 다르거나 한쪽에만 있다
ABSENT = "absent"        # 양쪽 모두에 없다 — 해당 없는 실행(예: 차단 안 된 실행)


#: 한 항목에서 보고할 어긋난 경로 수 상한. `metrics` 전체처럼 dict를 통째로
#: 대조하는 항목은 한 번 갈리면 leaf가 수백 개 나올 수 있는데(문서 §4.1 실측:
#: 모드 A 760건), 그걸 다 쏟으면 화면에서 결론이 안 읽힌다.
MAX_REPORTED_PATHS = 8


def leaf_diffs(left: Any, right: Any, prefix: str) -> list[str]:
    """두 값이 갈린 **말단 경로**를 찾는다.

    `metrics` 전체처럼 dict를 통째로 대조하는 항목에서 "metrics가 다르다"만
    보고하면 현장에서 원인을 못 찾는다. 어느 leaf가 갈렸는지까지 짚어 준다.
    타입이 다르거나 dict가 아니면 그 지점이 곧 말단이다.
    """
    if isinstance(left, dict) and isinstance(right, dict):
        diffs: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                diffs.append(child)
            elif left[key] != right[key]:
                diffs.extend(leaf_diffs(left[key], right[key], child))
        return diffs
    return [prefix]


@dataclass(frozen=True)
class ItemResult:
    item: ScopeItem
    status: str
    #: 어긋난 실제 경로들. `mismatch`일 때만 채워진다.
    diverged: tuple[str, ...]
    #: 지문 표시용 값. 양쪽이 같을 때만 채운다.
    value: Any = None
    #: `diverged`가 상한에 걸려 잘렸다면 전체 개수.
    diverged_total: int = 0


def compare_item(item: ScopeItem, left: dict, right: dict) -> ItemResult:
    """선언 1건을 대조한다.

    **한쪽에만 있는 경로는 불일치다.** 구조가 달라진 것이므로 "값 비교 불가"로
    넘기지 않는다. 양쪽 모두 없으면 그 실행에 해당 없는 항목이라 `ABSENT`다 —
    차단되지 않은 실행의 `decision_hash`가 그 경우다.
    """
    diverged: list[str] = []
    seen_any = False
    values: list[Any] = []
    for path in item.paths:
        left_hits = resolve(left, path)
        right_hits = resolve(right, path)
        if not left_hits and not right_hits:
            continue
        seen_any = True
        for key in sorted(set(left_hits) | set(right_hits)):
            lv = left_hits.get(key, MISSING)
            rv = right_hits.get(key, MISSING)
            if lv is MISSING or rv is MISSING:
                diverged.append(key)
            elif lv != rv:
                diverged.extend(leaf_diffs(lv, rv, key))
            else:
                values.append(lv)
    if not seen_any:
        return ItemResult(item, ABSENT, ())
    if diverged:
        return ItemResult(
            item,
            MISMATCH,
            tuple(diverged[:MAX_REPORTED_PATHS]),
            diverged_total=len(diverged),
        )
    return ItemResult(item, MATCH, (), values[0] if len(values) == 1 else None)


def compare_all(left: dict, right: dict) -> dict[str, list[ItemResult]]:
    """§2·§2.1·§3 전부를 대조한다. §3도 결과를 만들되 판정에는 쓰지 않는다."""
    return {
        "guaranteed": [compare_item(i, left, right) for i in GUARANTEED],
        "conditional": [compare_item(i, left, right) for i in CONDITIONAL],
        "excluded": [compare_item(i, left, right) for i in EXCLUDED],
    }
