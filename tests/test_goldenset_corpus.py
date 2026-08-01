"""정답 사례집 전용 코퍼스(goldenset/corpus/chunks.json)의 무결성 게이트.

이 코퍼스는 judge가 채점받는 정답 사례집이 인용하는 규정 원문이다. R2 어댑터가
`citations[].extra.chunk_text`를 채우는 원천이고, 레포를 클론한 사람이 R2를
재현하는 근거이기도 하다.

가장 중요한 검사는 **실존/가상 경계**이며, 이를 `synthetic` 플래그와 `source`
문자열의 **양방향 일치**로 건다. 라벨러와 judge가 실제로 보는 것은 `source`
문자열이지 `synthetic` 플래그가 아니다. 둘이 어긋나면 라벨러가 창작 규정을
"실존 규정인 줄 알고" 판정하게 되므로, 한쪽 방향만 막아서는 부족하다.

카테고리 제약은 출처 진위와 분리해서 건다(#140 리뷰, R1 오너). `tax`(국세청)나
`macro`(한은·FOMC 공개문)는 공공자료라 실존 인용이 가능하므로 "실존 문서는
regulation만"으로 묶으면 나중에 정당한 인용을 게이트가 막는다. 반대로
`house_view`는 저작권과 실존 기관 발표 날조 위험 때문에 **절대 실존일 수 없다** —
막아야 할 것은 이쪽이다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = ROOT / "goldenset" / "corpus" / "chunks.json"

REQUIRED_KEYS = ("chunk_id", "source", "category", "synthetic", "text")
MIN_CHUNK_COUNT = 12
SYNTHETIC_MARKER = "(가상)"
# 실존 기관 발표를 날조하는 형태가 되므로 하우스뷰는 가상 문서만 허용한다.
SYNTHETIC_ONLY_CATEGORIES = ("house_view",)
# `chunks.json`은 인용 원문 대조용으로 라벨러에게 배포된다. `note`는 작성 원칙을
# 적는 자리이지 출제 의도를 적는 자리가 아니다 — 사례 번호·함정 언급을 막는다.
NOTE_LEAK_PATTERNS = (
    (re.compile(r"case_\d+", re.I), "사례 번호"),
    (re.compile(r"trap", re.I), "함정(trap) 언급"),
    (re.compile(r"함정"), "함정 언급"),
)


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

        marked = SYNTHETIC_MARKER in source
        if synthetic and not marked:
            problems.append(
                f"{chunk_id}: synthetic=true인데 source에 '{SYNTHETIC_MARKER}' 표기가 없습니다 "
                f"— 실존 기관명을 붙인 가상 문서는 금지입니다 (source: {source!r})."
            )
        if not synthetic and marked:
            problems.append(
                f"{chunk_id}: source에 '{SYNTHETIC_MARKER}' 표기가 있는데 synthetic=false입니다 "
                f"— 표기와 플래그가 어긋나면 라벨러가 창작 규정을 실존으로 오인합니다 "
                f"(source: {source!r})."
            )
        if not synthetic and category in SYNTHETIC_ONLY_CATEGORIES:
            problems.append(
                f"{chunk_id}: category='{category}'는 가상 문서만 허용합니다 "
                "— 실존 기관의 발표를 날조하는 형태가 됩니다."
            )

        note = chunk.get("note")
        if note is not None:
            if not isinstance(note, str):
                problems.append(f"{chunk_id}: note는 문자열이어야 합니다 (받은 타입: {type(note).__name__}).")
            else:
                for pattern, what in NOTE_LEAK_PATTERNS:
                    if pattern.search(note):
                        problems.append(
                            f"{chunk_id}: note에 {what}이 있습니다 — chunks.json은 라벨러에게 "
                            "배포되므로 출제 의도를 적으면 그대로 새어나갑니다."
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


def test_synthetic_flag_and_source_marker_agree_both_ways():
    """`synthetic == ('(가상)' in source)` — 어느 방향으로 어긋나도 잡는다."""
    mismatched = [
        chunk["chunk_id"]
        for chunk in _load_chunks()
        if chunk.get("synthetic") is not (SYNTHETIC_MARKER in str(chunk.get("source", "")))
    ]
    assert not mismatched, f"synthetic 플래그와 '(가상)' 표기가 불일치: {mismatched}"


def test_house_view_documents_are_synthetic_only():
    real = [
        chunk["chunk_id"]
        for chunk in _load_chunks()
        if chunk.get("category") in SYNTHETIC_ONLY_CATEGORIES and chunk.get("synthetic") is False
    ]
    assert not real, f"가상만 허용되는 category인데 synthetic=false: {real}"


def test_notes_do_not_leak_case_intent():
    """note는 작성 원칙만 담는다 — 사례 번호·함정 언급이 들어가면 배포 시 유출된다."""
    leaks = [
        (chunk["chunk_id"], what)
        for chunk in _load_chunks()
        for pattern, what in NOTE_LEAK_PATTERNS
        if isinstance(chunk.get("note"), str) and pattern.search(chunk["note"])
    ]
    assert not leaks, f"note에 출제 의도가 노출됨: {leaks}"


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


def test_detects_marker_without_synthetic_flag():
    """역방향 — source에 '(가상)'인데 synthetic=false면 라벨러가 실존으로 오인한다."""
    problems = validate_chunks(
        _padded(
            _valid_chunk(
                chunk_id="mismatch-001",
                synthetic=False,
                category="regulation",
                source="사내 리스크리포트 작성기준(가상) 제5조",
            )
        )
    )
    assert any("mismatch-001" in p and "synthetic=false" in p for p in problems), problems


def test_detects_real_house_view():
    problems = validate_chunks(
        _padded(
            _valid_chunk(
                chunk_id="real-hv-001",
                synthetic=False,
                category="house_view",
                source="삼성증권 하우스뷰 2026년 하반기 전망",
            )
        )
    )
    assert any("real-hv-001" in p and "house_view" in p for p in problems), problems


def test_allows_real_public_document_outside_regulation():
    """국세청·한은 같은 공공 실존 자료는 regulation이 아니어도 통과해야 한다.

    이전 규칙(`synthetic=false ⇒ category=regulation`)이 막던 정당한 사례다.
    """
    problems = validate_chunks(
        _padded(
            _valid_chunk(
                chunk_id="real-tax-001",
                synthetic=False,
                category="tax",
                source="국세청 「소득세법 기본통칙」 88-0…1",
            )
        )
    )
    assert problems == [], problems


def test_detects_note_leaking_case_intent():
    problems = validate_chunks(
        _padded(_valid_chunk(chunk_id="note-001", note="case_007 함정용 청크"))
    )
    assert any("note-001" in p and "note" in p for p in problems), problems


def test_allows_note_with_authoring_principle():
    """실제 코퍼스의 note는 작성 원칙이다 — 정상 note가 오탐으로 걸리면 안 된다."""
    problems = validate_chunks(
        _padded(
            _valid_chunk(
                chunk_id="note-002",
                note="실존 기관명을 붙이지 않는다. '사내 하우스뷰(가상)'로 익명화.",
            )
        )
    )
    assert problems == [], problems


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
