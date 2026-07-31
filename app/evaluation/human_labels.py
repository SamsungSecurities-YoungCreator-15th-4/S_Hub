"""R1 정답 사례집(md frontmatter) → HumanLabel 원본 dict 로더.

R1은 사례 1건당 md 파일 1건, frontmatter(YAML)에 id/label/fail_axes/rationale을
담는다(starter-kit/labeling-guide-template.md §4). 이 모듈은 그 frontmatter만
읽어 calibration_schema.HumanLabel이 기대하는 원본 dict로 변환한다 — 본문(리포트
전문)은 읽지 않는다. judge가 채점할 사례 본문을 넘기는 건 실행·기록 담당의
로더 몫이라 R2 분석 쪽이 중복으로 읽을 이유가 없다. frontmatter의 다른 필드
(variant/trap_type/labelers/initial_agreement 등)도 이 계약이 쓰지 않으므로
버린다 — 실제 검증(정규화·중복 검사)은 calibration_schema.normalize_human_label()/
merge_records()가 한다.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_FRONTMATTER_DELIM = "---"


class HumanLabelLoadError(ValueError):
    """R1 md 파일의 frontmatter가 파싱 불가능하거나 형식을 벗어날 때 발생한다."""


def _parse_frontmatter(text: str, *, source: Path) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        raise HumanLabelLoadError(f"{source}: 파일이 '---'로 시작하는 frontmatter가 아닙니다.")
    try:
        end = lines[1:].index(_FRONTMATTER_DELIM) + 1
    except ValueError as exc:
        raise HumanLabelLoadError(f"{source}: frontmatter를 닫는 '---'를 찾을 수 없습니다.") from exc
    raw = "\n".join(lines[1:end])
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise HumanLabelLoadError(f"{source}: frontmatter YAML 파싱에 실패했습니다: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HumanLabelLoadError(f"{source}: frontmatter가 dict 형태가 아닙니다.")
    return parsed


def load_human_label_file(path: Path) -> dict:
    """md 파일 1건의 frontmatter를 HumanLabel 원본 dict로 읽는다."""
    frontmatter = _parse_frontmatter(path.read_text(encoding="utf-8"), source=path)
    return {
        "id": frontmatter.get("id"),
        "label": frontmatter.get("label"),
        "fail_axes": frontmatter.get("fail_axes"),
        "rationale": frontmatter.get("rationale"),
    }


def load_human_labels_from_dir(dir_path: Path) -> list[dict]:
    """디렉터리 안의 case_*.md 전부를 HumanLabel 원본 dict 목록으로 읽는다.

    이 함수는 frontmatter를 그대로 옮기기만 한다 — 개수·표기 검증은 호출자가
    calibration_schema.merge_records()/validate_official_case_set()으로 한다.
    """
    paths = sorted(dir_path.glob("case_*.md"))
    if not paths:
        raise HumanLabelLoadError(f"{dir_path}: case_*.md 파일을 찾을 수 없습니다.")
    return [load_human_label_file(path) for path in paths]
