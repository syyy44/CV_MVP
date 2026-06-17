from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.core.errors import RunCancelledError
from app.locale import zh_CN as msg
from app.storage import repository
from app.workflows.nodes import (
    aggregate_node,
    assemble_node,
    extract_rubric_node,
    ingest_node,
    new_candidate_id,
    profile_node,
    questions_node,
    score_node,
)
from app.workflows.state import CandidateState, RunGraphState


def _route(next_node: str):
    def router(state: CandidateState) -> str:
        return "assemble" if state.get("halt") else next_node

    return router


def build_candidate_graph():
    graph = StateGraph(CandidateState)
    graph.add_node("extract_profile", profile_node)
    graph.add_node("score", score_node)
    graph.add_node("interview_pack", questions_node)
    graph.add_node("assemble", assemble_node)

    graph.add_edge(START, "extract_profile")
    graph.add_conditional_edges(
        "extract_profile", _route("score"), {"score": "score", "assemble": "assemble"}
    )
    graph.add_conditional_edges(
        "score",
        _route("interview_pack"),
        {"interview_pack": "interview_pack", "assemble": "assemble"},
    )
    graph.add_edge("interview_pack", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()


_candidate_graph = None


def candidate_graph():
    global _candidate_graph
    if _candidate_graph is None:
        _candidate_graph = build_candidate_graph()
    return _candidate_graph


def fan_out(state: RunGraphState):
    if repository.is_run_cancelled(state["ctx"].run_id):
        raise RunCancelledError(msg.run_cancelled_by_user())
    resumes = state.get("resume_docs", [])
    if not resumes:
        return "aggregate"
    return [
        Send(
            "process_candidate",
            {
                "ctx": state["ctx"],
                "rubric": state["rubric"],
                "jd_doc": state["jd_doc"],
                "resume_doc": doc,
                "candidate_id": new_candidate_id(),
                "slug": doc["slug"],
            },
        )
        for doc in resumes
    ]


def process_candidate_node(state: CandidateState) -> dict:
    ctx = state["ctx"]
    if repository.is_run_cancelled(ctx.run_id):
        raise RunCancelledError(msg.run_cancelled_by_user())
    resume_doc = state["resume_doc"]
    ctx.ledger.emit(
        "candidate_started",
        node_name="process_candidate",
        candidate_id=state["candidate_id"],
        metadata={
            "filename": resume_doc["filename"],
            "document_id": resume_doc["document_id"],
            "slug": state["slug"],
        },
    )
    red_team = state["slug"] in ctx.red_team_slugs
    with ctx.tracer.candidate_scope(
        ctx.run_id,
        state["slug"],
        mode=ctx.mode,
        red_team=red_team,
    ) as candidate_span:
        candidate_trace_id = getattr(candidate_span, "trace_id", None)
        branch_state = {
            **state,
            "candidate_trace_id": str(candidate_trace_id) if candidate_trace_id else None,
        }
        output = candidate_graph().invoke(branch_state)
    return {"candidate_results": [output["result"]]}


def build_run_graph():
    graph = StateGraph(RunGraphState)
    graph.add_node("ingest_files", ingest_node)
    graph.add_node("extract_jd_rubric", extract_rubric_node)
    graph.add_node("process_candidate", process_candidate_node)
    graph.add_node("aggregate", aggregate_node)

    graph.add_edge(START, "ingest_files")
    graph.add_edge("ingest_files", "extract_jd_rubric")
    graph.add_conditional_edges(
        "extract_jd_rubric",
        fan_out,
        ["process_candidate", "aggregate"],
    )
    graph.add_edge("process_candidate", "aggregate")
    graph.add_edge("aggregate", END)
    return graph.compile()
