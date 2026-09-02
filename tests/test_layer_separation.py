"""3계층 분리를 **코드로** 강제한다.

README 가 이렇게 적어 놓았다.

    R6 3계층 분리 | `engine/deterministic/` LLM import 금지(**코드 강제**) + mermaid 시각 분리

그런데 2026-08-31 확인 결과 **강제하는 것이 없었다.** `metrics.py`·`returns.py`·
`stress.py` 독스트링에 "금지"라고 적혀 있을 뿐이고, 새로 추가한 `tax.py`·
`compare.py` 에는 그 문구조차 없었다.

R6 자체가 이런 상황을 겨냥한 항목이다.

    README·발표에 적은 기술 스택이 실제로 도는 코드와 같을 것

문서에만 있고 동작이 다르면 통제가 없는 것과 같다 — R3 가 judge 에 대해
말한 것과 같은 논리다. 그래서 여기서 실제로 막는다.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "engine" / "deterministic"

#: 결정론 계층이 기대면 안 되는 모듈. 최상위 이름으로 판정한다.
FORBIDDEN_ROOTS = {
    "langchain",
    "langchain_openai",
    "langchain_chroma",
    "langgraph",
    "langsmith",
    "openai",
    "chromadb",
    "streamlit",
}

#: 같은 저장소 안에서도 기대면 안 되는 패키지.
FORBIDDEN_INTERNAL_PREFIXES = (
    "engine.llm",
    "engine.rag",
    "engine.judge",
    "console.",
)


def _engine_modules() -> list[Path]:
    return sorted(p for p in ENGINE_DIR.glob("*.py") if p.name != "__init__.py")


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module)
    return names


def test_engine_directory_is_not_empty():
    """대상이 없으면 이 테스트가 조용히 통과한다 — 그것부터 막는다."""
    assert _engine_modules(), f"{ENGINE_DIR} 에 검사할 모듈이 없다 — 경로가 바뀌었는지 확인"


@pytest.mark.parametrize("path", _engine_modules(), ids=lambda p: p.name)
def test_engine_module_has_no_llm_dependency(path):
    """결정론 계층이 LLM·RAG·UI 에 기대면 재현성 주장이 무너진다."""
    offenders = []
    for name in _imported_names(path):
        root = name.split(".")[0]
        if root in FORBIDDEN_ROOTS:
            offenders.append(name)
        elif name.startswith(FORBIDDEN_INTERNAL_PREFIXES):
            offenders.append(name)
    assert not offenders, (
        f"{path.name} 이 결정론 계층에서 금지된 모듈을 import 한다: {offenders}. "
        "README 의 'R6 3계층 분리 — engine/deterministic/ LLM import 금지'와 어긋난다."
    )


@pytest.mark.parametrize("path", _engine_modules(), ids=lambda p: p.name)
def test_engine_module_states_the_rule(path):
    """새 모듈을 만들 때 규칙을 모르고 지나가지 않도록 독스트링에 적게 한다."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    doc = ast.get_docstring(tree) or ""
    assert doc.strip(), f"{path.name} 에 모듈 독스트링이 없다"
    assert ("결정론" in doc) or ("LLM" in doc) or ("llm" in doc), (
        f"{path.name} 독스트링이 결정론 계층임을 밝히지 않는다. "
        "이 계층의 제약을 다음 사람이 모르고 지나간다."
    )


def test_nodes_may_import_engine_but_not_the_other_way():
    """의존 방향이 뒤집히면 계층이 무너진다 — engine 은 nodes 를 모른다."""
    for path in _engine_modules():
        for name in _imported_names(path):
            assert not name.startswith("engine.nodes"), (
                f"{path.name} 이 engine.nodes 를 import 한다 — 계층 방향이 뒤집혔다"
            )
