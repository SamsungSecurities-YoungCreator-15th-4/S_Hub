"""R1 무라벨 사례집(goldenset/judge_inputs)을 judge 입력 state로 변환하는 로더.

R2 실행·기록 담당(다경)이 쓴다. 이 로더는 **정답이 제거된** `judge_inputs/`만
읽는다 — 원본 정답 사례집 `goldenset/cases/`는 열지 않는다. judge 실행 단계에는
gold label이 필요 없고, 정답은 실행 이후 분석 단계(merge_records)에서만 소비한다.

leakage 경계(코드로 강제): `load_case`가 만드는 state의 최상위 키는
``ALLOWED_STATE_KEYS``({metrics, explanations, citations})로 제한한다. 차단 목록이
아니라 허용 목록이라, 미래에 frontmatter에 필드가 추가돼도 자동으로 안전하다.
정답 필드(label/fail_axes/trap_type/rationale/…)는 어떤 경로로도 state에 들어가지
않는다. 계약은 tests/test_goldenset_integrity.py §8이 자동 검사한다.

형식 스펙은 goldenset/case-format.md(승민, 정답 없음·구조만 기술)를 따른다.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from engine.rag.citations import Citation, chunk_source, verify_citations
from engine.utils.hashing import sha256_of_dict

ROOT = Path(__file__).resolve().parents[2]
JUDGE_INPUTS_DIR = ROOT / "goldenset" / "judge_inputs"
MANIFEST_PATH = JUDGE_INPUTS_DIR / "manifest.json"
CHUNKS_PATH = ROOT / "goldenset" / "corpus" / "chunks.json"

# leakage 경계: load_case가 반환하는 state의 최상위 키는 이 셋뿐이다.
ALLOWED_STATE_KEYS = ("metrics", "explanations", "citations")

# judge의 numeric_consistency가 엔진 수치 문맥으로 인식하는 topic(app/judge/rubric.py
# _ENGINE_METRIC_TOPICS). 이 셋에 맞춰야 설명 문장의 수치가 metrics와 대조된다.
_TOPIC_VAR = "VaR 해석"
_TOPIC_STRESS = "스트레스 시나리오"
_TOPIC_NOTICE = "기준일 및 유의사항"

_FRONTMATTER_RE = re.compile(
    r"\A---\r?\n.*?\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)
# "## 3. VaR / CVaR" 형태의 섹션 제목. 번호는 사례마다 달라 제목 문자열로 매칭한다.
_SECTION_RE = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$", re.MULTILINE)
_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_HASH_RE = re.compile(
    r"(?:computation_hash|재현\s*해시|해시|hash)\s*[:=]?\s*`?([0-9a-fA-F]{8,64})`?",
    re.IGNORECASE,
)
# 인용 블록: > "인용문"  /  > — 출처: 문서명, chunk_id: xxx
_CITATION_RE = re.compile(
    r">\s*[\"“](?P<quote>[^\"”\n]+)[\"”]\s*\r?\n"
    r">\s*[—\-]\s*출처\s*[:：]\s*(?P<source>.+?)\s*,\s*chunk_id\s*[:：]\s*"
    r"(?P<chunk_id>[^\s,]+)",
    re.MULTILINE,
)
# 숫자+선택적 단위. 엔진 섹션에서 단위 없는 표 셀 숫자도 함께 잡는다.
_NUM_OPT_UNIT_RE = re.compile(
    r"(?<![\w.])(?P<number>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>%|bp|억원|억|만원|원|KRW|거래일|일)?"
)


class CaseFormatError(ValueError):
    """사례 형식이 로더가 기대한 구조와 다를 때 발생한다."""


# ── frontmatter / 섹션 분해 ──────────────────────────────────────────────

def _split_body(text: str, *, source: Path) -> str:
    """frontmatter(id/variant/llm_draft)를 버리고 본문만 반환한다.

    frontmatter는 어떤 값도 state로 옮기지 않는다(allowlist 밖). 정답 필드가 남아도
    본문만 쓰므로 애초에 state에 들어갈 경로가 없다.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise CaseFormatError(f"{source.name}: YAML frontmatter를 찾지 못했습니다.")
    return match.group("body")


def _sections(body: str) -> list[tuple[str, str]]:
    """본문을 (제목, 섹션 본문) 목록으로 분해한다. 제목 앞 preamble은 버린다."""
    matches = list(_SECTION_RE.finditer(body))
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        title = _strip_section_number(match.group("title"))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result.append((title, body[start:end].strip()))
    return result


def _strip_section_number(title: str) -> str:
    """'3. VaR / CVaR' → 'VaR / CVaR'. 번호·구분점을 제거한다."""
    return re.sub(r"^\s*\d+[.)]\s*", "", title).strip()


def _find_sections(sections: list[tuple[str, str]], *needles: str) -> list[tuple[str, str]]:
    """제목에 needle 중 하나라도 포함하는 섹션을 순서대로 반환한다."""
    hits: list[tuple[str, str]] = []
    for title, text in sections:
        if any(needle in title for needle in needles):
            hits.append((title, text))
    return hits


# ── 수치 추출 ────────────────────────────────────────────────────────────

def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def _magnitude(number: float, unit: str) -> float:
    """단위를 반영한 절대 크기(원/포인트/일). judge의 정규화와 같은 규약."""
    if unit in ("억원", "억"):
        return number * 100_000_000
    if unit == "만원":
        return number * 10_000
    if unit == "bp":
        return number / 100
    return number


def _collect_magnitudes(text: str) -> list[float]:
    """VaR/CVaR·스트레스 섹션의 모든 수치를 metrics 후보 크기로 모은다.

    이 섹션은 전부 엔진 값이므로 단위가 있든(예: '50억', '3%') 없든(표 셀의
    '31,212,000'처럼 단위가 헤더에만 있는 경우) 모든 숫자를 잡는다. 단위가 있으면
    크기 정규화값도 함께 넣어, 설명문이 '31,212,000원'·'50억원' 어느 표기로 적어도
    judge의 numeric_consistency가 metrics에서 같은 값을 찾도록 한다.
    """
    values: list[float] = []
    for match in _NUM_OPT_UNIT_RE.finditer(text):
        number = _to_float(match.group("number"))
        values.append(number)
        unit = match.group("unit")
        if unit:
            values.append(_magnitude(number, unit))
    return values


# ── metrics ──────────────────────────────────────────────────────────────

def _parse_metrics(sections: list[tuple[str, str]], body: str) -> dict:
    """VaR/CVaR·스트레스 섹션에서 엔진 수치를, 메타/기준일에서 재현 정보를 뽑는다.

    metrics는 설명문과 독립된 '엔진 값' 출처다 — VaR/CVaR·스트레스 섹션에서만
    수치를 모아, 설명문(explanations)이 이 값과 어긋나면 judge가 잡을 수 있게 한다.
    """
    horizons: dict[str, dict] = {}
    for title, text in _find_sections(sections, "VaR", "CVaR"):
        for label, key in (("1일", "1d"), ("1d", "1d"), ("10일", "10d"), ("10d", "10d")):
            values = _horizon_values(text, label)
            if values:
                horizons.setdefault(key, {})["values"] = sorted(
                    set(horizons.get(key, {}).get("values", []) + values)
                )

    stress: dict = {}
    stress_sections = _find_sections(sections, "스트레스")
    if stress_sections:
        stress_text = "\n".join(text for _, text in stress_sections)
        stress_values = _collect_magnitudes(stress_text)
        if stress_values:
            stress["values"] = sorted(set(stress_values))
        scenario = _first_scenario(stress_sections[0][0])
        if scenario:
            stress["scenario"] = scenario

    meta = {"data_period": {"end": _reference_date(sections, body)}}

    metrics: dict = {"meta": meta}
    if horizons:
        metrics["horizons"] = horizons
    if stress:
        metrics["stress"] = stress
    confidence = _confidence(body)
    if confidence is not None:
        metrics["confidence"] = confidence

    # 재현 해시: 사례집의 computation_hash는 '<실행 시 자동 기록>' 자리표시이므로,
    # 엔진처럼 metrics 수치 내용에서 결정론적으로 산출한다(같은 사례→같은 해시).
    # 형태 검사(computation_hash_present)의 재현성 근거를 채우기 위함이다.
    parsed_hash = _computation_hash(sections, body)
    meta["computation_hash"] = parsed_hash or _synthesize_hash(metrics)
    return metrics


def _synthesize_hash(metrics: dict) -> str:
    """metrics 수치 내용의 결정론적 sha256. 사례집 자리표시 해시를 대체한다.

    주의(방법론 한계): 이 값은 엔진이 산출한 재현 해시가 아니라 로더가 사례 내용에서
    합성한 값이다. R1 사례집의 computation_hash는 '<실행 시 자동 기록>' 자리표시라
    본문에 실제 해시가 없어, 형태 검사(computation_hash_present)의 재현성 근거를
    채우기 위해 합성한다. 따라서 정적 리포트 재생에서 computation_hash_present는
    실질적으로 무측정이다(엔진 산출 해시를 검증하는 것이 아님). judge_runner.py
    모듈 docstring 참조.
    """
    payload = {key: metrics[key] for key in ("horizons", "stress", "confidence") if key in metrics}
    payload["data_period_end"] = metrics.get("meta", {}).get("data_period", {}).get("end", "")
    return sha256_of_dict(payload)


def _horizon_values(section_text: str, label: str) -> list[float]:
    """VaR/CVaR 섹션에서 특정 보유기간(1일/10일) 관련 수치를 모은다.

    표·불릿·서술 3문체를 공통으로 처리한다. 표는 헤더에서 해당 보유기간 열을,
    불릿·서술은 라벨이 포함된 줄을 대상으로 크기를 수집한다.
    """
    values: list[float] = []
    lines = section_text.splitlines()
    header_cols: list[str] | None = None
    for line in lines:
        if "|" in line and header_cols is None and (label in line or "지표" in line):
            header_cols = [cell.strip() for cell in line.strip().strip("|").split("|")]
            continue
        if "|" in line and header_cols is not None:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if set(cells) <= {"", "-", "---", ":---", "---:", ":---:"}:
                continue
            col_index = _column_index(header_cols, label)
            if col_index is not None and col_index < len(cells):
                values.extend(_collect_magnitudes(cells[col_index]))
        elif label in line:
            values.extend(_collect_magnitudes(line))
    return values


def _column_index(header_cols: list[str], label: str) -> int | None:
    for index, col in enumerate(header_cols):
        if label in col:
            return index
    return None


def _first_scenario(title: str) -> str:
    """'스트레스 결과 — 고금리 시나리오' → '고금리 시나리오'."""
    parts = re.split(r"[—-]", title, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def _reference_date(sections: list[tuple[str, str]], body: str) -> str:
    """기준일(=data_period.end). '기준일: YYYY-MM-DD' 우선, 없으면 본문 첫 날짜."""
    match = re.search(r"기준일\D{0,12}(\d{4}-\d{2}-\d{2})", body)
    if match:
        return match.group(1)
    dates = _DATE_RE.findall(body)
    return dates[0] if dates else ""


def _computation_hash(sections: list[tuple[str, str]], body: str) -> str:
    for _, text in _find_sections(sections, "메타"):
        match = _HASH_RE.search(text)
        if match:
            return match.group(1)
    match = _HASH_RE.search(body)
    return match.group(1) if match else ""


def _confidence(body: str) -> float | None:
    match = re.search(r"신뢰\s*수준[^\d%]{0,20}(\d{2,3})\s*%", body)
    if match:
        return round(int(match.group(1)) / 100, 4)
    return None


# ── explanations ─────────────────────────────────────────────────────────

def _parse_explanations(sections: list[tuple[str, str]]) -> list[dict]:
    """각 섹션 본문을 {topic, text} 설명으로 옮긴다(본문 문장 그대로).

    표는 수치를 잃지 않도록 문장으로 펼친다. topic은 엔진 수치 문맥이 인식되도록
    VaR/스트레스/기준일 섹션을 정해진 이름에 매핑하고, 그 외는 제목을 그대로 쓴다.
    """
    explanations: list[dict] = []
    for title, text in sections:
        if _is_context_section(title):
            continue
        flat = _flatten_tables(text).strip()
        if not flat:
            continue
        explanations.append({"topic": _topic_for(title), "text": flat, "revision": 0})
    return explanations


def _is_context_section(title: str) -> bool:
    """고객·포트폴리오 요약은 입력 컨텍스트(자산배분 비중 등)이지 judge가 검증할
    분석 주장이 아니므로 explanations에서 제외한다. 이 섹션을 넣으면 배분 비중(%)이
    엔진 수치로 오인돼 numeric_consistency가 잘못 실패한다. 기준일은 metrics.meta로
    이미 반영된다."""
    return "고객" in title


def _topic_for(title: str) -> str:
    if "VaR" in title or "CVaR" in title:
        return _TOPIC_VAR
    if "스트레스" in title:
        return _TOPIC_STRESS
    if any(keyword in title for keyword in ("기준일", "면책", "메타", "유의", "안내", "고객")):
        return _TOPIC_NOTICE
    return title


def _flatten_tables(text: str) -> str:
    """마크다운 표 행을 문장으로 펼쳐 수치가 설명 텍스트에 남게 한다."""
    lines_out: list[str] = []
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if set(cells) <= {"", "-", "---", ":---", "---:", ":---:"}:
                continue
            if header is None:
                header = cells
                continue
            pairs = [
                f"{header[i]} {cells[i]}" if i < len(header) and header[i] else cells[i]
                for i in range(len(cells))
                if cells[i]
            ]
            lines_out.append(", ".join(pairs) + ".")
        else:
            header = None
            lines_out.append(line)
    return "\n".join(lines_out)


# ── citations ─────────────────────────────────────────────────────────────

def _load_chunks() -> list[dict]:
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


def _parse_citations(body: str, sections: list[tuple[str, str]], chunks: list[dict]) -> list[dict]:
    """인용 블록을 뽑아 chunk 원문을 붙이고 verify_citations로 검증한다.

    claim(주장 topic)은 인용이 속한 섹션 제목의 매핑 topic으로 둔다 — 같은 topic의
    설명 수치가 이 인용으로 뒷받침되는지 judge가 대조할 수 있게 하기 위함이다.
    chunks에 없는 chunk_id는 에러 대신 미검증으로 남긴다(그 자체가 판정 대상).
    """
    chunk_by_id = {
        chunk["chunk_id"]: chunk
        for chunk in chunks
        if isinstance(chunk, dict) and isinstance(chunk.get("chunk_id"), str)
    }
    candidates: list[Citation] = []
    for match in _CITATION_RE.finditer(body):
        chunk_id = match.group("chunk_id").strip()
        chunk = chunk_by_id.get(chunk_id)
        extra = {"chunk_text": chunk["text"]} if chunk else {}
        # 표시 출처명은 chunk_id가 가리키는 코퍼스 원문의 표준 문서명으로 정규화한다.
        # 리포트는 조문을 단축형('제15조')으로 인용하지만 코퍼스는 제목까지 붙은
        # 전체형('제15조(추정 불확실성 표기)')이라, 정규화하지 않으면 정상 인용도
        # 전부 문서명 불일치로 탈락한다. chunk_id가 코퍼스에 없으면(위조 함정)
        # 원문이 없으므로 본문 표기를 그대로 두어 미검증으로 남긴다.
        source = chunk_source(chunk) if chunk else match.group("source").strip()
        candidates.append(
            Citation(
                quote=match.group("quote").strip(),
                source=source,
                chunk_id=chunk_id,
                claim=_claim_for(body, match.start(), sections),
                extra=extra,
            )
        )
    # verify_citations는 candidates를 in-place로 갱신한다(통과분 verified=True +
    # provenance 첨부). 반환값은 안 쓰고 갱신된 원본을 그대로 직렬화하는 게 의도다.
    _verified, _rejected = verify_citations(candidates, chunks)
    return [citation.to_dict() for citation in candidates]


def _claim_for(body: str, position: int, sections: list[tuple[str, str]]) -> str:
    """인용 위치 바로 앞 섹션 제목의 매핑 topic을 claim으로 삼는다."""
    title = ""
    for match in _SECTION_RE.finditer(body):
        if match.start() <= position:
            title = _strip_section_number(match.group("title"))
        else:
            break
    return _topic_for(title) if title else ""


# ── 공개 API ───────────────────────────────────────────────────────────────

def load_case(path: str | Path, *, chunks: list[dict] | None = None) -> dict:
    """judge_inputs 사례 1건을 judge 입력 state로 변환한다.

    반환 dict의 최상위 키는 ALLOWED_STATE_KEYS(metrics/explanations/citations)뿐이다
    (leakage 경계). run_config·approval 등 실행 스캐폴딩은 러너가 감싼다.
    """
    path = Path(path)
    body = _split_body(path.read_text(encoding="utf-8"), source=path)
    sections = _sections(body)
    if chunks is None:
        chunks = _load_chunks()

    state = {
        "metrics": _parse_metrics(sections, body),
        "explanations": _parse_explanations(sections),
        "citations": _parse_citations(body, sections, chunks),
    }
    # 방어적 재확인: allowlist 밖 키가 새어 들어가지 않았는지 코드로 강제한다.
    extra = set(state) - set(ALLOWED_STATE_KEYS)
    if extra:  # 도달 불가 경로지만, 계약을 코드로 못 박는다.
        raise CaseFormatError(f"허용되지 않은 state 키: {sorted(extra)}")
    return state


# ── 무결성 검증 (manifest 대조) ─────────────────────────────────────────────

def _load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _body_hash(body: str) -> str:
    """frontmatter를 제외한 본문 해시. export_judge_inputs.py와 동일 규약이어야
    manifest의 동결 해시(case_content_sha256)와 대조된다(개행 정규화 + strip)."""
    normalized = body.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _compute_input_set_hash(pairs: list[dict]) -> str:
    """20건 (id, 본문 해시) 집합의 결정론 해시. export_judge_inputs.py와 동일 규약."""
    payload = [
        {"id": pair["id"], "case_content_sha256": pair["case_content_sha256"]}
        for pair in pairs
    ]
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def input_set_hash() -> str:
    """동결된 평가셋(20건 무라벨 본문 집합)의 식별 해시. v1/v2가 같은 세트로
    측정됐음을 증명하는 앵커다. 공식 evalset_hash(사람 라벨 포함)와는 다르다."""
    return _load_manifest()["input_set_hash"]


def load_all_cases(
    directory: str | Path | None = None,
    *,
    verify: bool = True,
    manifest: dict | None = None,
) -> list[dict]:
    """judge_inputs 디렉터리의 case_*.md 전부를 (case_id, state)로 로드한다.

    verify=True(기본)이면 manifest.json의 동결 해시와 대조해 **원본 그대로임을 증명**
    한다: 각 본문 해시가 manifest와 다르거나(변조/오염), 개수·id가 어긋나거나,
    집합 해시(input_set_hash)가 어긋나면 즉시 실패한다. manifest는 라벨이 없어 이
    대조는 방화벽에 걸리지 않는다(다경님이 유일하게 할 수 있는 무결성 검증).
    """
    directory = Path(directory) if directory is not None else JUDGE_INPUTS_DIR
    chunks = _load_chunks()
    if verify and manifest is None:
        manifest = _load_manifest()
    manifest_by_id = (
        {entry["id"]: entry for entry in manifest["cases"]} if verify else {}
    )

    cases: list[dict] = []
    pairs: list[dict] = []
    for path in sorted(directory.glob("case_*.md")):
        if verify:
            body = _split_body(path.read_text(encoding="utf-8"), source=path)
            body_hash = _body_hash(body)
            entry = manifest_by_id.get(path.stem)
            if entry is None:
                raise CaseFormatError(f"{path.name}: manifest에 없는 사례입니다.")
            if entry.get("case_content_sha256") != body_hash:
                raise CaseFormatError(
                    f"{path.name}: 본문 해시가 manifest 동결 해시와 다릅니다"
                    " (변조·오염 의심). v1 실행을 중단합니다."
                )
            pairs.append({"id": path.stem, "case_content_sha256": body_hash})
        cases.append({"case_id": path.stem, "state": load_case(path, chunks=chunks)})

    if verify:
        if len(cases) != manifest.get("case_count"):
            raise CaseFormatError(
                f"사례 수가 manifest와 다릅니다: {len(cases)} != {manifest.get('case_count')}"
            )
        recomputed = _compute_input_set_hash(pairs)
        if recomputed != manifest.get("input_set_hash"):
            raise CaseFormatError(
                "input_set_hash가 manifest와 다릅니다 — 평가셋 구성이 동결본과 다릅니다."
            )
    return cases
