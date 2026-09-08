"""Streamlit 시작 시 배포 RAG 인덱스를 준비하고 실패를 명시적으로 중단한다."""
from __future__ import annotations

import logging
import os

import streamlit as st

from engine.rag.deployment import (
    PUBLIC_ERROR_MESSAGE,
    ensure_deployment_index,
    load_index_supply_settings,
)

log = logging.getLogger(__name__)

#: 로컬 화면 열람 전용 스위치. 켜면 RAG 인덱스 준비를 건너뛰고, 엔진에 이미 있는
#: ``demo_options.offline``(engine/nodes/extract_ips.py, load_inputs.py)로 실행한다.
#: 외부 호출이 없으니 인용은 0건이고, judge가 그대로 미통과시켜 리포트는
#: manual_review_gate에서 다운로드가 차단된 채 끝난다 — 확정 계약은 건드리지 않는다.
#: 기본값은 꺼짐이고 배포(Streamlit Cloud secrets)에는 넣지 않는다.
OFFLINE_CONSOLE_ENV = "SYMPHONY_OFFLINE_CONSOLE"
OFFLINE_CONSOLE_NOTICE = (
    "오프라인 열람 모드입니다. 외부 검색·LLM 호출 없이 화면만 확인하는 상태라 "
    "근거 인용이 0건이며, 리포트는 수동검토로 종료되고 다운로드가 차단됩니다."
)


def offline_console_enabled() -> bool:
    """환경 변수로만 켜지는 로컬 열람 모드 여부."""
    return os.environ.get(OFFLINE_CONSOLE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


@st.cache_resource(show_spinner=False)
def _cached_ensure_index(
    index_version: str,
    expected_sha256: str,
    *,
    _settings,
    _ensure_index,
):
    """버전·SHA가 같은 설치본은 프로세스 수명 동안 최초 1회만 검증한다."""
    return _ensure_index(settings=_settings)


def prepare_index_or_stop(st_module, *, ensure_index=None):
    if offline_console_enabled():
        # 인덱스를 준비하지 않고 통과시키되, 어떤 상태의 화면인지 항상 띄운다.
        st_module.warning(OFFLINE_CONSOLE_NOTICE)
        return None
    index_preparer = ensure_index or ensure_deployment_index
    try:
        try:
            secrets = dict(st_module.secrets)
        except Exception:
            secrets = {}
        settings = load_index_supply_settings(secrets)
        with st_module.spinner("분석 근거 및 참고 자료를 확인하고 있습니다..."):
            if ensure_index is not None:
                return index_preparer(settings=settings)
            return _cached_ensure_index(
                settings.expected_version,
                settings.expected_sha256,
                _settings=settings,
                _ensure_index=index_preparer,
            )
    except Exception as exc:
        # SAS URL·토큰이 UI나 로그에 노출되지 않도록 예외 문자열은 출력하지 않는다.
        log.error("RAG index bootstrap failed: %s", type(exc).__name__)
        st_module.error(PUBLIC_ERROR_MESSAGE)
        st_module.stop()
        return None
