"""StateGraph 조립 — 9노드 + 조건부 분기 2개 + HITL 인터럽트."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from engine.nodes.approval_gate import approval_gate
from engine.nodes.assemble_report import assemble_report
from engine.nodes.conflict_check import conflict_check
from engine.nodes.extract_ips import extract_ips
from engine.nodes.judge_eval import judge_eval, resolve_max_judge_retries
from engine.nodes.load_inputs import load_inputs
from engine.nodes.manual_review_gate import manual_review_gate
from engine.nodes.rag_cite import rag_cite
from engine.nodes.var_engine import var_engine
from engine.state import RiskState

MAX_CONFLICT_RETRIES = 1


def route_after_conflict_check(state: RiskState) -> str:
    """분기 ①: 충돌이 있고 재추출 여유가 남아 있으면 extract_ips로 회귀.

    재시도 소진 시에는 충돌을 approval에 첨부한 채 사람 판단(approval_gate)으로 넘긴다.
    """
    conflict_retries = state.get("conflict_retries") or 0
    if state.get("conflicts") and conflict_retries < MAX_CONFLICT_RETRIES:
        return "extract_ips"
    return "approval_gate"


def route_after_judge(state: RiskState) -> str:
    """분기 ③: 통과는 조립, 재시도 여유는 재작성, 소진 실패는 Hard Stop."""
    judge = state.get("judge") or {}
    judge_retries = state.get("judge_retries") or 0
    if judge.get("passed") is True:
        return "assemble_report"
    if judge_retries >= resolve_max_judge_retries(state):
        return "manual_review_gate"
    return "rag_cite"


def build_graph():
    """컴파일된 그래프 반환. ②: approval_gate 직전 인터럽트(HITL) + MemorySaver."""
    g = StateGraph(RiskState)

    g.add_node("load_inputs", load_inputs)
    g.add_node("extract_ips", extract_ips)
    g.add_node("conflict_check", conflict_check)
    g.add_node("approval_gate", approval_gate)
    g.add_node("var_engine", var_engine)
    g.add_node("rag_cite", rag_cite)
    g.add_node("judge_eval", judge_eval)
    g.add_node("manual_review_gate", manual_review_gate)
    g.add_node("assemble_report", assemble_report)

    g.add_edge(START, "load_inputs")
    g.add_edge("load_inputs", "extract_ips")
    g.add_edge("extract_ips", "conflict_check")
    g.add_conditional_edges(
        "conflict_check",
        route_after_conflict_check,
        {"extract_ips": "extract_ips", "approval_gate": "approval_gate"},
    )
    g.add_edge("approval_gate", "var_engine")
    g.add_edge("var_engine", "rag_cite")
    g.add_edge("rag_cite", "judge_eval")
    g.add_conditional_edges(
        "judge_eval",
        route_after_judge,
        {
            "rag_cite": "rag_cite",
            "manual_review_gate": "manual_review_gate",
            "assemble_report": "assemble_report",
        },
    )
    g.add_edge("manual_review_gate", END)
    g.add_edge("assemble_report", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["approval_gate"],
    )
