"""judge 6축 한글↔영문 매핑 SSOT(app/judge/axes.py) 정합성 테스트."""
from __future__ import annotations

import pytest

from engine.judge.axes import (
    AXIS_EN_TO_KO,
    AXIS_KO_TO_EN,
    KOREAN_AXIS_NAMES,
    to_en,
    to_ko,
)
from engine.judge.rubric import AXIS_NAMES

EXPECTED_KOREAN = ("출처", "수치 정합", "환각", "위조정밀도", "면책", "금지표현")


def test_axis_count_is_six():
    assert len(AXIS_NAMES) == 6
    assert len(KOREAN_AXIS_NAMES) == 6
    assert len(AXIS_KO_TO_EN) == 6
    assert len(AXIS_EN_TO_KO) == 6


def test_en_keys_match_rubric_axis_names():
    assert set(AXIS_EN_TO_KO) <= set(AXIS_NAMES)
    assert set(AXIS_NAMES) <= set(AXIS_EN_TO_KO)


def test_korean_names_exact():
    assert KOREAN_AXIS_NAMES == EXPECTED_KOREAN


def test_round_trip():
    for ko in KOREAN_AXIS_NAMES:
        assert to_ko(to_en(ko)) == ko
    for en in AXIS_NAMES:
        assert to_en(to_ko(en)) == en


def test_unknown_values_raise_value_error():
    with pytest.raises(ValueError):
        to_en("존재하지 않는 축")
    with pytest.raises(ValueError):
        to_ko("unknown_axis")


def test_error_message_lists_allowed_values():
    with pytest.raises(ValueError, match="수치 정합"):
        to_en("출 처")
    with pytest.raises(ValueError, match="numeric_consistency"):
        to_ko("numeric consistency")
