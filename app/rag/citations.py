"""인용 검증 — 순수 결정론 계층.

★이 파일에는 langchain/openai 등 LLM 관련 import를 절대 추가하지 않는다.★
LLM은 인용 후보를 "만들" 수는 있어도, 이 검증을 "통과시킬" 수는 없다:
인용문이 해당 chunk_id 원문의 실제 부분문자열일 때만 verified=True가 된다.
같은 입력이면 항상 같은 결과가 나온다(재현성).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath


LOCATOR_KEYS = ("article", "clause", "section", "locator")


@dataclass
class Citation:
    """수치·주장 하나를 뒷받침하는 인용."""

    quote: str          # 원문에서 그대로 따온 인용문
    source: str         # 파일명 (청크 metadata의 source)
    chunk_id: str       # 인용이 속한 청크 id
    verified: bool = False
    claim: str = ""     # 이 인용이 뒷받침하는 수치/주장 (선택)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "quote": self.quote,
            "source": self.source,
            "chunk_id": self.chunk_id,
            "verified": self.verified,
            "claim": self.claim,
            **({"extra": self.extra} if self.extra else {}),
        }


def normalize_ws(text: str) -> str:
    """공백 정규화 — 모든 연속 공백(개행 포함)을 단일 스페이스로."""
    return " ".join(text.split())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(normalize_ws(text).encode("utf-8")).hexdigest()


def _source_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return PurePosixPath(value.replace("\\", "/")).name.strip()


def chunk_source(chunk: dict) -> str:
    """청크의 표시 문서명. `source`가 없으면 chunk_id 접두에서 되살린다.

    공개 API다 — 탈락 인용 감사 기록(`app/nodes/rag_cite.py`)이 검증기와 **같은**
    정규화를 써야 해서 노드에서 직접 호출한다. 재구현하면 기록과 판정이 어긋난다.
    """
    source = _source_name(chunk.get("source"))
    if source:
        return source
    chunk_id = chunk.get("chunk_id")
    if not isinstance(chunk_id, str) or "::" not in chunk_id:
        return ""
    return _source_name(chunk_id.rsplit("::", 1)[0])


def locator_metadata(value: object) -> dict[str, str]:
    """조항/절/항 표기만 정규화해 뽑는다. 공개 API — `chunk_source`와 같은 이유."""
    if not isinstance(value, dict):
        return {}
    return {
        key: normalize_ws(raw)
        for key in LOCATOR_KEYS
        if isinstance((raw := value.get(key)), str) and normalize_ws(raw)
    }


# 모듈 내부 기존 호출부 호환용 별칭.
_chunk_source = chunk_source
_locator_metadata = locator_metadata


def _citation_provenance(citation: Citation, chunk: dict) -> dict:
    """검색 원문과 검증된 인용의 결정론적 감사 지문을 만든다."""
    chunk_text = chunk.get("text")
    normalized_chunk_text = chunk_text if isinstance(chunk_text, str) else ""
    return {
        "source": _chunk_source(chunk),
        "chunk_id": citation.chunk_id,
        "claim": citation.claim,
        "quote_sha256": _sha256_text(citation.quote),
        "chunk_text_sha256": _sha256_text(normalized_chunk_text),
        "locator": _locator_metadata(chunk),
    }


def citation_contract_issues(
    citation: object,
    *,
    require_chunk_text: bool,
) -> list[str]:
    """Judge 직전 인용 payload의 원문·문서·조항·청크 일치를 검증한다.

    `verify_citations`가 만든 provenance가 있으면 지문까지 다시 대조한다.
    조항 메타데이터(article/clause/section/locator)는 코퍼스가 제공하는 경우에만
    검사하되, 제공된 값은 한 글자라도 다르면 실패한다.
    """
    if not isinstance(citation, dict):
        return ["인용 형식 오류"]

    issues: list[str] = []
    quote = citation.get("quote")
    source = citation.get("source")
    chunk_id = citation.get("chunk_id")
    claim = citation.get("claim")
    extra = citation.get("extra")
    extra = extra if isinstance(extra, dict) else {}
    chunk_text = extra.get("chunk_text")

    if citation.get("verified") is not True:
        issues.append("verified=true 아님")
    if not isinstance(quote, str) or not normalize_ws(quote):
        issues.append("인용문 누락")
    if not isinstance(source, str) or not _source_name(source):
        issues.append("문서명 누락")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        issues.append("chunk_id 누락")
    if not isinstance(claim, str) or not normalize_ws(claim):
        issues.append("인용 대상 조항/주장 누락")

    if (
        isinstance(source, str)
        and isinstance(chunk_id, str)
        and "::" in chunk_id
        and _source_name(source) != _source_name(chunk_id.rsplit("::", 1)[0])
    ):
        issues.append("문서명과 chunk_id 불일치")

    if not isinstance(chunk_text, str) or not normalize_ws(chunk_text):
        if require_chunk_text:
            issues.append("검증 원문 청크 누락")
    elif isinstance(quote, str) and normalize_ws(quote) not in normalize_ws(chunk_text):
        issues.append("인용문과 원문 청크 불일치")

    provenance = extra.get("provenance")
    if isinstance(provenance, dict):
        if _source_name(source) != _source_name(provenance.get("source")):
            issues.append("문서명 provenance 불일치")
        if chunk_id != provenance.get("chunk_id"):
            issues.append("chunk_id provenance 불일치")
        if claim != provenance.get("claim"):
            issues.append("인용 대상 조항/주장 provenance 불일치")
        if isinstance(quote, str) and _sha256_text(quote) != provenance.get(
            "quote_sha256"
        ):
            issues.append("인용문 provenance 지문 불일치")
        if isinstance(chunk_text, str) and _sha256_text(chunk_text) != provenance.get(
            "chunk_text_sha256"
        ):
            issues.append("원문 청크 provenance 지문 불일치")

        expected_locator = _locator_metadata(provenance.get("locator"))
        cited_locator = _locator_metadata(citation) or _locator_metadata(extra)
        if expected_locator and not cited_locator:
            issues.append("문서 조항/절/항 표기 누락")
        elif cited_locator and cited_locator != expected_locator:
            issues.append("문서 조항/절/항 provenance 불일치")

    return list(dict.fromkeys(issues))


def verify_citations(
    citations: list[Citation],
    chunks: list[dict],
) -> tuple[list[Citation], list[dict]]:
    """각 인용문이 해당 chunk_id 원문에 실제로 존재하는지 검증한다.

    Args:
        citations: 검증할 인용 후보 목록.
        chunks: 검색된 청크 목록. 각 항목은 최소 {"chunk_id": str, "text": str}.

    Returns:
        (verified, rejected)
        - verified: 검증을 통과한 Citation 목록 (verified=True로 마킹).
        - rejected: 탈락 인용의 로그용 목록 [{"quote", "source", "chunk_id", "reason"}].

    검증 규칙(순수 결정론):
    - chunk_id가 chunks에 존재해야 한다.
    - 표시 문서명이 해당 청크 metadata의 source와 일치해야 한다.
    - 공백 정규화 후, 인용문이 청크 원문의 부분문자열이어야 한다.
    - 조항 metadata가 함께 주어지면 원문 청크 metadata와 일치해야 한다.
    - 빈 인용문은 탈락.
    """
    chunk_by_id = {
        c["chunk_id"]: c
        for c in chunks
        if isinstance(c, dict) and isinstance(c.get("chunk_id"), str)
    }

    verified: list[Citation] = []
    rejected: list[dict] = []

    for cit in citations:
        reason = None
        norm_quote = normalize_ws(cit.quote)

        if not norm_quote:
            reason = "빈 인용문"
        elif cit.chunk_id not in chunk_by_id:
            reason = f"존재하지 않는 chunk_id: {cit.chunk_id}"
        else:
            chunk = chunk_by_id[cit.chunk_id]
            expected_source = _chunk_source(chunk)
            cited_source = _source_name(cit.source)
            cited_locator = _locator_metadata(cit.extra)
            expected_locator = _locator_metadata(chunk)

        if reason is None and expected_source and cited_source != expected_source:
            reason = (
                "문서명과 chunk_id 원문 source 불일치"
                f"({cited_source or '누락'} != {expected_source})"
            )
        elif reason is None and expected_locator and not cited_locator:
            reason = "원문 청크에 존재하는 문서 조항/절/항 표기 누락"
        elif reason is None and cited_locator and cited_locator != expected_locator:
            reason = "문서 조항/절/항과 원문 청크 metadata 불일치"
        elif reason is None:
            chunk_text = chunk.get("text")
            normalized_chunk = normalize_ws(chunk_text) if isinstance(chunk_text, str) else ""
            if norm_quote not in normalized_chunk:
                reason = "인용문이 청크 원문에 없음(환각 의심)"

        if reason is None:
            cit.verified = True
            raw_extra = cit.extra if isinstance(cit.extra, dict) else {}
            cit.extra = {
                **raw_extra,
                "provenance": _citation_provenance(cit, chunk),
            }
            verified.append(cit)
        else:
            cit.verified = False
            rejected.append(
                {
                    "quote": cit.quote,
                    "source": cit.source,
                    "chunk_id": cit.chunk_id,
                    "reason": reason,
                }
            )

    return verified, rejected
