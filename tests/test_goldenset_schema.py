"""정답 사례집(goldenset/cases/) frontmatter 스키마 게이트.

사례 20건은 라벨 확정 전이라 아직 레포에 없다. 그래서 이 테스트는 디렉터리가
없으면 skip하고, 사례가 들어오는 순간 자동으로 검사 대상이 된다
(tests/test_docs_config_consistency.py와 같은 패턴).

**이 테스트는 frontmatter만 읽고 사례 본문은 파싱하지 않는다.** 본문은 라벨러의
독립성 영역이고, 실패 메시지에 본문이 섞여 나가면 답안 유출이 된다.

의도적으로 검사하지 않는 것: **pass/fail 개수 균형.** 라벨링 가이드는 "10건
내외"이며 11:9도 요건 위반이 아니다. 균형을 assert로 강제하면 라벨을 숫자에
맞추려는 압력이 생기고, 그게 라벨 품질보다 큰 문제다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.judge.axes import KOREAN_AXIS_NAMES

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "goldenset" / "cases"

EXPECTED_CASE_COUNT = 20
EXPECTED_CASE_IDS = tuple(f"case_{i:03d}" for i in range(1, EXPECTED_CASE_COUNT + 1))
# 스타터 킷 견본 전용 접두 — 실제 20건에 쓰면 안 된다
# (starter-kit/labeling-guide-template.md §4).
SAMPLE_ID_PREFIX = "GS-EX-"
NO_TRAP = "none"
FRONTMATTER_FENCE = "---"


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
    """사례 1건의 frontmatter 위반 목록을 돌려준다. 비어 있으면 통과다.

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

    label = meta.get("label")
    if label not in ("pass", "fail"):
        problems.append(
            f"{name}: label은 pass|fail이어야 합니다 (받은 값: {label!r}) "
            "— 라벨 미기입이면 여기서 걸립니다."
        )

    raw_axes = meta.get("fail_axes")
    fail_axes: list = []
    if raw_axes is None:
        problems.append(f"{name}: fail_axes 필드가 없습니다 (pass면 빈 리스트로 명시합니다).")
    elif not isinstance(raw_axes, list):
        problems.append(f"{name}: fail_axes는 list여야 합니다 (받은 타입: {type(raw_axes).__name__}).")
    else:
        fail_axes = raw_axes
        unknown = [axis for axis in fail_axes if axis not in KOREAN_AXIS_NAMES]
        if unknown:
            problems.append(
                f"{name}: fail_axes에 허용되지 않은 축 {unknown} "
                f"— 허용값은 {list(KOREAN_AXIS_NAMES)}입니다(공백·표기 정확히)."
            )
        duplicates = sorted({axis for axis in fail_axes if fail_axes.count(axis) > 1})
        if duplicates:
            problems.append(f"{name}: fail_axes에 중복된 축 {duplicates}")

    trap_type = meta.get("trap_type")
    if not isinstance(trap_type, str) or not trap_type.strip():
        problems.append(f"{name}: trap_type이 비어 있습니다 (결함 없음이면 '{NO_TRAP}').")
        trap_type = ""

    if label == "pass":
        if fail_axes:
            problems.append(f"{name}: label=pass인데 fail_axes가 비어있지 않습니다 ({fail_axes}).")
        if trap_type and trap_type != NO_TRAP:
            problems.append(
                f"{name}: label=pass인데 trap_type이 '{trap_type}'입니다 (pass는 '{NO_TRAP}')."
            )
    elif label == "fail":
        if not fail_axes:
            problems.append(f"{name}: label=fail인데 fail_axes가 비어 있습니다.")
        if trap_type == NO_TRAP:
            problems.append(f"{name}: label=fail인데 trap_type이 '{NO_TRAP}'입니다.")

    rationale = meta.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        problems.append(f"{name}: rationale이 비어 있습니다.")

    return problems


def validate_case_set(metas: dict[str, dict]) -> list[str]:
    """사례 집합 전체 규약(20건 존재·6축 커버리지) 위반 목록을 돌려준다."""
    problems: list[str] = []
    for name, meta in sorted(metas.items()):
        problems.extend(validate_frontmatter(name, meta))

    present_ids = {
        meta.get("id") for meta in metas.values() if isinstance(meta.get("id"), str)
    }
    missing = [case_id for case_id in EXPECTED_CASE_IDS if case_id not in present_ids]
    if missing:
        problems.append(f"사례 id 누락 {len(missing)}건: {missing}")

    covered = {
        axis
        for meta in metas.values()
        if meta.get("label") == "fail" and isinstance(meta.get("fail_axes"), list)
        for axis in meta["fail_axes"]
    }
    uncovered = [axis for axis in KOREAN_AXIS_NAMES if axis not in covered]
    if uncovered:
        problems.append(
            f"fail 사례가 커버하지 않는 축 {uncovered} — 6축 각각 최소 1건이 필요합니다."
        )
    return problems


def _load_case_metas() -> dict[str, dict]:
    if not CASES_DIR.is_dir():
        pytest.skip(
            "goldenset/cases/가 없습니다 (사례가 들어오면 자동으로 검사 대상이 됩니다)."
        )
    paths = sorted(CASES_DIR.glob("case_*.md"))
    if not paths:
        pytest.skip(
            "goldenset/cases/에 case_*.md가 없습니다 (사례가 들어오면 자동으로 검사 대상이 됩니다)."
        )
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
def test_case_files_are_twenty():
    metas = _load_case_metas()
    assert len(metas) == EXPECTED_CASE_COUNT, (
        f"case_*.md는 {EXPECTED_CASE_COUNT}건이어야 합니다 (현재 {len(metas)}건: "
        f"{sorted(metas)})."
    )


def test_cases_satisfy_frontmatter_contract():
    problems = validate_case_set(_load_case_metas())
    assert not problems, "정답 사례집 frontmatter 위반:\n" + "\n".join(
        f"  - {p}" for p in problems
    )


# ---------------------------------------------------------------------------
# 검증 로직 자체의 음성 검증 — 합성 frontmatter로만 수행한다.
# 실제 사례 파일을 읽지 않으므로 사례가 없어도 항상 돌아간다.
# ---------------------------------------------------------------------------
def _pass_meta(index: int, **overrides) -> dict:
    meta = {
        "id": f"case_{index:03d}",
        "label": "pass",
        "fail_axes": [],
        "trap_type": NO_TRAP,
        "rationale": "합성 근거",
    }
    meta.update(overrides)
    return meta


def _fail_meta(index: int, axes: list[str], **overrides) -> dict:
    meta = {
        "id": f"case_{index:03d}",
        "label": "fail",
        "fail_axes": list(axes),
        "trap_type": "synthetic_trap",
        "rationale": "합성 근거",
    }
    meta.update(overrides)
    return meta


def _valid_case_set() -> dict[str, dict]:
    """20건·6축 커버리지를 만족하는 합성 사례 집합."""
    metas: dict[str, dict] = {}
    for offset, axis in enumerate(KOREAN_AXIS_NAMES, start=1):
        metas[f"case_{offset:03d}.md"] = _fail_meta(offset, [axis])
    for index in range(len(KOREAN_AXIS_NAMES) + 1, EXPECTED_CASE_COUNT + 1):
        metas[f"case_{index:03d}.md"] = _pass_meta(index)
    return metas


def test_synthetic_valid_case_set_passes():
    metas = _valid_case_set()
    assert len(metas) == EXPECTED_CASE_COUNT
    assert validate_case_set(metas) == []


def test_detects_axis_name_without_space():
    """'수치정합'(공백 없음)은 정본 '수치 정합'이 아니므로 반드시 거부돼야 한다."""
    metas = _valid_case_set()
    metas["case_001.md"] = _fail_meta(1, ["수치정합"])
    problems = validate_case_set(metas)
    assert any("수치정합" in p and "허용되지 않은 축" in p for p in problems), problems


def test_detects_sample_id_prefix():
    metas = _valid_case_set()
    metas["case_007.md"] = _pass_meta(7, id="GS-EX-01")
    problems = validate_case_set(metas)
    assert any(SAMPLE_ID_PREFIX in p for p in problems), problems


def test_detects_missing_label():
    metas = _valid_case_set()
    metas["case_008.md"] = _pass_meta(8, label=None)
    problems = validate_case_set(metas)
    assert any("label" in p for p in problems), problems


def test_detects_pass_with_fail_axes():
    metas = _valid_case_set()
    metas["case_009.md"] = _pass_meta(9, fail_axes=["출처"])
    problems = validate_case_set(metas)
    assert any("label=pass인데 fail_axes" in p for p in problems), problems


def test_detects_pass_with_trap_type():
    metas = _valid_case_set()
    metas["case_010.md"] = _pass_meta(10, trap_type="citation_swap")
    problems = validate_case_set(metas)
    assert any("label=pass인데 trap_type" in p for p in problems), problems


def test_detects_fail_without_fail_axes():
    metas = _valid_case_set()
    metas["case_001.md"] = _fail_meta(1, [])
    problems = validate_case_set(metas)
    assert any("label=fail인데 fail_axes가 비어" in p for p in problems), problems


def test_detects_fail_with_trap_type_none():
    metas = _valid_case_set()
    metas["case_002.md"] = _fail_meta(2, ["출처"], trap_type=NO_TRAP)
    problems = validate_case_set(metas)
    assert any(f"label=fail인데 trap_type이 '{NO_TRAP}'" in p for p in problems), problems


def test_detects_empty_rationale():
    metas = _valid_case_set()
    metas["case_011.md"] = _pass_meta(11, rationale="   ")
    problems = validate_case_set(metas)
    assert any("rationale" in p for p in problems), problems


def test_detects_missing_case_id():
    metas = _valid_case_set()
    del metas["case_020.md"]
    problems = validate_case_set(metas)
    assert any("case_020" in p for p in problems), problems


def test_detects_uncovered_axis():
    """6축 중 하나라도 fail 사례가 없으면 잡혀야 한다."""
    metas = _valid_case_set()
    metas["case_001.md"] = _pass_meta(1)
    problems = validate_case_set(metas)
    assert any("커버하지 않는 축" in p and KOREAN_AXIS_NAMES[0] in p for p in problems), problems


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


def test_real_case_files_are_parsed_via_tmp_roundtrip(tmp_path: Path):
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
    assert validate_case_set(metas) == []
