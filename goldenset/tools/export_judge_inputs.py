"""R1 정답 사례집에서 R2 Judge 실행용 무라벨 입력본을 생성한다.

이 도구는 정답과 문제가 한 파일에 있는 ``goldenset/cases/case_*.md``를
정답 관리자가 한 번 변환할 때 사용한다. R2 실행 담당자는 원본을 읽지 않고
생성된 ``goldenset/judge_inputs/``만 소비한다.

보안 경계는 차단 목록이 아니라 frontmatter allowlist로 구현한다. 따라서 미래에
정답 메타데이터가 추가되어도 ``id``·``variant``·``llm_draft`` 외에는 출력되지
않는다. 사례 본문은 한 글자도 바꾸지 않으며, R1 동결 해시와 대조한다.

사용:
  python goldenset/tools/export_judge_inputs.py
  python goldenset/tools/export_judge_inputs.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "cases"
OUTPUT_DIR = ROOT / "judge_inputs"
HASH_RECORD = ROOT / "case_hashes.json"

EXPECTED_CASE_COUNT = 20
ALLOWED_FRONTMATTER_FIELDS = ("id", "variant", "llm_draft")
ANSWER_FIELDS = (
    "label",
    "fail_axes",
    "trap_type",
    "rationale",
    "labelers",
    "initial_agreement",
    "labeling_method",
)
BODY_ANSWER_PATTERNS = (
    (
        re.compile(
            r"^\s*(?:label|fail_axes|trap_type|rationale|labelers|"
            r"initial_agreement|labeling_method)\s*:",
            re.IGNORECASE | re.MULTILINE,
        ),
        "정답 키 YAML 표기",
    ),
    (
        re.compile(r"정답|오답|gold[_ -]?label|함정", re.IGNORECASE),
        "정답·오답·Gold Label·함정 표기",
    ),
    (
        re.compile(r"^#{1,6}\s+.*(?:판정|채점|라벨)", re.MULTILINE),
        "판정·채점·라벨 제목",
    ),
    (
        re.compile(r"\b(?:pass|fail)\b", re.IGNORECASE),
        "PASS/FAIL 표기",
    ),
)
FRONTMATTER_RE = re.compile(
    r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)

README = """# R2 Judge 실행용 무라벨 입력본

이 디렉터리는 `goldenset/cases/case_*.md`에서 정답성 frontmatter를 제거한
Judge 실행 전용 입력입니다. R2 실행 담당자는 원본 정답 사례집을 열거나 파싱하지
않고 이 디렉터리만 사용합니다.

- 유지: `id`, `variant`, `llm_draft`, 사례 본문
- 제거: 사람 정답, 실패 축, 함정 유형, 판정 사유 및 라벨링 이력
- 생성: `python goldenset/tools/export_judge_inputs.py`
- 검증: `python goldenset/tools/export_judge_inputs.py --check`

`manifest.json`의 사례별 SHA-256은 frontmatter를 제외한 본문 해시이며,
`goldenset/case_hashes.json`의 R1 동결 해시와 일치해야 합니다.

`input_set_hash`는 **사람 라벨을 포함하지 않은 20건 본문 집합의 해시**입니다.
`app/evidence/schema.py`의 공식 `evalset_hash`와 다릅니다. 공식 값은 사례 본문과
사람 라벨을 함께 고정하므로 calibration summary에는 반드시 그 값을 사용합니다.
"""


def _split_case(text: str, *, source: Path) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError(f"{source}: YAML frontmatter를 찾지 못했습니다.")

    metadata = yaml.safe_load(match.group("frontmatter"))
    if not isinstance(metadata, dict):
        raise ValueError(f"{source}: frontmatter는 mapping이어야 합니다.")
    return metadata, match.group("body")


def _body_hash(body: str) -> str:
    normalized = body.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_body_has_no_answers(body: str, *, source: Path) -> None:
    leaked = [description for pattern, description in BODY_ANSWER_PATTERNS if pattern.search(body)]
    if leaked:
        raise ValueError(
            f"{source}: 사례 본문에 정답성 표기가 있습니다: {', '.join(leaked)}"
        )


def sanitize_case(text: str, *, source: Path) -> tuple[str, str, str]:
    """정답 메타데이터를 제거하고 ``(id, 본문 해시, 출력문)``을 반환한다."""
    metadata, body = _split_case(text, source=source)
    case_id = metadata.get("id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError(f"{source}: 비어 있지 않은 id가 필요합니다.")
    if case_id != source.stem:
        raise ValueError(f"{source}: id({case_id})와 파일명({source.stem})이 다릅니다.")
    _validate_body_has_no_answers(body, source=source)

    clean_metadata = {
        key: metadata[key]
        for key in ALLOWED_FRONTMATTER_FIELDS
        if key in metadata
    }
    clean_frontmatter = yaml.safe_dump(
        clean_metadata,
        allow_unicode=True,
        sort_keys=False,
        width=4096,
    ).rstrip()
    clean_text = f"---\n{clean_frontmatter}\n---\n{body}"
    return case_id, _body_hash(body), clean_text


def _load_frozen_hashes() -> dict[str, str]:
    try:
        payload = json.loads(HASH_RECORD.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"R1 동결 해시를 읽을 수 없습니다: {HASH_RECORD}") from exc
    hashes = payload.get("hashes") if isinstance(payload, dict) else None
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError(f"R1 동결 해시가 비어 있습니다: {HASH_RECORD}")
    return hashes


def build_outputs() -> dict[Path, str]:
    """동결 검증을 통과한 20건과 설명·manifest의 기대 출력을 만든다."""
    sources = sorted(SOURCE_DIR.glob("case_*.md"))
    if len(sources) != EXPECTED_CASE_COUNT:
        raise ValueError(
            f"R1 사례는 정확히 {EXPECTED_CASE_COUNT}건이어야 합니다: {len(sources)}건"
        )

    frozen_hashes = _load_frozen_hashes()
    outputs: dict[Path, str] = {OUTPUT_DIR / "README.md": README}
    cases: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for source in sources:
        case_id, content_hash, clean_text = sanitize_case(
            source.read_text(encoding="utf-8"),
            source=source,
        )
        if case_id in seen_ids:
            raise ValueError(f"중복 사례 id: {case_id}")
        seen_ids.add(case_id)
        if frozen_hashes.get(case_id) != content_hash:
            raise ValueError(
                f"{case_id}: 본문이 R1 동결 해시와 다릅니다. 입력본 생성을 중단합니다."
            )

        filename = f"{case_id}.md"
        outputs[OUTPUT_DIR / filename] = clean_text
        cases.append(
            {
                "id": case_id,
                "file": filename,
                "case_content_sha256": content_hash,
            }
        )

    input_set_payload = [
        {"id": case["id"], "case_content_sha256": case["case_content_sha256"]}
        for case in cases
    ]
    input_set_hash = hashlib.sha256(
        json.dumps(
            input_set_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": "2026-08-02.v2",
        "case_count": len(cases),
        "allowed_frontmatter_fields": list(ALLOWED_FRONTMATTER_FIELDS),
        "answer_fields_removed": list(ANSWER_FIELDS),
        "input_set_hash": input_set_hash,
        "cases": cases,
    }
    outputs[OUTPUT_DIR / "manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return outputs


def _unexpected_output_entries(outputs: dict[Path, str]) -> list[str]:
    if not OUTPUT_DIR.exists():
        return []
    allowed_names = {path.name for path in outputs}
    return sorted(path.name for path in OUTPUT_DIR.iterdir() if path.name not in allowed_names)


def write_outputs(outputs: dict[Path, str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    unexpected = _unexpected_output_entries(outputs)
    if unexpected:
        raise ValueError(
            "허용되지 않은 입력 디렉터리 항목이 있습니다: "
            + ", ".join(unexpected)
            + ". 해당 항목을 직접 제거한 뒤 다시 실행하세요."
        )
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> list[str]:
    problems: list[str] = []
    for path, expected in outputs.items():
        if not path.exists():
            problems.append(f"누락: {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"불일치: {path.relative_to(ROOT)}")

    for name in _unexpected_output_entries(outputs):
        problems.append(f"허용되지 않은 항목: judge_inputs/{name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="R1 사례집에서 R2 Judge 실행용 무라벨 입력본을 생성·검증합니다."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="파일을 쓰지 않고 커밋된 입력본이 생성 결과와 같은지 검증합니다.",
    )
    args = parser.parse_args()

    try:
        outputs = build_outputs()
        if args.check:
            problems = check_outputs(outputs)
            if problems:
                print("무라벨 Judge 입력본 검증 실패:")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            print(f"무라벨 Judge 입력본 {EXPECTED_CASE_COUNT}건이 생성 규칙과 일치합니다.")
            return 0

        write_outputs(outputs)
        print(f"무라벨 Judge 입력본 {EXPECTED_CASE_COUNT}건을 {OUTPUT_DIR}에 생성했습니다.")
        return 0
    except ValueError as exc:
        print(f"입력본 생성 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
