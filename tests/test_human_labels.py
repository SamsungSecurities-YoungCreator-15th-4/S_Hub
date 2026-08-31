from __future__ import annotations

from pathlib import Path

import pytest

from engine.evaluation.human_labels import (
    HumanLabelLoadError,
    load_human_label_file,
    load_human_labels_from_dir,
)

ROOT = Path(__file__).resolve().parents[1]
STARTER_KIT = ROOT / "goldenset" / "starter-kit"


def _write(path: Path, frontmatter: str) -> Path:
    path.write_text(f"---\n{frontmatter}\n---\n\n# 본문\n본문은 읽지 않는다.\n", encoding="utf-8")
    return path


class TestLoadHumanLabelFile:
    def test_parses_pass_sample_from_starter_kit(self):
        result = load_human_label_file(STARTER_KIT / "sample-case-01-pass.md")
        assert result["id"] == "GS-EX-01"
        assert result["label"] == "pass"
        assert result["fail_axes"] == []
        assert isinstance(result["rationale"], str) and result["rationale"].strip()

    def test_parses_fail_sample_from_starter_kit(self):
        result = load_human_label_file(STARTER_KIT / "sample-case-02-fail-citation.md")
        assert result["id"] == "GS-EX-02"
        assert result["label"] == "fail"
        assert result["fail_axes"] == ["출처"]

    def test_ignores_fields_outside_human_label_contract(self, tmp_path: Path):
        path = _write(
            tmp_path / "case_001.md",
            'id: case_001\nlabel: pass\nfail_axes: []\nrationale: "정상"\n'
            'variant: "테스트"\ntrap_type: none\nlabelers: ["a", "b"]\n',
        )
        result = load_human_label_file(path)
        assert set(result) == {"id", "label", "fail_axes", "rationale"}

    def test_missing_leading_delimiter_raises(self, tmp_path: Path):
        path = tmp_path / "case_001.md"
        path.write_text("id: case_001\nlabel: pass\n", encoding="utf-8")
        with pytest.raises(HumanLabelLoadError, match="frontmatter가 아닙니다"):
            load_human_label_file(path)

    def test_unclosed_frontmatter_raises(self, tmp_path: Path):
        path = tmp_path / "case_001.md"
        path.write_text("---\nid: case_001\nlabel: pass\n", encoding="utf-8")
        with pytest.raises(HumanLabelLoadError, match="닫는 '---'"):
            load_human_label_file(path)

    def test_non_mapping_frontmatter_raises(self, tmp_path: Path):
        path = _write(tmp_path / "case_001.md", "- a\n- b")
        with pytest.raises(HumanLabelLoadError, match="dict 형태가 아닙니다"):
            load_human_label_file(path)

    def test_invalid_yaml_raises(self, tmp_path: Path):
        path = _write(tmp_path / "case_001.md", "id: [unclosed")
        with pytest.raises(HumanLabelLoadError, match="YAML 파싱"):
            load_human_label_file(path)


class TestLoadHumanLabelsFromDir:
    def test_reads_all_case_files_sorted(self, tmp_path: Path):
        _write(tmp_path / "case_002.md", 'id: case_002\nlabel: fail\nfail_axes: ["환각"]\nrationale: "case_002"')
        _write(tmp_path / "case_001.md", 'id: case_001\nlabel: pass\nfail_axes: []\nrationale: "case_001"')
        results = load_human_labels_from_dir(tmp_path)
        assert [r["id"] for r in results] == ["case_001", "case_002"]

    def test_ignores_non_case_prefixed_files(self, tmp_path: Path):
        _write(tmp_path / "case_001.md", 'id: case_001\nlabel: pass\nfail_axes: []\nrationale: "case_001"')
        (tmp_path / "labeling-guide.md").write_text("# 가이드\n", encoding="utf-8")
        results = load_human_labels_from_dir(tmp_path)
        assert len(results) == 1

    def test_empty_dir_raises(self, tmp_path: Path):
        with pytest.raises(HumanLabelLoadError, match="찾을 수 없습니다"):
            load_human_labels_from_dir(tmp_path)
