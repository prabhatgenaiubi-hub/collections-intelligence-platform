"""
Customer Context & Memory Agent

Responsibilities:
  - Retrieve customer profile from SQL
  - Retrieve loan data from SQL
  - Retrieve recent chat messages from SQL
  - Retrieve semantic interaction summaries from Chroma Vector DB
  - Build a unified context object for LLM Reasoning Agent

This agent bridges SQL memory (structured) and
Vector memory (semantic) into a single context window.
"""

from sqlalchemy.orm import Session
from backend.db.models import (
    Customer, Loan, PaymentHistory,
    InteractionHistory, ChatSession, ChatMessage
)


# ─────────────────────────────────────────────
# Retrieve Customer Profile
# ─────────────────────────────────────────────

def get_customer_profile(db: Session, customer_id: str) -> dict:
    """
    Fetch customer profile from SQL database.
    """
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        return {}

    return {
        "customer_id":             customer.customer_id,
        "customer_name":           customer.customer_name,
        "mobile_number":           customer.mobile_number,
        "email_id":                customer.email_id,
        "preferred_language":      customer.preferred_language,
        "preferred_channel":       customer.preferred_channel,
        "credit_score":            customer.credit_score,
        "monthly_income":          customer.monthly_income,
        "relationship_assessment": customer.relationship_assessment,
    }


# ─────────────────────────────────────────────
# Retrieve Loan Data
# ─────────────────────────────────────────────

def get_customer_loans(db: Session, customer_id: str) -> list[dict]:
    """
    Fetch all loans for a customer from SQL database.
    """
    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()

    result = []
    for loan in loans:
        result.append({
            "loan_id":               loan.loan_id,
            "loan_type":             loan.loan_type,
            "loan_amount":           loan.loan_amount,
            "emi_amount":            loan.emi_amount,
            "emi_due_date":          loan.emi_due_date,
            "outstanding_balance":   loan.outstanding_balance,
            "days_past_due":         loan.days_past_due,
            "risk_segment":          loan.risk_segment,
            "self_cure_probability": loan.self_cure_probability,
            "recommended_channel":   loan.recommended_channel,
            "interest_rate":         loan.interest_rate,
        })
    return result


# ─────────────────────────────────────────────
# Retrieve Payment History for a Loan
# ─────────────────────────────────────────────

def get_payment_history(db: Session, loan_id: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent payment history for a loan from SQL database.
    """
    payments = (
        db.query(PaymentHistory)
        .filter(PaymentHistory.loan_id == loan_id)
        .order_by(PaymentHistory.payment_date.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "payment_id":     p.payment_id,
            "payment_date":   p.payment_date,
            "payment_amount": p.payment_amount,
            "payment_method": p.payment_method,
        }
        for p in payments
    ]


# ─────────────────────────────────────────────
# Retrieve Interaction History
# ─────────────────────────────────────────────

def get_interaction_history(db: Session, customer_id: str, limit: int = 5) -> list[dict]:
    """
    Fetch recent interaction history for a customer from SQL database.
    Returns last N interactions with summaries.
    """
    interactions = (
        db.query(InteractionHistory)
        .filter(InteractionHistory.customer_id == customer_id)
        .order_by(InteractionHistory.interaction_time.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "interaction_id":      i.interaction_id,
            "interaction_type":    i.interaction_type,
            "interaction_time":    i.interaction_time,
            "sentiment_score":     i.sentiment_score,
            "tonality_score":      i.tonality_score,
            "interaction_summary": i.interaction_summary,
        }
        for i in interactions
    ]


# ─────────────────────────────────────────────
# Retrieve Recent Chat Messages
# ─────────────────────────────────────────────

def get_recent_chat_messages(
    db: Session,
    session_id: str,
    limit: int = 10
) -> list[dict]:
    """
    Fetch recent chat messages for a session from SQL database.
    Used to build conversation context for LLM.
    """
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "role":         m.role,
            "message_text": m.message_text,
            "timestamp":    m.timestamp,
        }
        for m in messages
    ]


# ─────────────────────────────────────────────
# Retrieve Vector Memory (Chroma)
# ─────────────────────────────────────────────

def get_vector_memory(customer_id: str, query: str, top_k: int = 3) -> list[str]:
    """
    Retrieve semantically relevant interaction summaries
    from Chroma Vector DB for a given customer and query.

    Falls back gracefully if Chroma is unavailable.
    """
    try:
        from backend.vector.chroma_store import retrieve_memories
        memories = retrieve_memories(
            customer_id = customer_id,
            query       = query,
            top_k       = top_k
        )
        return memories
    except Exception as e:
        print(f"[ContextMemoryAgent] Vector memory unavailable: {e}")
        return []


# ─────────────────────────────────────────────
# Build Full Context for LLM
# ─────────────────────────────────────────────

def build_llm_context(
    db: Session,
    customer_id: str,
    session_id: str,
    user_query: str,
    loan_id: str = None
) -> dict:
    """
    Build a unified context object combining:
      - Customer profile (SQL)
      - Loan details (SQL)
      - Payment history (SQL)
      - Recent chat messages (SQL)
      - Semantic interaction summaries (Chroma Vector DB)

    This context is passed to the LLM Reasoning Agent.

    Args:
        db:           SQLAlchemy session
        customer_id:  Customer ID
        session_id:   Current chat session ID
        user_query:   Current user message (used for vector search)
        loan_id:      Optional specific loan ID for detailed context

    Returns:
        dict with all context assembled
    """

    # ── Customer Profile ──────────────────────────────────────────
    customer_profile = get_customer_profile(db, customer_id)

    # ── Loans ─────────────────────────────────────────────────────
    loans = get_customer_loans(db, customer_id)

    # ── Payment History (for the specified or first loan) ─────────
    payment_history = []
    target_loan_id = loan_id or (loans[0]["loan_id"] if loans else None)
    if target_loan_id:
        payment_history = get_payment_history(db, target_loan_id, limit=6)

    # ── Recent Chat Messages ──────────────────────────────────────
    recent_messages = get_recent_chat_messages(db, session_id, limit=10)

    # ── Interaction History ───────────────────────────────────────
    interactions = get_interaction_history(db, customer_id, limit=3)

    # ── Vector Memory ─────────────────────────────────────────────
    vector_memories = get_vector_memory(
        customer_id = customer_id,
        query       = user_query,
        top_k       = 3
    )

    # ── Assemble Context ──────────────────────────────────────────
    context = {
        "customer_profile":  customer_profile,
        "loans":             loans,
        "payment_history":   payment_history,
        "recent_messages":   recent_messages,
        "interactions":      interactions,
        "vector_memories":   vector_memories,
        "user_query":        user_query,
        "session_id":        session_id,
        "customer_id":       customer_id,
    }

    return context


# ─────────────────────────────────────────────
# LangGraph-Compatible Node
# ─────────────────────────────────────────────

def run_context_memory_agent(state: dict) -> dict:
    """
    LangGraph-compatible agent node.

    Expects state to have:
        - db (Session)
        - customer_id (str)
        - session_id (str)
        - user_query (str)
        - loan_id (str, optional)

    Adds to state:
        - context (dict)
        - customer_profile (dict)
        - loans (list)
        - payment_history (list)
        - recent_messages (list)
        - interactions (list)
        - vector_memories (list)
    """
    db           = state.get("db")
    customer_id  = state.get("customer_id")
    session_id   = state.get("session_id", "")
    user_query   = state.get("user_query", "")
    loan_id      = state.get("loan_id", None)

    context = build_llm_context(
        db          = db,
        customer_id = customer_id,
        session_id  = session_id,
        user_query  = user_query,
        loan_id     = loan_id,
    )

    state.update({
        "context":          context,
        "customer_profile": context["customer_profile"],
        "loans":            context["loans"],
        "payment_history":  context["payment_history"],
        "recent_messages":  context["recent_messages"],
        "interactions":     context["interactions"],
        "vector_memories":  context["vector_memories"],

        # Pass through to next agents
        "days_past_due":       context["loans"][0]["days_past_due"]       if context["loans"] else 0,
        "credit_score":        context["customer_profile"].get("credit_score", 650),
        "monthly_income":      context["customer_profile"].get("monthly_income", 30000.0),
        "emi_amount":          context["loans"][0]["emi_amount"]           if context["loans"] else 5000.0,
        "outstanding_balance": context["loans"][0]["outstanding_balance"]  if context["loans"] else 0.0,
        "preferred_channel":   context["customer_profile"].get("preferred_channel", "Email"),
    })

    return state