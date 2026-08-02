"""MAGI 반복 호출 하네스 — 같은 judge·같은 프롬프트를 같은 입력에 3회 돌린다.

무엇을 재는가: LLM 판정 축(환각·위조정밀도)의 **흔들림**이다. 판정이 매번 같다면
judge의 불일치는 프롬프트·기준의 문제이고, 매번 다르다면 그 앞에 표본 변동이 있다.
R2 일치율 숫자를 어떻게 읽어야 하는지가 이 구분에 달려 있다.

**관측 전용이다. v3 공식 판정에 반영하지 않는다.** 표본 7건에만 적용하므로
만장일치 규칙을 공식 판정에 넣으면 20건 일치율이 "일부 단일 호출·일부 3중 투표"인
혼합 지표가 되어 의미를 잃는다. 그래서 3표 원본을 그대로 저장하고, 만장일치·다수결
두 규칙의 결과는 사후 계산으로 **둘 다** 낸다.

결정론 4축(출처·수치 정합·면책·금지표현)은 3회가 같아야 정상이다. 다르면 그것은
흔들림이 아니라 결함 신호라 별도 목록과 전용 종료 코드로 알린다.

재현성 위치: judge 판정(pass/fail)은 `docs/reproducibility_scope.md` §2.1 조건부
항목이고 판정 이유 문구는 §3 제외 항목이다. **이 하네스의 산출물은 어떤 재현 지문
(config_hash·computation_hash·approval_hash)에도 들어가지 않는다.**

leakage 경계: judge_runner와 동일하다 — 무라벨 `goldenset/judge_inputs`만 읽고
사람 라벨은 읽지도 출력하지도 않는다. 표본 목록은 아래 동결 상수이며 실행 시점에
라벨을 보고 고르지 않는다.

사용:
    python scripts/magi_vote.py --dry-run
    python scripts/magi_vote.py --out out/magi_vote.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.judge.rubric import AXIS_NAMES  # noqa: E402

# R2 러너와 **같은 로더·같은 LLM 팩토리**를 쓴다. 여기서 별도 경로를 만들면 측정된
# 흔들림이 judge의 것인지 하네스의 것인지 구분할 수 없다. 비공개 이름을 가져오는
# 것은 그 동일성이 이 하네스의 전제이기 때문이며, 의도적인 재사용이다.
from scripts.judge_runner import (  # noqa: E402
    _load_r1_cases,
    _prompt_hash,
    _real_llm,
    case_content_sha256,
    resolve_code_sha,
)

# --- 표본 (동결 상수) --------------------------------------------------------
#
# 선정 규칙: 사람 라벨의 fail_axes에 환각 또는 위조정밀도가 포함된 사례.
# v1-freeze 시점 라벨 기준으로 R1 소유자가 집계해 확정했다.
# 통제군: 두 LLM 축이 관여하지 않고 다른 축에서도 조용한 pass 사례 2건.
#
# **실행 시점에 라벨을 읽어 선정하지 않는다.** 채점 결과를 보기 전에 목록이
# 고정돼 있었다는 것이 이 표본의 방어 논거이고, 코드가 라벨을 읽는 순간
# "결과를 보고 표본을 골랐다"는 반론을 막을 수 없게 된다.
SELECTION_RULE = (
    "사람 라벨 fail_axes에 환각 또는 위조정밀도가 포함된 사례 (v1-freeze 시점 라벨 "
    "기준, R1 소유자 집계·확정). 통제군은 두 LLM 축이 관여하지 않고 다른 축에서도 "
    "조용한 pass 사례 2건."
)

MAGI_PRIMARY_TARGETS = ("case_003", "case_011", "case_012", "case_017", "case_018")
MAGI_CONTROL_TARGETS = ("case_002", "case_019")
MAGI_TARGETS = MAGI_PRIMARY_TARGETS + MAGI_CONTROL_TARGETS

#: 한 사례를 몇 번 독립 호출하는가.
MAGI_RUNS = 3

# --- 축 분류 ----------------------------------------------------------------
#
# 6축 SSOT는 app/judge/rubric.py의 AXIS_NAMES다. 여기서는 그중 어느 것이 LLM
# 판정인지만 선언하고, 나머지를 결정론 축으로 **파생**시킨다. 목록 두 벌을 손으로
# 관리하면 축이 늘었을 때 새 축이 조용히 결정론 취급된다.
LLM_AXES = ("hallucination", "false_precision")
DETERMINISTIC_AXES = tuple(name for name in AXIS_NAMES if name not in LLM_AXES)

if set(LLM_AXES) - set(AXIS_NAMES) or len(DETERMINISTIC_AXES) != 4:
    raise RuntimeError(
        "축 분류가 AXIS_NAMES와 어긋났습니다 — LLM 축 정의를 먼저 갱신하세요: "
        f"AXIS_NAMES={AXIS_NAMES}, LLM_AXES={LLM_AXES}"
    )

#: 사례 1건의 judge 호출 1회가 발생시키는 LLM 호출 수(LLM 축 개수와 같다).
LLM_CALLS_PER_INVOCATION = len(LLM_AXES)

# --- 종료 코드 ---------------------------------------------------------------
EXIT_OK = 0
EXIT_RUN_FAILURE = 1        # judge 호출이 재시도 후에도 실패
EXIT_DETERMINISTIC_DRIFT = 2  # 결정론 4축이 3회 중 갈림 — 흔들림이 아니라 결함

#: 실패가 둘 다 나면 EXIT_RUN_FAILURE가 이긴다. 호출이 실패한 실행에서는 결정론
#: 축 판정 자체가 3표를 못 채워, 불변식 위반 여부를 말할 수 없기 때문이다.

# --- 주의 문구 ---------------------------------------------------------------
OBSERVATION_ONLY_NOTE = (
    "관측 전용. v3 공식 판정에 반영하지 않는다 — 표본 7건에만 3중 투표를 적용하면 "
    "20건 일치율이 '일부 단일 호출·일부 3중 투표'인 혼합 지표가 된다."
)
AXIS_BREAKDOWN_CAVEAT = (
    "축별 분리 수치는 참고용이다. 위조정밀도 표본이 2건뿐이라 축별 결론은 낼 수 "
    "없다. 정본 단위는 LLM 축 합산(사례별로 두 축 중 하나라도 갈리면 흔들린 사례)이다."
)
#: 흔들림이 0으로 나왔을 때 어떻게 말해야 하는가. "흔들림 미발견"은 조건 없는
#: 일반화라 사실보다 강하다 — 측정은 특정 샘플링 설정 아래에서만 이뤄졌다.
#: 현재 설정은 temperature=0.0 고정, seed 미지정(None)이다. 파라미터 정리는
#: 측정 이후로 미루고(팀 규칙 5) 여기서는 조건만 기록한다.
NULL_RESULT_PHRASING = (
    "흔들림이 관측되지 않더라도 '흔들림 없음'으로 일반화하지 않는다. "
    "'header.temperature·header.seed 설정 아래에서는 흔들림이 관측되지 않음'으로 "
    "조건을 명시한다 — 이 하네스는 한 가지 샘플링 설정만 관측했다."
)
REPRODUCIBILITY_NOTE = (
    "judge 판정(pass/fail)은 docs/reproducibility_scope.md §2.1 조건부 항목이고 "
    "판정 이유 문구는 §3 제외 항목이다. 이 산출물은 어떤 재현 지문"
    "(config_hash·computation_hash·approval_hash)에도 들어가지 않는다."
)


# --- 투표 규칙 ---------------------------------------------------------------
def unanimous_passed(votes: list[bool]) -> bool:
    """만장일치 규칙 — 3표가 모두 pass일 때만 pass. 하나라도 fail이면 fail."""
    if not votes:
        raise ValueError("표가 비어 있습니다")
    return all(votes)


def majority_passed(votes: list[bool]) -> bool:
    """다수결 규칙 — 과반이 pass면 pass (3표 중 2표 이상)."""
    if not votes:
        raise ValueError("표가 비어 있습니다")
    return sum(1 for vote in votes if vote) * 2 > len(votes)


def is_split(votes: list[bool]) -> bool:
    """3표가 갈렸는가. 이것이 '흔들림'의 정의다."""
    return len(set(votes)) > 1


def _vote_block(votes: list[bool]) -> dict:
    """한 대상의 3표와 두 규칙의 결과를 함께 낸다.

    `rules_disagree`는 만장일치와 다수결이 서로 다른 답을 낸 경우다. 3표에서는
    갈림(2-1)과 정확히 같은 조건이지만, 규칙 비교가 목적이므로 파생을 숨기지 않고
    별도 키로 낸다 — 사후 계산의 근거가 산출물 안에서 보여야 한다.
    """
    unanimous = unanimous_passed(votes)
    majority = majority_passed(votes)
    return {
        "votes": list(votes),
        "split": is_split(votes),
        "unanimous_passed": unanimous,
        "majority_passed": majority,
        "rules_disagree": unanimous != majority,
    }


# --- 실행 -------------------------------------------------------------------
def expected_calls(
    targets: tuple[str, ...] = MAGI_TARGETS, runs: int = MAGI_RUNS
) -> dict:
    """예상 호출 수. 실행 전에 출력하고 산출물 헤더에도 남긴다."""
    invocations = len(targets) * runs
    return {
        "cases": len(targets),
        "runs_per_case": runs,
        "judge_invocations": invocations,
        "llm_calls": invocations * LLM_CALLS_PER_INVOCATION,
    }


def _axis_snapshot(judge_output: dict) -> dict:
    """judge 반환값에서 6축 판정을 뽑는다. LLM 축만 이유 문구를 함께 남긴다.

    이유 문구는 §3 제외 항목이라 어떤 해시 계산에도 넣지 않는다. 그럼에도 저장하는
    이유는 오류 분석 재료이기 때문이다 — 판정만 남기면 '왜 갈렸는가'를 사후에
    되짚을 수 없다.
    """
    rubric = (judge_output.get("judge") or {}).get("rubric") or {}
    missing = [name for name in AXIS_NAMES if name not in rubric]
    if missing:
        raise KeyError(f"judge 반환값에 축이 없습니다: {missing}")
    snapshot = {}
    for name in AXIS_NAMES:
        entry = rubric[name] or {}
        axis = {"passed": bool(entry.get("passed"))}
        if name in LLM_AXES:
            axis["reason"] = entry.get("reason")
        snapshot[name] = axis
    return snapshot


def run_case(case: dict, *, llm, runs: int = MAGI_RUNS, retries: int = 1) -> dict:
    """사례 1건을 judge에 `runs`회 독립 호출한다.

    호출 간 상태를 공유하지 않는다 — 매 호출에 state 사본을 넘긴다. 병렬화하지
    않는 이유는 이번 목적이 지연 측정이 아니라 판정 기록이고, 순차 실행이 레이트
    리밋 위험이 낮아서다.

    호출 실패는 조용히 넘기지 않는다. `retries`회 재시도 후에도 실패하면 그 사례를
    실패로 기록하고 남은 실행은 시도하지 않는다(반쪽 표본은 투표에 못 쓴다).
    """
    from app.nodes.judge_eval import judge_eval  # noqa: PLC0415 — 오프라인 경로 보호

    case_id = case["case_id"]
    state = case["state"]
    record = {
        "case_id": case_id,
        "group": "primary" if case_id in MAGI_PRIMARY_TARGETS else "control",
        "case_content_sha256": case_content_sha256(state),
        "status": "ok",
        "runs": [],
    }
    for index in range(1, runs + 1):
        try:
            judge_output = _invoke_with_retry(
                lambda: judge_eval(dict(state), llm=llm), retries=retries
            )
        except Exception as error:  # noqa: BLE001 — 사유를 기록해야 하므로 광범위
            record["status"] = "failed"
            record["failure"] = {
                "run_index": index,
                "error_type": type(error).__name__,
                "error": str(error),
            }
            return record
        record["runs"].append(
            {
                "run_index": index,
                "judge_passed": bool((judge_output.get("judge") or {}).get("passed")),
                "axes": _axis_snapshot(judge_output),
                "prompt_hash": _prompt_hash(judge_output),
                "model_version": _model_version(judge_output),
            }
        )
    return record


def _invoke_with_retry(call, *, retries: int):
    """1회 재시도까지 허용한다. 마지막 예외를 그대로 올린다."""
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 — 재시도 후 그대로 재전파
            last = error
    raise last  # type: ignore[misc]


def _model_version(judge_output: dict) -> dict:
    """실행에 실제로 쓰인 모델 정보. judge 감사기록에서 읽기만 한다."""
    latest = (
        ((judge_output.get("run_config") or {}).get("audit") or {})
        .get("llm", {})
        .get("judge_eval", {})
        .get("latest", {})
    )
    model_version = latest.get("model_version") if isinstance(latest, dict) else None
    return model_version if isinstance(model_version, dict) else {}


def run_targets(cases: list[dict], *, llm, runs: int = MAGI_RUNS) -> list[dict]:
    """대상 사례를 순서대로 3회씩 돌린다. 한 사례가 실패해도 나머지는 진행한다."""
    return [run_case(case, llm=llm, runs=runs) for case in cases]


# --- 집계 -------------------------------------------------------------------
def deterministic_violations(records: list[dict]) -> list[dict]:
    """결정론 4축이 3회 중 갈린 사례·축 목록.

    이것은 흔들림이 아니라 결함 신호다. 순수 파이썬 규칙이 같은 입력에 다른 답을
    냈다는 뜻이라, 흔들림 통계에 섞으면 원인이 다른 두 현상이 한 숫자에 들어간다.
    """
    violations = []
    for record in records:
        if record["status"] != "ok":
            continue
        for axis in DETERMINISTIC_AXES:
            votes = [run["axes"][axis]["passed"] for run in record["runs"]]
            if is_split(votes):
                violations.append(
                    {
                        "case_id": record["case_id"],
                        "axis": axis,
                        "votes": votes,
                        "note": "결정론 축이 같은 입력에 다른 판정을 냈다 — 결함 신호",
                    }
                )
    return violations


def aggregate_case(record: dict) -> dict:
    """사례 1건의 3표를 축별·판정별로 접는다."""
    if record["status"] != "ok":
        return {
            "case_id": record["case_id"],
            "group": record["group"],
            "status": record["status"],
        }
    axes = {
        axis: _vote_block([run["axes"][axis]["passed"] for run in record["runs"]])
        for axis in AXIS_NAMES
    }
    llm_unstable = any(axes[axis]["split"] for axis in LLM_AXES)
    return {
        "case_id": record["case_id"],
        "group": record["group"],
        "status": "ok",
        "axes": axes,
        # 정본 단위 — 두 LLM 축 중 하나라도 갈리면 '흔들린 사례'로 센다.
        "llm_axis_unstable": llm_unstable,
        "deterministic_stable": not any(
            axes[axis]["split"] for axis in DETERMINISTIC_AXES
        ),
        # judge 전체 판정(pass/fail)의 3표. 6축 밖의 형태 검사까지 포함한 값이라
        # 축별 집계와 별개로 남긴다 — R2 일치율이 실제로 쓰는 단위가 이것이다.
        "judge_passed": _vote_block(
            [run["judge_passed"] for run in record["runs"]]
        ),
    }


def aggregate(records: list[dict]) -> dict:
    """정본(LLM 축 합산) 집계 + 축별 분리 + 두 규칙 대조."""
    per_case = [aggregate_case(record) for record in records]
    usable = [case for case in per_case if case["status"] == "ok"]

    def _group(name: str) -> dict:
        members = [case for case in usable if case["group"] == name]
        unstable = [case["case_id"] for case in members if case["llm_axis_unstable"]]
        return {
            "cases": len(members),
            "unstable_cases": len(unstable),
            "unstable_case_ids": unstable,
        }

    unstable_ids = [case["case_id"] for case in usable if case["llm_axis_unstable"]]
    per_axis = {
        axis: {
            "cases": len(usable),
            "split_cases": sum(1 for case in usable if case["axes"][axis]["split"]),
            "split_case_ids": [
                case["case_id"] for case in usable if case["axes"][axis]["split"]
            ],
        }
        for axis in LLM_AXES
    }
    divergent = [
        {"case_id": case["case_id"], "scope": scope}
        for case in usable
        for scope in (*LLM_AXES, "judge_passed")
        if (case["axes"][scope] if scope in LLM_AXES else case[scope])["rules_disagree"]
    ]
    return {
        "canonical_unit": "llm_axes_combined",
        "cases_recorded": len(per_case),
        "cases_usable": len(usable),
        "cases_failed": [
            case["case_id"] for case in per_case if case["status"] != "ok"
        ],
        "unstable_cases": len(unstable_ids),
        "unstable_case_ids": unstable_ids,
        "by_group": {"primary": _group("primary"), "control": _group("control")},
        "per_axis": per_axis,
        "per_axis_caveat": AXIS_BREAKDOWN_CAVEAT,
        "rule_comparison": {
            "unanimous_rule": "3표가 모두 pass일 때만 pass",
            "majority_rule": "2표 이상 pass면 pass",
            "divergent": divergent,
            "divergent_count": len(divergent),
        },
        "per_case": per_case,
    }


# --- 산출물 -----------------------------------------------------------------
def build_header(
    records: list[dict],
    *,
    code_sha: str,
    evalset_hash: str,
    temperature: float | None,
    seed: int | None,
    runs: int,
) -> dict:
    """해석에 필요한 조건을 전부 남긴다 — 나중에 이 수치를 읽는 사람 기준."""
    prompt_hashes = sorted(
        {run["prompt_hash"] for record in records for run in record["runs"] if run["prompt_hash"]}
    )
    models = sorted(
        {
            json.dumps(run["model_version"], ensure_ascii=False, sort_keys=True)
            for record in records
            for run in record["runs"]
            if run["model_version"]
        }
    )
    model_versions = [json.loads(item) for item in models]
    return {
        "harness": "magi_vote",
        "purpose": OBSERVATION_ONLY_NOTE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_sha": code_sha,
        # 한 실행 안에서 프롬프트가 갈리면 흔들림의 원인이 프롬프트가 되어 측정이
        # 무의미해진다. 값이 하나가 아니면 목록 그대로 남겨 그 사실을 드러낸다.
        "prompt_hash": prompt_hashes[0] if len(prompt_hashes) == 1 else None,
        "prompt_hashes_observed": prompt_hashes,
        "evalset_hash": evalset_hash,
        "evalset_hash_source": (
            "goldenset_loader.input_set_hash() — 무라벨 20건 본문 집합. "
            "app/evidence/schema.py:evalset_hash()는 사람 라벨을 해시에 포함하므로 "
            "라벨을 읽지 않는 이 하네스에서는 쓰지 않는다."
        ),
        "model_versions_observed": model_versions,
        "temperature": temperature,
        "seed": seed,
        "sampling_note": (
            "temperature·seed는 app/llm/client.py:get_llm의 값을 그대로 읽어 기록만 "
            "한다. 이 하네스는 샘플링 파라미터를 바꾸지 않는다."
        ),
        "null_result_phrasing": NULL_RESULT_PHRASING,
        "selection_rule": SELECTION_RULE,
        "targets": {
            "primary": list(MAGI_PRIMARY_TARGETS),
            "control": list(MAGI_CONTROL_TARGETS),
        },
        **expected_calls(MAGI_TARGETS, runs),
        "reproducibility_note": REPRODUCIBILITY_NOTE,
    }


def build_report(records: list[dict], *, header: dict) -> dict:
    """산출물 1건 — 헤더 · 3표 원본 · 집계 · 결정론 축 위반."""
    violations = deterministic_violations(records)
    return {
        "header": header,
        "raw_votes": records,
        "summary": aggregate(records),
        "deterministic_axis_violations": violations,
        "deterministic_axis_violation_count": len(violations),
    }


def exit_code_for(report: dict) -> int:
    """산출물 하나로 종료 코드를 정한다 — CLI 밖에서도 검증 가능하게 분리한다.

    호출 실패가 결정론 축 위반보다 우선한다. 실패한 사례는 3표를 못 채워 불변식
    판단 자체가 성립하지 않으므로, 둘을 같이 보고할 때 원인이 뒤섞인다.
    """
    if report["summary"]["cases_failed"]:
        return EXIT_RUN_FAILURE
    if report["deterministic_axis_violations"]:
        return EXIT_DETERMINISTIC_DRIFT
    return EXIT_OK


def write_report(report: dict, out_path: Path) -> Path:
    """결정론적(sort_keys) JSON으로 저장한다 — judge_runner와 같은 규약."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


# --- CLI --------------------------------------------------------------------
def select_cases(all_cases: list[dict], targets: tuple[str, ...] = MAGI_TARGETS) -> list[dict]:
    """동결 표본만 골라 targets 순서로 돌려준다. 없는 사례는 즉시 실패시킨다."""
    by_id = {case["case_id"]: case for case in all_cases}
    missing = [case_id for case_id in targets if case_id not in by_id]
    if missing:
        raise SystemExit(f"표본 사례를 찾을 수 없습니다: {missing}")
    return [by_id[case_id] for case_id in targets]


def _print_plan(runs: int) -> None:
    plan = expected_calls(MAGI_TARGETS, runs)
    print("MAGI 반복 호출 하네스 — 관측 전용 (v3 공식 판정에 반영하지 않음)")
    print(f"  주 표본 {len(MAGI_PRIMARY_TARGETS)}건: {', '.join(MAGI_PRIMARY_TARGETS)}")
    print(f"  통제군 {len(MAGI_CONTROL_TARGETS)}건: {', '.join(MAGI_CONTROL_TARGETS)}")
    print(f"  사례당 {plan['runs_per_case']}회 · judge 호출 {plan['judge_invocations']}회")
    print(f"  예상 LLM 호출 {plan['llm_calls']}회 (사례당 LLM 축 {LLM_CALLS_PER_INVOCATION}개)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="같은 입력에 judge를 3회 돌려 LLM 판정 축의 흔들림을 기록한다(관측 전용)."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("out/magi_vote.json"),
        help="산출물 JSON 경로 (기본: out/magi_vote.json)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=MAGI_RUNS,
        help=f"사례당 독립 호출 수 (기본 {MAGI_RUNS}). 투표 규칙은 홀수 표를 전제한다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="대상 목록과 예상 호출 수만 출력하고 종료한다. Azure를 호출하지 않는다.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Azure 대신 fake LLM으로 배선을 리허설한다(흔들림은 측정되지 않는다).",
    )
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs 는 1 이상이어야 합니다")

    _print_plan(args.runs)
    if args.dry_run:
        print("  --dry-run: Azure를 호출하지 않고 종료합니다.")
        raise SystemExit(EXIT_OK)

    from app.evaluation.goldenset_loader import input_set_hash  # noqa: PLC0415

    cases = select_cases(_load_r1_cases())
    llm = _offline_llm() if args.offline else _real_llm()
    records = run_targets(cases, llm=llm, runs=args.runs)

    header = build_header(
        records,
        code_sha=resolve_code_sha(),
        evalset_hash=input_set_hash(),
        # 있는 그대로 읽는다 — 이 하네스는 샘플링 파라미터를 정하지 않는다.
        temperature=getattr(llm, "temperature", None),
        seed=getattr(llm, "seed", None),
        runs=args.runs,
    )
    report = build_report(records, header=header)
    out_path = write_report(report, args.out)

    summary = report["summary"]
    print(
        f"기록 완료: {summary['cases_usable']}/{summary['cases_recorded']}건 "
        f"→ {out_path}"
    )
    print(
        f"  흔들린 사례(LLM 축 합산): {summary['unstable_cases']}건 "
        f"{summary['unstable_case_ids']}"
    )
    print(f"  두 규칙이 갈린 항목: {summary['rule_comparison']['divergent_count']}건")

    code = exit_code_for(report)
    if code == EXIT_RUN_FAILURE:
        print(
            f"실패: judge 호출이 재시도 후에도 실패했습니다 — {summary['cases_failed']}",
            file=sys.stderr,
        )
    elif code == EXIT_DETERMINISTIC_DRIFT:
        print(
            "결정론 축 불변식 위반 — 흔들림이 아니라 결함 신호입니다:\n  "
            + "\n  ".join(
                f"{item['case_id']}/{item['axis']} votes={item['votes']}"
                for item in report["deterministic_axis_violations"]
            ),
            file=sys.stderr,
        )
    raise SystemExit(code)


def _offline_llm():
    """배선 리허설용 fake LLM(judge_runner --offline과 동일한 것)."""
    from tests.test_judge_eval_evalset import _PassingLLM  # noqa: PLC0415

    return _PassingLLM()


if __name__ == "__main__":
    main()
