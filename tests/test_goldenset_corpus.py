"""정답 사례집 전용 코퍼스(goldenset/corpus/chunks.json)의 무결성 게이트.

이 코퍼스는 judge가 채점받는 정답 사례집이 인용하는 규정 원문이다. R2 어댑터가
`citations[].extra.chunk_text`를 채우는 원천이고, 레포를 클론한 사람이 R2를
재현하는 근거이기도 하다.

가장 중요한 검사는 **실존/가상 경계**다. 코퍼스 문서 §2의 "실존 기관명을 붙인
가상 문서 금지" 원칙은 문서에만 적어두면 지켜지는지 알 수 없다. 가상 문서
(`synthetic: true`)는 `source`에 반드시 `(가상)` 표기를 달아, 사례 본문을 읽는
사람이 실존 규정과 창작 규정을 혼동하지 않게 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = ROOT / "goldenset" / "corpus" / "chunks.json"

REQUIRED_KEYS = ("chunk_id", "source", "category", "synthetic", "text")
MIN_CHUNK_COUNT = 12
SYNTHETIC_MARKER = "(가상)"
# 실존 문서(synthetic=false)는 법령·규정 원문만 허용한다. 실존 하우스뷰·거시
# 브리프를 사례집에 넣으면 저작권·인용 범위 문제가 생기므로 category로 막는다.
REAL_DOCUMENT_CATEGORY = "regulation"


def _load_chunks() -> list[dict]:
    if not CHUNKS_PATH.exists():
        pytest.skip(
            "goldenset/corpus/chunks.json이 없습니다 (생성되면 자동으로 검사 대상이 됩니다)."
        )
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 순수 검증 함수 — 실제 파일과 합성 데이터 양쪽에 같은 규칙을 적용한다.
# ---------------------------------------------------------------------------
def validate_chunks(chunks: object) -> list[str]:
    """코퍼스 규약 위반 목록을 돌려준다. 비어 있으면 통과다."""
    problems: list[str] = []
    if not isinstance(chunks, list):
        return ["chunks.json 최상위는 list여야 합니다."]
    if len(chunks) < MIN_CHUNK_COUNT:
        problems.append(f"청크가 {MIN_CHUNK_COUNT}건 이상이어야 합니다 (현재 {len(chunks)}건).")

    seen: dict[str, int] = {}
    for index, chunk in enumerate(chunks):
        where = f"chunks[{index}]"
        if not isinstance(chunk, dict):
            problems.append(f"{where}: 항목은 dict여야 합니다.")
            continue

        missing = [key for key in REQUIRED_KEYS if key not in chunk]
        if missing:
            problems.append(f"{where}: 필수 키 누락 {missing}")
            continue

        chunk_id = chunk["chunk_id"]
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            problems.append(f"{where}: chunk_id는 비어있지 않은 문자열이어야 합니다.")
            continue
        if chunk_id in seen:
            problems.append(f"{where}: chunk_id '{chunk_id}'가 chunks[{seen[chunk_id]}]와 중복됩니다.")
        else:
            seen[chunk_id] = index

        text = chunk["text"]
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{chunk_id}: text가 비어 있습니다.")

        source = chunk["source"]
        if not isinstance(source, str) or not source.strip():
            problems.append(f"{chunk_id}: source는 비어있지 않은 문자열이어야 합니다.")
            source = ""

        category = chunk["category"]
        if not isinstance(category, str) or not category.strip():
            problems.append(f"{chunk_id}: category는 비어있지 않은 문자열이어야 합니다.")

        synthetic = chunk["synthetic"]
        if not isinstance(synthetic, bool):
            problems.append(
                f"{chunk_id}: synthetic은 bool이어야 합니다 (받은 값: {synthetic!r})."
            )
            continue

        if synthetic and SYNTHETIC_MARKER not in source:
            problems.append(
                f"{chunk_id}: synthetic=true인데 source에 '{SYNTHETIC_MARKER}' 표기가 없습니다 "
                f"— 실존 기관명을 붙인 가상 문서는 금지입니다 (source: {source!r})."
            )
        if not synthetic and category != REAL_DOCUMENT_CATEGORY:
            problems.append(
                f"{chunk_id}: synthetic=false인 실존 문서는 category가 "
                f"'{REAL_DOCUMENT_CATEGORY}'여야 합니다 (받은 값: {category!r})."
            )
    return problems


# ---------------------------------------------------------------------------
# 실제 코퍼스 검사
# ---------------------------------------------------------------------------
def test_chunks_json_is_valid_json():
    chunks = _load_chunks()
    assert isinstance(chunks, list) and chunks


def test_chunks_satisfy_corpus_contract():
    problems = validate_chunks(_load_chunks())
    assert not problems, "goldenset 코퍼스 규약 위반:\n" + "\n".join(f"  - {p}" for p in problems)


def test_chunk_ids_are_unique():
    chunks = _load_chunks()
    ids = [chunk["chunk_id"] for chunk in chunks]
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    assert not duplicates, f"chunk_id 중복: {duplicates}"


def test_synthetic_documents_are_marked():
    """가상 문서는 전건 source에 '(가상)' 표기가 있어야 한다."""
    unmarked = [
        chunk["chunk_id"]
        for chunk in _load_chunks()
        if chunk.get("synthetic") is True and SYNTHETIC_MARKER not in str(chunk.get("source", ""))
    ]
    assert not unmarked, f"'(가상)' 표기가 없는 synthetic 문서: {unmarked}"


def test_real_documents_are_regulation_only():
    misfiled = [
        (chunk["chunk_id"], chunk.get("category"))
        for chunk in _load_chunks()
        if chunk.get("synthetic") is False and chunk.get("category") != REAL_DOCUMENT_CATEGORY
    ]
    assert not misfiled, f"실존 문서인데 category가 regulation이 아님: {misfiled}"


# ---------------------------------------------------------------------------
# 검증 로직 자체의 음성 검증 — 위반 데이터가 실제로 잡히는지 확인한다.
# ---------------------------------------------------------------------------
def _valid_chunk(**overrides) -> dict:
    base = {
        "chunk_id": "synthetic-001",
        "source": "합성 규정(가상) 제1조",
        "category": "internal",
        "synthetic": True,
        "text": "본문",
    }
    base.update(overrides)
    return base


def _padded(*chunks: dict) -> list[dict]:
    """MIN_CHUNK_COUNT 미달로 인한 부수 위반이 섞이지 않게 정상 청크로 채운다."""
    filler = [
        _valid_chunk(chunk_id=f"filler-{i:03d}")
        for i in range(MIN_CHUNK_COUNT - len(chunks))
    ]
    return [*chunks, *filler]


def test_detects_synthetic_without_marker():
    """synthetic=true인데 '(가상)'이 없으면 반드시 잡혀야 한다 — 이 테스트의 존재 이유다."""
    problems = validate_chunks(
        _padded(_valid_chunk(chunk_id="fake-001", source="금융위원회 리스크리포트 작성기준 제5조"))
    )
    assert any("fake-001" in p and SYNTHETIC_MARKER in p for p in problems), problems


def test_detects_real_document_with_non_regulation_category():
    problems = validate_chunks(
        _padded(
            _valid_chunk(
                chunk_id="real-001",
                synthetic=False,
                category="house_view",
                source="「금융소비자 보호에 관한 법률」 제19조",
            )
        )
    )
    assert any("real-001" in p and "regulation" in p for p in problems), problems


def test_detects_duplicate_chunk_id():
    problems = validate_chunks(_padded(_valid_chunk(chunk_id="dup"), _valid_chunk(chunk_id="dup")))
    assert any("중복" in p for p in problems), problems


def test_detects_empty_text():
    problems = validate_chunks(_padded(_valid_chunk(chunk_id="empty-001", text="   ")))
    assert any("empty-001" in p and "text" in p for p in problems), problems


def test_detects_non_bool_synthetic():
    problems = validate_chunks(_padded(_valid_chunk(chunk_id="strbool-001", synthetic="true")))
    assert any("strbool-001" in p and "bool" in p for p in problems), problems


def test_detects_missing_required_key():
    chunk = _valid_chunk(chunk_id="nokey-001")
    del chunk["category"]
    problems = validate_chunks(_padded(chunk))
    assert any("category" in p for p in problems), problems


def test_detects_too_few_chunks():
    problems = validate_chunks([_valid_chunk()])
    assert any(str(MIN_CHUNK_COUNT) in p for p in problems), problems


def test_valid_corpus_has_no_problems():
    assert validate_chunks(_padded()) == []
