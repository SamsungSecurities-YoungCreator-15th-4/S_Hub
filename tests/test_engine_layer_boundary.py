"""결정론 계층(`engine/engine/`)의 import 경계를 강제한다 — AGENTS.md 불변 규칙 3.

규칙 자체는 처음부터 문서에 있었지만 강제하는 것이 사람 눈뿐이었다. 이 계층이
뚫리는 방식은 대개 조용하다 — 노드에서 쓰던 유틸을 "잠깐" 가져다 쓰려고
`from engine.llm...` 한 줄을 넣으면, 계산 결과가 모델 응답에 의존하기 시작하는데
테스트는 그대로 초록이다. 그때 깨지는 것은 import 하나가 아니라 불변 규칙 1
(재현성)과 2(화이트박스)다. VaR·스트레스 숫자에 붙은 computation_hash 가
"같은 입력이면 같은 결과"를 더 이상 보증하지 못하기 때문이다.

이 테스트는 **AST 만 읽고 engine 패키지를 import 하지 않는다.** 그래서
langgraph·langchain 이 설치되지 않은 환경에서도 돌고, 무엇보다 금지 대상을
직접 import 해서 검사하는 자기모순을 피한다.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYER = ROOT / "engine" / "engine"

# LLM 스택 — 이 계층에 들어오면 노드가 결정론이 아니게 된다.
# 최상위 모듈명 기준이며, `langchain_openai` 처럼 접두사가 같은 배포판까지 함께 막는다.
FORBIDDEN_PREFIXES = (
    "langchain",
    "langgraph",
    "langsmith",
    "openai",
    "anthropic",
    "chromadb",
    "tiktoken",
)

# 수치 계산에 허용되는 서드파티. AGENTS.md 는 "순수 파이썬/numpy" 라고 쓰지만
# 실제 계층은 pandas(시계열 정렬)·scipy(정규분포 분위수)까지 쓴다.
# 여기에 이름을 더하는 것은 계층의 의존 범위를 넓히는 결정이므로 팀 합의 사항이다.
#
# yfinance 는 이 목록에서 유일하게 네트워크를 타는 예외다. 실데이터로 계산한다는
# 금융 도메인 원칙(AGENTS.md — "가짜/더미 데이터가 아니라 실제 시장 데이터")상
# 시세 조회 자체는 이 계층에 있어야 하고, 재현성은 import 를 막는 대신 세 장치로
# 지킨다: `_fetch_real_returns` 안의 지연 import(더미 경로는 네트워크 무의존),
# as_of_date 고정(DEFAULT_AS_OF), 그리고 요청 파라미터를 키로 쓰는 parquet 캐시
# (`load_real_returns`). LLM 호출과 달리 같은 기준일이면 같은 시계열이 온다.
ALLOWED_THIRD_PARTY = {"numpy", "pandas", "scipy", "yfinance"}

# 같은 `engine.*` 안이라도 LLM 을 끌고 오는 하위 패키지는 막는다.
# 직접 import 는 없어도 이 경로들을 타면 결국 langchain 이 딸려 들어온다.
FORBIDDEN_INTERNAL = {
    "engine.llm",
    "engine.nodes",
    "engine.rag",
    "engine.judge",
    "engine.evaluation",
    "engine.observability",
}


def _layer_files() -> list[Path]:
    return sorted(p for p in LAYER.rglob("*.py") if "__pycache__" not in p.parts)


def _package_parts(path: Path, root: Path) -> list[str]:
    """`engine/engine/metrics.py` → ['engine', 'engine'] (상대 import 해석 기준)."""
    return list(path.relative_to(root).parent.parts)


def _imported_modules(path: Path, root: Path = ROOT) -> list[tuple[str, int]]:
    """파일이 import 하는 모듈의 완전한 점 표기 이름과 행 번호를 모은다.

    상대 import 는 파일 위치를 기준으로 절대 이름으로 되돌린다 — `from ..llm import x`
    가 `engine.llm` 으로 보이지 않으면 경계 검사를 그냥 우회한다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    found.append((node.module, node.lineno))
                continue
            pkg = _package_parts(path, root)
            base = pkg[: len(pkg) - (node.level - 1)]
            parts = base + ([node.module] if node.module else [])
            found.append((".".join(parts), node.lineno))

    return found


def _root(module: str) -> str:
    return module.split(".", 1)[0]


def test_layer_directory_exists():
    """검사 대상이 사라지면 이 테스트는 아무것도 검사하지 않고 통과한다 — 그것부터 막는다."""
    assert _layer_files(), f"결정론 계층에서 .py 를 찾지 못했다: {LAYER}"


def test_no_llm_stack_imports():
    """불변 규칙 3 본문 — langchain·openai 계열 직접 import 금지."""
    violations = [
        f"{path.relative_to(ROOT)}:{lineno} → {module}"
        for path in _layer_files()
        for module, lineno in _imported_modules(path)
        if _root(module).startswith(FORBIDDEN_PREFIXES)
    ]

    assert not violations, (
        "결정론 계층에 LLM 스택 import 가 들어왔다 (AGENTS.md 불변 규칙 3):\n  "
        + "\n  ".join(violations)
        + "\nLLM 호출은 engine/llm/ 과 노드 계층에서만 한다."
    )


def test_no_llm_bearing_internal_imports():
    """`engine.*` 내부 경로로 우회해 LLM 을 끌어오는 것도 같은 위반이다."""
    violations = [
        f"{path.relative_to(ROOT)}:{lineno} → {module}"
        for path in _layer_files()
        for module, lineno in _imported_modules(path)
        if any(
            module == banned or module.startswith(banned + ".")
            for banned in FORBIDDEN_INTERNAL
        )
    ]

    assert not violations, (
        "결정론 계층이 LLM 을 끌고 오는 내부 패키지를 import 했다:\n  "
        + "\n  ".join(violations)
    )


def test_third_party_dependencies_stay_numeric():
    """허용 목록 방식 — 새 서드파티가 조용히 섞이는 것을 막는다.

    금지 목록만 두면 목록에 없는 새 LLM SDK 가 그대로 통과한다. 계층의 의존
    범위를 넓히는 것은 팀 결정이므로, 여기서 한 번 걸리게 해서 드러낸다.
    """
    unexpected = {
        f"{path.relative_to(ROOT)}:{lineno} → {module}"
        for path in _layer_files()
        for module, lineno in _imported_modules(path)
        if _root(module) not in sys.stdlib_module_names
        and _root(module) not in ALLOWED_THIRD_PARTY
        and _root(module) != "engine"
    }

    assert not unexpected, (
        "결정론 계층에 허용되지 않은 의존이 있다:\n  "
        + "\n  ".join(sorted(unexpected))
        + f"\n허용 서드파티: {sorted(ALLOWED_THIRD_PARTY)}. "
        "넓히려면 팀 합의 후 ALLOWED_THIRD_PARTY 를 고친다."
    )


def test_guard_detects_a_planted_violation(tmp_path):
    """가드가 실제로 잡는지 확인한다 — 통과하는 이유가 '아무것도 안 봐서' 가 아니어야 한다."""
    planted = tmp_path / "engine" / "engine" / "leak.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(
        "from langchain_openai import AzureChatOpenAI\n"
        "from ..llm.factory import build_chain\n"
        "import openai.types\n",
        encoding="utf-8",
    )

    modules = [module for module, _ in _imported_modules(planted, root=tmp_path)]

    assert any(_root(m).startswith(FORBIDDEN_PREFIXES) for m in modules)
    assert "engine.llm.factory" in modules, (
        f"상대 import 가 절대 이름으로 해석되지 않았다: {modules}"
    )
