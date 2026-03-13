"""
LLM Reasoning Agent

Responsibilities:
  - Generate explainable recovery recommendations (narrative)
  - Generate customer relationship assessment text
  - Summarize borrower conversations
  - Answer customer AI assistant queries with full context
  - Uses Llama-3 via Ollama for local inference

Falls back to rule-based responses if Ollama is unavailable.
"""

import httpx
import json


# ─────────────────────────────────────────────
# Ollama Configuration
# ─────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "llama3"
OLLAMA_TIMEOUT  = 120  # seconds


# ─────────────────────────────────────────────
# Ollama Availability Check
# ─────────────────────────────────────────────

def is_ollama_available() -> bool:
    """Check if Ollama is running locally."""
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────
# Core LLM Call
# ─────────────────────────────────────────────

def call_ollama(prompt: str, system_prompt: str = "") -> str:
    """
    Send a prompt to Ollama Llama-3 and return the response text.

    Falls back to rule-based response if Ollama is unavailable.
    """
    if not is_ollama_available():
        return None  # Signal to use fallback

    try:
        payload = {
            "model":  OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 512,
            }
        }

        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json    = payload,
            timeout = OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    except Exception as e:
        print(f"[LLMReasoningAgent] Ollama call failed: {e}")
        return None


# ─────────────────────────────────────────────
# Build Context String for Prompts
# ─────────────────────────────────────────────

def build_context_string(context: dict) -> str:
    """
    Convert the context dict into a readable string for LLM prompts.
    """
    profile  = context.get("customer_profile", {})
    loans    = context.get("loans", [])
    payments = context.get("payment_history", [])
    memories = context.get("vector_memories", [])
    interactions = context.get("interactions", [])

    lines = []

    # Customer
    if profile:
        lines.append(f"Customer: {profile.get('customer_name', 'N/A')}")
        lines.append(f"Credit Score: {profile.get('credit_score', 'N/A')}")
        lines.append(f"Monthly Income: ₹{profile.get('monthly_income', 0):,.0f}")
        lines.append(f"Preferred Channel: {profile.get('preferred_channel', 'N/A')}")

    # Loans
    if loans:
        loan = loans[0]
        lines.append(f"\nLoan ID: {loan.get('loan_id')}")
        lines.append(f"Loan Type: {loan.get('loan_type')}")
        lines.append(f"Outstanding Balance: ₹{loan.get('outstanding_balance', 0):,.0f}")
        lines.append(f"EMI Amount: ₹{loan.get('emi_amount', 0):,.0f}")
        lines.append(f"Days Past Due: {loan.get('days_past_due', 0)}")
        lines.append(f"Risk Segment: {loan.get('risk_segment', 'N/A')}")

    # Recent payments
    if payments:
        lines.append(f"\nRecent Payments (last {len(payments)}):")
        for p in payments[:3]:
            lines.append(f"  - {p.get('payment_date')}: ₹{p.get('payment_amount', 0):,.0f} via {p.get('payment_method')}")

    # Interaction summaries
    if interactions:
        lines.append("\nRecent Interactions:")
        for i in interactions[:3]:
            lines.append(f"  - [{i.get('interaction_type')}] {i.get('interaction_summary', '')}")

    # Vector memories
    if memories:
        lines.append("\nSemantic Memory:")
        for m in memories:
            lines.append(f"  - {m}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 1. Generate Recovery Recommendation (Narrative)
# ─────────────────────────────────────────────

def generate_recovery_recommendation(
    context: dict,
    analytics: dict
) -> str:
    """
    Generate an explainable recovery recommendation narrative using LLM.
    Falls back to rule-based text if Ollama is unavailable.

    Args:
        context:   Full customer context dict
        analytics: Output from collections_intelligence_agent

    Returns:
        Narrative recommendation string
    """
    strategy      = analytics.get("recovery_strategy", {})
    risk_segment  = analytics.get("risk_segment", "Medium")
    delinquency   = analytics.get("delinquency_score", 0)
    self_cure     = analytics.get("self_cure_probability", 0.5)
    dpd           = analytics.get("days_past_due", 0)

    context_str = build_context_string(context)

    system_prompt = (
        "You are an expert collections intelligence analyst at a bank. "
        "Your role is to provide clear, empathetic, and actionable recovery recommendations "
        "for bank officers. Be concise (3-4 sentences). Do not use bullet points. "
        "Focus on the borrower situation and recommended action."
    )

    prompt = f"""
Based on the following borrower profile and analytics, generate an explainable recovery recommendation.

{context_str}

Analytics:
- Risk Segment: {risk_segment}
- Delinquency Score: {delinquency}/100
- Self Cure Probability: {self_cure * 100:.0f}%
- Days Past Due: {dpd}
- Recommended Strategy: {strategy.get('strategy', 'N/A')}
- Recommended Action: {strategy.get('action', 'N/A')}

Write a clear 3-4 sentence recovery recommendation for the bank officer.
"""

    llm_response = call_ollama(prompt, system_prompt)

    if llm_response:
        return llm_response

    # ── Fallback: Rule-based narrative ────────────────────────────
    return (
        f"Based on the borrower's current profile, the recommended strategy is "
        f"'{strategy.get('strategy', 'Standard Follow-Up')}'. "
        f"The borrower has a delinquency score of {delinquency}/100 with "
        f"a self-cure probability of {self_cure * 100:.0f}%. "
        f"Recommended action: {strategy.get('action', 'Send payment reminder and provide repayment options.')} "
        f"Priority level is {strategy.get('priority', 'Medium')}."
    )


# ─────────────────────────────────────────────
# 2. Generate Customer Relationship Assessment
# ─────────────────────────────────────────────

def generate_relationship_assessment(
    customer_name: str,
    loans: list,
    payment_history: list,
    interactions: list
) -> str:
    """
    Generate a customer-friendly relationship assessment narrative.
    Shown to the customer in the Customer Portal.
    Falls back to rule-based text if Ollama unavailable.
    """
    if not loans:
        return (
            f"Welcome, {customer_name}. Your account is in good standing. "
            "Please contact us if you need any assistance with your loans."
        )

    loan        = loans[0]
    dpd         = loan.get("days_past_due", 0)
    emi_due     = loan.get("emi_due_date", "N/A")
    risk        = loan.get("risk_segment", "Low")
    total_paid  = len([p for p in payment_history if p.get("payment_amount", 0) > 0])

    system_prompt = (
        "You are a helpful and empathetic bank assistant. "
        "Write a short, supportive, customer-friendly relationship assessment (3-4 sentences). "
        "Do not use negative or alarming language. Be encouraging and helpful."
    )

    prompt = f"""
Write a personalized relationship assessment for the customer to display in their portal.

Customer Name: {customer_name}
Days Past Due: {dpd}
Next EMI Due Date: {emi_due}
Risk Segment: {risk}
Total Payments Made: {total_paid}
Recent Interactions: {len(interactions)}

Write a warm, supportive 3-4 sentence assessment.
"""

    llm_response = call_ollama(prompt, system_prompt)

    if llm_response:
        return llm_response

    # ── Fallback ──────────────────────────────────────────────────
    if dpd == 0:
        return (
            f"You have maintained an excellent repayment pattern with the bank. "
            f"Your next EMI is due on {emi_due}. "
            f"Thank you for your consistent and timely payments. "
            f"We value your continued trust in us."
        )
    elif dpd < 15:
        return (
            f"You have maintained a generally stable repayment pattern with the bank. "
            f"There have been a few short-term delays recently, but your overall repayment behavior remains positive. "
            f"Your next EMI is due on {emi_due}. "
            f"Based on your recent activity, you may receive reminders or support options if needed."
        )
    else:
        return (
            f"We have noticed some recent delays in your repayment schedule. "
            f"Your next EMI was due on {emi_due}. "
            f"We encourage you to contact the bank to discuss available support options "
            f"such as grace period or loan restructuring. We are here to help."
        )


# ─────────────────────────────────────────────
# 3. Answer Customer Query (AI Assistant)
# ─────────────────────────────────────────────

def answer_customer_query(
    user_message: str,
    context: dict,
    chat_history: list
) -> str:
    """
    Answer a customer's query using LLM with full context.
    Used by the Customer AI Assistant chat interface.

    Args:
        user_message: Current customer message
        context:      Full customer context dict
        chat_history: List of {role, message_text} dicts

    Returns:
        AI assistant response string
    """
    context_str = build_context_string(context)

    # Build conversation history string
    history_lines = []
    for msg in chat_history[-6:]:  # Last 6 messages for context window
        role = "Customer" if msg.get("role") == "user" else "Assistant"
        history_lines.append(f"{role}: {msg.get('message_text', '')}")
    history_str = "\n".join(history_lines)

    system_prompt = (
        "You are a helpful, empathetic AI assistant for a bank's collections platform. "
        "You help customers understand their loan details, EMI schedules, grace periods, "
        "and restructuring options. Always be polite, clear, and supportive. "
        "Never provide specific legal advice. Keep responses concise (2-4 sentences). "
        "Use ₹ for Indian Rupee amounts."
    )

    prompt = f"""
Customer Profile & Loan Context:
{context_str}

Recent Conversation:
{history_str}

Customer: {user_message}

Respond helpfully as the bank's AI assistant.
"""

    llm_response = call_ollama(prompt, system_prompt)

    if llm_response:
        return llm_response

    # ── Fallback: Rule-based responses ────────────────────────────
    msg_lower = user_message.lower()
    loans     = context.get("loans", [])
    profile   = context.get("customer_profile", {})

    if any(kw in msg_lower for kw in ["emi", "payment", "due", "next"]):
        if loans:
            loan = loans[0]
            return (
                f"Your next EMI of ₹{loan.get('emi_amount', 0):,.0f} is due on "
                f"{loan.get('emi_due_date', 'N/A')} for loan {loan.get('loan_id')}. "
                f"Your outstanding balance is ₹{loan.get('outstanding_balance', 0):,.0f}."
            )

    if any(kw in msg_lower for kw in ["grace", "extension", "delay"]):
        if loans:
            dpd = loans[0].get("days_past_due", 0)
            if dpd < 30:
                return (
                    "Based on your account status, you may be eligible for a grace period of up to 7 days. "
                    "You can submit a grace request from the 'Your Loans' section. "
                    "A bank officer will review and respond within 1-2 business days."
                )
            else:
                return (
                    "Your current overdue period exceeds the grace period eligibility threshold. "
                    "Please contact the bank directly to discuss restructuring options. "
                    "We are here to help find the best solution for you."
                )

    if any(kw in msg_lower for kw in ["restructur", "restructure"]):
        return (
            "Loan restructuring options include extending your loan tenure or adjusting your EMI amount. "
            "You can submit a restructure request from the 'Your Loans' section. "
            "A bank officer will review your request within 2 business days."
        )

    if any(kw in msg_lower for kw in ["balance", "outstanding"]):
        if loans:
            loan = loans[0]
            return (
                f"Your current outstanding balance for loan {loan.get('loan_id')} is "
                f"₹{loan.get('outstanding_balance', 0):,.0f}."
            )

    # Generic fallback
    name = profile.get("customer_name", "")
    return (
        f"Thank you for your query{', ' + name if name else ''}. "
        "I can help you with information about your EMI schedule, outstanding balance, "
        "grace period eligibility, and loan restructuring options. "
        "Please feel free to ask any specific question about your loan."
    )


# ─────────────────────────────────────────────
# 4. Summarize Interaction (for Vector Storage)
# ─────────────────────────────────────────────

def summarize_interaction(
    conversation_text: str,
    customer_name: str = "Customer"
) -> str:
    """
    Generate a concise summary of an interaction for vector storage.
    """
    system_prompt = (
        "You are a bank collections analyst. "
        "Summarize the following customer interaction in 1-2 sentences. "
        "Be factual and concise."
    )

    prompt = f"""
Summarize this customer interaction in 1-2 sentences:

Customer: {customer_name}
Interaction: {conversation_text}
"""

    llm_response = call_ollama(prompt, system_prompt)
    if llm_response:
        return llm_response

    # Fallback: return truncated text
    return conversation_text[:200] + "..." if len(conversation_text) > 200 else conversation_text


# ─────────────────────────────────────────────
# LangGraph-Compatible Node
# ─────────────────────────────────────────────

def run_llm_reasoning_agent(state: dict) -> dict:
    """
    LangGraph-compatible agent node.

    Expects state keys:
        - context (dict)          ← from context_memory_agent
        - analytics (dict)        ← from collections_intelligence_agent
        - user_query (str)        ← current user message
        - recent_messages (list)  ← chat history

    Adds to state:
        - llm_recommendation (str)
        - llm_response (str)       ← for chat assistant
    """
    context          = state.get("context", {})
    user_query       = state.get("user_query", "")
    recent_messages  = state.get("recent_messages", [])

    # Build analytics dict from state
    analytics = {
        "recovery_strategy":     state.get("recovery_strategy", {}),
        "risk_segment":          state.get("risk_segment", "Low"),
        "delinquency_score":     state.get("delinquency_score", 0),
        "self_cure_probability": state.get("self_cure_probability", 0.5),
        "days_past_due":         state.get("days_past_due", 0),
    }

    # Generate recovery recommendation narrative
    llm_recommendation = generate_recovery_recommendation(context, analytics)

    # Generate chat response if user query provided
    llm_response = ""
    if user_query:
        llm_response = answer_customer_query(
            user_message = user_query,
            context      = context,
            chat_history = recent_messages,
        )

    state.update({
        "llm_recommendation": llm_recommendation,
        "llm_response":       llm_response,
    })

    return state