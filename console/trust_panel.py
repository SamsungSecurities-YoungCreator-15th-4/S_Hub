"""judge 신뢰 지표 전용 패널 (streamlit 렌더).

9월 과제 요구:

    이 신뢰 지표가 폴더 깊숙이만 있지 않고, Hub 화면 또는 **전용 패널**에서
    팀·리뷰어가 볼 수 있을 것

계산·집계는 전부 `console.trust_metrics`(순수 함수)에 있고 이 모듈은 그리기만 한다.
`start_page.py` 와 같은 분리 방식이다.

사용:
    from console.trust_panel import render_trust_panel
    render_trust_panel()

패널의 성격 — 핸드아웃이 이렇게 적었다.

    "100% 일치" 과신보다, 불일치를 정직하게 분석한 쪽이 이 과제 취지에 맞다

그래서 큰 숫자 하나를 띄우지 않는다. 미탐·오탐을 나누고, 어긋난 사례를
이름으로 부르고, 추이가 **나빠진 구간까지** 그대로 보여준다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from console.trust_metrics import (
    axis_rows,
    confusion_rows,
    load_human_labels,
    load_version_trend,
    mismatch_rows,
    split_frozen_and_added,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "goldenset" / "reports" / "r2_calibration"
CASES_DIR = ROOT / "goldenset" / "cases"
RUNS_DIR = ROOT / "docs" / "engine" / "r2_calibration_runs"


@st.cache_data(show_spinner=False)
def _latest_summary() -> tuple[str | None, dict]:
    """가장 최신 비교 요약과 그 버전 이름."""
    trend = load_version_trend(REPORTS_DIR)   # 이 함수 자체가 캐시된다
    if not trend:
        return None, {}
    latest = trend[-1]["version"]
    for path in sorted(REPORTS_DIR.glob("*_compare_summary.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (payload.get("v2") or {}).get("prompt_version") == latest:
            return latest, payload
    return latest, {}


@st.cache_data(show_spinner=False)
def _latest_case_results() -> list:
    """가장 최신 사례별 판정 기록."""
    candidates = sorted(RUNS_DIR.glob("judge_v*_results.json"))
    if not candidates:
        return []
    try:
        return json.loads(candidates[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


@st.cache_data(show_spinner=False)
def _cached_trend() -> list:
    return load_version_trend(REPORTS_DIR)


@st.cache_data(show_spinner=False)
def _cached_labels() -> dict:
    return load_human_labels(CASES_DIR)


def render_trust_panel() -> None:
    """신뢰 지표 패널 전체를 그린다."""
    version, summary = _latest_summary()
    if version is None:
        st.info("아직 judge 캘리브레이션 기록이 없습니다.")
        return

    st.caption(
        f"judge 프롬프트 **{version}** 기준 · 사람 라벨과의 대조 결과입니다. "
        "일치율은 분수로 적습니다 — 20건에서 1건은 5%p 라 퍼센트 표기는 "
        "실제보다 정밀해 보입니다."
    )

    # ── 1. 혼동행렬 ─────────────────────────────────────────────────
    st.markdown("##### 혼동행렬")
    st.dataframe(
        pd.DataFrame(
            [
                {"구분": r["label"], "건수": r["fraction"], "뜻": r["meaning"]}
                for r in confusion_rows(summary.get("v2"))
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "미탐과 오탐은 성격이 다르므로 하나의 '정확도'로 합치지 않습니다. "
        "미탐은 불량이 고객에게 나가는 것이고, 오탐은 멀쩡한 리포트를 막는 것입니다."
    )

    # ── 2. 버전별 추이 ──────────────────────────────────────────────
    st.markdown("##### 프롬프트 버전별 추이")
    trend = _cached_trend()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "버전": r["version"],
                    "일치": r["fraction"],
                    "오탐(FP)": r["false_positive"],
                    "미탐(FN)": r["false_negative"],
                }
                for r in trend
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if len(trend) >= 2:
        first, last = trend[0], trend[-1]
        worst = min(trend, key=lambda r: (r["match"] if isinstance(r["match"], int) else 99))
        st.caption(
            f"{first['version']} {first['fraction']} → {last['version']} {last['fraction']}. "
            f"중간에 {worst['version']} 에서 {worst['fraction']} 까지 떨어진 구간이 있습니다. "
            "단조 개선이 아니었다는 사실을 그대로 둡니다."
        )

    # ── 3. 축별 ────────────────────────────────────────────────────
    st.markdown("##### 6축별 대조")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "축": r["axis_ko"],
                    "일치": r["fraction"],
                    "오탐": r["false_positive"],
                    "미탐": r["false_negative"],
                    "사람 fail 건수": r["human_fail_support"],
                }
                for r in axis_rows(summary)
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "**사람 fail 건수**는 그 축의 근거 표본 수입니다. 이 값이 2~3건이면 "
        "일치 20/20 이라도 '그 축을 잘 잡는다'고 단정하기 어렵습니다."
    )

    # ── 4. 어긋난 사례 ─────────────────────────────────────────────
    st.markdown("##### 어긋난 사례")
    labels = _cached_labels()
    results = _latest_case_results()
    rows = mismatch_rows(results, labels)
    if not rows:
        st.caption("어긋난 사례가 없습니다.")
    else:
        for r in rows:
            st.markdown(
                f"**{r['case_id']}** · {r['kind']} — "
                f"사람 `{r['human_label']}` vs judge `{r['judge_label']}`"
            )
            if r["human_fail_axes"]:
                st.caption(f"사람이 지목한 축: {', '.join(r['human_fail_axes'])}")
            if r["trap_type"] and r["trap_type"] != "none":
                st.caption(f"함정 유형: {r['trap_type']}")
            if r["judge_failed_checks"]:
                st.caption(f"judge 가 잡은 검사: {', '.join(r['judge_failed_checks'])}")

    # ── 5. 동결본 / 신규 분리 ───────────────────────────────────────
    split = split_frozen_and_added(results, labels)
    if split["added"]["total"]:
        st.markdown("##### 동결본과 신규 사례")
        st.dataframe(
            pd.DataFrame(
                [
                    {"구분": "동결 20건 (v1-freeze)", **_split_row(split["frozen"])},
                    {"구분": "운영에서 추가된 사례", **_split_row(split["added"])},
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "두 집합을 **섞어서 집계하지 않습니다.** 동결 20건은 프롬프트 "
            "v1↔v7 비교의 기준선이라 구성이 바뀌면 그 비교가 무효가 됩니다."
        )


def _split_row(tally: dict) -> dict:
    return {
        "일치": tally["fraction"],
        "오탐(FP)": tally["false_positive"],
        "미탐(FN)": tally["false_negative"],
    }
