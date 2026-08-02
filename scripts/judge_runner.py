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
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evaluation.calibration_schema import build_judge_result  # noqa: E402
from app.goldenset.loader import load_case  # noqa: E402,F401  (테스트 계약: scripts.judge_runner.load_case)
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


def resolve_freeze_commit() -> str:
    """v1-freeze 태그가 가리키는 커밋 SHA. v1이 '라벨 동결 시점' 기준임을 증명한다.

    '고치고 나서 v1을 잰 것 아니냐'를 반박하는 감사 앵커라, 태그가 없으면 조용히
    넘기지 않고 즉시 실패시킨다(동결 기준을 못 박지 못하면 v1의 의미가 없다).
    """
    completed = subprocess.run(
        ["git", "rev-parse", "v1-freeze^{commit}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _run_judge_with_langsmith(
    state: dict, *, llm, case_id: str, langsmith_project: str | None
) -> tuple[dict, str | None, str | None]:
    """judge_eval을 실행하되, LangSmith가 켜졌으면 사례당 부모 run으로 감싼다.

    judge는 사례당 LLM을 2번(hallucination·false_precision) 호출하므로, 사례마다
    langsmith.trace(run_id)로 감싸 두 호출을 한 run의 자식으로 묶는다(계약: 사례당
    고유 run 1개). LangSmith가 꺼졌거나 오프라인이면 감싸지 않고 run id를 None으로
    둔다 — 실제 기록이 없는데 run id만 채워 '유령 링크'를 만들지 않기 위함이다.

    반환: (judge_output, langsmith_run_id, langsmith_trace_url)
    """
    if not langsmith_project:
        return judge_eval(state, llm=llm), None, None

    from langsmith.run_helpers import trace

    run_id = uuid.uuid4()
    with trace(name=f"judge:{case_id}", run_id=run_id, project_name=langsmith_project):
        judge_output = judge_eval(state, llm=llm)
    return judge_output, str(run_id), _trace_url(run_id, langsmith_project)


def _trace_url(run_id: uuid.UUID, project: str) -> str | None:
    """LangSmith run의 UI URL(best-effort). 계약상 선택이라 실패하면 None."""
    endpoint = os.environ.get("LANGSMITH_ENDPOINT", "").strip()
    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not (endpoint and api_key and project):
        return None
    from app.observability.langsmith import _get_run_url

    return _get_run_url(run_id, endpoint=endpoint, api_key=api_key, project=project)


def record_case(
    case: dict,
    *,
    llm,
    prompt_version: str,
    code_sha: str,
    freeze_commit: str | None = None,
    input_set_hash: str | None = None,
    langsmith_project: str | None = None,
) -> dict:
    """사례 1건을 judge_eval에 돌려 JudgeResult 계약으로 변환한다.

    case: {"case_id": str, "state": dict}. state는 judge가 읽는 입력(run_config·
    metrics·explanations·citations·approval 등)만 담는다 — 사람 라벨은 넣지 않는다.

    freeze_commit이 주어지면 결과에 감사 앵커로 덧붙인다. 계약 함수
    build_judge_result는 팀 데이터 계약이라 건드리지 않고, normalize가 미지 필드를
    무시하므로 소비자를 깨지 않는다. langsmith_project가 주어지면 사례당 LangSmith
    run을 남기고 그 run id/URL을 기록한다(공식 제출 요건).
    """
    case_id = case["case_id"]
    state = case["state"]
    judge_output, langsmith_run_id, langsmith_trace_url = _run_judge_with_langsmith(
        state, llm=llm, case_id=case_id, langsmith_project=langsmith_project
    )
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
        # LangSmith가 켜졌으면 사례당 run id/URL, 오프라인이면 None(계약상 선택).
        langsmith_run_id=langsmith_run_id,
        langsmith_trace_url=langsmith_trace_url,
    )
    # 계약 검증은 소비자(R2 분석 담당의 merge_records/validate_official_case_set)의
    # 몫이다. 러너는 judge 출력을 충실히 옮기기만 한다 — 특히 오프라인 리허설은
    # model_version이 비어(실제 Azure 배포 없음) 제출 등급 검증을 통과할 수 없으므로,
    # 여기서 normalize를 강제하면 배선 리허설 자체가 불가능해진다.
    if freeze_commit is not None:
        result["freeze_commit"] = freeze_commit
    # input_set_hash: v1·v2가 '같은 20건 세트'로 측정됐음을 증명하는 평가셋 앵커.
    if input_set_hash is not None:
        result["input_set_hash"] = input_set_hash
    # prompt_hash: v1·v2가 '프롬프트만 달랐다'를 증명하는 앵커. 같은 사례에서
    # code_sha는 같고 prompt_hash만 달라야 개선 효과를 프롬프트로 귀속할 수 있다.
    prompt_hash = _prompt_hash(judge_output)
    if prompt_hash:
        result["prompt_hash"] = prompt_hash
    return result


def _prompt_hash(judge_output: dict) -> str:
    """judge 감사기록에서 프롬프트 집계 해시를 뽑는다. 없으면 빈 문자열."""
    latest = (
        ((judge_output.get("run_config") or {}).get("audit") or {})
        .get("llm", {})
        .get("judge_eval", {})
        .get("latest", {})
    )
    prompt_hash = latest.get("prompt_hash") if isinstance(latest, dict) else None
    if isinstance(prompt_hash, dict):
        aggregate = prompt_hash.get("aggregate_sha256")
        return aggregate if isinstance(aggregate, str) else ""
    return ""


def record_cases(
    cases: Iterable[dict],
    *,
    llm,
    prompt_version: str,
    code_sha: str,
    freeze_commit: str | None = None,
    input_set_hash: str | None = None,
    langsmith_project: str | None = None,
) -> list[dict]:
    """사례 목록을 순서대로 judge에 돌려 JudgeResult 목록을 만든다."""
    return [
        record_case(
            case,
            llm=llm,
            prompt_version=prompt_version,
            code_sha=code_sha,
            freeze_commit=freeze_commit,
            input_set_hash=input_set_hash,
            langsmith_project=langsmith_project,
        )
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


def manifest_path_for(out_path: Path) -> Path:
    """결과 파일 옆의 실행 요약 카드 경로. judge_v1_results.json →
    judge_v1_results.manifest.json."""
    return out_path.with_suffix(".manifest.json")


def write_run_manifest(
    out_path: Path,
    *,
    prompt_version: str,
    code_sha: str,
    freeze_commit: str,
    input_set_hash: str,
    langsmith_run: str | None = None,
) -> Path:
    """실행 1건의 출처(provenance) 요약 카드를 결과 파일 옆에 남긴다.

    자동 파생 필드(prompt_version·code_sha·freeze_commit·input_set_hash·
    executed_at·langsmith_run)만 러너가 채우고, 사람이 확인한 사실을 적는
    verifications는 빈 배열로 둔다 — R2 분석 담당이 사후에 손으로 채운다(예:
    citations.py 동작동일 확인). 사례별 JudgeResult 리스트(자동 파생 전용 계약)에
    사람 메모를 섞지 않기 위한 분리다.

    prompt_version·code_sha는 사례별 결과에도 있지만(validate_run_consistency가
    한 실행 내 동일성을 보장), 카드에 요약해두면 실행 식별과 verifications의
    method(git diff <freeze_commit>..<code_sha> ...) 작성이 카드 한 장으로 끝난다.
    """
    manifest = {
        "prompt_version": prompt_version,
        "code_sha": code_sha,
        "freeze_commit": freeze_commit,
        "input_set_hash": input_set_hash,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "langsmith_run": langsmith_run,
        "verifications": [],
    }
    path = manifest_path_for(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


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


def _wrap_state(parsed: dict, *, run_config_defaults: dict) -> dict:
    """load_case 출력(metrics/explanations/citations)을 실행 state로 감싼다.

    load_case는 leakage 경계상 metrics/explanations/citations만 반환한다. judge
    실행에 필요한 스캐폴딩(run_config·approval)은 정답이 아니므로 러너가 채운다.
    기준일(as_of_date)은 각 사례 본문의 기준일(=metrics.meta.data_period.end)을 써서
    사례별로 날짜 정합 축이 자기완결적으로 작동하게 한다.
    """
    as_of_date = (
        (parsed.get("metrics") or {}).get("meta", {}).get("data_period", {}).get("end")
    )
    run_config = dict(run_config_defaults)
    if as_of_date:
        run_config["as_of_date"] = as_of_date
    return {
        "run_config": run_config,
        "approval": {"status": "locked"},
        "judge_retries": 0,
        **parsed,
    }


def _load_r1_cases() -> list[dict]:
    """R1 무라벨 사례집(goldenset/judge_inputs) 20건을 실행 state로 불러온다.

    정답이 제거된 judge_inputs만 읽는다 — 원본 정답 사례집은 열지 않는다. 실행
    스캐폴딩의 기준값(judge_max_retries·strict_citation_gate 등)은 config.yaml을
    적재하는 load_inputs에서 가져와 사례별 기준일만 덮어쓴다.
    """
    from app.goldenset.loader import load_all_cases
    from app.nodes.load_inputs import load_inputs

    run_config_defaults = load_inputs({})["run_config"]
    return [
        {"case_id": case["case_id"], "state": _wrap_state(case["state"], run_config_defaults=run_config_defaults)}
        for case in load_all_cases()
    ]


def _r1_input_set_hash() -> str:
    """R1 무라벨 평가셋 식별 해시(manifest input_set_hash)."""
    from app.goldenset.loader import input_set_hash

    return input_set_hash()


def _langsmith_project() -> str | None:
    """LangSmith 트레이싱이 실제 활성일 때만 프로젝트명을 반환한다(아니면 None).

    app.observability.langsmith.langsmith_enabled()가 트레이싱 플래그와 필수 키
    (API_KEY·ENDPOINT·PROJECT)가 모두 있을 때만 True다. 여기서 None이면 러너는
    run id를 만들지 않고 결과를 '리허설' 신분으로 둔다(유령 링크 방지).
    """
    from app.observability.langsmith import langsmith_enabled

    if not langsmith_enabled():
        return None
    return os.environ.get("LANGSMITH_PROJECT", "").strip() or None


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
        "--r1",
        action="store_true",
        help="R1 무라벨 사례집(goldenset/judge_inputs) 20건으로 실행한다(Phase 2).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Azure 대신 fake LLM으로 실행(오프라인 리허설).",
    )
    args = parser.parse_args()

    if args.ec_demo == args.r1:
        parser.error("--ec-demo 또는 --r1 중 정확히 하나를 지정하세요.")

    cases = _load_r1_cases() if args.r1 else _load_ec_cases()
    llm = _offline_llm() if args.offline else _real_llm()
    code_sha = resolve_code_sha()
    # freeze 앵커는 실제 R1 v1/v2 실행에서만 기록한다. EC 리허설은 정답 동결과
    # 무관하므로 남기지 않는다.
    freeze_commit = resolve_freeze_commit() if args.r1 else None
    # 평가셋 앵커: load_all_cases가 이미 manifest 무결성을 검증했으므로 이 값은
    # 신뢰 가능하다. EC 리허설은 동결 평가셋이 아니라 기록하지 않는다.
    input_set_hash = _r1_input_set_hash() if args.r1 else None
    # LangSmith 실행 기록은 공식 v1/v2 제출 요건이다. 실제 R1 실행이고 트레이싱이
    # 켜졌을 때만 남긴다 — 오프라인/키 없음이면 None(정직하게 '리허설' 신분).
    langsmith_project = _langsmith_project() if (args.r1 and not args.offline) else None
    if args.r1:
        _warn_if_judge_code_uncommitted()
        if langsmith_project is None and not args.offline:
            print(
                "경고: LangSmith 트레이싱이 꺼져 있습니다 — 이 v1은 공식(--official)"
                " 등급이 될 수 없습니다(LANGSMITH_* 환경변수 확인).",
                file=sys.stderr,
            )
    results = record_cases(
        cases,
        llm=llm,
        prompt_version=args.prompt_version,
        code_sha=code_sha,
        freeze_commit=freeze_commit,
        input_set_hash=input_set_hash,
        langsmith_project=langsmith_project,
    )
    out_path = write_results(results, args.out)
    passed = sum(1 for r in results if r["passed"])
    anchor = f", freeze_commit={freeze_commit[:12]}" if freeze_commit else ""
    print(
        f"기록 완료: {len(results)}건 (통과 {passed} / 미통과 {len(results) - passed}) "
        f"→ {out_path}  [prompt_version={args.prompt_version}, code_sha={code_sha[:12]}{anchor}]"
    )
    # 실행 요약 카드는 실제 R1 v1/v2 실행에서만 남긴다(동결 평가셋 대상).
    if args.r1:
        manifest_out = write_run_manifest(
            out_path,
            prompt_version=args.prompt_version,
            code_sha=code_sha,
            freeze_commit=freeze_commit,
            input_set_hash=input_set_hash,
            # 사례별 run id는 각 JudgeResult에 있다. 카드의 run-level 값은 모든 사례
            # run이 모인 LangSmith 프로젝트를 가리킨다(트레이싱 꺼졌으면 None).
            langsmith_run=langsmith_project,
        )
        print(f"실행 요약 카드: {manifest_out}  (verifications는 사후 수기 기록)")


# judge 판정에 영향을 주는 경로. v1↔v2 비교는 이 코드가 두 실행에서 동일해야
# 성립한다(배선 코드는 판정에 무관하므로 제외).
_JUDGE_RELEVANT_PATHS = ("app/judge", "app/nodes/judge_eval.py", "app/rag/citations.py")


def _warn_if_judge_code_uncommitted() -> None:
    """judge 판정 코드에 커밋 안 된 변경이 있으면 경고한다.

    v1↔v2 비교는 결과에 기록된 code_sha(=HEAD)가 실제 실행한 judge 코드와 같음을
    전제로 한다. 작업트리에 커밋 안 된 수정이 있으면 code_sha가 실제 코드를 대변하지
    못해, 나중에 'v1·v2가 같은 코드였다'를 code_sha로 증명할 수 없다. (freeze 이후
    코드가 바뀌는 것 자체는 정상이며 경고 대상이 아니다 — 중요한 건 v1과 v2가 서로
    같은 코드인지이지, freeze 시점과 같은지가 아니다.)
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", *_JUDGE_RELEVANT_PATHS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    dirty = [line for line in completed.stdout.splitlines() if line.strip()]
    if dirty:
        print(
            "경고: judge 판정 코드에 커밋되지 않은 변경이 있습니다 — 기록된 code_sha가"
            " 실제 실행 코드를 대변하지 못해 v1↔v2 동일 코드 증명이 깨질 수 있습니다."
            " 커밋 후 실행하세요:\n  " + "\n  ".join(dirty),
            file=sys.stderr,
        )


def _real_llm():
    """실제 Azure judge LLM(.env 필요). 오프라인이 아닐 때만 지연 로드한다.

    temperature=0.0을 명시한다 — judge_eval의 기본 LLM과 같은 결정론 설정을 러너가
    독립적으로 못박아, get_llm 기본값이 나중에 바뀌어도 재현성이 흔들리지 않게 한다.
    """
    from app.llm.client import get_llm

    return get_llm(temperature=0.0)


if __name__ == "__main__":
    main()
