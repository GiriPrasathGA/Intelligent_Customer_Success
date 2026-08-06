"""
novaTech — LangGraph Multi-Agent State Machine

Implements the agent orchestration graph using LangGraph:
User Message → Supervisor Routing → Specialist Agent → RAG → LLM → Response
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, AsyncIterator, TypedDict

from langgraph.graph import StateGraph, END

from backend.agents.supervisor import supervisor_route
from backend.agents.product_agent import product_agent_respond
from backend.agents.order_agent import order_agent_respond
from backend.agents.billing_agent import billing_agent_respond
from backend.agents.warranty_agent import warranty_agent_respond
from backend.agents.account_agent import account_agent_respond
from backend.agents.support_agent import support_agent_respond
from backend.agents.human_agent import human_agent_respond
from backend.rag.rag_pipeline import query_knowledge_base
from backend.config.settings import SUGGESTED_QUESTIONS_COUNT

logger = logging.getLogger(__name__)


# ── State Definition ──────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """State passed between nodes in the LangGraph pipeline."""
    # Input
    user_message: str
    conversation_id: str
    conversation_history: list[dict[str, str]]
    user_id: int

    # Routing
    routed_agent: str

    # RAG
    rag_context: str
    sources: list[dict[str, Any]]

    # Output
    response: str
    agent_used: str
    suggested_questions: list[str]
    escalated: bool
    error: str


# ── Graph Nodes ───────────────────────────────────────────────────────────────

async def supervisor_node(state: AgentState) -> AgentState:
    """Route the message to the appropriate specialist agent."""
    try:
        agent = await supervisor_route(
            message=state["user_message"],
            conversation_history=state["conversation_history"],
        )
        return {**state, "routed_agent": agent}
    except Exception as e:
        logger.error("Supervisor node error: %s", e)
        return {**state, "routed_agent": "support_agent"}


async def rag_node(state: AgentState) -> AgentState:
    """Retrieve relevant knowledge base context for the query."""
    try:
        result = await query_knowledge_base(
            query=state["user_message"],
            agent_type=state.get("routed_agent"),
        )
        return {
            **state,
            "rag_context": result["context"],
            "sources": result["sources"],
        }
    except Exception as e:
        logger.error("RAG node error: %s", e)
        return {**state, "rag_context": "", "sources": []}


async def product_node(state: AgentState) -> AgentState:
    result = await product_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result, "escalated": False}


async def order_node(state: AgentState) -> AgentState:
    result = await order_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result, "escalated": False}


async def billing_node(state: AgentState) -> AgentState:
    result = await billing_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result, "escalated": False}


async def warranty_node(state: AgentState) -> AgentState:
    result = await warranty_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result, "escalated": False}


async def account_node(state: AgentState) -> AgentState:
    result = await account_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result, "escalated": False}


async def support_node(state: AgentState) -> AgentState:
    result = await support_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result, "escalated": False}


async def human_node(state: AgentState) -> AgentState:
    result = await human_agent_respond(
        message=state["user_message"],
        context=state.get("rag_context", ""),
        conversation_history=state["conversation_history"],
    )
    return {**state, **result}


# ── Routing Logic ─────────────────────────────────────────────────────────────

def route_to_agent(state: AgentState) -> str:
    """LangGraph conditional edge: route based on supervisor decision."""
    agent = state.get("routed_agent", "support_agent")
    agent_to_node = {
        "product_agent": "product",
        "order_agent": "order",
        "billing_agent": "billing",
        "warranty_agent": "warranty",
        "account_agent": "account",
        "support_agent": "support",
        "human_agent": "human",
    }
    return agent_to_node.get(agent, "support")


# ── Graph Construction ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent state machine."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("rag", rag_node)
    graph.add_node("product", product_node)
    graph.add_node("order", order_node)
    graph.add_node("billing", billing_node)
    graph.add_node("warranty", warranty_node)
    graph.add_node("account", account_node)
    graph.add_node("support", support_node)
    graph.add_node("human", human_node)

    # Set entry point
    graph.set_entry_point("supervisor")

    # Supervisor → RAG (always retrieve context after routing)
    graph.add_edge("supervisor", "rag")

    # RAG → Conditional routing to specialist agent
    graph.add_conditional_edges(
        "rag",
        route_to_agent,
        {
            "product": "product",
            "order": "order",
            "billing": "billing",
            "warranty": "warranty",
            "account": "account",
            "support": "support",
            "human": "human",
        },
    )

    # All specialist agents → END
    for node in ["product", "order", "billing", "warranty", "account", "support", "human"]:
        graph.add_edge(node, END)

    return graph.compile()


# Module-level compiled graph
_compiled_graph = None


def get_graph():
    """Return the compiled LangGraph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ── Main Chat Interface ───────────────────────────────────────────────────────

async def process_chat(
    message: str,
    conversation_history: list[dict[str, str]],
    conversation_id: str,
    user_id: int,
) -> dict[str, Any]:
    """
    Process a chat message through the full LangGraph pipeline.

    Args:
        message: User's message text.
        conversation_history: Previous messages in format [{"role": ..., "content": ...}]
        conversation_id: Unique identifier for the conversation.
        user_id: Authenticated user's ID.

    Returns:
        Dict with response, agent_used, sources, suggested_questions, escalated.
    """
    graph = get_graph()

    initial_state: AgentState = {
        "user_message": message,
        "conversation_id": conversation_id,
        "conversation_history": conversation_history,
        "user_id": user_id,
        "routed_agent": "",
        "rag_context": "",
        "sources": [],
        "response": "",
        "agent_used": "",
        "suggested_questions": [],
        "escalated": False,
        "error": "",
    }

    try:
        final_state = await graph.ainvoke(initial_state)

        return {
            "response": final_state.get("response", "I apologize, I couldn't process your request. Please try again."),
            "agent_used": final_state.get("agent_used", ""),
            "sources": final_state.get("sources", []),
            "suggested_questions": final_state.get("suggested_questions", [])[:SUGGESTED_QUESTIONS_COUNT],
            "escalated": final_state.get("escalated", False),
        }

    except Exception as e:
        logger.error("Graph processing error: %s", str(e))
        return {
            "response": (
                "I'm sorry, I'm having trouble retrieving a response right now. "
                "Please try again in a moment, or contact us at **1800-NOVACART-HELP** "
                "or **support@novacart.com**."
            ),
            "agent_used": "error",
            "sources": [],
            "suggested_questions": ["How can I contact support?"],
            "escalated": False,
        }
