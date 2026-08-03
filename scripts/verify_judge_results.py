"""v1/v2 결과 파일이 R2 제출 등급인지 확인한다(실행 후 사전 점검).

지은님 소비자(merge_records)가 받기 전에, 각 JudgeResult가 계약
(app.evaluation.calibration_schema.normalize_judge_result)을 통과하는지 러너
실행 담당(다경)이 미리 확인하기 위한 도구다. 여기서 걸리는 문제(예: 오프라인
실행이라 model_version이 빔)를 조기에 잡아 재실행 판단을 빠르게 한다.

leakage 경계: 이 도구는 judge가 낸 판정(JudgeResult)만 읽는다 — 사람 정답 라벨은
다루지 않는다. 판정은 실행 담당이 봐도 되는 산출물이다.

사용:
  python scripts/verify_judge_results.py out/judge_v1_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evaluation.calibration_schema import (  # noqa: E402
    CalibrationSchemaError,
    normalize_judge_result,
)


def verify_results(results: list[dict]) -> list[tuple[str, str]]:
    """각 결과를 normalize에 통과시켜 (case_id, 실패사유) 목록을 반환한다.

    빈 목록이면 전부 제출 등급이다.
    """
    failures: list[tuple[str, str]] = []
    for index, raw in enumerate(results):
        case_id = raw.get("case_id", f"#{index}") if isinstance(raw, dict) else f"#{index}"
        try:
            normalize_judge_result(raw)
        except CalibrationSchemaError as exc:
            failures.append((str(case_id), str(exc)))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="v1/v2 결과가 R2 제출 등급 계약을 통과하는지 확인한다."
    )
    parser.add_argument("results", type=Path, help="검사할 결과 JSON 경로.")
    args = parser.parse_args()

    try:
        results = json.loads(args.results.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"결과 파일을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 2
    if not isinstance(results, list):
        print("결과 파일은 JudgeResult 리스트여야 합니다.", file=sys.stderr)
        return 2

    failures = verify_results(results)
    total = len(results)
    if not failures:
        print(f"제출 등급 확인 완료: {total}건 전부 계약 통과.")
        return 0

    print(f"제출 등급 미달: {total}건 중 {len(failures)}건이 계약을 통과하지 못했습니다.")
    for case_id, reason in failures:
        print(f"  - {case_id}: {reason}")
    print(
        "\n힌트: 전 건이 model_version 관련으로 실패하면 오프라인(가짜 LLM) 결과일 수"
        " 있습니다. 실제 Azure(--r1, --offline 없이)로 다시 실행하세요."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
