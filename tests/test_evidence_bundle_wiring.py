"""증거 번들 자동 생성 배선 — state 덤프 · CLI 플래그 · 탈락 인용 기록.

여기서 막는 것
  1. 명령 한 번으로 번들이 나오지 않는 상태 (R4 DoD "자동 생성" 미달)
  2. 차단 경로에서 번들이 안 나오는 상태 — 차단 사례도 제출물 3건 중 1건이다
  3. state 덤프가 실행마다 바이트가 흔들려 재현 대조가 불가능한 상태
  4. citation_verification.json의 rejected_citations가 계속 비어 있는 상태

CLI 경로는 subprocess로 실제 `scripts/run_graph.py`를 돌린다. 함수를 직접
부르면 "명령 한 번"이 성립하는지를 검증하지 못한다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.evidence.schema import (  # noqa: E402
    BUNDLE_FILENAMES,
    CITATION_VERIFICATION_FILENAME,
    CITATION_VERIFICATION_REQUIRED_KEYS,
    HARD_STOP_RECORD_FILENAME,
    MANIFEST_FILENAME,
)
from app.evidence.state_dump import (  # noqa: E402
    SERIALIZATION_NOTES_KEY,
    canonical_for_replay,
    dumps_state,
    serialize_state,
)

CLI_TIMEOUT_SECONDS = 900


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_graph.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_SECONDS,
    )


def _only_bundle_dir(root: Path) -> Path:
    dirs = [child for child in root.iterdir() if child.is_dir()]
    assert len(dirs) == 1, f"번들 디렉터리가 1개가 아님: {[d.name for d in dirs]}"
    return dirs[0]


# ---------------------------------------------------------------------------
# state 덤프 — 결정론
# ---------------------------------------------------------------------------
def test_dump_is_byte_identical_for_same_state():
    """같은 state를 두 번 덤프하면 바이트가 같아야 한다."""
    state = {"b": 1, "a": {"z": [3, 2, 1], "y": "한글"}, "trace_id": "run-x"}
    assert dumps_state(state) == dumps_state(state)


def test_dump_key_order_is_stable_regardless_of_insertion_order():
    """삽입 순서가 달라도 sort_keys=True라 같은 바이트가 나온다."""
    first = dumps_state({"a": 1, "b": 2, "c": 3})
    second = dumps_state({"c": 3, "b": 2, "a": 1})
    assert first == second


def test_dump_differs_only_by_trace_id_across_runs():
    """trace_id를 제외하면 두 덤프가 동일해야 한다."""
    base = {"report": {"status": "confirmed"}, "metrics": {"var": 0.1}}
    first = serialize_state({**base, "trace_id": "run-aaa"})
    second = serialize_state({**base, "trace_id": "run-bbb"})
    assert first != second
    assert canonical_for_replay(first) == canonical_for_replay(second)


def test_dump_preserves_hangul_without_escaping():
    assert "한글" in dumps_state({"k": "한글"})


def test_serialization_notes_are_empty_when_nothing_converted():
    """변환이 없으면 notes가 비어야 한다 — 비어 있음이 '원형 그대로'의 증거다."""
    notes = serialize_state({"a": 1, "b": "x", "c": [1.5, True, None]})[
        SERIALIZATION_NOTES_KEY
    ]
    assert notes["converted"] is False
    assert notes["conversions"] == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc), "2026-07-03T12:00:00+00:00"),
        (Path("/tmp/x"), "/tmp/x"),
    ],
)
def test_known_types_are_converted_and_recorded(value, expected):
    dumped = serialize_state({"field": value})
    assert dumped["field"] == expected
    notes = dumped[SERIALIZATION_NOTES_KEY]
    assert notes["converted"] is True
    assert notes["conversions"][0]["path"] == "state.field"
    # 원형을 잃지 않는다 — 감사에서 값의 원형을 물을 수 있다.
    assert notes["conversions"][0]["original_repr"]


def test_decimal_keeps_original_precision_as_string():
    from decimal import Decimal

    dumped = serialize_state({"amount": Decimal("0.1")})
    assert dumped["amount"] == "0.1"


def test_set_is_sorted_so_dump_is_deterministic():
    first = dumps_state({"s": {"b", "a", "c"}})
    second = dumps_state({"s": {"c", "a", "b"}})
    assert first == second


def test_serialization_notes_are_sorted_by_path():
    """conversions는 리스트라 sort_keys로 정렬되지 않는다 — 직접 정렬해야 한다.

    내용이 같은데 dict 삽입 순서만 다른 두 state의 덤프가 바이트까지 같아야 한다.
    """
    from decimal import Decimal

    value = {"z": Decimal("1"), "a": Decimal("2"), "m": Decimal("3")}
    first = dumps_state(value)
    second = dumps_state({"m": Decimal("3"), "z": Decimal("1"), "a": Decimal("2")})
    assert first == second

    paths = [c["path"] for c in serialize_state(value)[SERIALIZATION_NOTES_KEY]["conversions"]]
    assert paths == sorted(paths)


def test_unknown_type_is_marked_not_silently_stringified():
    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    dumped = serialize_state({"field": Opaque()})
    assert dumped["field"] != "<opaque>", "조용히 str()로 뭉개면 안 된다"
    assert "_unserializable" in dumped["field"]
    assert dumped[SERIALIZATION_NOTES_KEY]["converted"] is True


# ---------------------------------------------------------------------------
# 탈락 인용 기록 — 하위 호환 포함
# ---------------------------------------------------------------------------
def _rejection(**overrides) -> dict:
    record = {
        "topic": "VaR 해석",
        "chunk_id": "methodology_var_2026#3",
        "cited_source": "리스크 계량 방법론(가상) 제3조",
        "cited_locator": {"article": "제3조"},
        "quote": "원문에 없는 문장",
        "reason": "인용문이 청크 원문에 없음(환각 의심)",
        "original_comparison": {
            "chunk_found": True,
            "chunk_source": "리스크 계량 방법론(가상)",
            "chunk_locator": {"article": "제4조"},
            "quote_found_in_chunk": False,
        },
    }
    record.update(overrides)
    return record


def test_citation_verification_carries_actual_rejections():
    from make_evidence_bundle import build_citation_verification

    payload = build_citation_verification(
        {"citations": [], "citation_rejections": [_rejection()]}
    )
    rejected = payload["rejected_citations"]
    assert isinstance(rejected, list) and len(rejected) == 1
    assert rejected[0]["chunk_id"] == "methodology_var_2026#3"
    assert rejected[0]["cited_locator"] == {"article": "제3조"}
    assert rejected[0]["original_comparison"]["quote_found_in_chunk"] is False


def test_citation_verification_is_backward_compatible_without_key():
    """키가 없는 과거 state에서는 기존대로 available:false여야 한다."""
    from make_evidence_bundle import build_citation_verification

    payload = build_citation_verification({"citations": []})
    assert payload["rejected_citations"]["available"] is False


def test_citation_verification_keeps_required_keys():
    from make_evidence_bundle import build_citation_verification

    payload = build_citation_verification({"citations": [], "citation_rejections": []})
    assert set(CITATION_VERIFICATION_REQUIRED_KEYS) <= set(payload)


def test_bundle_builds_when_rejection_key_absent(tmp_path: Path):
    """하위 호환 — 탈락 인용 키가 없는 state로도 번들 생성이 성공해야 한다."""
    from make_evidence_bundle import make_bundle

    out = make_bundle(
        {"trace_id": "run-old", "citations": [], "report": {}},
        tmp_path / "bundle",
        run_id="run-old",
        generated_at="2026-08-01T00:00:00+00:00",
    )
    assert not [name for name in BUNDLE_FILENAMES if not (out / name).is_file()]


def test_rejected_citation_flows_from_node_to_bundle(tmp_path: Path):
    """환각 인용이 노드 → state → 번들까지 실제로 이어지는지 (end-to-end).

    `_FakeLLM`은 실존 인용 1건과 환각 인용 1건을 내놓는다. 환각분은 citations에
    실리면 안 되고, citation_verification.json에는 사유와 함께 실려야 한다.
    """
    from make_evidence_bundle import make_bundle
    from tests.test_rag_cite_node import _FakeLLM, _FakeRetriever

    from app.nodes.rag_cite import rag_cite

    out = rag_cite({"metrics": {}}, llm=_FakeLLM(), retriever=_FakeRetriever())
    rejections = out["citation_rejections"]
    assert rejections, "환각 인용이 탈락 기록에 남지 않았다"

    # 탈락분이 citations로 되살아나지 않았는지 — 되살리면 judge 판정이 달라진다.
    quotes = {citation["quote"] for citation in out["citations"]}
    assert all(rejection["quote"] not in quotes for rejection in rejections)

    bundle = make_bundle(
        {"citations": out["citations"], "citation_rejections": rejections, "report": {}},
        tmp_path / "bundle",
        run_id="run-test-001",
        generated_at="2026-08-01T00:00:00+00:00",
    )
    payload = json.loads(
        (bundle / CITATION_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    )
    assert len(payload["rejected_citations"]) == len(rejections)
    first = payload["rejected_citations"][0]
    assert first["reason"]
    assert first["original_comparison"]["quote_found_in_chunk"] is False


# ---------------------------------------------------------------------------
# 재작성 루프 — 시도별 탈락 기록 누적
# ---------------------------------------------------------------------------
def _run_rag_attempts(attempts: int) -> dict:
    """judge 재작성 루프를 흉내내 rag_cite를 연속 호출하고 최종 state를 돌려준다.

    LangGraph가 노드 반환값을 state에 병합하는 것과 같게, 반환 키를 state에 덮어쓴다.
    """
    from tests.test_rag_cite_node import _FakeLLM, _FakeRetriever

    from app.nodes.rag_cite import rag_cite

    state: dict = {"metrics": {}}
    for revision in range(attempts):
        state["judge_retries"] = revision
        state.update(
            rag_cite(state, llm=_FakeLLM(), retriever=_FakeRetriever())
        )
    return state


def test_rewrite_loop_preserves_every_attempt_rejections():
    """3회 재작성해도 앞선 시도의 탈락 기록이 남아야 한다 (R3 감사 추적).

    덮어쓰면 최종 state에는 마지막 시도의 탈락만 남아 "무엇이 왜 떨어졌나"의
    이력이 끊긴다.
    """
    state = _run_rag_attempts(3)
    rejections = state["citation_rejections"]

    attempts = sorted({rejection["attempt"] for rejection in rejections})
    assert attempts == [1, 2, 3], f"시도별 기록이 보존되지 않았다: {attempts}"

    # 각 시도가 최소 1건씩 남았는지 — 마지막 시도만 살아남는 회귀를 잡는다.
    for attempt in (1, 2, 3):
        assert [r for r in rejections if r["attempt"] == attempt]

    # attempt 오름차순으로 쌓여야 감사에서 시간순으로 읽힌다.
    assert [r["attempt"] for r in rejections] == sorted(
        r["attempt"] for r in rejections
    )


def test_same_attempt_rerun_does_not_duplicate_rejections():
    """체크포인트 재생으로 같은 시도가 두 번 실행돼도 기록이 중복되면 안 된다."""
    from tests.test_rag_cite_node import _FakeLLM, _FakeRetriever

    from app.nodes.rag_cite import rag_cite

    state: dict = {"metrics": {}, "judge_retries": 0}
    state.update(rag_cite(state, llm=_FakeLLM(), retriever=_FakeRetriever()))
    once = state["citation_rejections"]
    state.update(rag_cite(state, llm=_FakeLLM(), retriever=_FakeRetriever()))

    assert state["citation_rejections"] == once


def test_bundle_carries_attempt_for_every_rejection(tmp_path: Path):
    """누적된 시도 번호가 번들까지 이어져야 감사에서 구분된다."""
    from make_evidence_bundle import make_bundle

    state = _run_rag_attempts(2)
    bundle = make_bundle(
        {
            "citations": state["citations"],
            "citation_rejections": state["citation_rejections"],
            "report": {},
        },
        tmp_path / "bundle",
        run_id="run-test-002",
        generated_at="2026-08-01T00:00:00+00:00",
    )
    payload = json.loads(
        (bundle / CITATION_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    )
    rejected = payload["rejected_citations"]
    assert {row["attempt"] for row in rejected} == {1, 2}


def test_empty_quote_is_not_reported_as_found_in_chunk():
    """빈 인용문은 원문 대조가 성립하지 않는다.

    `"" in text`가 True라, 그대로 두면 탈락 사유 '빈 인용문'과
    `quote_found_in_chunk: true`가 동시에 기록돼 감사 기록이 자기모순이 된다.
    """
    from app.nodes.rag_cite import _rejection_record

    record = _rejection_record(
        {"chunk_id": "c1", "quote": "   ", "source": "문서(가상)", "reason": "빈 인용문"},
        "VaR 해석",
        [],
        {"c1": {"chunk_id": "c1", "text": "실제 원문", "source": "문서(가상)"}},
        attempt=1,
    )
    assert record["original_comparison"]["quote_found_in_chunk"] is False


def test_rag_cite_records_rejection_shape():
    """rag_cite의 탈락 기록이 계약대로 6개 필드를 담는지 — 노드 헬퍼 직접 검사."""
    from app.nodes.rag_cite import _rejection_record
    from app.rag.citations import Citation

    candidate = Citation(
        claim="VaR 해석",
        quote="원문에 없는 문장",
        source="리스크 계량 방법론(가상)",
        chunk_id="c1",
        extra={"article": "제3조"},
    )
    candidate.verified = False
    record = _rejection_record(
        {
            "chunk_id": "c1",
            "quote": "원문에 없는 문장",
            "source": "리스크 계량 방법론(가상)",
            "reason": "인용문이 청크 원문에 없음(환각 의심)",
        },
        "VaR 해석",
        [candidate],
        {"c1": {"chunk_id": "c1", "text": "실제 원문", "source": "리스크 계량 방법론(가상)"}},
        attempt=1,
    )
    assert record["cited_locator"] == {"article": "제3조"}
    assert record["original_comparison"]["chunk_found"] is True
    assert record["original_comparison"]["quote_found_in_chunk"] is False
    assert record["reason"]


# ---------------------------------------------------------------------------
# run_id 자동 부여
# ---------------------------------------------------------------------------
def test_run_id_is_allocated_without_human_input(tmp_path: Path):
    from run_graph import allocate_run_id

    assert allocate_run_id(tmp_path, "20260801") == "run-20260801-001"
    (tmp_path / "run-20260801-001").mkdir()
    assert allocate_run_id(tmp_path, "20260801") == "run-20260801-002"


def test_run_id_does_not_overwrite_existing_bundle(tmp_path: Path):
    from run_graph import allocate_run_id

    for index in (1, 2, 3):
        (tmp_path / f"run-20260801-{index:03d}").mkdir()
    assert allocate_run_id(tmp_path, "20260801") == "run-20260801-004"


# ---------------------------------------------------------------------------
# CLI 통합 — 명령 한 번으로 번들이 나오는가
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def normal_run(tmp_path_factory) -> tuple[Path, Path]:
    """`--auto-approve --offline` 1회 실행 결과를 여러 검사가 공유한다 (실행이 비싸다).

    ⚠️ 이 실행의 judge 통과 여부는 **환경에 따라 달라진다.** `--offline`은 시장
    데이터와 IPS 추출만 스텁으로 바꾸고 RAG·judge LLM은 실제로 호출한다. Azure 키가
    없는 CI에서는 인용 0건이 되어 `source_validity`·`hallucination`·`false_precision`이
    떨어지고 정상적으로 차단된다. 따라서 pass/fail 결과를 단정하면 안 되고,
    **환경과 무관하게 성립하는 것**(번들이 나오는가, 기록이 자기모순 없는가)만 본다.
    확정 경로의 결과 단정은 강제 차단 테스트가 결정론적으로 담당한다.
    """
    workdir = tmp_path_factory.mktemp("normal")
    out_root, state_path = workdir / "evidence", workdir / "state.json"
    result = _run_cli(
        "--auto-approve", "--offline",
        "--dump-state", str(state_path),
        "--evidence-bundle", str(out_root),
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return _only_bundle_dir(out_root), state_path


def test_cli_generates_full_bundle_in_one_command(normal_run):
    """명령 한 번으로 규정 파일이 전부 나오는가 — R4 DoD의 핵심."""
    bundle, _ = normal_run
    missing = [name for name in BUNDLE_FILENAMES if not (bundle / name).is_file()]
    assert not missing, f"규정 파일 누락: {missing}"


def test_cli_hard_stop_record_is_self_consistent(normal_run):
    """차단 여부가 어느 쪽이든 확정·제공 허용 필드가 함께 움직여야 한다.

    judge 통과 여부는 환경에 좌우되지만, "차단인데 확정됨" 같은 조합은 어느
    환경에서도 나오면 안 된다. 이게 hard stop 계약의 실질이다.
    """
    bundle, _ = normal_run
    hard_stop = json.loads((bundle / HARD_STOP_RECORD_FILENAME).read_text(encoding="utf-8"))
    blocked = hard_stop["blocked"]
    assert isinstance(blocked, bool)
    if blocked:
        assert hard_stop["report_finalized"] is False
        assert hard_stop["export_allowed"] is False
        assert hard_stop["manual_review_required"] is True
        assert hard_stop["report_status"] == "pending_manual_review"
    else:
        assert hard_stop["report_finalized"] is True
        assert hard_stop["export_allowed"] is True
        assert hard_stop["report_status"] == "confirmed"


def test_cli_manifest_records_generator_and_git_sha(normal_run):
    bundle, _ = normal_run
    manifest = json.loads((bundle / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert manifest["generated_by"]["script"] == "scripts/make_evidence_bundle.py"
    assert manifest["generated_by"]["git_sha"]
    assert manifest["run_id"] == bundle.name


def test_cli_bundle_contains_citation_verification_section(normal_run):
    bundle, _ = normal_run
    payload = json.loads(
        (bundle / CITATION_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    )
    assert set(CITATION_VERIFICATION_REQUIRED_KEYS) <= set(payload)


def test_cli_dump_state_is_reloadable_and_notes_conversions(normal_run):
    _, state_path = normal_run
    dumped = json.loads(state_path.read_text(encoding="utf-8"))
    assert dumped[SERIALIZATION_NOTES_KEY]["converted"] is False
    assert dumped["report"]["status"]


def test_cli_blocked_path_still_generates_bundle(tmp_path: Path):
    """차단 경로에서도 번들이 나와야 한다 — 제출물 3건 중 1건이 차단 사례다."""
    out_root = tmp_path / "evidence"
    result = _run_cli(
        "--auto-approve", "--offline", "--force-judge-fail", "3",
        "--evidence-bundle", str(out_root),
    )
    assert result.returncode == 0, result.stderr[-2000:]

    bundle = _only_bundle_dir(out_root)
    assert not [name for name in BUNDLE_FILENAMES if not (bundle / name).is_file()]

    hard_stop = json.loads((bundle / HARD_STOP_RECORD_FILENAME).read_text(encoding="utf-8"))
    assert hard_stop["blocked"] is True
    assert hard_stop["report_finalized"] is False
    assert hard_stop["export_allowed"] is False
