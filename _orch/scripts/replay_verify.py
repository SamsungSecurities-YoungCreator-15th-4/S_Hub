"""같은 입력 2회 실행의 state 덤프를 재현 선언 기준으로 대조한다.

사용 예:
  python scripts/replay_verify.py run1.json run2.json

덤프는 `scripts/run_graph.py --dump-state PATH`가 만든다. 무엇을 대조하는지는
이 파일이 정하지 않는다 — `docs/reproducibility_scope.md` §2·§2.1·§3의 선언을
`app/evidence/replay_scope.py`가 옮겨 적고, 그 대조는 테스트가 고정한다.

**fail-closed다.** 대조할 수 없으면 성공으로 처리하지 않는다. 종료 코드는 네 가지로
구분한다 — 일치 / 불일치 / 입력 문제 / 대조 불가. "왜 실패했는가"를 종료 코드만
보고도 알 수 있어야 CI와 시연 양쪽에서 쓸 수 있다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evidence.replay_scope import (  # noqa: E402
    ABSENT,
    FINGERPRINT_LABELS,
    MATCH,
    MISMATCH,
    ItemResult,
    compare_all,
)

# --- 종료 코드 ---------------------------------------------------------------
EXIT_MATCH = 0          # §2·§2.1 전부 일치
EXIT_MISMATCH = 1       # 하나라도 불일치
EXIT_INPUT_ERROR = 2    # 파일 없음·JSON 깨짐·최상위가 객체가 아님
EXIT_NOTHING_TO_COMPARE = 3  # 대조된 항목이 하나도 없음 — 빈 덤프를 통과시키지 않는다

MARK = {MATCH: "일치", MISMATCH: "불일치", ABSENT: "해당 없음"}


def force_utf8_output() -> None:
    """콘솔 기본 인코딩과 무관하게 출력이 깨지지 않게 한다.

    출력에 `—`·`✔`·`✘` 같은 문자를 쓰는데, Windows 기본 콘솔(cp949)에 그대로
    `print()`하면 `UnicodeEncodeError`로 **스크립트가 그 자리에서 죽는다.**
    결과가 안 예쁘게 나오는 정도가 아니라 종료 코드가 판정과 무관해진다.

    이 스크립트는 현장 3분 재실행에서 라이브로 도는 것이 목적이라, 발표
    노트북 콘솔이 cp949인 것만으로 시연이 멈추면 안 된다. 재현 대조가 막으려는
    실패와 같은 종류라 여기서 막는다.

    `reconfigure`가 없는 스트림(테스트 캡처 등)은 건드리지 않는다.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            # 이미 닫혔거나 재설정할 수 없는 스트림이면 그대로 둔다.
            pass


def _input_error(message: str) -> SystemExit:
    """입력 문제로 끝낸다. 사유는 stderr로 내보내 대조 결과와 섞이지 않게 한다."""
    print(f"오류: {message}", file=sys.stderr)
    return SystemExit(EXIT_INPUT_ERROR)


def _load(path: Path) -> dict:
    """덤프 하나를 읽는다. 읽을 수 없으면 일치 실패와 구분되는 코드로 끝낸다."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _input_error(f"덤프를 읽을 수 없습니다: {path} — {exc}") from None
    try:
        dump = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _input_error(f"덤프 JSON 파싱 실패: {path} — {exc}") from None
    if not isinstance(dump, dict):
        raise _input_error(f"덤프 최상위가 객체가 아닙니다: {path}")
    return dump


def _short(value: object, width: int = 20) -> str:
    text = str(value)
    return text if len(text) <= width else f"{text[:width]}…"


def _render_section(title: str, results: list[ItemResult], *, compared: bool) -> list[str]:
    lines = [f"  {title}"]
    for result in results:
        if not compared:
            # §3은 판정하지 않는다. 다만 값이 갈렸는지는 그대로 보여 준다.
            note = "다름" if result.status == MISMATCH else MARK[result.status]
            lines.append(f"    ·  {result.item.label}  ({note})")
            continue
        mark = {MATCH: "✔", MISMATCH: "✘", ABSENT: "–"}[result.status]
        line = f"    {mark}  {result.item.label}"
        if result.item.label in FINGERPRINT_LABELS and result.status == MATCH:
            line += f"  {_short(result.value)}"
        if result.status == ABSENT:
            line += "  (이 실행에 해당 없음)"
        lines.append(line)
        for path in result.diverged:
            lines.append(f"         ↳ {path}")
        hidden = result.diverged_total - len(result.diverged)
        if hidden > 0:
            lines.append(f"         ↳ … 외 {hidden}개 (총 {result.diverged_total}개)")
    return lines


def render(results: dict[str, list[ItemResult]], left: Path, right: Path) -> tuple[str, int]:
    """사람이 위에서 아래로 읽으면 5초 안에 결론이 나오도록 배치한다."""
    judged = results["guaranteed"] + results["conditional"]
    failed = [r for r in judged if r.status == MISMATCH]
    compared = [r for r in judged if r.status != ABSENT]

    if not compared:
        verdict = "대조 불가 — 선언한 항목이 어느 덤프에도 없습니다"
        code = EXIT_NOTHING_TO_COMPARE
    elif failed:
        verdict = f"불일치 {len(failed)}건 — 재현 보장 대상이 어긋났습니다"
        code = EXIT_MISMATCH
    else:
        verdict = f"일치 — 재현 보장 대상 {len(compared)}건 전부 같습니다"
        code = EXIT_MATCH

    lines = [
        "",
        f"  결과: {verdict}",
        "",
        f"  A: {left}",
        f"  B: {right}",
        "",
    ]
    lines += _render_section("[§2] 무조건 보장", results["guaranteed"], compared=True)
    lines.append("")
    lines += _render_section("[§2.1] 조건부 — LLM 판정 포함", results["conditional"], compared=True)
    lines.append("")
    lines += _render_section(
        "[§3] 재현 대상 아님 — 대조하지 않음", results["excluded"], compared=False
    )
    lines += [
        "",
        "  §3은 갈리는 것이 정상입니다. 선언은 docs/reproducibility_scope.md가 원본이고,",
        "  이 스크립트는 그 선언만 대조합니다.",
        "",
    ]
    return "\n".join(lines), code


def main() -> None:
    force_utf8_output()
    parser = argparse.ArgumentParser(
        description="같은 입력 2회 실행의 state 덤프를 재현 선언 기준으로 대조한다."
    )
    parser.add_argument("left", type=Path, metavar="DUMP_A", help="1회차 state 덤프 JSON")
    parser.add_argument("right", type=Path, metavar="DUMP_B", help="2회차 state 덤프 JSON")
    args = parser.parse_args()

    results = compare_all(_load(args.left), _load(args.right))
    report, code = render(results, args.left, args.right)
    print(report)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
