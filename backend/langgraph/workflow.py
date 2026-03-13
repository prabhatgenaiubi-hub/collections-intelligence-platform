"""
LangGraph Orchestration Workflow

Defines the full agentic pipeline using LangGraph StateGraph.

Workflow sequence:
  1. Context Memory Agent     → fetch customer + loan + interaction context
  2. Collections Intelligence Agent → risk scoring, analytics, strategy
  3. Sentiment Agent          → aggregate sentiment analysis
  4. Policy Guardrail Agent   → validate strategy against policy rules
  5. LLM Reasoning Agent      → generate narrative recommendation + chat response

Each node receives and returns the full shared state dict.
The workflow supports two entry modes:
  - "analysis"  → full pipeline for bank officer loan intelligence
  - "chat"      → context + LLM for customer AI assistant responses
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Any

from backend.agents.context_memory_agent      import run_context_memory_agent
from backend.agents.collections_intelligence_agent import run_collections_intelligence_agent
from backend.agents.sentiment_agent           import run_sentiment_agent
from backend.agents.policy_guardrail_agent    import run_policy_guardrail_agent
from backend.agents.llm_reasoning_agent       import run_llm_reasoning_agent


# ─────────────────────────────────────────────
# Shared State Schema
# ─────────────────────────────────────────────

class WorkflowState(TypedDict, total=False):
    # ── Inputs ────────────────────────────────
    db:                   Any        # SQLAlchemy Session
    customer_id:          str
    loan_id:              Optional[str]
    session_id:           str
    user_query:           str
    mode:                 str        # "analysis" | "chat"

    # ── Customer Profile ──────────────────────
    customer_profile:     dict
    loans:                list
    payment_history:      list
    interactions:         list
    recent_messages:      list
    vector_memories:      list
    context:              dict

    # ── Loan Attributes (passed through) ──────
    days_past_due:        int
    credit_score:         int
    monthly_income:       float
    emi_amount:           float
    outstanding_balance:  float
    preferred_channel:    str

    # ── Analytics Outputs ─────────────────────
    risk_segment:         str
    self_cure_probability: float
    value_at_risk:        float
    delinquency_score:    int
    payment_trend:        dict
    recovery_strategy:    dict
    recommended_channel:  str
    npv_result:           dict
    strategy_comparison:  list

    # ── Sentiment Outputs ─────────────────────
    sentiment_summary:    dict

    # ── Policy Outputs ────────────────────────
    policy_validation:    dict

    # ── LLM Outputs ───────────────────────────
    llm_recommendation:   str
    llm_response:         str

    # ── Outreach ──────────────────────────────
    outreach_result:      dict


# ─────────────────────────────────────────────
# Conditional Router
# ─────────────────────────────────────────────

def route_after_context(state: WorkflowState) -> str:
    """
    Route to appropriate next node based on workflow mode.

    "chat"     → skip analytics, go directly to LLM
    "analysis" → run full analytics pipeline
    """
    mode = state.get("mode", "analysis")
    if mode == "chat":
        return "llm_reasoning"
    return "collections_intelligence"


# ─────────────────────────────────────────────
# Build Full Analysis Workflow
# ─────────────────────────────────────────────

def build_analysis_workflow() -> StateGraph:
    """
    Build the full LangGraph workflow for loan intelligence analysis.

    Pipeline:
        context_memory
            ↓
        collections_intelligence
            ↓
        sentiment
            ↓
        policy_guardrail
            ↓
        llm_reasoning
            ↓
           END
    """
    graph = StateGraph(WorkflowState)

    # ── Register Nodes ────────────────────────────────────────────
    graph.add_node("context_memory",           run_context_memory_agent)
    graph.add_node("collections_intelligence", run_collections_intelligence_agent)
    graph.add_node("sentiment",                run_sentiment_agent)
    graph.add_node("policy_guardrail",         run_policy_guardrail_agent)
    graph.add_node("llm_reasoning",            run_llm_reasoning_agent)

    # ── Entry Point ───────────────────────────────────────────────
    graph.set_entry_point("context_memory")

    # ── Conditional Routing after context ─────────────────────────
    graph.add_conditional_edges(
        "context_memory",
        route_after_context,
        {
            "collections_intelligence": "collections_intelligence",
            "llm_reasoning":            "llm_reasoning",
        }
    )

    # ── Linear edges for analysis path ────────────────────────────
    graph.add_edge("collections_intelligence", "sentiment")
    graph.add_edge("sentiment",                "policy_guardrail")
    graph.add_edge("policy_guardrail",         "llm_reasoning")
    graph.add_edge("llm_reasoning",            END)

    return graph.compile()


# ─────────────────────────────────────────────
# Build Chat-Only Workflow
# ─────────────────────────────────────────────

def build_chat_workflow() -> StateGraph:
    """
    Lightweight workflow for customer AI assistant chat.

    Pipeline:
        context_memory
            ↓
        llm_reasoning
            ↓
           END
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("context_memory", run_context_memory_agent)
    graph.add_node("llm_reasoning",  run_llm_reasoning_agent)

    graph.set_entry_point("context_memory")
    graph.add_edge("context_memory", "llm_reasoning")
    graph.add_edge("llm_reasoning",  END)

    return graph.compile()


# ─────────────────────────────────────────────
# Compiled Workflow Instances
# ─────────────────────────────────────────────

analysis_workflow = build_analysis_workflow()
chat_workflow     = build_chat_workflow()


# ─────────────────────────────────────────────
# Run Analysis Workflow (used by officer router)
# ─────────────────────────────────────────────

def run_loan_analysis(
    db,
    customer_id: str,
    loan_id: str = None,
    session_id: str = ""
) -> dict:
    """
    Run the full loan intelligence analysis workflow.

    Used by:
        - Bank Officer Loan Intelligence Panel
        - Dashboard analytics

    Returns:
        Final workflow state dict with all analytics + LLM outputs
    """
    initial_state: WorkflowState = {
        "db":          db,
        "customer_id": customer_id,
        "loan_id":     loan_id,
        "session_id":  session_id,
        "user_query":  "",
        "mode":        "analysis",
    }

    try:
        result = analysis_workflow.invoke(initial_state)
        return result
    except Exception as e:
        print(f"[Workflow] Analysis workflow error: {e}")
        return {**initial_state, "error": str(e)}


# ─────────────────────────────────────────────
# Run Chat Workflow (used by chat router)
# ─────────────────────────────────────────────

def run_chat_response(
    db,
    customer_id: str,
    session_id: str,
    user_query: str,
    loan_id: str = None
) -> dict:
    """
    Run the chat workflow to generate an AI assistant response.

    Used by:
        - Customer AI Assistant chat endpoint

    Returns:
        Final workflow state with llm_response populated
    """
    initial_state: WorkflowState = {
        "db":          db,
        "customer_id": customer_id,
        "loan_id":     loan_id,
        "session_id":  session_id,
        "user_query":  user_query,
        "mode":        "chat",
    }

    try:
        result = chat_workflow.invoke(initial_state)
        return result
    except Exception as e:
        print(f"[Workflow] Chat workflow error: {e}")
        return {**initial_state, "error": str(e), "llm_response": (
            "I'm sorry, I'm having trouble processing your request right now. "
            "Please try again in a moment or contact the bank directly for assistance."
        )}
    