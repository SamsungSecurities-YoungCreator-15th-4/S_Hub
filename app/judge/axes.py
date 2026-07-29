"""judge 6축 명칭의 한글↔영문 매핑 SSOT.

이 파일이 6축 명칭의 단일 진실 공급원(SSOT)이다. 한글 문자열은 과제
스타터킷 라벨링 가이드 §4 표기 규칙에서 온 규정값이므로 공백·철자를
임의로 바꾸지 않는다. 영문 키는 app.judge.rubric.AXIS_NAMES와 동일하다.
"""
from __future__ import annotations

from app.judge.rubric import AXIS_NAMES

# 스타터킷 규정값 — "수치 정합"의 공백 1칸 포함, 한 글자도 바꾸지 말 것.
KOREAN_AXIS_NAMES = (
    "출처",
    "수치 정합",
    "환각",
    "위조정밀도",
    "면책",
    "금지표현",
)

AXIS_KO_TO_EN = dict(zip(KOREAN_AXIS_NAMES, AXIS_NAMES))
AXIS_EN_TO_KO = dict(zip(AXIS_NAMES, KOREAN_AXIS_NAMES))


def to_en(ko: str) -> str:
    """한글 축 이름을 영문 키로 변환한다. 미지의 값이면 ValueError."""
    if ko not in AXIS_KO_TO_EN:
        raise ValueError(
            f"알 수 없는 한글 축 이름: {ko!r}. 허용값: {list(AXIS_KO_TO_EN)}"
        )
    return AXIS_KO_TO_EN[ko]


def to_ko(en: str) -> str:
    """영문 축 키를 한글 이름으로 변환한다. 미지의 값이면 ValueError."""
    if en not in AXIS_EN_TO_KO:
        raise ValueError(
            f"알 수 없는 영문 축 키: {en!r}. 허용값: {list(AXIS_EN_TO_KO)}"
        )
    return AXIS_EN_TO_KO[en]
