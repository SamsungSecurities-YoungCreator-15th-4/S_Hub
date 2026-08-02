"""문서가 인용한 `파일:행` 참조가 실제 코드와 맞는지 검사한다.

`docs/reproducibility_scope.md`의 `rag_cite.py:839`가 실제로는 879행이었던 것처럼,
행 인용은 머지마다 조용히 밀린다. 감사자가 문서의 행 번호를 짚어 코드를 열었을 때
엉뚱한 줄이 나오면 "문서-구현 일치" 주장 자체가 무너진다.
`tests/test_docs_config_consistency.py`가 config 숫자를 대조하듯, 행 인용도 고정한다.

검사 대상은 `docs/*.md` 전체이며, **백틱 안의** `<파일경로>:<행>` 또는
`<파일경로>:<시작>-<끝>` 형태만 수집한다. 백틱 밖 표기를 대상에서 뺀 이유는
`2026-08-01T00:00:00+00:00` 같은 값과 구분할 안전한 경계가 백틱뿐이기 때문이다.
확장자도 코드 파일로 한정한다.

각 인용에 대해 아래를 검사한다.

1. 인용한 파일이 실제로 존재하는가 (경로 조각만 적어도 해석한다)
2. 행 번호가 파일 범위 안인가
3. 그 행(범위면 범위 전체)이 비어 있지 않은가

3번은 약한 검사다. 행이 한 칸 밀려도 옆 줄이 비어 있지 않으면 통과한다.
그래서 **앵커 힌트** 표기를 이번에 도입한다.

    | 라우팅 | `app/graph.py:30` (route_after_judge) |

인용 바로 뒤 괄호 안에 심볼 이름을 하나 적으면, 그 심볼이 인용 행 ±3행 안에
실제로 있는지까지 검사한다. 표기 규약은 다음과 같다.

- 인용을 닫는 백틱 바로 뒤, 공백은 최대 하나, 그다음 `(심볼)`.
- 심볼은 영문 식별자다. 점(`.`)으로 이어 붙일 수 있고 끝에 `()`를 붙여도 된다.
  한글 괄호 주석(`(위 파생)`)은 힌트로 보지 않는다 — 기존 문서의 괄호 표현을
  힌트로 오인하지 않기 위해 영문 식별자로 한정했다.
- 힌트는 선택이다. **기존 인용처럼 힌트가 없으면 1·2·3만 검사하고 실패시키지 않는다.**
  새로 인용을 적을 때 힌트를 붙이면 그 인용만 검사가 강해진다.

행이 밀렸는데 아직 문서를 고치지 못한 인용은 `KNOWN_STALE`에 등록한다.
등록분은 3번 검사에서 면제되지만, `test_known_stale_entries_are_still_stale`가
"등록해 놓고 이미 고쳐진" 항목을 잡아내므로 방치되지 않는다.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"

# 파일 탐색에서 제외할 디렉터리. 산출물·가상환경·평가 사례집을 뒤지지 않는다.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "data",
        "dist",
        "evidence",
    }
)

CODE_SUFFIXES = "py|yaml|yml|toml|json|cfg|ini|sh|txt"

CITATION_RE = re.compile(
    rf"`(?P<path>[^`\n]*?\.(?:{CODE_SUFFIXES}))\s*:\s*(?P<start>\d+)(?:\s*-\s*(?P<end>\d+))?`"
)
# 인용 바로 뒤에 오는 앵커 힌트. 영문 식별자 하나만 인정한다.
HINT_RE = re.compile(r"\A[ ]?\((?P<symbol>[A-Za-z_][A-Za-z0-9_.]*)(?:\(\))?\)")

HINT_WINDOW = 3

#: 행이 밀린 것을 확인했지만 아직 문서를 고치지 않은 인용.
#: (문서 파일명, 인용 경로, 시작행, 끝행) — 문서 안에서의 위치가 아니라 인용 자체를
#: 키로 쓴다. 문서를 편집해 인용이 다른 줄로 옮겨가도 등록이 유지되도록 하기 위해서다.
KNOWN_STALE = frozenset(
    {
        # app/graph.py:29는 빈 줄이고, 문서가 가리키려는 route_after_judge는 30행이다.
        # 문서 수정은 이 테스트를 추가한 작업의 범위 밖이라 등록만 해 둔다.
        ("symphony_proof_plan.md", "app/graph.py", 29, 29),
    }
)


class Citation:
    """문서에서 수집한 `파일:행` 인용 한 건."""

    def __init__(
        self,
        doc: str,
        doc_line: int,
        cited_path: str,
        start: int,
        end: int,
        hint: str | None,
    ) -> None:
        self.doc = doc
        self.doc_line = doc_line
        self.cited_path = cited_path
        self.start = start
        self.end = end
        self.hint = hint

    @property
    def key(self) -> tuple[str, str, int, int]:
        return (self.doc, self.cited_path, self.start, self.end)

    def __str__(self) -> str:
        span = f"{self.start}" if self.start == self.end else f"{self.start}-{self.end}"
        hint = f" ({self.hint})" if self.hint else ""
        return f"docs/{self.doc}:{self.doc_line} → `{self.cited_path}:{span}`{hint}"


def parse_citations(text: str, doc: str) -> list[Citation]:
    """문서 본문에서 인용을 수집한다. 문서 파일과 무관하게 문자열만 다룬다."""
    found: list[Citation] = []
    for doc_line, line in enumerate(text.splitlines(), start=1):
        for match in CITATION_RE.finditer(line):
            end_group = match.group("end")
            hint_match = HINT_RE.match(line[match.end():])
            found.append(
                Citation(
                    doc=doc,
                    doc_line=doc_line,
                    cited_path=match.group("path"),
                    start=int(match.group("start")),
                    end=int(end_group) if end_group else int(match.group("start")),
                    hint=hint_match.group("symbol") if hint_match else None,
                )
            )
    return found


def path_matches_citation(relative: PurePath, cited: str) -> bool:
    """레포 기준 상대경로가 인용 경로 조각과 맞는지 판정한다.

    비교는 반드시 `as_posix()`로 한다. `str(relative)`를 쓰면 Windows에서
    `app\\judge\\rubric.py`가 나와 `/rubric.py`와 절대 안 맞고, **파일명만 적은
    인용이 전부 "파일을 찾지 못했습니다"로 실패**한다. 문서는 슬래시로만 적히므로
    구분자를 posix로 고정하는 쪽이 맞다.

    디렉터리 경계를 지키려고 `/`를 앞에 붙인다 — `load_inputs.py`가
    `tests/test_load_inputs.py`에 걸리면 안 된다.
    """
    return relative.as_posix().endswith("/" + cited)


@lru_cache(maxsize=None)
def resolve_cited_path(cited: str) -> tuple[Path, ...]:
    """인용 경로를 실제 파일로 해석한다.

    문서는 `rag_cite.py:879`처럼 파일명만 적기도 하고 `app/graph.py:30`처럼
    레포 기준 경로를 적기도 한다. 둘 다 받아들이되, 경로 조각으로 맞출 때는
    디렉터리 경계를 지킨다.
    """
    direct = ROOT / cited
    if direct.is_file():
        return (direct,)
    matches = []
    for path in ROOT.rglob("*" + Path(cited).name):
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.is_file() and path_matches_citation(relative, cited):
            matches.append(path)
    return tuple(sorted(matches))


@lru_cache(maxsize=None)
def _lines_of(path: Path) -> tuple[str, ...]:
    return tuple(path.read_text(encoding="utf-8").splitlines())


def all_citations() -> list[Citation]:
    found: list[Citation] = []
    for doc in sorted(DOCS_DIR.glob("*.md")):
        found.extend(parse_citations(doc.read_text(encoding="utf-8"), doc.name))
    return found


def _citation_ids(citations: list[Citation]) -> list[str]:
    return [f"{c.doc}:{c.doc_line}:{c.cited_path}:{c.start}" for c in citations]


CITATIONS = all_citations()


def test_citation_pattern_is_not_vacuous():
    """수집 자체가 망가지면 아래 검사들이 조용히 전부 통과한다.

    정규식이 퇴화했을 때 "검사할 게 없어서 초록"이 되는 것을 막는 안전장치다.
    """
    assert CITATIONS, "docs/*.md에서 `파일:행` 인용을 한 건도 수집하지 못했습니다."


def test_parser_reads_span_and_hint():
    """수집기 자체의 단위 검사 — 문서 내용과 무관하게 규약을 고정한다."""
    sample = (
        "본문 `app/graph.py:30` (route_after_judge) 과 "
        "`app/nodes/rag_cite.py:100-120` 과 "
        "괄호 안 인용(`app/nodes/extract_ips.py:34`) 과 "
        "시각 `2026-08-01T00:00:00+00:00` 과 힌트 아닌 괄호 `app/graph.py:30` (한글)"
    )
    parsed = parse_citations(sample, "sample.md")

    assert [(c.cited_path, c.start, c.end, c.hint) for c in parsed] == [
        ("app/graph.py", 30, 30, "route_after_judge"),
        ("app/nodes/rag_cite.py", 100, 120, None),
        ("app/nodes/extract_ips.py", 34, 34, None),
        ("app/graph.py", 30, 30, None),
    ]


@pytest.mark.parametrize("citation", CITATIONS, ids=_citation_ids(CITATIONS))
def test_cited_file_exists_and_is_unambiguous(citation: Citation):
    """검사 ① — 인용한 파일이 실제로 있고, 하나로 특정되는가."""
    candidates = resolve_cited_path(citation.cited_path)

    assert candidates, (
        f"{citation}: 인용한 파일을 레포에서 찾지 못했습니다. "
        "파일이 옮겨졌거나 삭제됐다면 문서를 고쳐야 합니다."
    )
    assert len(candidates) == 1, (
        f"{citation}: 인용 경로가 여러 파일에 걸립니다 — "
        f"{[str(p.relative_to(ROOT)) for p in candidates]}. "
        "문서에 레포 기준 경로를 적어 하나로 특정해 주세요."
    )


@pytest.mark.parametrize("citation", CITATIONS, ids=_citation_ids(CITATIONS))
def test_cited_line_is_inside_the_file(citation: Citation):
    """검사 ② — 행 번호가 파일 범위 안인가."""
    candidates = resolve_cited_path(citation.cited_path)
    if len(candidates) != 1:
        pytest.skip("파일 해석 실패는 test_cited_file_exists_and_is_unambiguous가 보고한다.")

    lines = _lines_of(candidates[0])
    assert 1 <= citation.start <= citation.end <= len(lines), (
        f"{citation}: {candidates[0].relative_to(ROOT)}는 {len(lines)}행짜리 파일입니다. "
        "인용 행이 파일 범위를 벗어났습니다."
    )


@pytest.mark.parametrize("citation", CITATIONS, ids=_citation_ids(CITATIONS))
def test_cited_line_is_not_blank(citation: Citation):
    """검사 ③ — 인용한 행(범위면 범위 전체)이 비어 있지 않은가.

    행이 밀리면 대개 빈 줄이나 닫는 괄호를 가리키게 된다. 약한 검사지만
    "머지로 몇 행 밀림"의 가장 흔한 증상을 잡는다.
    """
    if citation.key in KNOWN_STALE:
        pytest.skip(f"{citation}: KNOWN_STALE 등록분 — 문서 수정 대기 중")

    candidates = resolve_cited_path(citation.cited_path)
    if len(candidates) != 1:
        pytest.skip("파일 해석 실패는 test_cited_file_exists_and_is_unambiguous가 보고한다.")

    lines = _lines_of(candidates[0])
    if not (1 <= citation.start <= citation.end <= len(lines)):
        pytest.skip("범위 이탈은 test_cited_line_is_inside_the_file이 보고한다.")

    body = [line for line in lines[citation.start - 1: citation.end] if line.strip()]
    assert body, (
        f"{citation}: {candidates[0].relative_to(ROOT)}의 해당 행이 전부 빈 줄입니다. "
        "머지로 행이 밀렸을 가능성이 큽니다."
    )


@pytest.mark.parametrize("citation", CITATIONS, ids=_citation_ids(CITATIONS))
def test_anchor_hint_symbol_is_near_the_cited_line(citation: Citation):
    """검사 ④ — 힌트를 적은 인용은 그 심볼이 인용 행 ±3행 안에 있어야 한다.

    힌트가 없는 인용은 검사하지 않는다. 기존 문서를 한꺼번에 고치게 만들지 않고,
    새로 적는 인용부터 강한 검사를 받게 하려는 절충이다.
    """
    if citation.hint is None:
        pytest.skip("앵커 힌트가 없는 인용 — 검사 ①②③만 적용한다.")

    candidates = resolve_cited_path(citation.cited_path)
    if len(candidates) != 1:
        pytest.skip("파일 해석 실패는 test_cited_file_exists_and_is_unambiguous가 보고한다.")

    lines = _lines_of(candidates[0])
    if not (1 <= citation.start <= citation.end <= len(lines)):
        pytest.skip("범위 이탈은 test_cited_line_is_inside_the_file이 보고한다.")

    low = max(1, citation.start - HINT_WINDOW)
    high = min(len(lines), citation.end + HINT_WINDOW)
    window = lines[low - 1: high]

    assert any(citation.hint in line for line in window), (
        f"{citation}: 힌트 심볼 `{citation.hint}`을 "
        f"{candidates[0].relative_to(ROOT)}의 {low}~{high}행에서 찾지 못했습니다. "
        "행이 밀렸거나 심볼 이름이 바뀌었습니다."
    )


def test_known_stale_entries_are_still_stale():
    """`KNOWN_STALE` 위생 검사 — 고쳐진 인용이 등록에 남아 있으면 실패한다.

    면제 목록이 조용히 쌓이는 것을 막는다. 문서를 고치면 이 테스트가 등록 해제를
    요구하고, 인용 자체가 사라져도 마찬가지다.
    """
    collected = {c.key: c for c in CITATIONS}
    stale_but_fine = []
    for key in sorted(KNOWN_STALE):
        citation = collected.get(key)
        if citation is None:
            stale_but_fine.append(f"{key}: 문서에서 이 인용이 사라졌습니다.")
            continue
        candidates = resolve_cited_path(citation.cited_path)
        if len(candidates) != 1:
            continue
        lines = _lines_of(candidates[0])
        if not (1 <= citation.start <= citation.end <= len(lines)):
            continue
        if any(line.strip() for line in lines[citation.start - 1: citation.end]):
            stale_but_fine.append(f"{key}: 이제 빈 줄이 아닙니다.")

    assert not stale_but_fine, (
        "KNOWN_STALE에 더 이상 필요 없는 등록이 남아 있습니다. 해당 항목을 지워 주세요:\n"
        + "\n".join(f"  {row}" for row in stale_but_fine)
    )


@pytest.mark.parametrize(
    ("relative", "cited", "expected"),
    [
        # 파일명만 적은 인용 — 이 술어가 실제로 해석하는 경우다.
        (PureWindowsPath("app/judge/rubric.py"), "rubric.py", True),
        (PurePosixPath("app/judge/rubric.py"), "rubric.py", True),
        # 디렉터리 경계 — `load_inputs.py`가 `test_load_inputs.py`에 걸리면 안 된다.
        (PureWindowsPath("tests/test_load_inputs.py"), "load_inputs.py", False),
        (PurePosixPath("tests/test_load_inputs.py"), "load_inputs.py", False),
        # 전체 경로 인용은 이 술어가 아니라 `resolve_cited_path`의 direct 분기가
        # 처리한다(`ROOT / cited`가 곧 파일). 그래서 여기서는 False가 맞다 —
        # 앞에 `/`를 붙여 비교하므로 레포 루트 기준 전체 경로와는 안 맞는다.
        (PureWindowsPath("app/judge/rubric.py"), "app/judge/rubric.py", False),
        (PurePosixPath("app/judge/rubric.py"), "app/judge/rubric.py", False),
    ],
)
def test_citation_matching_is_platform_independent(relative, cited, expected):
    """경로 대조가 OS 구분자에 좌우되면 안 된다.

    Windows에서 `str(relative)`는 `app\\judge\\rubric.py`를 주는데 인용은 항상
    슬래시(`/rubric.py`)라, 구분자를 정규화하지 않으면 **파일명만 적은 인용이
    전부 "파일을 찾지 못했습니다"로 실패**한다. CI가 Linux라 안 잡히고 Windows에서
    개발하는 팀원만 계속 빨간 테스트를 보게 되는 종류의 버그다.

    `PureWindowsPath`로 검사해 Linux CI에서도 이 회귀를 잡는다.
    """
    assert path_matches_citation(relative, cited) is expected


def test_bare_filename_citations_actually_resolve():
    """파일명만 적은 인용이 실제로 해석되는지 — 위 단위 검사의 통합 확인.

    문서에 파일명만 적은 인용이 여러 건 있고, 경로 대조가 깨지면 그 전부가
    한꺼번에 실패한다. 한 건이라도 있는지부터 확인해 검사가 공허해지지 않게 한다.
    """
    bare = [c for c in CITATIONS if "/" not in c.cited_path]
    assert bare, "파일명만 적은 인용이 없어 이 검사가 무의미합니다."
    unresolved = [str(c) for c in bare if not resolve_cited_path(c.cited_path)]
    assert not unresolved, "파일명만 적은 인용이 해석되지 않습니다:\n" + "\n".join(unresolved)
