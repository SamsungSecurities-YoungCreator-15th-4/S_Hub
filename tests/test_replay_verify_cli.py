"""`scripts/replay_verify.py`의 판정·출력·종료 코드 계약.

종료 코드 네 가지가 **서로 구분되는지**를 고정한다. "실패했다"만 알면 시연장에서
원인을 못 찾는다 — 값이 갈린 것인지, 파일을 못 읽은 것인지, 대조할 게 없었던
것인지가 코드만 보고 갈려야 한다.

Azure·그래프를 쓰지 않는다. 합성 덤프만 쓴다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.replay_verify import (
    EXIT_INPUT_ERROR,
    EXIT_MATCH,
    EXIT_MISMATCH,
    EXIT_NOTHING_TO_COMPARE,
)
from tests.test_replay_scope import _blocked_dump, _passing_dump

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "replay_verify.py"


def _write(tmp_path: Path, name: str, dump: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(dump, ensure_ascii=False), encoding="utf-8")
    return path


def _run(*paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(p) for p in paths)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_identical_runs_exit_zero(tmp_path):
    left = _write(tmp_path, "a.json", _passing_dump())
    right = _write(tmp_path, "b.json", _passing_dump())

    result = _run(left, right)

    assert result.returncode == EXIT_MATCH
    assert "일치" in result.stdout


def test_guaranteed_mismatch_exits_nonzero_and_names_the_path(tmp_path):
    """§2가 어긋나면 실패하고, **어느 경로인지**가 출력에 나와야 한다."""
    diverged = _passing_dump()
    diverged["metrics"]["var"] = 9.9

    result = _run(
        _write(tmp_path, "a.json", _passing_dump()),
        _write(tmp_path, "b.json", diverged),
    )

    assert result.returncode == EXIT_MISMATCH
    assert "불일치" in result.stdout
    assert "metrics" in result.stdout


def test_excluded_only_difference_still_exits_zero(tmp_path):
    """§3만 갈린 것은 정상이다 — 종료 코드 0이고, 화면에는 함께 보인다.

    감사자가 차이를 먼저 발견하기 전에 우리가 밝히는 것이 런북 §4의 원칙이라,
    "숨겨서 통과"가 아니라 "보여 주면서 통과"여야 한다.
    """
    diverged = _passing_dump()
    diverged["citations"] = [{"chunk_id": "b.pdf::7"}]
    diverged["trace_id"] = "run-bbbbbbbbbbbb"
    diverged["judge"]["rubric"]["hallucination"]["reason"] = "다른 산문"

    result = _run(
        _write(tmp_path, "a.json", _passing_dump()),
        _write(tmp_path, "b.json", diverged),
    )

    assert result.returncode == EXIT_MATCH
    assert "재현 대상 아님" in result.stdout
    assert "`citations` 집합·순서" in result.stdout
    assert "다름" in result.stdout


def test_missing_file_exits_with_input_error(tmp_path):
    result = _run(tmp_path / "없는파일.json", _write(tmp_path, "b.json", _passing_dump()))

    assert result.returncode == EXIT_INPUT_ERROR
    assert "읽을 수 없습니다" in result.stderr


def test_broken_json_exits_with_input_error(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{ 이건 JSON이 아니다", encoding="utf-8")

    result = _run(broken, _write(tmp_path, "b.json", _passing_dump()))

    assert result.returncode == EXIT_INPUT_ERROR
    assert "파싱 실패" in result.stderr


def test_non_object_dump_exits_with_input_error(tmp_path):
    result = _run(
        _write(tmp_path, "a.json", ["배열은 안 된다"]),
        _write(tmp_path, "b.json", _passing_dump()),
    )

    assert result.returncode == EXIT_INPUT_ERROR
    assert "최상위가 객체가 아닙니다" in result.stderr


def test_empty_dumps_are_not_treated_as_success(tmp_path):
    """대조할 게 하나도 없으면 성공이 아니다 — fail-closed.

    빈 덤프 두 개를 "전부 일치"로 통과시키면, 시연에서 잘못된 파일을 넘겨도
    초록이 뜬다.
    """
    result = _run(
        _write(tmp_path, "a.json", {}),
        _write(tmp_path, "b.json", {}),
    )

    assert result.returncode == EXIT_NOTHING_TO_COMPARE
    assert "대조 불가" in result.stdout


@pytest.mark.parametrize(
    ("code", "name"),
    [
        (EXIT_MATCH, "일치"),
        (EXIT_MISMATCH, "불일치"),
        (EXIT_INPUT_ERROR, "입력 문제"),
        (EXIT_NOTHING_TO_COMPARE, "대조 불가"),
    ],
)
def test_exit_codes_are_distinct(code, name):
    """네 상태가 같은 코드로 뭉개지면 원인 구분이 불가능해진다."""
    all_codes = [EXIT_MATCH, EXIT_MISMATCH, EXIT_INPUT_ERROR, EXIT_NOTHING_TO_COMPARE]
    assert len(set(all_codes)) == len(all_codes), f"{name} 코드가 다른 것과 겹칩니다."
    assert code in all_codes


def test_blocked_run_pair_compares_decision_hash(tmp_path):
    """차단 실행끼리는 `decision_hash`가 대조 대상에 들어온다."""
    result = _run(
        _write(tmp_path, "a.json", _blocked_dump()),
        _write(tmp_path, "b.json", _blocked_dump()),
    )

    assert result.returncode == EXIT_MATCH
    assert "decision_hash" in result.stdout
    assert "이 실행에 해당 없음" not in result.stdout


def test_fingerprints_show_values(tmp_path):
    """재현 지문 3종은 값까지 보여야 한다 — 감사자가 눈으로 대조한다."""
    result = _run(
        _write(tmp_path, "a.json", _passing_dump()),
        _write(tmp_path, "b.json", _passing_dump()),
    )

    for value in ("cfg-1", "comp-1", "appr-1"):
        assert value in result.stdout
