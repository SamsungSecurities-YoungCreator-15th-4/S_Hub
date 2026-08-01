"""최종 RiskState를 감사 재현이 가능한 형태로 JSON 직렬화한다.

증거 번들은 state를 입력으로 받는다(`scripts/make_evidence_bundle.py`). 그 state를
사람이 손으로 만들면 서류철을 손으로 조립하는 셈이므로, 실행이 끝난 자리에서
결정론적으로 덤프해야 한다.

## 결정론

`sort_keys=True`로 키 순서를 고정하고 `ensure_ascii=False`로 한글을 원문 유지한다.
같은 입력이면 타임스탬프·trace_id를 제외한 바이트가 동일하다.

## 변환을 기록하는 이유

JSON에 없는 타입(datetime·Decimal·set·numpy 스칼라 등)을 조용히 `str()`로 뭉개면
감사에서 "이 값의 원형이 무엇이었나"를 물었을 때 답할 수 없다. 그래서 변환기는
타입별로 **명시적으로** 다루고, 무엇을 어떤 경로에서 어떻게 바꿨는지
`_serialization_notes`에 함께 싣는다. 모르는 타입은 추측해서 바꾸지 않고
구조화된 표식으로 남긴다 — 조용히 통과시키는 것보다 눈에 띄는 편이 낫다.

현재 그래프의 최종 state에는 변환 대상이 없다(`app/engine/`이 경계에서 전부
`float()`로 캐스팅한다). 그래서 `_serialization_notes.conversions`는 보통 빈
리스트이며, **비어 있다는 사실 자체가 "원형 그대로 실렸다"는 증거**가 된다.
변환기는 그 전제가 깨지는 순간을 잡기 위한 안전망이다.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path, PurePath
from typing import Any

SERIALIZATION_NOTES_KEY = "_serialization_notes"
UNSERIALIZABLE_MARKER = "_unserializable"

#: 덤프 재현성 비교에서 제외하는 최상위 키 — 실행마다 값이 달라진다.
NONDETERMINISTIC_TOP_LEVEL_KEYS = ("trace_id",)


def _record(notes: list[dict], path: str, value: object, converted_to: str) -> None:
    notes.append(
        {
            "path": path,
            "original_type": f"{type(value).__module__}.{type(value).__qualname__}",
            "converted_to": converted_to,
            "original_repr": repr(value)[:200],
        }
    )


def _convert(value: Any, path: str, notes: list[dict]) -> Any:
    """JSON이 표현할 수 있는 값으로 바꾸고, 바꾼 것은 notes에 남긴다."""
    # json이 그대로 다루는 타입 — bool은 int보다 먼저 걸러야 한다.
    if value is None or isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if isinstance(key, str):
                key_name = key
            else:
                key_name = str(key)
                _record(notes, f"{path}.<key>{key_name}", key, "str")
            converted[key_name] = _convert(item, f"{path}.{key_name}", notes)
        return converted

    if isinstance(value, (list, tuple)):
        if isinstance(value, tuple):
            _record(notes, path, value, "list")
        return [_convert(item, f"{path}[{index}]", notes) for index, item in enumerate(value)]

    if isinstance(value, (set, frozenset)):
        # 집합은 순서가 없다. 정렬해야 덤프가 결정론적이다.
        _record(notes, path, value, "list (sorted)")
        items = sorted(value, key=repr)
        return [_convert(item, f"{path}[{index}]", notes) for index, item in enumerate(items)]

    if isinstance(value, (datetime, date, time)):
        _record(notes, path, value, "str (ISO 8601)")
        return value.isoformat()

    if isinstance(value, Decimal):
        # float 변환은 값을 바꾼다. 문자열이 원형을 보존한다.
        _record(notes, path, value, "str (10진 원형 보존)")
        return str(value)

    if isinstance(value, (Path, PurePath)):
        _record(notes, path, value, "str")
        return str(value)

    if isinstance(value, (bytes, bytearray)):
        _record(notes, path, value, "str (latin-1 escape)")
        return value.decode("latin-1")

    # numpy 등 __module__로만 식별되는 스칼라/배열 — 선택적 의존성이라 지연 처리한다.
    numpy_converted = _convert_numpy(value, path, notes)
    if numpy_converted is not _NOT_NUMPY:
        return numpy_converted

    # 모르는 타입 — 추측해서 str()로 뭉개지 않고 표식을 남긴다.
    _record(notes, path, value, f"{UNSERIALIZABLE_MARKER} 표식")
    return {
        UNSERIALIZABLE_MARKER: {
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "repr": repr(value)[:200],
        }
    }


_NOT_NUMPY = object()


def _convert_numpy(value: Any, path: str, notes: list[dict]) -> Any:
    if type(value).__module__.split(".")[0] != "numpy":
        return _NOT_NUMPY
    if hasattr(value, "tolist"):
        converted = value.tolist()
        _record(notes, path, value, "tolist()")
        return _convert(converted, path, notes)
    return _NOT_NUMPY


def serialize_state(state: dict) -> dict:
    """state를 JSON 안전한 dict로 바꾸고 `_serialization_notes`를 덧붙인다."""
    notes: list[dict] = []
    converted = _convert(dict(state), "state", notes)
    # 리스트는 sort_keys=True로도 정렬되지 않는다. 순회 순서에 기대면 내용이 같아도
    # dict 삽입 순서가 달라질 때 덤프 바이트가 흔들려 재현 대조가 무의미해진다.
    notes.sort(key=lambda note: (note["path"], note["converted_to"]))
    converted[SERIALIZATION_NOTES_KEY] = {
        "converted": bool(notes),
        "conversions": notes,
        "note": (
            "JSON이 표현하지 못하는 타입을 바꾼 내역이다. 비어 있으면 state가 "
            "원형 그대로 실렸다는 뜻이다."
        ),
    }
    return converted


def dumps_state(state: dict) -> str:
    """결정론적 JSON 문자열. 같은 state면 같은 바이트가 나온다."""
    return json.dumps(
        serialize_state(state),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def dump_state(state: dict, path: Path) -> Path:
    """state를 `path`에 덤프하고 그 경로를 돌려준다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_state(state), encoding="utf-8")
    return path


def canonical_for_replay(dumped: dict) -> dict:
    """재현성 비교용 — 실행마다 달라지는 키를 걷어낸 사본을 돌려준다."""
    stripped = {k: v for k, v in dumped.items() if k not in NONDETERMINISTIC_TOP_LEVEL_KEYS}
    stripped.pop(SERIALIZATION_NOTES_KEY, None)
    return stripped
