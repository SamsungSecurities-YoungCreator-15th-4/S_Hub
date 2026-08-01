"""Hard Stop 정책 설정의 단일 로더와 검증 계약."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

HARD_STOP_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "hard_stop_policy.yaml"
)


@lru_cache(maxsize=1)
def resolve_hard_stop_policy_version() -> str:
    """버전된 Hard Stop 정책 설정에서 유효한 버전을 읽는다.

    결정 지문을 바꾸는 정책 버전의 SSOT는 코드 상수가 아니라
    ``config/hard_stop_policy.yaml``이다. 누락·오염된 설정을 임의의 기본값으로
    대체하면 감사 지문의 의미가 갈라지므로 명시적으로 실패한다.
    """
    with open(HARD_STOP_POLICY_PATH, encoding="utf-8") as file:
        policy = yaml.safe_load(file)
    version = policy.get("version") if isinstance(policy, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Hard Stop 정책 설정에 비어 있지 않은 version이 필요합니다.")
    return version.strip()
