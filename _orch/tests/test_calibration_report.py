from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calibration_report  # noqa: E402

from app.judge.axes import to_ko  # noqa: E402
from app.judge.rubric import AXIS_NAMES  # noqa: E402


def _sha256_hex(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _rubric(fail_axes: tuple[str, ...] = ()) -> dict:
    return {axis: {"passed": axis not in fail_axes, "reason": "mock reason"} for axis in AXIS_NAMES}


def _checks(*, rubric_fail_axes: tuple[str, ...] = ()) -> list[dict]:
    checks = [
        {"name": axis, "passed": axis not in rubric_fail_axes, "required": True, "detail": "mock axis detail"}
        for axis in AXIS_NAMES
    ]
    checks.extend(
        {"name": name, "passed": True, "required": True, "detail": "mock system detail"}
        for name in ("metrics_present", "computation_hash_present", "citations_all_verified")
    )
    return checks


def _human(case_id: str, label: str, fail_axes: list[str] | None = None) -> dict:
    return {"id": case_id, "label": label, "fail_axes": fail_axes or [], "rationale": f"{case_id} rationale"}


def _model_version() -> dict:
    return {"deployment": "gpt-mock", "model": "gpt-mock-2026", "api_version": "2026-01-01"}


def _judge(
    case_id: str,
    passed: bool,
    fail_axes_en: tuple[str, ...] = (),
    *,
    prompt_version: str = "v1",
    code_sha: str = "deadbeef",
) -> dict:
    return {
        "case_id": case_id,
        "passed": passed,
        "reason": f"{case_id} judge reason",
        "rubric": _rubric(fail_axes_en),
        "checks": _checks(rubric_fail_axes=fail_axes_en),
        "judge_attempt": 1,
        "judge_feedback": "" if passed else f"{case_id} rewrite feedback",
        "manual_review_flags": [],
        "prompt_version": prompt_version,
        "prompt_hash": _sha256_hex(f"{prompt_version}-{case_id}"),
        "model_version": _model_version(),
        "trace_id": f"trace-{case_id}-{prompt_version}",
        "langsmith_run_id": None,
        "langsmith_trace_url": None,
        "code_sha": code_sha,
        "case_content_sha256": _sha256_hex(case_id),
        "as_of_date": "2026-06-30",
        "strict_citation_gate": False,
    }


# case_001: 사람 pass, judge pass (TN) / case_002: 사람 fail(출처), judge pass (FN)
# case_003: 사람 pass, judge fail(면책) (FP) / case_004: 사람 fail(수치 정합), judge 동일 축 fail (TP)
HUMAN_LABELS = [
    _human("case_001", "pass"),
    _human("case_002", "fail", ["출처"]),
    _human("case_003", "pass"),
    _human("case_004", "fail", ["수치 정합"]),
]
JUDGE_RESULTS_V1 = [
    _judge("case_001", True),
    _judge("case_002", True),
    _judge("case_003", False, ("disclaimer",)),
    _judge("case_004", False, ("numeric_consistency",)),
]
# v2: case_002의 FN을 잡아 개선된 상황을 흉내낸다.
JUDGE_RESULTS_V2 = [
    _judge("case_001", True, prompt_version="v2", code_sha="cafebabe"),
    _judge("case_002", False, ("source_validity",), prompt_version="v2", code_sha="cafebabe"),
    _judge("case_003", False, ("disclaimer",), prompt_version="v2", code_sha="cafebabe"),
    _judge("case_004", False, ("numeric_consistency",), prompt_version="v2", code_sha="cafebabe"),
]


@pytest.fixture()
def files(tmp_path: Path) -> dict[str, Path]:
    human_path = tmp_path / "human_labels.json"
    human_path.write_text(json.dumps(HUMAN_LABELS, ensure_ascii=False), encoding="utf-8")
    v1_path = tmp_path / "v1.json"
    v1_path.write_text(json.dumps(JUDGE_RESULTS_V1, ensure_ascii=False), encoding="utf-8")
    v2_path = tmp_path / "v2.json"
    v2_path.write_text(json.dumps(JUDGE_RESULTS_V2, ensure_ascii=False), encoding="utf-8")
    return {"human": human_path, "v1": v1_path, "v2": v2_path}


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["calibration_report.py", *argv])
    calibration_report.main()


def _official_human_labels() -> list[dict]:
    """공식 20건(case_001~020) — pass 10건 + 6축 전부 최소 1건씩 커버하는 fail 10건."""
    labels = [_human(f"case_{i:03d}", "pass") for i in range(1, 11)]
    fail_axes_en = list(AXIS_NAMES) + [AXIS_NAMES[2]] * 4  # 나머지 4건은 환각을 재사용
    for offset, axis_en in enumerate(fail_axes_en):
        case_id = f"case_{11 + offset:03d}"
        labels.append(_human(case_id, "fail", [to_ko(axis_en)]))
    return labels


def _official_judge_results(*, prompt_version: str, code_sha: str) -> list[dict]:
    """_official_human_labels()와 축까지 정확히 일치하는(TP) judge 결과 — 검증 통과가 목적."""
    results = [
        _judge(f"case_{i:03d}", True, prompt_version=prompt_version, code_sha=code_sha) for i in range(1, 11)
    ]
    fail_axes_en = list(AXIS_NAMES) + [AXIS_NAMES[2]] * 4
    for offset, axis_en in enumerate(fail_axes_en):
        case_id = f"case_{11 + offset:03d}"
        results.append(_judge(case_id, False, (axis_en,), prompt_version=prompt_version, code_sha=code_sha))
    return results


@pytest.fixture()
def official_files(tmp_path: Path) -> dict[str, Path]:
    human_path = tmp_path / "human_labels.json"
    human_path.write_text(json.dumps(_official_human_labels(), ensure_ascii=False), encoding="utf-8")
    v1_path = tmp_path / "v1.json"
    v1_path.write_text(
        json.dumps(_official_judge_results(prompt_version="v1", code_sha="deadbeef"), ensure_ascii=False),
        encoding="utf-8",
    )
    v2_path = tmp_path / "v2.json"
    v2_path.write_text(
        json.dumps(_official_judge_results(prompt_version="v2", code_sha="cafebabe"), ensure_ascii=False),
        encoding="utf-8",
    )
    return {"human": human_path, "v1": v1_path, "v2": v2_path}


@pytest.fixture()
def official_files_with_v3(official_files, tmp_path: Path) -> dict[str, Path]:
    """v2→v3처럼 prompt_hash는 v2와 동일하고 code_sha만 다른 v3.json을 추가한다."""
    v2_by_id = {
        r["case_id"]: r
        for r in json.loads(official_files["v2"].read_text(encoding="utf-8"))
    }
    v3 = _official_judge_results(prompt_version="v3", code_sha="fadedbee")
    for result in v3:
        result["prompt_hash"] = v2_by_id[result["case_id"]]["prompt_hash"]
    v3_path = tmp_path / "v3.json"
    v3_path.write_text(json.dumps(v3, ensure_ascii=False), encoding="utf-8")
    return {**official_files, "v3": v3_path}


class TestCalibrationReportV1Only:
    def test_prints_overall_metrics_and_mismatches(self, files, monkeypatch, capsys):
        _run(
            monkeypatch,
            ["--human-labels-json", str(files["human"]), "--judge-results", str(files["v1"])],
        )
        out = capsys.readouterr().out
        assert "총 4건" in out
        assert "결함 놓침(FN" in out
        assert "과잉 차단(FP" in out
        assert "case_002" in out and "false_negative" in out
        assert "case_003" in out and "false_positive" in out

    def test_writes_out_json_report(self, files, monkeypatch, capsys, tmp_path: Path):
        out_path = tmp_path / "report.json"
        _run(
            monkeypatch,
            [
                "--human-labels-json", str(files["human"]),
                "--judge-results", str(files["v1"]),
                "--out", str(out_path),
            ],
        )
        report = json.loads(out_path.read_text(encoding="utf-8"))
        assert report["schema_version"] == calibration_report.SCHEMA_VERSION
        assert report["mode"] == "dev_mock"
        assert report["official_validation_passed"] is False
        assert "evalset_hash" in report["v1"]
        assert report["v1"]["overall"]["total"] == 4
        assert report["v1"]["overall"]["false_negative"] == 1
        assert report["v1"]["overall"]["false_positive"] == 1
        assert "v2" not in report

    def test_human_labels_dir_matches_json_input(self, files, monkeypatch, capsys, tmp_path: Path):
        label_dir = tmp_path / "labels"
        label_dir.mkdir()
        for label in HUMAN_LABELS:
            fail_axes = json.dumps(label["fail_axes"], ensure_ascii=False)
            (label_dir / f"{label['id']}.md").write_text(
                f"---\nid: {label['id']}\nlabel: {label['label']}\n"
                f"fail_axes: {fail_axes}\nrationale: \"{label['rationale']}\"\n---\n\n본문\n",
                encoding="utf-8",
            )
        _run(
            monkeypatch,
            ["--human-labels-dir", str(label_dir), "--judge-results", str(files["v1"])],
        )
        out = capsys.readouterr().out
        assert "총 4건" in out


class TestCalibrationReportVersionComparison:
    def test_prints_and_saves_v1_v2_comparison(self, files, monkeypatch, capsys, tmp_path: Path):
        out_path = tmp_path / "report.json"
        _run(
            monkeypatch,
            [
                "--human-labels-json", str(files["human"]),
                "--judge-results", str(files["v1"]),
                "--judge-results-v2", str(files["v2"]),
                "--out", str(out_path),
            ],
        )
        out = capsys.readouterr().out
        assert "v1 → v2 비교" in out
        assert "code_sha: deadbeef" in out and "cafebabe" in out

        report = json.loads(out_path.read_text(encoding="utf-8"))
        comparison = report["comparison"]
        assert comparison["before"]["false_negative"] == 1
        assert comparison["after"]["false_negative"] == 0
        assert comparison["false_negative_delta"] == -1
        assert comparison["before_code_sha"] == "deadbeef"
        assert comparison["after_code_sha"] == "cafebabe"


class TestCalibrationReportOfficialMode:
    def test_no_langsmith_without_official_is_rejected(self, files, monkeypatch):
        with pytest.raises(SystemExit):
            _run(
                monkeypatch,
                [
                    "--human-labels-json", str(files["human"]),
                    "--judge-results", str(files["v1"]),
                    "--no-langsmith",
                ],
            )

    def test_official_no_langsmith_v1_v2_comparison_succeeds(self, official_files, monkeypatch, capsys, tmp_path: Path):
        """회귀 테스트: --official --no-langsmith일 때 compare_official_versions()에
        require_langsmith가 전달되지 않아 validate_official_case_set() 통과 뒤
        비교 단계에서 다시 실패하던 버그(중현 리뷰 PR #147)의 재발을 막는다."""
        out_path = tmp_path / "report.json"
        _run(
            monkeypatch,
            [
                "--human-labels-json", str(official_files["human"]),
                "--judge-results", str(official_files["v1"]),
                "--judge-results-v2", str(official_files["v2"]),
                "--official", "--no-langsmith",
                "--out", str(out_path),
            ],
        )
        out = capsys.readouterr().out
        assert "v1 → v2 비교" in out

        report = json.loads(out_path.read_text(encoding="utf-8"))
        assert report["mode"] == "offline_rehearsal"
        assert report["official_validation_passed"] is True
        assert report["langsmith_required"] is False

    def test_official_without_no_langsmith_still_requires_langsmith_ids(self, official_files, monkeypatch):
        # official_files의 langsmith_run_id는 전부 None이므로 --no-langsmith 없이
        # --official만 쓰면 validate_official_case_set()에서 거부돼야 한다.
        with pytest.raises(Exception, match="LangSmith"):
            _run(
                monkeypatch,
                [
                    "--human-labels-json", str(official_files["human"]),
                    "--judge-results", str(official_files["v1"]),
                    "--official",
                ],
            )

    def test_no_prompt_change_required_without_official_is_rejected(self, files, monkeypatch):
        with pytest.raises(SystemExit):
            _run(
                monkeypatch,
                [
                    "--human-labels-json", str(files["human"]),
                    "--judge-results", str(files["v1"]),
                    "--no-prompt-change-required",
                ],
            )

    def test_v2_v3_with_identical_prompt_hash_is_rejected_without_the_flag(
        self, official_files_with_v3, monkeypatch
    ):
        """--no-prompt-change-required 없이 v2→v3(prompt_hash 동일)를 official로
        비교하면 여전히 거부돼야 한다 — 이 플래그가 실제로 필요함을 보여준다."""
        with pytest.raises(Exception, match="prompt_hash"):
            _run(
                monkeypatch,
                [
                    "--human-labels-json", str(official_files_with_v3["human"]),
                    "--judge-results", str(official_files_with_v3["v2"]),
                    "--judge-results-v2", str(official_files_with_v3["v3"]),
                    "--official", "--no-langsmith",
                ],
            )

    def test_no_prompt_change_required_allows_code_only_v2_v3_comparison(
        self, official_files_with_v3, monkeypatch, capsys, tmp_path: Path
    ):
        out_path = tmp_path / "report.json"
        _run(
            monkeypatch,
            [
                "--human-labels-json", str(official_files_with_v3["human"]),
                "--judge-results", str(official_files_with_v3["v2"]),
                "--judge-results-v2", str(official_files_with_v3["v3"]),
                "--official", "--no-langsmith", "--no-prompt-change-required",
                "--out", str(out_path),
            ],
        )
        capsys.readouterr()
        report = json.loads(out_path.read_text(encoding="utf-8"))
        assert report["mode"] == "official_offline_code_change"
        assert report["official_validation_passed"] is True
        assert report["comparison"]["before_code_sha"] == "cafebabe"
        assert report["comparison"]["after_code_sha"] == "fadedbee"

    def test_no_prompt_change_required_does_not_bypass_langsmith_requirement(
        self, official_files_with_v3, monkeypatch, tmp_path: Path
    ):
        """--no-prompt-change-required와 --no-langsmith는 독립적인 요건이다 —
        official_files_with_v3의 langsmith_run_id는 전부 None이므로,
        --no-langsmith 없이 --no-prompt-change-required만 쓰면 여전히
        LangSmith 요건에서 거부돼야 한다(한쪽 플래그가 다른 쪽을 몰래 완화하면 안 됨)."""
        out_path = tmp_path / "report.json"
        with pytest.raises(Exception, match="LangSmith"):
            _run(
                monkeypatch,
                [
                    "--human-labels-json", str(official_files_with_v3["human"]),
                    "--judge-results", str(official_files_with_v3["v2"]),
                    "--judge-results-v2", str(official_files_with_v3["v3"]),
                    "--official", "--no-prompt-change-required",
                    "--out", str(out_path),
                ],
            )
