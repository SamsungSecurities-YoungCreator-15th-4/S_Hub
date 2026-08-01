"""R1 정답과 R2 Judge 실행 입력 사이의 비누출 방화벽 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GS = ROOT / "goldenset"
TOOL_PATH = GS / "tools" / "export_judge_inputs.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("export_judge_inputs", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n")
    raw = text.split("---\n", 2)[1]
    parsed = yaml.safe_load(raw)
    assert isinstance(parsed, dict)
    return parsed


def test_sanitize_case_uses_allowlist_and_preserves_body(tmp_path):
    tool = _load_tool()
    source = tmp_path / "case_001.md"
    body = "# 문제 본문\n\n수치와 인용은 그대로 유지합니다.\n"
    raw = (
        "---\n"
        "id: case_001\n"
        "variant: 테스트\n"
        "label: fail\n"
        "fail_axes: [환각]\n"
        "rationale: 정답 사유\n"
        "future_answer_metadata: 새 정답 필드\n"
        "llm_draft: true\n"
        f"---\n{body}"
    )

    case_id, _, clean = tool.sanitize_case(raw, source=source)

    assert case_id == "case_001"
    assert _frontmatter(clean) == {
        "id": "case_001",
        "variant": "테스트",
        "llm_draft": True,
    }
    assert clean.endswith(body)


def test_committed_judge_inputs_match_generator():
    tool = _load_tool()
    problems = tool.check_outputs(tool.build_outputs())
    assert not problems, problems


def test_judge_inputs_contain_20_cases_without_answer_metadata():
    tool = _load_tool()
    files = sorted(tool.OUTPUT_DIR.glob("case_*.md"))
    assert len(files) == tool.EXPECTED_CASE_COUNT

    for path in files:
        metadata = _frontmatter(path.read_text(encoding="utf-8"))
        assert set(metadata) <= set(tool.ALLOWED_FRONTMATTER_FIELDS)
        assert not set(metadata) & set(tool.ANSWER_FIELDS)
        assert metadata["id"] == path.stem


def test_manifest_hashes_match_frozen_r1_case_hashes():
    manifest = json.loads(
        (GS / "judge_inputs" / "manifest.json").read_text(encoding="utf-8")
    )
    frozen = json.loads((GS / "case_hashes.json").read_text(encoding="utf-8"))[
        "hashes"
    ]

    assert manifest["case_count"] == 20
    assert {
        case["id"]: case["case_content_sha256"] for case in manifest["cases"]
    } == frozen
    assert len(manifest["evalset_hash"]) == 64
