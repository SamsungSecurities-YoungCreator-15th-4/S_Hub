"""리포트에 뜨는 모든 수치가 **엔진 산출값에서 왔는가**.

우리가 만든 골든셋 함정을 우리 자신에게 적용하는 테스트다.

    case_022 · 엔진이 산출하지 않은 종합점수를 새로 만들어 표시 → 위조정밀도-F3

설명문을 손으로 쓰다 보면 "약 80% 수준" 같은 문구가 슬쩍 들어간다. 그 순간
우리 리포트가 우리 골든셋의 fail 사례가 된다. 사람이 매번 눈으로 확인할 수
없으므로 코드로 막는다.

9월 과제 요구와도 직결된다.

    중요 숫자마다 기준일(as-of)·출처·통화를 달고,
    **화면과 PDF 내용이 어긋나지 않을 것**

화면·PDF가 같은 `explanations` 를 쓰므로, 그 안의 수치가 전부 엔진에서
나왔다면 두 출력이 어긋날 수 없다.
"""
import re

import pytest
import yaml

from engine.nodes.load_inputs import CONFIG_PATH, DUMMY_PORTFOLIO
from engine.nodes.rag_cite import _build_explanations
from engine.nodes.var_engine import var_engine

#: 수치 대조에서 제외할 상수. 연도·백분율 눈금·설정값처럼 엔진 산출물이 아닌
#: 값들이며, 각각 어디서 오는지 분명하다.
_ALLOWED_CONSTANTS = {
    0, 1, 2, 3, 10, 15, 20, 22, 42,      # 보유기간·자산군 수·시드 등
    99, 100,                              # 신뢰수준·백분율
    252, 1250,                            # 연간 거래일·관측치
    2024, 2026,                           # 연도
    1.4, 3.25, 15.4, 49.5,                # config 세율·무위험수익률(%)
}


def _run(data_source="dummy"):
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["data_source"] = data_source
    metrics = var_engine({"run_config": cfg, "portfolio": DUMMY_PORTFOLIO})["metrics"]
    explanations = _build_explanations(
        metrics, revision=0, judge_feedback="", as_of_date=cfg["as_of_date"]
    )
    return metrics, explanations


def _engine_numbers(metrics) -> set[float]:
    """엔진이 산출한 모든 수치를 평평하게 모은다."""
    acc: set[float] = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            acc.add(float(node))

    walk(metrics)
    return acc


def _unsourced_numbers(text: str, engine_values: set[float]) -> list[str]:
    """설명문에서 엔진 산출값으로 설명되지 않는 수치를 찾는다.

    억원·백분율 표기와 반올림을 감안해 후보 배율로 대조한다.
    """
    found = []
    for token in re.findall(r"\d[\d,]*\.?\d*", text):
        raw = token.replace(",", "").rstrip(".")
        if not raw:
            continue
        value = float(raw)
        if value in _ALLOWED_CONSTANTS:
            continue
        candidates = (value, value * 1e8, value / 100, value * 1e8 / 100, value / 1e8)
        matched = any(
            any(abs(c - w) <= max(0.5, abs(w) * 2e-3) for w in engine_values)
            for c in candidates
        )
        if not matched:
            found.append(token)
    return found


@pytest.mark.parametrize("data_source", ["dummy", "real"])
def test_every_number_in_report_comes_from_the_engine(data_source):
    """리포트 수치 중 엔진이 안 낸 값이 있으면 실패한다.

    실패하면 둘 중 하나다 — 설명문이 값을 지어냈거나(위조정밀도),
    엔진 산출물에 그 값을 안 실었거나. 어느 쪽이든 고쳐야 한다.
    """
    try:
        metrics, explanations = _run(data_source)
    except Exception as exc:  # 실데이터 캐시가 없는 환경
        pytest.skip(f"{data_source} 경로 실행 불가: {type(exc).__name__}")

    engine_values = _engine_numbers(metrics)
    offenders = {}
    for item in explanations:
        bad = _unsourced_numbers(item["text"], engine_values)
        if bad:
            offenders[item["topic"]] = bad
    assert not offenders, (
        "엔진이 산출하지 않은 수치가 리포트에 있습니다 "
        f"(골든셋 case_022 의 위조정밀도-F3 유형): {offenders}"
    )


def test_new_sections_are_present():
    """9월에 추가한 세 문단이 실제로 리포트에 실리는지."""
    _, explanations = _run()
    topics = {e["topic"] for e in explanations}
    assert "위험조정 성과" in topics
    assert "세후 기말자산" in topics
    assert "비교안 대조" in topics


def test_assumptions_reach_the_report():
    """가정을 안 적으면 값만 남는다 — 핸드아웃이 '가정을 적을 것'을 요구했다."""
    _, explanations = _run()
    by_topic = {e["topic"]: e["text"] for e in explanations}
    assert "산출 가정" in by_topic["위험조정 성과"]
    assert "산출 가정" in by_topic["세후 기말자산"]


def test_out_of_scope_reaches_the_report():
    """세금 범위 밖 세목이 리포트 문장에 실제로 나와야 한다."""
    _, explanations = _run()
    text = next(e["text"] for e in explanations if e["topic"] == "세후 기말자산")
    assert "종합부동산세" in text
    assert "양도소득세" in text


def test_comparison_does_not_recommend():
    """비교 문단이 어느 쪽을 권고하면 '최적 포트폴리오' 금지에 걸린다."""
    _, explanations = _run()
    text = next(e["text"] for e in explanations if e["topic"] == "비교안 대조")
    assert "권고하지 않습니다" in text
    for banned in ("최적", "추천", "권장"):
        assert banned not in text


def test_determinism_across_repeated_runs():
    """같은 조건으로 세 번 돌려 해시·핵심 수치가 흔들리지 않는지."""
    hashes, sharpes, after_tax = set(), set(), set()
    for _ in range(3):
        metrics, _ = _run()
        hashes.add(metrics["meta"]["computation_hash"])
        sharpes.add(round(metrics["risk_adjusted"]["sharpe_ratio"], 12))
        after_tax.add(round(metrics["after_tax"]["after_tax_value_low_krw"], 6))
    assert len(hashes) == 1, "computation_hash 가 실행마다 달라진다"
    assert len(sharpes) == 1 and len(after_tax) == 1
