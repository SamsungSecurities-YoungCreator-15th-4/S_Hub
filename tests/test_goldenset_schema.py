"""정답 사례집(goldenset/cases/) frontmatter 스키마 게이트 — 식별자·중복·정원.

**이 테스트는 frontmatter만 읽고 사례 본문은 파싱하지 않는다.** 본문은 라벨러의
독립성 영역이고, 실패 메시지에 본문이 섞여 나가면 답안 유출이 된다.

## 검사 범위 — #146과 중복을 제거한 잔여분

PR #146이 `tests/test_goldenset_integrity.py`로 라벨 값·pass/fail↔`fail_axes`·
`trap_type` 관계·`rationale`·축 SSOT 정합·6축 커버리지·라벨 분포를 상시 검사한다.
같은 계약을 두 파일에서 assert하면 SSOT가 둘로 갈라지므로, 이 파일은 그쪽이
덮지 않는 것만 남긴다.

- `id` 존재 및 견본 접두(`GS-EX-`) 거부 — 스타터킷 견본 ID가 실제 20건에 남는 사고
- `case_001`~`case_020` **정확한 ID 집합** (#146은 총 20건만 센다)
- `fail_axes` 중복 원소 거부 — 중복은 R2 집계에서 축별 건수를 부풀린다

## 정원 계약과 fail-closed (#140 리뷰 1·3번)

사례가 아직 없는 동안 이 게이트는 skip한다. 다만 skip은 "사례 0건이어도 CI가
green"을 뜻하므로, 제출 전 확인에는 쓸 수 없다. `GOLDENSET_REQUIRED=1`을 주면
skip이 실패로 바뀌고 정원 계약(정확히 20건, 정상 10·결함 10 —
`docs/hard_stop_contract.md` §8)까지 함께 강제한다.

    GOLDENSET_REQUIRED=1 pytest tests/test_goldenset_schema.py

분포를 상수로 박아둔 것은 "10:10을 맞춰라"는 목표가 아니다. 라벨은 사람이 정하며,
정당한 재라벨로 분포가 바뀌면 라벨이 아니라 이 상수와 계약 문서를 함께 고친다.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "goldenset" / "cases"

EXPECTED_CASE_COUNT = 20
EXPECTED_CASE_IDS = tuple(f"case_{i:03d}" for i in range(1, EXPECTED_CASE_COUNT + 1))
# docs/hard_stop_contract.md §8 — 정상 10 · 결함 10
EXPECTED_PASS_COUNT = 10
EXPECTED_FAIL_COUNT = 10
# 스타터 킷 견본 전용 접두 — 실제 20건에 쓰면 안 된다
# (goldenset/starter-kit/labeling-guide-template.md §4).
SAMPLE_ID_PREFIX = "GS-EX-"
FRONTMATTER_FENCE = "---"

REQUIRED_ENV = "GOLDENSET_REQUIRED"


def goldenset_is_required() -> bool:
    """공식 제출 전 확인 모드인가 — 켜지면 사례 미존재가 skip이 아니라 실패다."""
    return os.environ.get(REQUIRED_ENV, "").strip().lower() in ("1", "true", "yes")


def parse_frontmatter(text: str) -> dict:
    """`---`로 감싼 YAML frontmatter만 dict로 돌려준다. 본문은 버린다.

    정규식으로 긁지 않는 이유: 값에 줄바꿈이나 `---`가 들어가면 오탐이 난다.
    펜스로 구간만 자르고 파싱은 PyYAML에 맡긴다.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        raise ValueError("frontmatter가 '---'로 시작하지 않습니다.")
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONTMATTER_FENCE:
            parsed = yaml.safe_load("\n".join(lines[1:index]))
            if not isinstance(parsed, dict):
                raise ValueError("frontmatter가 YAML 매핑이 아닙니다.")
            return parsed
    raise ValueError("frontmatter 종료 '---'가 없습니다.")


def validate_frontmatter(name: str, meta: dict) -> list[str]:
    """사례 1건의 위반 목록을 돌려준다. 비어 있으면 통과다.

    메시지에는 파일명·필드명·라벨 값만 담는다 — 사례 본문이나 rationale 원문은
    넣지 않는다(실패 로그로 답안이 유출되지 않게).
    """
    problems: list[str] = []

    case_id = meta.get("id")
    if not isinstance(case_id, str) or not case_id.strip():
        problems.append(f"{name}: id가 비어 있습니다.")
    elif case_id.startswith(SAMPLE_ID_PREFIX):
        problems.append(
            f"{name}: id '{case_id}'는 견본 전용 접두 '{SAMPLE_ID_PREFIX}'를 씁니다 "
            "— 실제 20건에는 case_001~case_020을 사용합니다."
        )

    raw_axes = meta.get("fail_axes")
    if isinstance(raw_axes, list):
        duplicates = sorted({axis for axis in raw_axes if raw_axes.count(axis) > 1})
        if duplicates:
            problems.append(
                f"{name}: fail_axes에 중복된 축 {duplicates} "
                "— 중복은 R2 축별 집계 건수를 부풀립니다."
            )
    elif raw_axes is not None and not isinstance(raw_axes, list):
        problems.append(
            f"{name}: fail_axes는 list여야 합니다 (받은 타입: {type(raw_axes).__name__})."
        )

    return problems


def validate_case_set(metas: dict[str, dict], *, required: bool = False) -> list[str]:
    """사례 집합 전체 규약 위반 목록을 돌려준다.

    `required=True`면 정원 계약(20건·정상 10·결함 10)까지 검사한다.
    """
    problems: list[str] = []
    for name, meta in sorted(metas.items()):
        problems.extend(validate_frontmatter(name, meta))

    present_ids = {
        meta.get("id") for meta in metas.values() if isinstance(meta.get("id"), str)
    }
    missing = [case_id for case_id in EXPECTED_CASE_IDS if case_id not in present_ids]
    if missing:
        problems.append(f"사례 id 누락 {len(missing)}건: {missing}")

    if required:
        if len(metas) != EXPECTED_CASE_COUNT:
            problems.append(
                f"사례가 정확히 {EXPECTED_CASE_COUNT}건이어야 합니다 (현재 {len(metas)}건)."
            )
        labels = [meta.get("label") for meta in metas.values()]
        pass_count = labels.count("pass")
        fail_count = labels.count("fail")
        if (pass_count, fail_count) != (EXPECTED_PASS_COUNT, EXPECTED_FAIL_COUNT):
            problems.append(
                f"라벨 분포는 정상 {EXPECTED_PASS_COUNT}·결함 {EXPECTED_FAIL_COUNT}이어야 "
                f"합니다 (현재 정상 {pass_count}·결함 {fail_count}) "
                "— docs/hard_stop_contract.md §8."
            )
    return problems


def _load_case_metas() -> dict[str, dict]:
    required = goldenset_is_required()
    paths = sorted(CASES_DIR.glob("case_*.md")) if CASES_DIR.is_dir() else []
    if not paths:
        message = "goldenset/cases/에 case_*.md가 없습니다"
        if required:
            pytest.fail(f"{message} — {REQUIRED_ENV}=1은 사례 부재를 허용하지 않습니다.")
        pytest.skip(f"{message} (사례가 들어오면 자동으로 검사 대상이 됩니다).")
    metas: dict[str, dict] = {}
    for path in paths:
        try:
            metas[path.name] = parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            pytest.fail(f"{path.name}: frontmatter 파싱 실패 — {exc}")
    return metas


# ---------------------------------------------------------------------------
# 실제 사례집 검사 (사례가 들어오면 활성화)
# ---------------------------------------------------------------------------
def test_cases_satisfy_frontmatter_contract():
    metas = _load_case_metas()
    problems = validate_case_set(metas, required=goldenset_is_required())
    assert not problems, "정답 사례집 frontmatter 위반:\n" + "\n".join(
        f"  - {p}" for p in problems
    )


# ---------------------------------------------------------------------------
# 검증 로직 자체의 음성 검증 — 합성 frontmatter로만 수행한다.
# 실제 사례 파일을 읽지 않으므로 사례가 없어도 항상 돌아간다.
# ---------------------------------------------------------------------------
def _meta(index: int, **overrides) -> dict:
    meta = {"id": f"case_{index:03d}", "label": "pass", "fail_axes": []}
    meta.update(overrides)
    return meta


def _valid_case_set() -> dict[str, dict]:
    """정원 계약(20건·정상 10·결함 10)을 만족하는 합성 사례 집합."""
    metas: dict[str, dict] = {}
    for index in range(1, EXPECTED_FAIL_COUNT + 1):
        metas[f"case_{index:03d}.md"] = _meta(index, label="fail", fail_axes=["출처"])
    for index in range(EXPECTED_FAIL_COUNT + 1, EXPECTED_CASE_COUNT + 1):
        metas[f"case_{index:03d}.md"] = _meta(index)
    return metas


def test_synthetic_valid_case_set_passes():
    metas = _valid_case_set()
    assert len(metas) == EXPECTED_CASE_COUNT
    assert validate_case_set(metas, required=True) == []


def test_detects_sample_id_prefix():
    metas = _valid_case_set()
    metas["case_007.md"] = _meta(7, id="GS-EX-01")
    problems = validate_case_set(metas)
    assert any(SAMPLE_ID_PREFIX in p for p in problems), problems


def test_detects_missing_id():
    metas = _valid_case_set()
    metas["case_007.md"] = _meta(7, id=None)
    problems = validate_case_set(metas)
    assert any("id가 비어" in p for p in problems), problems


def test_detects_duplicate_fail_axis():
    metas = _valid_case_set()
    metas["case_001.md"] = _meta(1, label="fail", fail_axes=["출처", "출처"])
    problems = validate_case_set(metas)
    assert any("중복된 축" in p for p in problems), problems


def test_detects_missing_case_id():
    metas = _valid_case_set()
    del metas["case_020.md"]
    problems = validate_case_set(metas)
    assert any("case_020" in p for p in problems), problems


# ---------------------------------------------------------------------------
# 정원 계약 — required 모드에서만 강제한다 (#140 리뷰 1번)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pass_count", [9, 11])
def test_required_mode_rejects_unbalanced_distribution(pass_count: int):
    """9:11 · 11:9는 정확히 10:10 계약 위반이다."""
    metas: dict[str, dict] = {}
    for index in range(1, EXPECTED_CASE_COUNT + 1):
        label = "pass" if index <= pass_count else "fail"
        metas[f"case_{index:03d}.md"] = _meta(
            index, label=label, fail_axes=[] if label == "pass" else ["출처"]
        )
    problems = validate_case_set(metas, required=True)
    assert any("라벨 분포" in p for p in problems), problems


def test_required_mode_rejects_wrong_count():
    metas = _valid_case_set()
    del metas["case_020.md"]
    problems = validate_case_set(metas, required=True)
    assert any("정확히" in p for p in problems), problems


def test_non_required_mode_ignores_distribution():
    """평상시에는 분포를 강제하지 않는다 — 상시 검사는 #146 통합 게이트가 맡는다."""
    metas: dict[str, dict] = {}
    for index in range(1, EXPECTED_CASE_COUNT + 1):
        metas[f"case_{index:03d}.md"] = _meta(index, label="pass", fail_axes=[])
    assert validate_case_set(metas, required=False) == []


def test_required_flag_reads_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(REQUIRED_ENV, raising=False)
    assert goldenset_is_required() is False
    monkeypatch.setenv(REQUIRED_ENV, "1")
    assert goldenset_is_required() is True
    monkeypatch.setenv(REQUIRED_ENV, "0")
    assert goldenset_is_required() is False


# ---------------------------------------------------------------------------
# frontmatter 파서 검증 — tmp_path에 합성 파일을 만들어 확인한다.
# ---------------------------------------------------------------------------
def test_parse_frontmatter_reads_yaml_and_ignores_body(tmp_path: Path):
    path = tmp_path / "case_001.md"
    path.write_text(
        "---\n"
        "id: case_001\n"
        "label: fail\n"
        'fail_axes: ["출처", "면책"]\n'
        "trap_type: citation_swap\n"
        "rationale: 합성 근거\n"
        "---\n"
        "\n"
        "## 본문\n"
        "본문에 --- 구분선이 있어도 frontmatter 파싱에 영향을 주지 않는다.\n",
        encoding="utf-8",
    )
    meta = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta == {
        "id": "case_001",
        "label": "fail",
        "fail_axes": ["출처", "면책"],
        "trap_type": "citation_swap",
        "rationale": "합성 근거",
    }
    assert "본문" not in str(meta)


def test_parse_frontmatter_rejects_missing_fence(tmp_path: Path):
    path = tmp_path / "case_002.md"
    path.write_text("id: case_002\nlabel: pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'---'로 시작"):
        parse_frontmatter(path.read_text(encoding="utf-8"))


def test_parse_frontmatter_rejects_unterminated_fence(tmp_path: Path):
    path = tmp_path / "case_003.md"
    path.write_text("---\nid: case_003\nlabel: pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="종료"):
        parse_frontmatter(path.read_text(encoding="utf-8"))


def test_directory_scan_and_validation_roundtrip(tmp_path: Path):
    """디렉터리 스캔·파싱·검증 경로 전체가 합성 사례 20건에서 통과하는지 확인한다."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    for name, meta in _valid_case_set().items():
        (cases_dir / name).write_text(
            "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n## 본문\n",
            encoding="utf-8",
        )
    metas = {
        path.name: parse_frontmatter(path.read_text(encoding="utf-8"))
        for path in sorted(cases_dir.glob("case_*.md"))
    }
    assert len(metas) == EXPECTED_CASE_COUNT
    assert validate_case_set(metas, required=True) == []
