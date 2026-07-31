"""R2 캘리브레이션 리포트 CLI — 계산 로직(app/evaluation/)을 실행해 사람이 보는
표로 뽑는다.

이 스크립트는 judge를 호출하지 않는다. judge_runner.py가 만든 JudgeResult
JSON과 R1 정답 사례집(md frontmatter, 또는 개발용 HumanLabel JSON)을 읽어
app.evaluation.calibration_schema.merge_records()로 합치고,
app.evaluation.judge_calibration의 집계 함수를 실행해 콘솔 표 + (선택) JSON
파일로 출력한다. 새 화면이나 UI가 아니라 R4 증거번들·발표 서류철에 붙일
분석 산출물을 만드는 용도다.

사용 예:
    python scripts/calibration_report.py --judge-results out/v1.json \\
        --human-labels-dir corpus/r1_gold_labels --official

    python scripts/calibration_report.py --judge-results out/v1.json \\
        --judge-results-v2 out/v2.json --human-labels-dir corpus/r1_gold_labels \\
        --official --out out/calibration_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evaluation.calibration_schema import (  # noqa: E402
    CalibrationRecord,
    merge_records,
    validate_official_case_set,
)
from app.evaluation.human_labels import load_human_labels_from_dir  # noqa: E402
from app.evaluation.judge_calibration import (  # noqa: E402
    build_confusion_matrix,
    calculate_axis_metrics,
    calculate_overall_metrics,
    compare_official_versions,
    compare_versions,
    find_mismatches,
)


def _load_json_list(path: Path, *, what: str) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: {what}는 JSON 배열이어야 합니다.")
    return data


def _load_human_labels(args: argparse.Namespace) -> list[dict]:
    if args.human_labels_dir is not None:
        return load_human_labels_from_dir(args.human_labels_dir)
    return _load_json_list(args.human_labels_json, what="사람 라벨")


def _print_overall(records: list[CalibrationRecord], *, title: str) -> None:
    overall = calculate_overall_metrics(records)
    matrix = build_confusion_matrix(records)
    print(f"\n=== {title}: 전체 일치율 ===")
    print(f"  총 {overall.total}건 | 일치 {overall.match}건 | 일치율 {overall.match_rate:.1%}")
    print(f"  결함 놓침(FN, 사람 fail→judge pass): {overall.false_negative}건")
    print(f"  과잉 차단(FP, 사람 pass→judge fail): {overall.false_positive}건")
    print("  혼동행렬 (행=사람, 열=judge):")
    print(f"    {'':12}{'judge pass':>12}{'judge fail':>12}")
    print(f"    {'human pass':12}{matrix['human_pass']['judge_pass']:>12}{matrix['human_pass']['judge_fail']:>12}")
    print(f"    {'human fail':12}{matrix['human_fail']['judge_pass']:>12}{matrix['human_fail']['judge_fail']:>12}")

    print(f"\n=== {title}: 6축별 일치율 ===")
    axis_metrics = calculate_axis_metrics(records)
    for axis, metrics in axis_metrics.items():
        recall = "N/A" if metrics.defect_recall is None else f"{metrics.defect_recall:.1%}"
        print(
            f"  {metrics.axis_ko:10} 일치율 {metrics.match_rate:6.1%}  "
            f"결함탐지율(recall) {recall:>6}  (결함사례 {metrics.human_fail_support}건)"
        )


def _print_mismatches(records: list[CalibrationRecord], *, title: str) -> None:
    mismatches = find_mismatches(records)
    print(f"\n=== {title}: 오판 사례 ({len(mismatches)}건) ===")
    if not mismatches:
        print("  없음.")
        return
    for m in mismatches:
        print(f"  - {m.case_id} [{m.error_type}]")
        print(f"      사람 fail_axes: {list(m.human_fail_axes)} / judge fail_axes: {list(m.judge_fail_axes)}")
        if m.axis_mismatch:
            print(f"      축 불일치: {list(m.axis_mismatch)}")
        print(f"      사람 사유: {m.human_rationale}")
        print(f"      judge 사유: {m.judge_reason}")
        if m.judge_failed_required_checks:
            print(f"      judge 6축 밖 실패 검사: {list(m.judge_failed_required_checks)}")


def _print_version_comparison(comparison) -> None:
    print("\n=== v1 → v2 비교 ===")
    print(f"  일치율: {comparison.before.match_rate:.1%} → {comparison.after.match_rate:.1%} "
          f"(Δ {comparison.match_rate_delta:+.1%})")
    print(f"  FN(결함 놓침): {comparison.before.false_negative} → {comparison.after.false_negative} "
          f"(Δ {comparison.false_negative_delta:+d})")
    print(f"  FP(과잉 차단): {comparison.before.false_positive} → {comparison.after.false_positive} "
          f"(Δ {comparison.false_positive_delta:+d})")
    print(f"  code_sha: {comparison.before_code_sha[:12]} → {comparison.after_code_sha[:12]}")
    print("  6축별 결함탐지율(recall) 변화:")
    for axis in comparison.axis_before:
        before_r = comparison.axis_before[axis].defect_recall
        after_r = comparison.axis_after[axis].defect_recall
        before_s = "N/A" if before_r is None else f"{before_r:.1%}"
        after_s = "N/A" if after_r is None else f"{after_r:.1%}"
        print(f"    {comparison.axis_before[axis].axis_ko:10} {before_s:>6} → {after_s:>6}")


def _to_jsonable(records: list[CalibrationRecord]) -> list[dict]:
    return [asdict(record) for record in records]


def main() -> None:
    parser = argparse.ArgumentParser(description="사람 라벨과 judge 결과를 비교해 캘리브레이션 리포트를 출력한다.")
    labels_group = parser.add_mutually_exclusive_group(required=True)
    labels_group.add_argument("--human-labels-dir", type=Path, help="R1 case_*.md 사례집 디렉터리.")
    labels_group.add_argument("--human-labels-json", type=Path, help="개발용 HumanLabel JSON 배열 파일.")
    parser.add_argument("--judge-results", required=True, type=Path, help="v1 JudgeResult JSON 배열 파일.")
    parser.add_argument("--judge-results-v2", type=Path, help="v2 JudgeResult JSON 배열 파일(있으면 v1·v2 비교도 출력).")
    parser.add_argument(
        "--official",
        action="store_true",
        help="R2 공식 제출 검증(정확히 20건·1차 판정·run 일관성·LangSmith)까지 강제한다.",
    )
    parser.add_argument(
        "--no-langsmith",
        action="store_true",
        help="--official과 함께 쓸 때 LangSmith run ID 필수 요건을 낮춘다(오프라인 리허설용).",
    )
    parser.add_argument("--out", type=Path, help="리포트를 JSON으로도 저장할 경로(증거번들·서류철용).")
    args = parser.parse_args()

    human_labels = _load_human_labels(args)
    judge_results = _load_json_list(args.judge_results, what="judge 결과")
    records = merge_records(human_labels, judge_results)
    if args.official:
        validate_official_case_set(records, require_langsmith=not args.no_langsmith)

    _print_overall(records, title="v1")
    _print_mismatches(records, title="v1")

    report: dict = {
        "v1": {
            "records": _to_jsonable(records),
            "overall": asdict(calculate_overall_metrics(records)),
            "confusion_matrix": build_confusion_matrix(records),
            "axis_metrics": {axis: asdict(m) for axis, m in calculate_axis_metrics(records).items()},
            "mismatches": [asdict(m) for m in find_mismatches(records)],
        }
    }

    if args.judge_results_v2 is not None:
        judge_results_v2 = _load_json_list(args.judge_results_v2, what="judge 결과(v2)")
        records_v2 = merge_records(human_labels, judge_results_v2)
        if args.official:
            validate_official_case_set(records_v2, require_langsmith=not args.no_langsmith)
        _print_overall(records_v2, title="v2")
        _print_mismatches(records_v2, title="v2")

        compare = compare_official_versions if args.official else compare_versions
        comparison = compare(records, records_v2)
        _print_version_comparison(comparison)

        report["v2"] = {
            "records": _to_jsonable(records_v2),
            "overall": asdict(calculate_overall_metrics(records_v2)),
            "confusion_matrix": build_confusion_matrix(records_v2),
            "axis_metrics": {axis: asdict(m) for axis, m in calculate_axis_metrics(records_v2).items()},
            "mismatches": [asdict(m) for m in find_mismatches(records_v2)],
        }
        report["comparison"] = asdict(comparison)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\n리포트 저장: {args.out}")


if __name__ == "__main__":
    main()
