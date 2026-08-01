"""R2 실행·기록 러너 — 사례를 judge_eval에 돌려 JudgeResult(JSON)로 기록한다.

역할(R2 실행·기록): judge(심판)를 사례마다 실행하고, 그 판정을 R2 분석 담당의
`merge_records()`가 소비할 수 있는 JudgeResult 계약(app.evaluation.calibration_schema)
으로 저장한다. 저장물은 개선 전(v1)·개선 후(v2) 두 파일로 나뉜다.

leakage 경계(중요): 이 러너는 judge가 채점 대상으로 보는 사례 '내용'만 처리한다.
사람 정답 라벨(pass/fail)·rationale은 읽지도, 로그·출력하지도 않는다 — 정답은 R2
분석 담당의 merge_records()가 별도로 소비한다. 러너 출력(JudgeResult)은 judge가 낸
판정이지 정답지가 아니므로 실행 담당이 봐도 leakage가 아니다.

이번 단계(Phase 1): R1 정답 사례집이 오기 전, EC 회귀 평가셋(시스템 테스트용이며
정답지가 아님)으로 배선을 검증한다. R1 사례가 오면 case 로더만 교체하면 된다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evaluation.calibration_schema import build_judge_result  # noqa: E402
from app.nodes.judge_eval import judge_eval  # noqa: E402
from app.utils.hashing import sha256_of_dict  # noqa: E402

# judge가 실제로 채점 대상으로 보는 사례 내용. v1·v2 대조가 성립하도록(같은 사례
# 내용 → 같은 해시) 이 키만 정규 해시해 case_content_sha256을 만든다. 사람 라벨은
# judge 입력이 아니므로 이 해시에 포함되지 않는다.
JUDGE_INPUT_KEYS = ("metrics", "explanations", "citations")


def case_content_sha256(state: dict) -> str:
    """judge가 보는 사례 내용의 정규 sha256. v1·v2가 같은 사례를 썼음을 증명한다."""
    return sha256_of_dict({key: state.get(key) for key in JUDGE_INPUT_KEYS})


def resolve_code_sha() -> str:
    """현재 커밋 SHA. JudgeResult가 '어느 코드로 실행했는지'를 못박는 값이다.

    상한·정답처럼 결과를 좌우하는 값이 아니라 실행 환경 식별자라, 조회 실패 시
    조용히 대체하지 않고 즉시 실패시킨다(재현 근거가 비면 기록의 의미가 없다).
    """
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def record_case(case: dict, *, llm, prompt_version: str, code_sha: str) -> dict:
    """사례 1건을 judge_eval에 돌려 JudgeResult 계약으로 변환한다.

    case: {"case_id": str, "state": dict}. state는 judge가 읽는 입력(run_config·
    metrics·explanations·citations·approval 등)만 담는다 — 사람 라벨은 넣지 않는다.
    """
    case_id = case["case_id"]
    state = case["state"]
    judge_output = judge_eval(state, llm=llm)
    result = build_judge_result(
        case_id=case_id,
        judge_output=judge_output,
        # trace_id는 judge_eval 반환값에 없다. 그래프 실행분은 state["trace_id"]를
        # 가지지만, EC 오프라인 리허설은 없으므로 사례별 로컬 식별자로 채운다.
        trace_id=state.get("trace_id") or f"local-{case_id}",
        prompt_version=prompt_version,
        code_sha=code_sha,
        case_content_sha256=case_content_sha256(state),
        # v1·v2가 같은 기준일로 채점됐음을 계약이 검증할 수 있도록, 실행에 쓴
        # run_config의 as_of_date를 그대로 넘긴다(judge disclaimer/numeric 축의
        # expected_dates 재료). 필수 실행 조건이라 없으면 즉시 실패시킨다.
        as_of_date=state["run_config"]["as_of_date"],
        # LangSmith 연결은 실제 그래프 실행(Phase 2)에서 채운다. EC 오프라인
        # 리허설엔 run이 없으므로 None(계약상 선택 필드).
        langsmith_run_id=None,
        langsmith_trace_url=None,
    )
    # 계약 검증은 소비자(R2 분석 담당의 merge_records/validate_official_case_set)의
    # 몫이다. 러너는 judge 출력을 충실히 옮기기만 한다 — 특히 오프라인 리허설은
    # model_version이 비어(실제 Azure 배포 없음) 제출 등급 검증을 통과할 수 없으므로,
    # 여기서 normalize를 강제하면 배선 리허설 자체가 불가능해진다.
    return result


def record_cases(cases: Iterable[dict], *, llm, prompt_version: str, code_sha: str) -> list[dict]:
    """사례 목록을 순서대로 judge에 돌려 JudgeResult 목록을 만든다."""
    return [
        record_case(case, llm=llm, prompt_version=prompt_version, code_sha=code_sha)
        for case in cases
    ]


def write_results(results: list[dict], out_path: Path) -> Path:
    """JudgeResult 목록을 결정론적(sort_keys) JSON으로 저장한다."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


def _load_ec_cases() -> list[dict]:
    """EC 회귀 평가셋(시스템 테스트용, 정답지 아님)을 case 형식으로 불러온다.

    register_judge_dataset.py와 동일하게 tests의 단일 팩토리를 재사용한다. R1
    정답 사례집이 오면 이 로더만 교체하고 record_cases는 그대로 쓴다.
    """
    from tests.test_judge_eval_evalset import DETERMINISTIC_CASE_IDS, build_eval_case

    return [
        {"case_id": case_id, "state": build_eval_case(case_id)["state"]}
        for case_id in DETERMINISTIC_CASE_IDS
    ]


def _offline_llm():
    """EC 오프라인 리허설용 fake LLM(테스트와 동일 동작)."""
    from tests.test_judge_eval_evalset import _PassingLLM

    return _PassingLLM()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="사례를 judge에 돌려 JudgeResult JSON으로 기록한다."
    )
    parser.add_argument(
        "--prompt-version",
        required=True,
        help="이 실행이 어떤 judge 프롬프트 버전인지(예: v1, v2). JudgeResult에 기록된다.",
    )
    parser.add_argument("--out", required=True, type=Path, help="결과 JSON 저장 경로.")
    parser.add_argument(
        "--ec-demo",
        action="store_true",
        help="R1 사례 대신 EC 회귀 평가셋으로 배선을 리허설한다(Phase 1).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Azure 대신 fake LLM으로 실행(오프라인 리허설).",
    )
    args = parser.parse_args()

    if not args.ec_demo:
        # R1 정답 사례집 로더는 다음 단계에서 연결한다. 지금은 배선 리허설만 지원.
        parser.error("현재는 --ec-demo만 지원합니다 (R1 사례 로더는 Phase 2에서 연결).")

    cases = _load_ec_cases()
    llm = _offline_llm() if args.offline else _real_llm()
    code_sha = resolve_code_sha()
    results = record_cases(
        cases, llm=llm, prompt_version=args.prompt_version, code_sha=code_sha
    )
    out_path = write_results(results, args.out)
    passed = sum(1 for r in results if r["passed"])
    print(
        f"기록 완료: {len(results)}건 (통과 {passed} / 미통과 {len(results) - passed}) "
        f"→ {out_path}  [prompt_version={args.prompt_version}, code_sha={code_sha[:12]}]"
    )


def _real_llm():
    """실제 Azure judge LLM(.env 필요). 오프라인이 아닐 때만 지연 로드한다."""
    from app.llm.client import get_llm

    return get_llm()


if __name__ == "__main__":
    main()
