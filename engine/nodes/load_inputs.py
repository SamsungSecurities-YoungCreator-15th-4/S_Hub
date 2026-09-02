"""config.yaml 로드 + 고객 상담/제안 포트폴리오 입력 정규화."""
import math
from pathlib import Path

import yaml

from engine.hard_stop_policy import resolve_hard_stop_policy_version
from engine.state import RiskState
from engine.utils.hashing import sha256_of_dict

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"

# 7자산군 더미 포트폴리오 — 위탁자산 총 50억 원 (고정)
#
#  2026-09 확장: 기존 `alternatives`(대체투자 10%)를 `gold` 6% + `reits` 4% 로 쪼갰다.
#  9월 과제가 "대체자산(금·리츠·원자재·달러 등)을 하나 이상"을 요구했고, 한 덩어리로
#  두면 리포트에 '대체투자'로만 보여 실체가 드러나지 않기 때문이다.
#
#  둘로 나눈 이유는 **스트레스 반응이 반대**라서다 — 고금리 국면에서 금은 상대적으로
#  방어하고 리츠는 금리에 직격당한다. 같은 '대체'가 반대로 움직이는 것이 보여야
#  분산 효과를 숫자로 설명할 수 있다.
#
#  ⚠️ 이 변경으로 computation_hash 가 바뀐다. 8월 제출물과 대조되지 않는다.
#     8월 번들은 그대로 보존하고 9월 기준선을 새로 선언한다.
DUMMY_PORTFOLIO = [
    {"asset_class": "domestic_equity", "name": "국내주식", "value_krw": 1_250_000_000, "weight": 0.25},
    {"asset_class": "global_equity", "name": "해외주식", "value_krw": 1_000_000_000, "weight": 0.20},
    {"asset_class": "domestic_bond", "name": "국내채권", "value_krw": 1_250_000_000, "weight": 0.25},
    {"asset_class": "global_bond", "name": "해외채권", "value_krw": 750_000_000, "weight": 0.15},
    {"asset_class": "gold", "name": "금", "value_krw": 300_000_000, "weight": 0.06},
    {"asset_class": "reits", "name": "리츠", "value_krw": 200_000_000, "weight": 0.04},
    {"asset_class": "cash", "name": "현금성자산", "value_krw": 250_000_000, "weight": 0.05},
]

ASSET_DEFINITIONS = [
    ("domestic_equity", "국내주식"),
    ("global_equity", "해외주식"),
    ("domestic_bond", "국내채권"),
    ("global_bond", "해외채권"),
    ("gold", "금"),
    ("reits", "리츠"),
    ("cash", "현금성자산"),
]

TOTAL_ASSET_KRW = 5_000_000_000

SAMPLE_RAW_INPUT = (
    "고객: 50대 자영업자, 위탁자산 50억 원. 위험성향은 중립적이며, "
    "은퇴까지 약 10년의 투자기간을 상정한다. 최근 고금리·강달러 환경이 "
    "지속되는 상황에서 포트폴리오의 하방 리스크를 점검하고자 한다. "
    "사업 운영상 일부 유동성 확보가 필요할 수 있다."
)


def portfolio_from_percentages(
    percentages: dict[str, float],
    *,
    total_asset_krw: float = TOTAL_ASSET_KRW,
) -> list[dict]:
    """7자산 비중(%)을 정량 엔진의 금액·0~1 비중 계약으로 변환한다."""
    expected = {asset_class for asset_class, _name in ASSET_DEFINITIONS}
    if set(percentages) != expected:
        missing = sorted(expected - set(percentages))
        extra = sorted(set(percentages) - expected)
        raise ValueError(f"포트폴리오 자산군 불일치: missing={missing}, extra={extra}")

    normalized = {key: float(value) for key, value in percentages.items()}
    if any(
        not math.isfinite(value) or value < 0 or value > 100
        for value in normalized.values()
    ):
        raise ValueError(
            "자산별 비중은 0% 이상 100% 이하의 유효한 숫자여야 합니다."
        )
    total_pct = sum(normalized.values())
    if abs(total_pct - 100.0) > 1e-6:
        raise ValueError(f"포트폴리오 비중 합계는 100%여야 합니다: 현재 {total_pct:g}%")

    return [
        {
            "asset_class": asset_class,
            "name": name,
            "value_krw": round(total_asset_krw * normalized[asset_class] / 100.0, 2),
            "weight": normalized[asset_class] / 100.0,
        }
        for asset_class, name in ASSET_DEFINITIONS
    ]


def load_inputs(state: RiskState) -> dict:
    # terminal gate에서 뒤늦게 설정 오류로 중단되지 않도록 그래프 첫 노드에서
    # Hard Stop 정책 파일을 검증한다. 값의 SSOT와 실제 사용은 공용 로더가 맡는다.
    resolve_hard_stop_policy_version()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    run_config = dict(config)
    demo_options = state.get("demo_options") or {}
    if demo_options.get("offline") is True:
        run_config["data_source"] = "dummy"
    run_config["config_hash"] = sha256_of_dict(run_config)
    incoming_run_config = state.get("run_config") or {}
    if isinstance(incoming_run_config, dict):
        observability = incoming_run_config.get("observability")
        if isinstance(observability, dict):
            run_config["observability"] = dict(observability)

    raw_input = state["raw_input"] if "raw_input" in state else SAMPLE_RAW_INPUT
    portfolio = state["portfolio"] if "portfolio" in state else DUMMY_PORTFOLIO

    return {
        "run_config": run_config,
        "trace_id": state.get("trace_id") or f"run-{run_config['config_hash'][:12]}",
        "raw_input": raw_input,
        "portfolio": [dict(item) for item in portfolio],
        "market_data_ref": {
            "source": run_config.get("data_source", "real"),
            "as_of_date": config["as_of_date"],
            "note": (
                "yfinance 실데이터(app.engine.returns.load_real_returns) 연동"
                if run_config.get("data_source", "real") == "real"
                else "고정 수식 더미 데이터(오프라인 개발·테스트용)"
            ),
        },
        "approval": {
            "status": "draft",
            "created_as_of": run_config.get("as_of_date"),
            "scope": "risk_calculation_only",
        },
    }
