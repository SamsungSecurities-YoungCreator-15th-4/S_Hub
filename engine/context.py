"""계산 컨텍스트 — 한 실행의 '어떤 조건에서 계산했나'를 한 곳에 묶는다.

왜 필요한가
-----------
`as_of_date` 는 10개 파일에 64회 등장하고, 각 노드가 `run_config` 에서 각자 꺼내
쓴다. 동작에는 문제가 없지만 **새 값을 붙일 때 조용히 빠진다.**

실제로 빠져 있었다 — `rf_annual = 0.0325` 는 실데이터 경로에서 `cash` 수익률
계산에 쓰이는데(`returns.py:173`), `metrics.meta` 에는 기록되지 않았다.
`base_currency`·`seed`·`data_source`·`fx_rate_asof` 는 있는데 이것만 없었다.
누가 뺀 게 아니라 meta 딕셔너리를 손으로 채우는 구조라 잊으면 그냥 빠진다.

9월 과제 요구가 이것이다.

    중요 숫자마다 기준일(as-of)·출처·통화를 달고,
    화면과 PDF 내용이 어긋나지 않을 것

값마다 손으로 붙이면 하나라도 빠질 때 조용히 틀린다. 컨텍스트에 넣으면
**빠뜨릴 수가 없는 구조**가 된다.

범위 — 축소판이다
-----------------
기존 7개 노드는 건드리지 않는다. 지금은 **결과에 기록을 붙이는 것**만 한다.
`computation_hash` 의 payload 에는 넣지 않으므로 **해시가 바뀌지 않는다.**
전면 전환(모든 노드가 컨텍스트에서 읽기)은 9/11 이후로 미룬다.

설계 결정 — contextvars 가 아니라 명시적 전달
---------------------------------------------
`with 계산컨텍스트(...)` 형태의 암묵적 전파가 코드는 짧지만, 감사에서
"이 값이 어디서 왔나"를 추적하기 어렵다. 우리 시스템은 설명가능성이 강점이므로
**인자로 명시적으로 넘긴다.** `run_config` 를 이미 넘기고 있어 비용도 작다.
"""
from __future__ import annotations

import hashlib
import pathlib
import sqlite3
from dataclasses import dataclass, replace

# config.yaml 의 rf_rate 기본값과 동일. returns.DEFAULT_RF_ANNUAL 과 같은 값이지만
# 순환 import 를 피하려고 여기서 참조하지 않는다 — 불일치는 테스트가 잡는다.
_CHROMA_DB = pathlib.Path(__file__).resolve().parents[1] / "data" / "chroma" / "chroma.sqlite3"


def rag_index_fingerprint(db_path: pathlib.Path | str | None = None) -> str | None:
    """활성 검색 인덱스의 지문. 없거나 읽을 수 없으면 None.

    왜 인덱스까지 기록하는가 — 실제로 재현 대조를 깨뜨린 적이 있다.
    2026-08-06 검색 인덱스를 v3 에서 v4 로 교체했을 때, 코드·설정·시드가 모두
    그대로인데도 `prompt_hash.rag_cite` 가 이전 실행과 어긋났다. 인용으로 뽑히는
    문단이 달라졌기 때문이다. **인덱스는 코드가 아니지만 결과를 바꾼다.**
    그래서 계산 환경의 일부로 보고 실행마다 지문을 남긴다. 이 값이 다르면
    "같은 코드인데 왜 다르지"를 인덱스부터 의심할 수 있다.

    지문은 `embeddings_queue` 의 id 순 상위 3행을 sha256 한 앞 16자다. 같은 규칙으로
    셸에서 뽑으면 이 값과 직접 대조할 수 있다. 표준 라이브러리만 쓴다(chroma 를
    import 하지 않는다) — 이 모듈은 결정론 계층이라 무거운 의존을 들이지 않는다.
    """
    db = pathlib.Path(db_path) if db_path is not None else _CHROMA_DB
    if not db.exists():
        return None
    try:
        rows = sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
            "select id, vector from embeddings_queue order by id limit 3"
        ).fetchall()
    except Exception:
        # 인덱스를 못 읽는 것이 계산을 막을 이유는 아니다. 기록만 비운다.
        return None
    return hashlib.sha256(repr(rows).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class CalcContext:
    """한 실행의 계산 조건. 불변이다 — 중간에 바뀌면 같은 실행이 아니다."""

    as_of: str | None
    currency: str = "KRW"
    data_source: str = "real"
    seed: int = 42

    # 무위험수익률은 **실데이터 경로에서만** cash 수익률에 쓰인다(returns.py:173).
    # 더미 경로는 _DUMMY_VOL["cash"] 를 쓰므로 rf 가 결과에 개입하지 않는다.
    # 안 쓰인 값을 쓴 것처럼 기록하면 그 자체가 위조정밀도다 — rf_applied 로 구분한다.
    rf_annual: float | None = None
    rf_applied: bool = False
    rf_source: str | None = None

    # 검색 인덱스 지문. 인덱스 교체가 인용 결과를 바꾼 사례가 있어 함께 남긴다
    # (rag_index_fingerprint 참고). 인용이 관여하지 않는 계산에서는 None 이어도 된다.
    rag_index: str | None = None

    @classmethod
    def from_run_config(
        cls,
        run_config: dict | None,
        *,
        rf_annual: float | None = None,
        rf_applied: bool = False,
        rag_index: str | None = None,
    ) -> "CalcContext":
        """`run_config` 에서 계산 조건을 모은다.

        rf_annual 은 호출자가 **실제로 엔진에 넘긴 값**을 준다. run_config 에서
        직접 읽지 않는 이유는, 설정에 값이 있어도 경로에 따라 안 쓰일 수 있기
        때문이다. '설정에 있는 값'이 아니라 '계산에 쓰인 값'을 기록한다.
        """
        cfg = run_config or {}
        return cls(
            as_of=cfg.get("as_of_date"),
            currency=cfg.get("base_currency", "KRW"),
            data_source=cfg.get("data_source", "real"),
            seed=cfg.get("seed", 42),
            rf_annual=rf_annual,
            rf_applied=rf_applied,
            rf_source="config.yaml:rf_rate" if rf_annual is not None else None,
            rag_index=rag_index,
        )

    def with_rag_index(self, fingerprint: str | None = None) -> "CalcContext":
        """검색 인덱스 지문을 채운 새 컨텍스트. 인자가 없으면 현재 인덱스에서 읽는다."""
        return replace(
            self,
            rag_index=fingerprint if fingerprint is not None else rag_index_fingerprint(),
        )

    def as_meta(self) -> dict:
        """결과에 실을 기록.

        ⚠️ 이 값은 `computation_hash` 의 payload 에 **넣지 않는다.** 넣으면 해시가
        바뀌어 기존 실행과 대조가 끊긴다. 여기는 '무엇으로 계산했나'를 남기는
        자리이지 계산 입력을 바꾸는 자리가 아니다.
        """
        return {
            "as_of": self.as_of,
            "currency": self.currency,
            "data_source": self.data_source,
            "seed": self.seed,
            "rf_annual": self.rf_annual,
            "rf_applied": self.rf_applied,
            "rf_source": self.rf_source,
            "rag_index": self.rag_index,
        }

    def describe(self) -> str:
        """감사 질문에 한 줄로 답하기 위한 사람이 읽는 요약."""
        parts = [
            f"기준일 {self.as_of or '미지정'}",
            self.currency,
            f"데이터 {self.data_source}",
            f"시드 {self.seed}",
        ]
        if self.rf_applied and self.rf_annual is not None:
            parts.append(f"무위험수익률 {self.rf_annual:.4%}")
        else:
            parts.append("무위험수익률 미적용")
        if self.rag_index:
            parts.append(f"검색인덱스 {self.rag_index}")
        return " · ".join(parts)
