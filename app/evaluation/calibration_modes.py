"""R2 캘리브레이션 실행 등급의 단일 계약(SSOT).

실행 등급 문자열을 생산자(`scripts/calibration_report.py`)와 소비자
(`scripts/make_evidence_bundle.py`)가 각각 정의하면, 한쪽에 새 모드를 추가한
순간 R4 증거 번들이 그 값을 모르는 상태가 된다. 허용값과 각 모드의 검증 조건을
이 모듈 한 곳에서 함께 관리한다.
"""
from __future__ import annotations


MODE_DEV_MOCK = "dev_mock"
MODE_OFFLINE_REHEARSAL = "offline_rehearsal"
MODE_OFFICIAL = "official"
MODE_OFFICIAL_CODE_CHANGE = "official_code_change"
MODE_OFFICIAL_OFFLINE_CODE_CHANGE = "official_offline_code_change"

#: mode별로 calibration 리포트 최상위에 반드시 함께 기록돼야 하는 검증 메타데이터.
#: `official_validation_passed`는 `--official` 구조 검증 통과 여부이고,
#: `langsmith_required`는 공식 LangSmith run ID 요건을 실제로 적용했는지다.
CALIBRATION_MODE_REQUIREMENTS: dict[str, dict[str, bool]] = {
    MODE_DEV_MOCK: {
        "official_validation_passed": False,
        "langsmith_required": False,
    },
    MODE_OFFLINE_REHEARSAL: {
        "official_validation_passed": True,
        "langsmith_required": False,
    },
    MODE_OFFICIAL: {
        "official_validation_passed": True,
        "langsmith_required": True,
    },
    MODE_OFFICIAL_CODE_CHANGE: {
        "official_validation_passed": True,
        "langsmith_required": True,
    },
    MODE_OFFICIAL_OFFLINE_CODE_CHANGE: {
        "official_validation_passed": True,
        "langsmith_required": False,
    },
}

CALIBRATION_MODES = tuple(CALIBRATION_MODE_REQUIREMENTS)

#: R4 최종 제출에서 공식 증거로 인정할 수 있는 모드. 코드 개선 비교도 정확히
#: 20건·1차 판정·run 일관성·LangSmith 요건을 통과하므로 공식 등급이다.
OFFICIAL_CALIBRATION_MODES = frozenset(
    {MODE_OFFICIAL, MODE_OFFICIAL_CODE_CHANGE}
)


def calibration_mode_issue(
    mode: object,
    *,
    official_validation_passed: object,
    langsmith_required: object,
) -> str | None:
    """알 수 없거나 메타데이터가 모순된 등급이면 사유를 반환한다.

    증거 번들은 모르는 등급을 추측해서 공식 수치로 싣지 않는다. 허용된 문자열이어도
    함께 기록된 검증 플래그가 해당 모드의 계약과 다르면 같은 원칙으로 거부한다.
    """
    if not isinstance(mode, str) or mode not in CALIBRATION_MODE_REQUIREMENTS:
        return f"알 수 없는 calibration mode: {mode!r}"
    if not isinstance(official_validation_passed, bool):
        return "official_validation_passed는 bool이어야 한다"
    if not isinstance(langsmith_required, bool):
        return "langsmith_required는 bool이어야 한다"

    expected = CALIBRATION_MODE_REQUIREMENTS[mode]
    actual = {
        "official_validation_passed": official_validation_passed,
        "langsmith_required": langsmith_required,
    }
    if actual != expected:
        return f"calibration mode={mode!r}의 검증 메타데이터 불일치: expected={expected}, actual={actual}"
    return None
