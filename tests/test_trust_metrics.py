"""신뢰 지표 화면 헬퍼(console.trust_metrics) 계약 테스트.

이 패널의 목적은 잘 나온 숫자를 크게 보여주는 게 아니라 **불일치를 정직하게
보이는 것**이다. 그래서 테스트도 그 규약을 지킨다.

  1. 일치율은 분수로만 — 퍼센트 표기 금지
  2. 미탐(FN)과 오탐(FP)을 합치지 않는다
  3. 동결 20건과 신규를 섞어 집계하지 않는다
"""
import json
from pathlib import Path

import pytest

from console.trust_metrics import (
    FROZEN_CASE_IDS,
    axis_rows,
    confusion_rows,
    format_fraction,
    load_human_labels,
    load_version_trend,
    mismatch_rows,
    split_frozen_and_added,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "goldenset" / "reports" / "r2_calibration"
CASES = ROOT / "goldenset" / "cases"
V7_RESULTS = ROOT / "docs" / "engine" / "r2_calibration_runs" / "judge_v7_results.json"


# ── 1. 표기 규약 ──────────────────────────────────────────────────────────

def test_fraction_never_renders_percent():
    """20건에서 1건은 5%p 다. 퍼센트는 없는 정밀도를 만든다."""
    assert format_fraction(16, 20) == "16/20"
    assert "%" not in format_fraction(16, 20)


@pytest.mark.parametrize("bad", [(None, 20), (16, 0), ("16", 20), (16, None)])
def test_fraction_is_dash_when_undefined(bad):
    """값이 없으면 0/0 이나 0% 대신 '—' 로 비운다."""
    assert format_fraction(*bad) == "—"


def test_no_percent_anywhere_in_rendered_rows():
    summary = json.loads((REPORTS / "v6_v7_compare_summary.json").read_text(encoding="utf-8"))
    rendered = [r["fraction"] for r in confusion_rows(summary["v2"])]
    rendered += [r["fraction"] for r in axis_rows(summary)]
    rendered += [r["fraction"] for r in load_version_trend(REPORTS)]
    assert all("%" not in value for value in rendered)


# ── 2. 미탐·오탐 분리 ─────────────────────────────────────────────────────

def test_confusion_keeps_fn_and_fp_separate():
    summary = json.loads((REPORTS / "v6_v7_compare_summary.json").read_text(encoding="utf-8"))
    rows = {r["key"]: r for r in confusion_rows(summary["v2"])}
    assert set(rows) == {"true_positive", "true_negative", "false_negative", "false_positive"}
    # 성격 설명이 붙어 있어야 한다 — 숫자만 보면 둘을 같은 것으로 읽는다.
    assert "불량이 나간다" in rows["false_negative"]["meaning"]
    assert "멀쩡한 걸 막는다" in rows["false_positive"]["meaning"]


def test_mismatch_lists_false_negative_first():
    """불량이 나가는 쪽(미탐)을 먼저 보여준다."""
    labels = {"case_003": {"label": "fail", "fail_axes": ["출처"]},
              "case_004": {"label": "pass"}}
    results = [{"case_id": "case_004", "passed": False},
               {"case_id": "case_003", "passed": True}]
    rows = mismatch_rows(results, labels)
    assert [r["case_id"] for r in rows] == ["case_003", "case_004"]
    assert rows[0]["kind"].startswith("미탐")
    assert rows[1]["kind"].startswith("오탐")


def test_mismatch_skips_agreements():
    labels = {"case_001": {"label": "pass"}}
    assert mismatch_rows([{"case_id": "case_001", "passed": True}], labels) == []


# ── 3. 동결/신규 분리 ─────────────────────────────────────────────────────

def test_frozen_and_added_are_tallied_separately():
    labels = {
        "case_001": {"label": "pass"}, "case_002": {"label": "fail"},
        "case_021": {"label": "fail"}, "case_022": {"label": "fail"},
    }
    results = [
        {"case_id": "case_001", "passed": True},    # 동결 · 일치
        {"case_id": "case_002", "passed": True},    # 동결 · 미탐
        {"case_id": "case_021", "passed": False},   # 신규 · 일치
        {"case_id": "case_022", "passed": True},    # 신규 · 미탐
    ]
    out = split_frozen_and_added(results, labels)
    assert out["frozen"]["fraction"] == "1/2"
    assert out["frozen"]["false_negative"] == 1
    assert out["added"]["fraction"] == "1/2"
    assert out["added"]["false_negative"] == 1


def test_frozen_ids_are_exactly_the_first_twenty():
    assert FROZEN_CASE_IDS == tuple(f"case_{i:03d}" for i in range(1, 21))


# ── 4. 실제 기록과의 회귀 고정 ────────────────────────────────────────────

def test_version_trend_matches_recorded_runs():
    """v1→v2 에서 **나빠졌다**는 사실을 고정한다.

    이 추이를 '꾸준히 좋아졌다'로 잘못 읽기 쉽다. 실제로는 v2 에서 15/20 →
    11/20 으로 떨어졌고, v1 을 다시 넘은 것은 v6(16/20) 이다.
    v1 대비 v7 의 순증은 **1건**뿐이다.
    """
    trend = {r["version"]: r for r in load_version_trend(REPORTS)}
    assert trend["v1"]["fraction"] == "15/20"
    assert trend["v2"]["fraction"] == "11/20"     # 떨어졌다
    assert trend["v6"]["fraction"] == "16/20"
    assert trend["v7"]["fraction"] == "16/20"
    # 미탐 1건은 v1 부터 v7 까지 한 번도 줄지 않았다 — 오탐만 깎였다.
    assert {trend[v]["false_negative"] for v in ("v1", "v2", "v6", "v7")} == {1}


def test_version_trend_prefers_recorded_prompt_version():
    """파일명이 아니라 실행이 기록한 prompt_version 을 쓴다."""
    trend = load_version_trend(REPORTS)
    assert [r["version"] for r in trend] == ["v1", "v2", "v3", "v4", "v5", "v6", "v7"]


def test_axis_rows_cover_all_six_axes():
    summary = json.loads((REPORTS / "v6_v7_compare_summary.json").read_text(encoding="utf-8"))
    names = [r["axis_ko"] for r in axis_rows(summary)]
    assert names == ["출처", "수치 정합", "환각", "위조정밀도", "면책", "금지표현"]


def test_axis_rows_expose_support_count():
    """재현율 1.0 이어도 분모가 2건이면 근거가 약하다 — 함께 보여야 한다."""
    summary = json.loads((REPORTS / "v6_v7_compare_summary.json").read_text(encoding="utf-8"))
    rows = {r["axis_ko"]: r for r in axis_rows(summary)}
    assert rows["위조정밀도"]["human_fail_support"] == 2


# ── 5. 실데이터 연결 ──────────────────────────────────────────────────────

def test_real_mismatch_rows_have_reasons():
    """어긋난 사례에 '왜 틀렸는지'가 함께 나와야 한다(핸드아웃 요구)."""
    labels = load_human_labels(CASES)
    results = json.loads(V7_RESULTS.read_text(encoding="utf-8"))
    rows = mismatch_rows(results, labels)
    assert rows, "v7 에는 어긋난 사례가 4건 있다"
    fn = [r for r in rows if r["kind"].startswith("미탐")]
    assert len(fn) == 1 and fn[0]["case_id"] == "case_003"
    # 미탐 사례는 사람이 지목한 축과 함정 유형이 함께 나와야 한다.
    assert fn[0]["human_fail_axes"] == ["출처", "환각"]
    assert fn[0]["trap_type"]


def test_load_human_labels_reads_all_cases():
    labels = load_human_labels(CASES)
    assert len(labels) >= 20
    assert all(v.get("label") in ("pass", "fail") for v in labels.values())


def test_missing_reports_dir_is_tolerated(tmp_path):
    assert load_version_trend(tmp_path / "없음") == []
    assert load_human_labels(tmp_path / "없음") == {}
