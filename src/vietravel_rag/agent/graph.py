"""LangGraph orchestration for guarded, cited tour answers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from vietravel_rag.agent.nodes import (
    analyze_query,
    conflict_guard,
    direct_response_node,
    generate_answer,
    input_guard_node,
    output_guard_node,
    prepare_evidence,
    resolve_tour_node,
    retrieve_node,
)
from vietravel_rag.models import AgentState


def _get(deps: Any, name: str, default=None):
    return deps.get(name, default) if isinstance(deps, Mapping) else getattr(deps, name, default)


def _load_records(value, default_path: str) -> list[dict]:
    if value is None:
        path = Path(default_path)
        if not path.exists():
            return []
        value = path
    if isinstance(value, (str, Path)):
        return json.loads(Path(value).read_text(encoding="utf-8"))
    return list(value)


def build_graph(deps) -> Any:
    """Build the complete guarded graph from injected model and retrieval dependencies.

    ``deps`` accepts ``model``, ``resolver``, and ``retriever`` plus optional
    ``conflicts`` and ``sales_guidance`` values or paths. The in-memory saver
    isolates conversations by the ``thread_id`` supplied at invocation time.
    """
    model = _get(deps, "model") or _get(deps, "llm")
    resolver = _get(deps, "resolver")
    retriever = _get(deps, "retriever")
    if model is None or resolver is None or retriever is None:
        raise ValueError("build_graph requires model, resolver, and retriever dependencies")
    conflicts = _load_records(
        _get(deps, "conflicts"), "data/processed/conflicts.json"
    )
    guidance = _load_records(
        _get(deps, "sales_guidance"), "data/processed/sales_guidance.json"
    )

    def query_analysis_node(state: AgentState) -> dict:
        update = analyze_query(state, model)
        update["query_analysis"] = update["query_analysis"].model_dump()
        return update

    workflow = StateGraph(AgentState)
    workflow.add_node("input_guard", input_guard_node)
    workflow.add_node("query_analysis", query_analysis_node)
    workflow.add_node("tour_resolver", lambda state: resolve_tour_node(state, resolver))
    workflow.add_node("retrieval", lambda state: retrieve_node(state, retriever))
    workflow.add_node("conflict_guard", lambda state: conflict_guard(state, conflicts))
    workflow.add_node("evidence_preparation", prepare_evidence)
    workflow.add_node(
        "response_generation",
        lambda state: {
            "sales_guidance": guidance,
            **generate_answer({**state, "sales_guidance": guidance}, model),
        },
    )
    workflow.add_node("output_guard", output_guard_node)
    workflow.add_node("direct_response", direct_response_node)

    workflow.add_edge(START, "input_guard")
    workflow.add_conditional_edges(
        "input_guard",
        lambda state: "continue" if state.get("input_decision") == "continue" else "finish",
        {"continue": "query_analysis", "finish": "direct_response"},
    )
    workflow.add_edge("query_analysis", "tour_resolver")
    workflow.add_conditional_edges(
        "tour_resolver",
        lambda state: "retrieve" if state.get("route") == "retrieve" else "finish",
        {"retrieve": "retrieval", "finish": "direct_response"},
    )
    workflow.add_edge("retrieval", "conflict_guard")
    workflow.add_edge("conflict_guard", "evidence_preparation")
    workflow.add_edge("evidence_preparation", "response_generation")
    workflow.add_edge("response_generation", "output_guard")
    workflow.add_edge("output_guard", END)
    workflow.add_edge("direct_response", END)
    return workflow.compile(checkpointer=MemorySaver())


def invoke_turn(graph, message, session_id: str, *, history: list | None = None) -> dict:
    """Invoke one user turn in a session-scoped checkpoint thread."""
    from langchain_core.messages import AIMessage, HumanMessage

    current = message if hasattr(message, "content") else HumanMessage(content=str(message))
    conversation = list(history or [])
    if history is None:
        config = {"configurable": {"thread_id": session_id}}
        previous = graph.get_state(config).values
        conversation = list(previous.get("messages", []))
        response = previous.get("response") or {}
        if response.get("answer"):
            conversation.append(AIMessage(content=str(response["answer"])))
    messages = [*conversation, current][-10:]
    return graph.invoke(
        {"messages": messages},
        {"configurable": {"thread_id": session_id}},
    )
