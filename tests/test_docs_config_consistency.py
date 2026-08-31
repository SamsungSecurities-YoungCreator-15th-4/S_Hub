"""문서에 적힌 judge 재시도 상한이 config/config.yaml과 어긋나지 않는지 검사한다.

지난 총평에서 "문서엔 3회, 코드엔 2회" 유형의 불일치를 지적받았다. 상한 숫자의
유일한 원천은 `config/config.yaml`의 `judge_max_retries`이고, 코드는
`resolve_max_judge_retries`로만 읽는다. 문서는 두 가지 중 하나여야 한다:

1. 숫자를 쓰지 않고 `judge_max_retries` 키를 참조만 한다 (권장 — 값이 바뀌어도
   문서를 고칠 필요가 없다)
2. 숫자를 쓴다면 그 값이 config와 같아야 한다

이 테스트는 두 형태를 모두 통과로 인정하고, 2번인데 값이 다른 경우만 잡는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"

# judge 재시도 상한을 서술하는(또는 서술할 수 있는) 문서 목록.
# 새 문서에서 재시도 횟수를 언급하기 시작하면 여기에 추가한다.
# 발표·시연용 해설 문서는 값이 갈라지기 가장 쉬운 자리라, 레포에 들어오는 즉시 여기에
# 등록한다 — 목록에 있으면서 파일이 없으면 skip이므로 미리 등록해 두어도 된다.
#
# 다만 **레포에 들어올 계획이 없는 개인 로컬 문서는 등록하지 않는다.** 영구 skip으로
# 남아 "검사 장치는 있는데 검사 대상이 없는" 상태가 되고, 목록을 읽는 사람이 그 문서가
# 검사되고 있다고 오해한다. 실제로 `발표대비_오케스트레이션_완전해설.md`가 그 상태였다.
# `docs/symphony_proof_plan.md`는 넣지 않는다. 번들 3건 시나리오를 "judge 1회 통과"·
# "judge 1회 실패 → 재작성"처럼 서술하는데, 이건 상한 주장이 아니라 실행 횟수 서술이라
# 아래 정규식이 오탐한다(_UNRELATED_RE로도 걸러지지 않는다). 그 문서에 상한을 숫자로
# 적기 시작하면 문장을 먼저 다듬고 여기에 추가한다.
RETRY_DOCS = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs/hard_stop_contract.md",
    "docs/audit_demo_runbook.md",
)

# "judge ... N회/N번/N차례" 형태만 잡는다. conflict 재추출 상한(1회)이나
# IPS 추출 3회 반복 실측처럼 judge와 무관한 숫자는 대상이 아니다.
_JUDGE_RETRY_CLAIM_RE = re.compile(
    r"(?P<claim>"
    r"(?:judge|Judge|저지|재시도|재작성)[^\n。]{0,60}?"
    r"(?P<count>\d+)\s*(?:회|번|차례)"
    r"|"
    r"(?P<count2>\d+)\s*(?:회|번|차례)[^\n。]{0,60}?"
    r"(?:judge_max_retries|Judge 재시도|judge 재시도)"
    r")"
)
# 재시도와 무관한 문맥에서 "N회"가 걸리는 것을 걸러낸다. conflict 재추출 상한(1회)이
# 일반 키워드 "재시도"에 걸리는 것을 막는 필수 필터다.
#
# 알려진 한계(#139 리뷰): 이 필터는 줄 단위로 동작하므로, judge 재시도 숫자와
# 위 무관 키워드가 **한 줄에 공존하면 그 줄 전체가 스킵되어** 불일치를 놓친다.
# 현재 문서에는 그런 줄이 없다. 새로 문서를 쓸 때는 judge 재시도 횟수를
# conflict 재추출 서술과 같은 줄에 섞지 말고 줄을 나눈다.
_UNRELATED_RE = re.compile(r"충돌|conflict|재추출|IPS 추출|computation_hash|예열|단일 기간")


def _configured_max_retries() -> int:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    value = config["judge_max_retries"]
    assert isinstance(value, int) and not isinstance(value, bool) and value >= 1, (
        f"config.yaml의 judge_max_retries는 1 이상의 정수여야 합니다 (현재: {value!r})"
    )
    return value


def _judge_retry_claims(text: str) -> list[tuple[int, str, int]]:
    """(줄번호, 줄 원문, 주장된 횟수) 목록을 돌려준다."""
    claims: list[tuple[int, str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _UNRELATED_RE.search(line):
            continue
        for match in _JUDGE_RETRY_CLAIM_RE.finditer(line):
            count = match.group("count") or match.group("count2")
            claims.append((lineno, line.strip(), int(count)))
    return claims


def test_config_judge_max_retries_is_valid():
    assert _configured_max_retries() >= 1


@pytest.mark.parametrize("doc_name", RETRY_DOCS)
def test_doc_retry_count_matches_config(doc_name: str):
    """문서가 숫자로 상한을 적었다면 config 값과 같아야 한다.

    문서가 없으면 skip한다 — 이 목록은 "있으면 반드시 검사한다"는 뜻이고,
    발표 자료처럼 레포 밖에서 관리되다 들어오는 문서를 미리 등록해 둘 수 있어야
    한다. 파일이 생기는 순간 자동으로 검사 대상이 된다.
    """
    path = ROOT / doc_name
    if not path.exists():
        pytest.skip(f"{doc_name}이 레포에 없습니다 (생성되면 자동으로 검사 대상이 됩니다).")

    expected = _configured_max_retries()
    mismatched = [
        (lineno, line, count)
        for lineno, line, count in _judge_retry_claims(path.read_text(encoding="utf-8"))
        if count != expected
    ]
    assert not mismatched, (
        f"{doc_name}의 judge 재시도 횟수 서술이 config/config.yaml의 "
        f"judge_max_retries({expected})와 다릅니다:\n"
        + "\n".join(f"  {doc_name}:{lineno}: {line} (문서 주장: {count}회)"
                    for lineno, line, count in mismatched)
    )


def test_hard_stop_doc_states_no_fallback():
    """#135로 폴백 상수가 제거됐으므로, 계약 문서가 그 사실을 명시해야 한다.

    코드(resolve_max_judge_retries)는 값이 없거나 오염되면 즉시 ValueError를
    낸다. 문서에 "기본값으로 대체"류 서술이 남아 있으면 실제 동작과 갈라진다.
    """
    text = (ROOT / "docs" / "hard_stop_contract.md").read_text(encoding="utf-8")
    assert "코드 기본값으로 대체하지 않고 즉시 실패한다" in text, (
        "hard_stop_contract.md에 폴백 부재(설정 부재 시 실행 거부) 서술이 없습니다."
    )


def test_no_hardcoded_fallback_in_code():
    """문서가 '폴백 없음'이라고 적었으니 코드에도 폴백 기본값이 없어야 한다."""
    from app.nodes.judge_eval import resolve_max_judge_retries

    with pytest.raises(ValueError, match="judge_max_retries"):
        resolve_max_judge_retries({"run_config": {}})


def test_agents_requires_success_and_hard_stop_graph_runs():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "python scripts/run_graph.py --auto-approve\n" in text
    assert (
        "python scripts/run_graph.py --auto-approve --force-judge-fail 3" in text
    )


def test_agents_corpus_count_matches_manifest():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    manifest = (ROOT / "corpus" / "manifest.md").read_text(encoding="utf-8")
    agents_match = re.search(r"RAG 근거 문서 \((\d+)건", agents)
    manifest_match = re.search(r"총 문서 수: \*\*(\d+)건\*\*", manifest)

    assert agents_match is not None, "AGENTS.md 레포 구조에 코퍼스 문서 수가 없습니다."
    assert manifest_match is not None, "corpus/manifest.md에 총 문서 수가 없습니다."
    assert int(agents_match.group(1)) == int(manifest_match.group(1))


def test_reproducibility_scope_does_not_guarantee_llm_judge_axes():
    text = (ROOT / "docs" / "reproducibility_scope.md").read_text(encoding="utf-8")
    unconditional, conditional = text.split("### 2.1", maxsplit=1)

    assert "judge 6축" not in unconditional.lower()
    assert "Judge 6축" in conditional
    normalized = " ".join(conditional.split())
    assert "항상 같다고 보장하지 않는다" in normalized
