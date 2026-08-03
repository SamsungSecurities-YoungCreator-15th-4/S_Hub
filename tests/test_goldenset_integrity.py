"""R1 골든셋 무결성 게이트.

여기서 막는 것
  1. 사례 20건의 frontmatter가 완전한가 (라벨·축·근거)
  2. `fail_axes` 문자열이 6축 SSOT와 정확히 같은가 — 띄어쓰기 하나로 R2 집계가 깨진다
  3. 6축이 fail 사례에서 전부 커버되는가
  4. fail 사유가 기준표 항목 번호를 인용하는가
  5. 인용된 `chunk_id`가 코퍼스에 있고 인용문이 원문과 일치하는가
  6. **블라인드 배포본에 정답이 새지 않는가** — 생성기 재실행 안전성

라벨 분포(pass/fail 건수)는 상수로 박아둔다. 자동으로 따라가게 하면 라벨이
조용히 바뀌어도 아무도 모른다. 분포를 바꾸려면 이 파일도 같이 고쳐야 하므로
변경이 diff에 드러난다.

⚠️ 이 상수는 "10:10을 맞춰라"는 목표가 아니다. 라벨은 사람이 정하며, 정당한
   재라벨로 분포가 바뀌면 **라벨이 아니라 이 상수를 고친다.** 반대로 하면
   CI를 green으로 만들려고 라벨을 비트는 일이 생긴다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
GS = ROOT / "goldenset"
CASES = GS / "cases"
JUDGE_INPUTS = GS / "judge_inputs"

AXES = ("출처", "수치 정합", "환각", "위조정밀도", "면책", "금지표현")
EXPECTED_PASS = 10
EXPECTED_FAIL = 10
EXPECTED_TOTAL = 20

# 기준표 항목 번호 — 예: 출처-F2, 면책-B7, 수치 정합-F1
RULE_REF = re.compile(r"[가-힣]+\s*-\s*[FPB]\d")

pytestmark = pytest.mark.skipif(not CASES.exists(), reason="goldenset/cases 없음")


def _frontmatter(path: Path) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    assert m, f"{path.name}: frontmatter 없음"
    return yaml.safe_load(m.group(1)) or {}


@pytest.fixture(scope="module")
def cases() -> dict[str, dict]:
    files = sorted(CASES.glob("case_*.md"))
    return {p.stem: _frontmatter(p) for p in files}


# ── 1. 구성 ────────────────────────────────────────────────────────────────

def test_case_count(cases):
    assert len(cases) == EXPECTED_TOTAL


def test_label_distribution(cases):
    """분포가 바뀌면 실패한다. 라벨이 아니라 이 파일의 상수를 고칠 것."""
    labels = [c.get("label") for c in cases.values()]
    assert labels.count("pass") == EXPECTED_PASS
    assert labels.count("fail") == EXPECTED_FAIL


# ── 2. frontmatter 완전성 ──────────────────────────────────────────────────

@pytest.mark.parametrize("field", ["label", "fail_axes", "trap_type", "rationale",
                                   "labelers", "labeling_method"])
def test_required_fields_present(cases, field):
    missing = [cid for cid, c in cases.items() if field not in c]
    assert not missing, f"{field} 누락: {missing}"


def test_label_values_valid(cases):
    bad = {cid: c.get("label") for cid, c in cases.items()
           if c.get("label") not in ("pass", "fail")}
    assert not bad, f"label 값 오류: {bad}"


def test_pass_cases_have_no_axes(cases):
    bad = [cid for cid, c in cases.items()
           if c["label"] == "pass" and (c.get("fail_axes") or c.get("trap_type") not in (None, "none"))]
    assert not bad, f"pass인데 fail_axes/trap_type이 채워짐: {bad}"


def test_fail_cases_have_axes_and_trap(cases):
    bad = [cid for cid, c in cases.items()
           if c["label"] == "fail" and (not c.get("fail_axes")
                                        or c.get("trap_type") in (None, "", "none"))]
    assert not bad, f"fail인데 fail_axes/trap_type 미기입: {bad}"


# ── 3. 축 SSOT 정합 ────────────────────────────────────────────────────────

def test_axis_strings_match_ssot(cases):
    """띄어쓰기 하나만 달라도 R2 집계가 깨진다."""
    bad = {cid: [a for a in c.get("fail_axes") or [] if a not in AXES]
           for cid, c in cases.items()}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"허용되지 않은 축 표기: {bad}"


def test_axis_strings_match_code_ssot():
    """골든셋 축 문자열이 app.judge.axes 와 같은지 — 두 곳이 갈라지면 안 된다."""
    sys.path.insert(0, str(ROOT))
    axes_mod = pytest.importorskip("app.judge.axes")
    assert set(AXES) == set(axes_mod.KOREAN_AXIS_NAMES)


def test_all_six_axes_covered(cases):
    covered = {a for c in cases.values() for a in c.get("fail_axes") or []}
    assert covered == set(AXES), f"커버되지 않은 축: {set(AXES) - covered}"


# ── 4. 근거 품질 ───────────────────────────────────────────────────────────

def test_fail_rationale_cites_rule_number(cases):
    """'감으로 fail'을 막는다. 기준표 항목 번호가 없으면 판정이 아니다."""
    bad = [cid for cid, c in cases.items()
           if c["label"] == "fail" and not RULE_REF.search(str(c.get("rationale") or ""))]
    assert not bad, f"rationale에 기준표 항목 번호 없음: {bad}"


def test_rationale_not_empty(cases):
    bad = [cid for cid, c in cases.items() if not str(c.get("rationale") or "").strip()]
    assert not bad, f"rationale 비어 있음: {bad}"


def test_labelers_recorded(cases):
    bad = [cid for cid, c in cases.items() if len(c.get("labelers") or []) < 2]
    assert not bad, f"라벨러가 2인 미만: {bad}"


# ── 5. 코퍼스 무결성 ───────────────────────────────────────────────────────

CITE_RE = re.compile(r'>\s*"(.+?)"\s*\n>\s*—\s*출처:\s*(.+?),\s*chunk_id:\s*(\S+)')


@pytest.fixture(scope="module")
def chunks() -> dict[str, dict]:
    p = GS / "corpus" / "chunks.json"
    if not p.exists():
        pytest.skip("chunks.json 없음")
    raw = json.loads(p.read_text(encoding="utf-8"))
    lst = raw if isinstance(raw, list) else raw.get("chunks", [])
    return {c["chunk_id"]: c for c in lst}


def test_synthetic_flag_matches_source_label(chunks):
    """`synthetic`과 출처명의 '(가상)' 표기가 어긋나면 합성 데이터 고지가 무너진다."""
    bad = [cid for cid, c in chunks.items()
           if bool(c.get("synthetic")) != ("(가상)" in c.get("source", ""))]
    assert not bad, f"synthetic 플래그와 출처 표기 불일치: {bad}"


def test_pass_cases_citations_are_valid(chunks):
    """pass 사례의 인용은 전부 실재하고 원문과 일치해야 한다.

    fail 사례는 출처·환각 함정이 심겨 있으므로 검사 대상이 아니다.
    """
    problems: list[str] = []
    for p in sorted(CASES.glob("case_*.md")):
        fm = _frontmatter(p)
        if fm.get("label") != "pass":
            continue
        for quote, _source, cid in CITE_RE.findall(p.read_text(encoding="utf-8")):
            chunk = chunks.get(cid)
            if chunk is None:
                problems.append(f"{p.stem}: 존재하지 않는 chunk_id {cid}")
            elif quote not in chunk["text"]:
                problems.append(f"{p.stem}: 인용문이 {cid} 원문에 없음")
    assert not problems, problems


# ── 6. 블라인드 배포본 누출 ────────────────────────────────────────────────

BLIND_FORBIDDEN = (
    (r"^label:", "정답 라벨"),
    (r"^fail_axes:", "실패 축"),
    (r"^trap_type:", "함정 유형"),
    (r"^rationale:", "판정 사유"),
    (r"case_\d+", "원본 사례 ID"),
)


# blind 배포본에만 적용한다.
#   judge_inputs — R2 실행용이라 사례 ID를 그대로 쓰는 것이 설계다 (§9에서 별도 검사)
#   starter-kit  — 템플릿·견본이라 `label:` 등이 예시로 들어간다
@pytest.mark.parametrize("folder", ["cases_blind", "dist_relabel"])
def test_blind_packages_have_no_answers(folder):
    d = GS / folder
    if not d.exists():
        pytest.skip(f"{folder} 없음")
    problems = []
    for p in d.rglob("*.md"):
        if p.name == "README.md":       # 설명 문서는 대상 아님
            continue
        text = p.read_text(encoding="utf-8")
        for pattern, what in BLIND_FORBIDDEN:
            if re.search(pattern, text, re.M):
                problems.append(f"{folder}/{p.name}: {what} 노출 ({pattern})")
    assert not problems, problems


def test_labeler_guide_generator_is_rerun_safe():
    """라벨링 이후 갱신된 가이드로 생성기를 다시 돌려도 누출이 없어야 한다.

    §4(규칙 갱신 로그)에는 사례 ID와 판정 이력이 누적된다. 1회차에는 비어 있어
    안전해 보이지만 재실행 시 정답표가 되므로, 생성기가 스스로 막아야 한다.
    """
    src = GS / "labeling-guide.md"
    tools = GS / "tools"
    if not src.exists() or not (tools / "make_blind.py").exists():
        pytest.skip("가이드 또는 생성기 없음")
    sys.path.insert(0, str(tools))
    from make_blind import build_labeler_guide  # noqa: PLC0415

    guide = build_labeler_guide(src.read_text(encoding="utf-8"))
    for pattern, what in (
        (r"case_\d+", "원본 사례 ID"),
        (r"규칙 갱신 로그", "§4 규칙 갱신 로그"),
        (r"pass\s*\d+건", "pass 건수 배분"),
        (r"fail\s*\d+건", "fail 건수 배분"),
        (r"함정", "출제 의도 어휘"),
        (r"\.sealed", "봉인 경로"),
    ):
        assert not re.search(pattern, guide), f"배포용 가이드에 {what} 유출"


# ── 9. R2 무라벨 입력본(judge_inputs) ────────────────────────────────────

def test_judge_inputs_hashes_match_frozen_cases():
    """judge_inputs 본문 해시가 R1 동결 해시와 같아야 한다.

    이게 깨지면 judge가 동결된 것과 **다른 사례**를 채점하고 있다는 뜻이다.
    v1/v2 비교의 전제가 무너지므로 가장 먼저 막아야 할 실패다.
    """
    mf = JUDGE_INPUTS / "manifest.json"
    if not mf.exists():
        pytest.skip("judge_inputs/manifest.json 없음")
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    frozen = (json.loads((GS / "case_hashes.json").read_text(encoding="utf-8"))
              .get("hashes") or {})
    got = {c["id"]: c["case_content_sha256"] for c in manifest["cases"]}
    assert got == frozen, "judge_inputs 본문이 동결된 사례와 다르다"


def test_judge_inputs_frontmatter_allowlist():
    """무라벨 입력본에 허용된 frontmatter 필드만 남아야 한다."""
    if not JUDGE_INPUTS.exists():
        pytest.skip("judge_inputs 없음")
    allowed = {"id", "variant", "llm_draft"}
    problems = []
    for p in sorted(JUDGE_INPUTS.glob("case_*.md")):
        fm = _frontmatter(p)
        extra = set(fm) - allowed
        if extra:
            problems.append(f"{p.name}: 허용 밖 필드 {sorted(extra)}")
    assert not problems, problems


def test_judge_inputs_cover_all_cases():
    """20건이 빠짐없이 내보내졌는가 — 일부만 채점하면 일치율이 왜곡된다."""
    if not JUDGE_INPUTS.exists():
        pytest.skip("judge_inputs 없음")
    exported = {p.stem for p in JUDGE_INPUTS.glob("case_*.md")}
    assert exported == {p.stem for p in CASES.glob("case_*.md")}


# ── 7. 사례 본문 해시 (v1/v2 동일성 앵커) ──────────────────────────────────

def _hash_tool():
    tools = GS / "tools"
    if not (tools / "case_hashes.py").exists():
        pytest.skip("case_hashes.py 없음")
    sys.path.insert(0, str(tools))
    import case_hashes  # noqa: PLC0415
    return case_hashes


def test_case_hashes_match_record():
    """동결 이후 사례 본문이 바뀌지 않았는가.

    바뀌었다면 v1/v2 비교가 무효다. 정당한 수정이면 --write 로 갱신하고
    사유를 labeling-guide.md §4에 남긴다.
    """
    ch = _hash_tool()
    recorded = (ch.load() or {}).get("hashes") or {}
    if not recorded:
        pytest.skip("case_hashes.json 기록 없음")
    assert ch.compute() == recorded, "사례 본문이 기록된 해시와 다르다"


def test_hash_excludes_answer_fields():
    """라벨을 바꿔도 해시가 변하지 않아야 한다 — 정답이 해시에 섞이지 않았다는 증거."""
    ch = _hash_tool()
    src = (CASES / "case_001.md").read_text(encoding="utf-8")
    flipped = re.sub(r"^label: \w+", "label: fail__PROBE", src, count=1, flags=re.M)
    flipped = re.sub(r"^trap_type: .*", "trap_type: PROBE", flipped, count=1, flags=re.M)
    assert flipped != src, "probe가 frontmatter를 바꾸지 못했다 — 테스트 자체가 무의미하다"
    assert ch.content_hash(flipped) == ch.content_hash(src)


def test_hash_detects_body_change():
    """본문이 한 글자만 바뀌어도 잡아야 한다."""
    ch = _hash_tool()
    src = (CASES / "case_001.md").read_text(encoding="utf-8")
    assert ch.content_hash(src + "\n무단 수정") != ch.content_hash(src)


# ── 8. judge 실행 로더 비누출 계약 ─────────────────────────────────────────

ANSWER_FIELDS = ("label", "fail_axes", "trap_type", "rationale",
                 "labelers", "initial_agreement")
ALLOWED_STATE_KEYS = {"metrics", "explanations", "citations"}


# R2 실행 로더 후보 — 모듈이 옮겨져도 검사가 조용히 꺼지지 않도록 넓게 찾는다.
LOADER_CANDIDATES = (
    ("app.evaluation.goldenset_loader", ("load_case", "load_judge_state", "build_state")),
    ("app.goldenset.loader", ("load_case",)),
    ("scripts.judge_runner", ("load_case",)),
)


def _loader():
    """R2 실행 로더. 아직 없으면 skip — 생기는 순간 자동으로 검사 대상이 된다."""
    sys.path.insert(0, str(ROOT))
    for mod, names in LOADER_CANDIDATES:
        try:
            m = __import__(mod, fromlist=list(names))
        except Exception:
            continue
        for fn in names:
            if hasattr(m, fn):
                return getattr(m, fn)
    pytest.skip("judge 실행 로더가 아직 없습니다 (생성되면 자동으로 검사 대상이 됩니다)")


def test_loader_does_not_expose_answer_fields():
    """로더 출력에 정답 필드가 섞이면 안 된다.

    judge 실행 단계에는 gold label이 필요 없다. 정답은 실행 이후
    **일치율 계산 단계**에서만 쓰인다.
    """
    load_case = _loader()
    state = load_case(JUDGE_INPUTS / "case_001.md")
    assert isinstance(state, dict)
    leaked = [f for f in ANSWER_FIELDS if f in state]
    assert not leaked, f"로더가 정답 필드를 state에 넣었다: {leaked}"
    blob = json.dumps(state, ensure_ascii=False, default=str)
    for f in ANSWER_FIELDS:
        assert f'"{f}"' not in blob, f"직렬화된 state에 {f} 가 남아 있다"


def test_loader_uses_allowlist_only():
    """allowlist 밖의 키를 state에 넣지 않는다 — 차단 목록이 아니라 허용 목록이어야 한다."""
    load_case = _loader()
    state = load_case(JUDGE_INPUTS / "case_001.md")
    extra = set(state) - ALLOWED_STATE_KEYS
    assert not extra, f"allowlist({sorted(ALLOWED_STATE_KEYS)}) 밖의 키: {sorted(extra)}"


def test_make_blind_refuses_after_freeze():
    """라벨 확정 후에는 --force 없이 cases_blind/ 를 덮을 수 없다.

    cases_blind/ 는 라벨러가 실제로 본 본문의 유일한 사본이다. 재라벨한 2건
    (case_008·case_010)은 cases/ 와 의도적으로 다르며, 재생성하면
    labeling-guide.md §4의 재라벨 경위가 근거를 잃는다.

    가드가 리팩터링으로 사라져도 CI가 초록이면 안 되므로 여기서 고정한다.
    """
    tool = GS / "tools" / "make_blind.py"
    blind = GS / "cases_blind"
    if not (GS / "case_hashes.json").exists() or not tool.exists():
        pytest.skip("동결 전이거나 생성기 없음")

    before = {p.name: p.read_bytes() for p in blind.glob("*.md")}
    assert before, "cases_blind/ 가 비어 있어 검사 의미가 없다"

    result = subprocess.run(
        [sys.executable, str(tool)], capture_output=True, text=True, cwd=str(ROOT)
    )
    assert result.returncode != 0, "동결 후인데 재생성이 통과했다"
    after = {p.name: p.read_bytes() for p in blind.glob("*.md")}
    assert after == before, "가드가 걸렸는데도 cases_blind/ 가 바뀌었다"
