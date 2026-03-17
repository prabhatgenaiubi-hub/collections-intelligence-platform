"""
Bank Officer Router

Endpoints:
  GET  /officer/dashboard              → Portfolio dashboard stats + chart data
  GET  /officer/search                 → Customer / loan search (OR logic)
  GET  /officer/loan-intelligence/{loan_id}  → Full loan intelligence panel
  GET  /officer/customers/{customer_id}      → Customer full profile for officer
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel

from backend.db.database import get_db
from backend.db.models import (
    Customer, Loan, PaymentHistory,
    InteractionHistory, GraceRequest, RestructureRequest,
    OfficerChatSession, OfficerChatMessage,
    ChatSession, ChatMessage,
)
from backend.routers.auth import get_current_officer
from backend.agents.collections_intelligence_agent import analyze_loan
from backend.agents.sentiment_agent import aggregate_sentiment
from backend.agents.llm_reasoning_agent import generate_recovery_recommendation
from analytics.npv_calculator import calculate_portfolio_npv

router = APIRouter(prefix="/officer", tags=["Bank Officer"])


# ─────────────────────────────────────────────
# Helper: Build Loan Summary Dict
# ─────────────────────────────────────────────

def build_loan_summary(loan: Loan, customer: Customer) -> dict:
    return {
        "loan_id":             loan.loan_id,
        "customer_id":         customer.customer_id,
        "customer_name":       customer.customer_name,
        "loan_type":           loan.loan_type,
        "loan_amount":         loan.loan_amount,
        "outstanding_balance": loan.outstanding_balance,
        "emi_amount":          loan.emi_amount,
        "emi_due_date":        loan.emi_due_date,
        "days_past_due":       loan.days_past_due,
        "risk_segment":        loan.risk_segment,
        "self_cure_probability": loan.self_cure_probability,
        "recommended_channel": loan.recommended_channel,
    }


# ─────────────────────────────────────────────
# GET /officer/dashboard
# ─────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db)
):
    """
    Return portfolio-level dashboard statistics for the bank officer.

    Includes:
      - Total borrowers
      - High / Medium / Low risk account counts
      - Expected recovery
      - Self cure rate
      - NPV estimate
      - Risk distribution chart data
      - Recovery strategy mix chart data
    """

    # ── Fetch all loans ───────────────────────────────────────────
    all_loans    = db.query(Loan).all()
    all_customers = db.query(Customer).all()

    total_borrowers = len(all_customers)
    total_loans     = len(all_loans)

    # ── Risk counts ───────────────────────────────────────────────
    high_risk   = [l for l in all_loans if l.risk_segment == "High"]
    medium_risk = [l for l in all_loans if l.risk_segment == "Medium"]
    low_risk    = [l for l in all_loans if l.risk_segment == "Low"]

    # ── Self cure rate ────────────────────────────────────────────
    avg_self_cure = (
        sum(l.self_cure_probability for l in all_loans) / len(all_loans)
        if all_loans else 0.0
    )

    # ── Total outstanding ─────────────────────────────────────────
    total_outstanding = sum(l.outstanding_balance for l in all_loans)

    # ── Portfolio NPV ─────────────────────────────────────────────
    from analytics.risk_models import recommend_recovery_strategy
    loan_inputs = []
    for loan in all_loans:
        strategy = recommend_recovery_strategy(
            days_past_due         = loan.days_past_due,
            risk_segment          = loan.risk_segment or "Medium",
            self_cure_probability = loan.self_cure_probability or 0.5,
            outstanding_balance   = loan.outstanding_balance,
            missed_payments       = 0,
        )
        loan_inputs.append({
            "outstanding_balance":   loan.outstanding_balance,
            "strategy":              strategy["strategy"],
            "self_cure_probability": loan.self_cure_probability or 0.5,
        })

    portfolio_npv = calculate_portfolio_npv(loan_inputs)

    # ── Pending requests ──────────────────────────────────────────
    pending_grace       = db.query(GraceRequest).filter(GraceRequest.request_status == "Pending").count()
    pending_restructure = db.query(RestructureRequest).filter(RestructureRequest.request_status == "Pending").count()

    # ── Risk Distribution (for pie/bar chart) ─────────────────────
    risk_distribution = [
        {"segment": "High",   "count": len(high_risk),   "color": "#EF4444"},
        {"segment": "Medium", "count": len(medium_risk), "color": "#F59E0B"},
        {"segment": "Low",    "count": len(low_risk),    "color": "#10B981"},
    ]

    # ── Recovery Strategy Mix (for chart) ────────────────────────
    strategy_counts = {}
    for li in loan_inputs:
        strat = li["strategy"]
        strategy_counts[strat] = strategy_counts.get(strat, 0) + 1

    recovery_strategy_mix = [
        {"strategy": k, "count": v}
        for k, v in sorted(strategy_counts.items(), key=lambda x: -x[1])
    ]

    # ── Overdue loans breakdown ───────────────────────────────────
    overdue_loans = [l for l in all_loans if l.days_past_due > 0]

    return {
        "summary": {
            "total_borrowers":          total_borrowers,
            "total_loans":              total_loans,
            "high_risk_accounts":       len(high_risk),
            "medium_risk_accounts":     len(medium_risk),
            "low_risk_accounts":        len(low_risk),
            "overdue_loans":            len(overdue_loans),
            "total_outstanding":        round(total_outstanding, 2),
            "expected_recovery":        portfolio_npv["total_expected_recovery"],
            "total_npv":                portfolio_npv["total_npv"],
            "overall_recovery_rate":    round(portfolio_npv["overall_recovery_rate"] * 100, 1),
            "self_cure_rate":           round(avg_self_cure * 100, 1),
            "pending_grace_requests":   pending_grace,
            "pending_restructure_requests": pending_restructure,
        },
        "charts": {
            "risk_distribution":    risk_distribution,
            "recovery_strategy_mix": recovery_strategy_mix,
        }
    }


# ─────────────────────────────────────────────
# GET /officer/search
# ─────────────────────────────────────────────

@router.get("/search")
def search_customers(
    loan_id:      Optional[str] = Query(None, description="Search by Loan ID"),
    customer_id:  Optional[str] = Query(None, description="Search by Customer ID"),
    name:         Optional[str] = Query(None, description="Search by Customer Name"),
    loan_type:    Optional[str] = Query(None, description="Search by Loan Type"),
    risk_segment: Optional[str] = Query(None, description="Search by Risk Segment"),
    current_user: dict          = Depends(get_current_officer),
    db: Session                 = Depends(get_db)
):
    """
    Search customers and loans using OR logic across all filters.

    At least one search parameter must be provided.
    Returns a list of matching loan records with customer details.
    """
    if not any([loan_id, customer_id, name, loan_type, risk_segment]):
        raise HTTPException(
            status_code = 400,
            detail      = "At least one search parameter is required: loan_id, customer_id, name, loan_type, or risk_segment."
        )

    # ── Build filter conditions (OR logic) ────────────────────────
    conditions = []

    if loan_id:
        conditions.append(Loan.loan_id.ilike(f"%{loan_id}%"))

    if loan_type:
        conditions.append(Loan.loan_type.ilike(f"%{loan_type}%"))

    if risk_segment:
        conditions.append(Loan.risk_segment.ilike(f"%{risk_segment}%"))

    # ── Customer-based filters (join required) ────────────────────
    customer_ids_from_search = []

    if customer_id:
        matched = db.query(Customer.customer_id).filter(
            Customer.customer_id.ilike(f"%{customer_id}%")
        ).all()
        customer_ids_from_search.extend([c[0] for c in matched])

    if name:
        matched = db.query(Customer.customer_id).filter(
            Customer.customer_name.ilike(f"%{name}%")
        ).all()
        customer_ids_from_search.extend([c[0] for c in matched])

    if customer_ids_from_search:
        conditions.append(Loan.customer_id.in_(customer_ids_from_search))

    # ── Execute query ─────────────────────────────────────────────
    if not conditions:
        return {"results": [], "total": 0}

    matched_loans = (
        db.query(Loan)
        .filter(or_(*conditions))
        .order_by(Loan.days_past_due.desc())
        .limit(50)
        .all()
    )

    # ── Build results ─────────────────────────────────────────────
    results = []
    for loan in matched_loans:
        customer = db.query(Customer).filter(
            Customer.customer_id == loan.customer_id
        ).first()
        if customer:
            results.append(build_loan_summary(loan, customer))

    return {
        "results": results,
        "total":   len(results),
    }


# ─────────────────────────────────────────────
# GET /officer/loan-intelligence/{loan_id}
# ─────────────────────────────────────────────

@router.get("/loan-intelligence/{loan_id}")
def get_loan_intelligence(
    loan_id:      str,
    current_user: dict  = Depends(get_current_officer),
    db: Session         = Depends(get_db)
):
    """
    Full Loan Intelligence Panel for bank officers.

    Returns:
      - Loan details
      - Customer details
      - Payment history + trend
      - Risk analytics (delinquency score, VaR, self cure)
      - Sentiment & tonality analysis
      - Last 3 interaction summaries
      - Recovery recommendation (LLM-generated narrative)
      - NPV analysis
      - Policy validation
      - Grace / Restructure request history
    """

    # ── Fetch Loan ────────────────────────────────────────────────
    loan = db.query(Loan).filter(Loan.loan_id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found.")

    # ── Fetch Customer ────────────────────────────────────────────
    customer = db.query(Customer).filter(Customer.customer_id == loan.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    # ── Payment History ───────────────────────────────────────────
    payments = (
        db.query(PaymentHistory)
        .filter(PaymentHistory.loan_id == loan_id)
        .order_by(PaymentHistory.payment_date.desc())
        .limit(12)
        .all()
    )
    payment_dicts = [
        {
            "payment_date":   p.payment_date,
            "payment_amount": p.payment_amount,
            "payment_method": p.payment_method,
            "emi_amount":     loan.emi_amount,
        }
        for p in payments
    ]

    # ── Analytics ─────────────────────────────────────────────────
    analytics = analyze_loan(
        days_past_due       = loan.days_past_due,
        credit_score        = customer.credit_score or 650,
        monthly_income      = customer.monthly_income or 30000.0,
        emi_amount          = loan.emi_amount,
        outstanding_balance = loan.outstanding_balance,
        preferred_channel   = customer.preferred_channel or "Email",
        payment_history     = [
            {"payment_amount": p["payment_amount"], "emi_amount": loan.emi_amount}
            for p in payment_dicts
        ],
    )

    # ── Interactions (last 3) ─────────────────────────────────────
    interactions = (
        db.query(InteractionHistory)
        .filter(InteractionHistory.customer_id == loan.customer_id)
        .order_by(InteractionHistory.interaction_time.desc())
        .limit(3)
        .all()
    )
    interaction_dicts = [
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

    # ── Sentiment Aggregation ─────────────────────────────────────
    sentiment_summary = aggregate_sentiment(interaction_dicts)

    # ── LLM Recovery Recommendation ──────────────────────────────
    context = {
        "customer_profile": {
            "customer_name":    customer.customer_name,
            "credit_score":     customer.credit_score,
            "monthly_income":   customer.monthly_income,
            "preferred_channel": customer.preferred_channel,
        },
        "loans": [{
            "loan_id":             loan.loan_id,
            "loan_type":           loan.loan_type,
            "outstanding_balance": loan.outstanding_balance,
            "emi_amount":          loan.emi_amount,
            "days_past_due":       loan.days_past_due,
            "risk_segment":        analytics.get("risk_segment"),
        }],
        "payment_history":  payment_dicts[:3],
        "interactions":     interaction_dicts,
        "vector_memories":  [],
    }

    llm_recommendation = generate_recovery_recommendation(
        context   = context,
        analytics = analytics,
    )

    # ── Policy Validation ─────────────────────────────────────────
    from backend.agents.policy_guardrail_agent import validate_recovery_recommendation
    policy_validation = validate_recovery_recommendation(
        strategy            = analytics.get("recovery_strategy", {}).get("strategy", "Standard Follow-Up"),
        risk_segment        = analytics.get("risk_segment", "Low"),
        days_past_due       = loan.days_past_due,
        outstanding_balance = loan.outstanding_balance,
    )

    # ── Grace Request History ─────────────────────────────────────
    grace_requests = (
        db.query(GraceRequest)
        .filter(GraceRequest.loan_id == loan_id)
        .order_by(GraceRequest.request_date.desc())
        .all()
    )
    grace_history = [
        {
            "request_id":       gr.request_id,
            "request_status":   gr.request_status,
            "decision_comment": gr.decision_comment,
            "request_date":     gr.request_date,
            "decision_date":    gr.decision_date,
            "approved_by":      gr.approved_by,
        }
        for gr in grace_requests
    ]

    # ── Restructure Request History ───────────────────────────────
    restructure_requests = (
        db.query(RestructureRequest)
        .filter(RestructureRequest.loan_id == loan_id)
        .order_by(RestructureRequest.request_date.desc())
        .all()
    )
    restructure_history = [
        {
            "request_id":       rr.request_id,
            "request_status":   rr.request_status,
            "decision_comment": rr.decision_comment,
            "request_date":     rr.request_date,
            "decision_date":    rr.decision_date,
            "approved_by":      rr.approved_by,
        }
        for rr in restructure_requests
    ]

    return {
        # ── Loan Details ──────────────────────────────────────────
        "loan": {
            "loan_id":             loan.loan_id,
            "loan_type":           loan.loan_type,
            "loan_amount":         loan.loan_amount,
            "interest_rate":       loan.interest_rate,
            "emi_amount":          loan.emi_amount,
            "emi_due_date":        loan.emi_due_date,
            "outstanding_balance": loan.outstanding_balance,
            "days_past_due":       loan.days_past_due,
        },

        # ── Customer Details ──────────────────────────────────────
        "customer": {
            "customer_id":      customer.customer_id,
            "customer_name":    customer.customer_name,
            "mobile_number":    customer.mobile_number,
            "email_id":         customer.email_id,
            "credit_score":     customer.credit_score,
            "monthly_income":   customer.monthly_income,
            "preferred_channel": customer.preferred_channel,
            "preferred_language": customer.preferred_language,
        },

        # ── Analytics ─────────────────────────────────────────────
        "analytics": {
            "risk_segment":          analytics.get("risk_segment"),
            "self_cure_probability": analytics.get("self_cure_probability"),
            "delinquency_score":     analytics.get("delinquency_score"),
            "value_at_risk":         analytics.get("value_at_risk"),
            "payment_trend":         analytics.get("payment_trend"),
            "recovery_strategy":     analytics.get("recovery_strategy"),
            "recommended_channel":   analytics.get("recommended_channel"),
            "npv_result":            analytics.get("npv_result"),
            "strategy_comparison":   analytics.get("strategy_comparison", [])[:3],
        },

        # ── Sentiment ─────────────────────────────────────────────
        "sentiment": sentiment_summary,

        # ── Interactions ──────────────────────────────────────────
        "interactions":        interaction_dicts,

        # ── Payment History ───────────────────────────────────────
        "payment_history":     payment_dicts,

        # ── LLM Recommendation ────────────────────────────────────
        "llm_recommendation":  llm_recommendation,

        # ── Policy Validation ─────────────────────────────────────
        "policy_validation":   policy_validation,

        # ── Request History ───────────────────────────────────────
        "grace_history":       grace_history,
        "restructure_history": restructure_history,
    }


# ─────────────────────────────────────────────
# GET /officer/customers/{customer_id}
# ─────────────────────────────────────────────

@router.get("/customers/{customer_id}")
def get_customer_for_officer(
    customer_id:  str,
    current_user: dict  = Depends(get_current_officer),
    db: Session         = Depends(get_db)
):
    """
    Return full customer profile and all loans for officer view.
    """
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found.")

    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()

    loan_summaries = [build_loan_summary(l, customer) for l in loans]

    total_outstanding = sum(l.outstanding_balance for l in loans)
    high_risk_loans   = [l for l in loans if l.risk_segment == "High"]

    # Latest interactions
    interactions = (
        db.query(InteractionHistory)
        .filter(InteractionHistory.customer_id == customer_id)
        .order_by(InteractionHistory.interaction_time.desc())
        .limit(5)
        .all()
    )

    return {
        "customer": {
            "customer_id":      customer.customer_id,
            "customer_name":    customer.customer_name,
            "mobile_number":    customer.mobile_number,
            "email_id":         customer.email_id,
            "credit_score":     customer.credit_score,
            "monthly_income":   customer.monthly_income,
            "preferred_channel": customer.preferred_channel,
            "preferred_language": customer.preferred_language,
            "relationship_assessment": customer.relationship_assessment,
        },
        "loans":              loan_summaries,
        "total_loans":        len(loans),
        "total_outstanding":  total_outstanding,
        "high_risk_loans":    len(high_risk_loans),
        "interactions": [
            {
                "interaction_type":    i.interaction_type,
                "interaction_time":    i.interaction_time,
                "sentiment_score":     i.sentiment_score,
                "tonality_score":      i.tonality_score,
                "interaction_summary": i.interaction_summary,
            }
            for i in interactions
        ],
    }


# ═════════════════════════════════════════════
# OFFICER CHAT ENDPOINTS
# ═════════════════════════════════════════════

class OfficerChatRequest(BaseModel):
    session_title: Optional[str] = "General Collections Chat"


class OfficerMessageRequest(BaseModel):
    message: str
    loan_id: Optional[str] = None


def _format_officer_session(session: OfficerChatSession, db: Session) -> dict:
    last_msg = (
        db.query(OfficerChatMessage)
        .filter(OfficerChatMessage.session_id == session.session_id,
                OfficerChatMessage.role == "user")
        .order_by(OfficerChatMessage.timestamp.desc())
        .first()
    )
    return {
        "session_id":    session.session_id,
        "session_title": session.session_title,
        "created_at":    session.created_at,
        "last_updated":  session.last_updated,
        "last_message":  last_msg.message_text[:60] if last_msg else None,
    }


# ─────────────────────────────────────────────
# GET /officer/chat/sessions
# ─────────────────────────────────────────────

@router.get("/chat/sessions")
def officer_list_sessions(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db),
):
    """List all chat sessions for the current officer."""
    officer_id = current_user["user_id"]
    sessions = (
        db.query(OfficerChatSession)
        .filter(OfficerChatSession.officer_id == officer_id)
        .order_by(OfficerChatSession.last_updated.desc())
        .all()
    )
    return {
        "success":  True,
        "sessions": [_format_officer_session(s, db) for s in sessions],
    }


# ─────────────────────────────────────────────
# POST /officer/chat/sessions
# ─────────────────────────────────────────────

@router.post("/chat/sessions")
def officer_create_session(
    body:         OfficerChatRequest,
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db),
):
    """Create a new officer chat session."""
    from datetime import datetime
    officer_id = current_user["user_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    session = OfficerChatSession(
        officer_id    = officer_id,
        session_title = body.session_title or "General Collections Chat",
        created_at    = now,
        last_updated  = now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Welcome message
    welcome = OfficerChatMessage(
        session_id   = session.session_id,
        role         = "assistant",
        message_text = (
            "Hello! I'm your Collections Intelligence AI Assistant.\n"
            "I can help you with:\n"
            "• Portfolio analysis and risk insights\n"
            "• Recovery strategy recommendations\n"
            "• Loan-specific intelligence\n"
            "• Customer sentiment and behaviour trends\n\n"
            "How can I assist you today?"
        ),
        timestamp    = now,
    )
    db.add(welcome)
    db.commit()

    return {
        "success":    True,
        "session_id": session.session_id,
        "session":    _format_officer_session(session, db),
        "message":    "Officer chat session created successfully.",
    }


# ─────────────────────────────────────────────
# GET /officer/chat/sessions/{session_id}
# ─────────────────────────────────────────────

@router.get("/chat/sessions/{session_id}")
def officer_get_session(
    session_id:   str,
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db),
):
    """Return a session with all its messages."""
    officer_id = current_user["user_id"]
    session = db.query(OfficerChatSession).filter(
        OfficerChatSession.session_id == session_id,
        OfficerChatSession.officer_id == officer_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages = (
        db.query(OfficerChatMessage)
        .filter(OfficerChatMessage.session_id == session_id)
        .order_by(OfficerChatMessage.timestamp.asc())
        .all()
    )
    return {
        "session_id":    session.session_id,
        "session_title": session.session_title,
        "created_at":    session.created_at,
        "last_updated":  session.last_updated,
        "messages": [
            {
                "message_id":   m.message_id,
                "role":         m.role,
                "message_text": m.message_text,
                "timestamp":    m.timestamp,
            }
            for m in messages
        ],
        "total_messages": len(messages),
    }


# ─────────────────────────────────────────────
# POST /officer/chat/sessions/{session_id}/message
# ─────────────────────────────────────────────

@router.post("/chat/sessions/{session_id}/message")
def officer_send_message(
    session_id:   str,
    body:         OfficerMessageRequest,
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db),
):
    """Send a message in an officer chat session and get AI response."""
    from datetime import datetime
    officer_id = current_user["user_id"]

    session = db.query(OfficerChatSession).filter(
        OfficerChatSession.session_id == session_id,
        OfficerChatSession.officer_id == officer_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Fetch conversation history BEFORE saving current message ──
    # Order by message_id (autoincrement) — never by timestamp which can collide
    prior_msgs = (
        db.query(OfficerChatMessage)
        .filter(OfficerChatMessage.session_id == session_id)
        .order_by(OfficerChatMessage.message_id.asc())
        .limit(12)
        .all()
    )
    history_str = ""
    for m in prior_msgs:
        role_label = "Officer" if m.role == "user" else "AI"
        history_str += f"[{role_label}]: {m.message_text}\n"

    # Save user message
    user_msg = OfficerChatMessage(
        session_id   = session_id,
        role         = "user",
        message_text = body.message.strip(),
        timestamp    = now,
    )
    db.add(user_msg)
    db.commit()

    # ── Build rich context for the AI ────────────────────────────
    all_loans   = db.query(Loan).all()
    high_risk   = [l for l in all_loans if l.risk_segment == "High"]
    medium_risk = [l for l in all_loans if l.risk_segment == "Medium"]
    low_risk    = [l for l in all_loans if l.risk_segment == "Low"]
    total_outstanding = sum(l.outstanding_balance for l in all_loans)
    overdue_loans = [l for l in all_loans if l.days_past_due > 0]
    overdue_outstanding = sum(l.outstanding_balance for l in overdue_loans)

    portfolio_summary = (
        f"Portfolio: {len(all_loans)} total loans | "
        f"Outstanding: ₹{total_outstanding:,.0f} | "
        f"High Risk: {len(high_risk)} | Medium Risk: {len(medium_risk)} | Low Risk: {len(low_risk)} | "
        f"Overdue Loans: {len(overdue_loans)} | Overdue Outstanding: ₹{overdue_outstanding:,.0f}"
    )

    # If loan_id provided, fetch specific loan data
    loan_context = ""
    if body.loan_id:
        specific_loan = db.query(Loan).filter(Loan.loan_id == body.loan_id).first()
        if specific_loan:
            cust = db.query(Customer).filter(Customer.customer_id == specific_loan.customer_id).first()

            # Payment history
            payments = (
                db.query(PaymentHistory)
                .filter(PaymentHistory.loan_id == body.loan_id)
                .order_by(PaymentHistory.payment_date.desc())
                .limit(6)
                .all()
            )
            payment_str = ", ".join(
                [f"₹{p.payment_amount:,.0f} on {p.payment_date}" for p in payments]
            ) or "No payment history"

            # Grace / restructure history
            grace_count = db.query(GraceRequest).filter(GraceRequest.loan_id == body.loan_id).count()
            rest_count  = db.query(RestructureRequest).filter(RestructureRequest.loan_id == body.loan_id).count()

            loan_context = (
                f"\nLoan Details for {body.loan_id}:\n"
                f"  Type: {specific_loan.loan_type}\n"
                f"  Amount: ₹{specific_loan.loan_amount:,.0f} | Outstanding: ₹{specific_loan.outstanding_balance:,.0f}\n"
                f"  EMI: ₹{specific_loan.emi_amount:,.0f} | Due Date: {specific_loan.emi_due_date}\n"
                f"  Days Past Due (DPD): {specific_loan.days_past_due}\n"
                f"  Risk Segment: {specific_loan.risk_segment}\n"
                f"  Self-Cure Probability: {(specific_loan.self_cure_probability or 0)*100:.0f}%\n"
                f"  Recommended Channel: {specific_loan.recommended_channel}\n"
            )
            if cust:
                loan_context += (
                    f"Customer: {cust.customer_name} | Credit Score: {cust.credit_score} | "
                    f"Income: ₹{cust.monthly_income:,.0f}/mo | Channel: {cust.preferred_channel}\n"
                )
            loan_context += (
                f"  Recent Payments: {payment_str}\n"
                f"  Grace Requests: {grace_count} | Restructure Requests: {rest_count}\n"
            )

    # ── Generate AI response ──────────────────────────────────────
    ai_text = _generate_officer_chat_response(
        question         = body.message.strip(),
        portfolio_summary= portfolio_summary,
        loan_context     = loan_context,
        history          = history_str,
        db               = db,
        loan_id          = body.loan_id,
    )

    # Save assistant response
    now2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assistant_msg = OfficerChatMessage(
        session_id   = session_id,
        role         = "assistant",
        message_text = ai_text,
        timestamp    = now2,
    )
    db.add(assistant_msg)

    # Update session title from first user question
    session.last_updated = now2
    user_msgs_count = db.query(OfficerChatMessage).filter(
        OfficerChatMessage.session_id == session_id,
        OfficerChatMessage.role == "user"
    ).count()
    if user_msgs_count == 1:  # first user message — set as title
        session.session_title = body.message.strip()[:60]

    db.commit()
    db.refresh(assistant_msg)

    return {
        "success":    True,
        "session_id": session_id,
        "user_message": {
            "role":         "user",
            "message_text": body.message.strip(),
            "timestamp":    now,
        },
        "ai_response": {
            "message_id":   assistant_msg.message_id,
            "role":         "assistant",
            "message_text": ai_text,
            "timestamp":    assistant_msg.timestamp,
        },
    }


# ─────────────────────────────────────────────
# DELETE /officer/chat/sessions/{session_id}
# ─────────────────────────────────────────────

@router.delete("/chat/sessions/{session_id}")
def officer_delete_session(
    session_id:   str,
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db),
):
    """Delete an officer chat session and all its messages."""
    officer_id = current_user["user_id"]
    session = db.query(OfficerChatSession).filter(
        OfficerChatSession.session_id == session_id,
        OfficerChatSession.officer_id == officer_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    db.query(OfficerChatMessage).filter(OfficerChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()

    return {"success": True, "message": f"Session {session_id} deleted."}


# ─────────────────────────────────────────────
# GET /officer/customer/{customer_id}/interactions
# Full interaction detail for officer modal view
# ─────────────────────────────────────────────

@router.get("/customer/{customer_id}/interactions")
def get_customer_interactions(
    customer_id:  str,
    current_user: dict    = Depends(get_current_officer),
    db:           Session = Depends(get_db),
):
    """
    Returns full interaction detail for a customer:
      - Chat: all chat sessions with full message threads (user + assistant bubbles)
      - Call: all InteractionHistory rows of type Call with full transcript
    Used by the officer sentiment modal pop-up.
    """
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found.")

    # ── Chat sessions: full thread per session ──────────────────
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.customer_id == customer_id)
        .order_by(ChatSession.last_updated.desc())
        .all()
    )

    chat_sessions = []
    for session in sessions:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.session_id)
            .order_by(ChatMessage.timestamp.asc())
            .all()
        )
        # Skip sessions with only the system welcome message (no real user messages)
        user_msgs = [m for m in messages if m.role == "user"]
        if not user_msgs:
            continue
        chat_sessions.append({
            "session_id":    session.session_id,
            "session_title": session.session_title,
            "created_at":    session.created_at,
            "last_updated":  session.last_updated,
            "messages": [
                {
                    "role":         m.role,
                    "message_text": m.message_text,
                    "timestamp":    m.timestamp,
                }
                for m in messages
            ],
        })

    # ── Call interactions: full transcript per call ─────────────
    call_interactions = (
        db.query(InteractionHistory)
        .filter(
            InteractionHistory.customer_id      == customer_id,
            InteractionHistory.interaction_type == "Call",
        )
        .order_by(InteractionHistory.interaction_time.desc())
        .all()
    )

    calls = [
        {
            "interaction_id":      i.interaction_id,
            "interaction_time":    i.interaction_time,
            "sentiment_score":     i.sentiment_score,
            "tonality_score":      i.tonality_score,
            "interaction_summary": i.interaction_summary,
            "conversation_text":   i.conversation_text,   # full Whisper transcript
        }
        for i in call_interactions
    ]

    return {
        "customer_id":   customer_id,
        "customer_name": customer.customer_name,
        "chat_sessions": chat_sessions,
        "calls":         calls,
    }


# ─────────────────────────────────────────────
# GET /officer/sentiment
# Portfolio-level + per-customer sentiment
# ─────────────────────────────────────────────

@router.get("/sentiment")
def get_portfolio_sentiment(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db),
):
    """
    Return sentiment overview:
      - Portfolio-level aggregation (positive/neutral/negative counts + %)
      - Per-customer latest sentiment + trend
    """
    from backend.agents.sentiment_agent import aggregate_sentiment, classify_tonality

    all_customers = db.query(Customer).all()
    # Only consider real data sources: live Chat and uploaded Call recordings.
    # Email / SMS / WhatsApp are excluded — we have no real pipeline for those.
    VALID_TYPES = {"Chat", "Call"}
    all_interactions = [
        i for i in db.query(InteractionHistory).all()
        if i.interaction_type in VALID_TYPES
    ]

    # Portfolio-level totals
    total = len(all_interactions)
    pos   = sum(1 for i in all_interactions if i.tonality_score == "Positive")
    neu   = sum(1 for i in all_interactions if i.tonality_score == "Neutral")
    neg   = sum(1 for i in all_interactions if i.tonality_score == "Negative")

    portfolio_summary = {
        "total_interactions": total,
        "positive":  pos,
        "neutral":   neu,
        "negative":  neg,
        "positive_pct": round(pos / total * 100, 1) if total else 0,
        "neutral_pct":  round(neu / total * 100, 1) if total else 0,
        "negative_pct": round(neg / total * 100, 1) if total else 0,
    }

    # Per-customer sentiment
    customer_sentiments = []
    for cust in all_customers:
        interactions = [
            i for i in all_interactions if i.customer_id == cust.customer_id
        ]
        interaction_dicts = [
            {"sentiment_score": i.sentiment_score, "tonality_score": i.tonality_score}
            for i in sorted(interactions, key=lambda x: x.interaction_time)
        ]
        agg  = aggregate_sentiment(interaction_dicts)
        last = sorted(interactions, key=lambda x: x.interaction_time, reverse=True)

        # Last-3 sentiment — what matters most for collections officers
        last3       = last[:3]
        last3_dicts = [
            {"sentiment_score": i.sentiment_score, "tonality_score": i.tonality_score}
            for i in last3
        ]
        agg3 = aggregate_sentiment(last3_dicts)

        customer_sentiments.append({
            "customer_id":        cust.customer_id,
            "customer_name":      cust.customer_name,
            "total_interactions": len(interactions),
            # All-time aggregate
            "average_sentiment":  agg["average_sentiment"],
            "dominant_tonality":  agg["dominant_tonality"],
            "sentiment_trend":    agg["sentiment_trend"],
            # Last-3 aggregate (shown in card header)
            "last3_sentiment":    agg3["average_sentiment"],
            "last3_tonality":     agg3["dominant_tonality"],
            "last3_trend":        agg3["sentiment_trend"],
            "last_interaction":   last[0].interaction_time if last else None,
            "last_tonality":      last[0].tonality_score  if last else "N/A",
            "recent_interactions": [
                {
                    "interaction_type":    i.interaction_type,
                    "interaction_time":    i.interaction_time,
                    "sentiment_score":     i.sentiment_score,
                    "tonality_score":      i.tonality_score,
                    "interaction_summary": i.interaction_summary,
                }
                for i in last3          # only last 3
            ],
        })

    # Sort: worst last-3 sentiment first (most at-risk based on recent behaviour)
    customer_sentiments.sort(key=lambda x: x["last3_sentiment"])

    return {
        "portfolio_sentiment": portfolio_summary,
        "customers":           customer_sentiments,
    }


# ─────────────────────────────────────────────
# POST /officer/sentiment/analyze-call
# Upload voice file → Whisper transcribe → sentiment
# ─────────────────────────────────────────────

from fastapi import UploadFile, File, Form
import tempfile, os

@router.post("/sentiment/analyze-call")
async def analyze_call_sentiment(
    customer_id:   str        = Form(...),
    audio_file:    UploadFile = File(...),
    current_user:  dict       = Depends(get_current_officer),
    db:            Session    = Depends(get_db),
):
    """
    Officer uploads a call recording (.mp3 / .wav / .m4a).
    Pipeline:
      1. Save audio to a temp file
      2. Transcribe with Whisper (base model, local, no API key)
      3. Run sentiment analysis on transcript
      4. Store in InteractionHistory as type "Call"
      5. Return transcript + sentiment result
    """
    from backend.agents.sentiment_agent import (
        calculate_sentiment_score, classify_tonality,
        generate_interaction_summary, analyze_and_store_interaction,
    )

    # Validate customer exists
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found.")

    # Validate file type
    allowed_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
    _, ext = os.path.splitext(audio_file.filename or "")
    # For browser recordings sent as .webm (no extension in filename), fallback to .webm
    if not ext:
        ext = ".webm"
    if ext.lower() not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save to temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await audio_file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio file: {e}")

    # Transcribe with Whisper
    try:
        import whisper
        model = whisper.load_model("base")          # ~150 MB, cached after first download
        result = model.transcribe(tmp_path)
        transcript = result.get("text", "").strip()
    except ImportError:
        os.unlink(tmp_path)
        raise HTTPException(
            status_code=501,
            detail="Whisper is not installed. Run: pip install openai-whisper"
        )
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not transcript:
        raise HTTPException(status_code=422, detail="Whisper returned an empty transcript. Check audio quality.")

    # Run sentiment pipeline + store in DB
    try:
        result_data = analyze_and_store_interaction(
            db               = db,
            customer_id      = customer_id,
            interaction_type = "Call",
            conversation_text= transcript,
            customer_name    = customer.customer_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {e}")

    return {
        "success":             True,
        "customer_id":         customer_id,
        "customer_name":       customer.customer_name,
        "transcript":          transcript,
        "sentiment_score":     result_data["sentiment_score"],
        "tonality":            result_data["tonality_score"],
        "interaction_summary": result_data["interaction_summary"],
        "interaction_id":      result_data["interaction_id"],
    }


# ─────────────────────────────────────────────
# Officer Chat – Primary AI Response Generator
# ─────────────────────────────────────────────

def _generate_officer_chat_response(
    question: str,
    portfolio_summary: str,
    loan_context: str,
    history: str,
    db: Session,
    loan_id: Optional[str] = None,
) -> str:
    """
    Calls Ollama with a proper multi-turn conversational prompt.
    Falls back to _officer_fallback if Ollama is unavailable or returns empty.
    """
    try:
        from backend.agents.llm_reasoning_agent import call_ollama, is_ollama_available

        if not is_ollama_available():
            return _officer_fallback(question, db, loan_id)

        system_prompt = (
            "You are a Collections Intelligence AI Assistant for bank officers at a collections department. "
            "This is a multi-turn conversation. The conversation history is provided so you can understand "
            "follow-up questions, corrections, and context from previous messages. "
            "IMPORTANT RULES:\n"
            "- Read the full conversation history before answering\n"
            "- If the officer corrects a previous request, update your answer accordingly\n"
            "- If the officer asks a follow-up like 'what are they?' refer to the prior AI response\n"
            "- Never repeat the question back. Do not include labels like 'Officer:' or 'Answer:'\n"
            "- Start your response directly with the answer\n"
            "- Be concise: maximum 4 sentences. Do not pad with generic advice\n"
            "- Only use numbers and facts explicitly present in the provided data\n"
            "- Never invent, estimate, or calculate values not given — if a figure is missing, say so\n"
            "- Do not use numbered lists or bullet points unless the officer specifically asks for a list\n"
            "- State exact figures (EMI, outstanding, DPD) from the data when asked\n"
            "- Do not give generic banking advice; base every answer strictly on the provided portfolio data"
        )

        loan_section = f"\n\nLoan Data:\n{loan_context}" if loan_context else ""
        history_section = (
            f"\n\nConversation so far:\n{history.strip()}"
            if history.strip()
            else ""
        )

        prompt = (
            f"Available Data:\n"
            f"Portfolio: {portfolio_summary}"
            f"{loan_section}"
            f"{history_section}\n\n"
            f"The officer now says: {question}\n\n"
            f"Respond directly as the AI assistant, considering the full conversation above."
        )

        response = call_ollama(prompt, system_prompt)
        if response and response.strip():
            # Strip any accidental "Officer:" / "AI:" / "Answer:" prefixes the LLM may add
            cleaned = response.strip()
            for prefix in ("Officer:", "AI:", "Answer:", "Assistant:"):
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):].lstrip()
            return cleaned

    except Exception as e:
        print(f"[OfficerChat] LLM call failed: {e}")

    # Ollama unavailable or returned empty — use structured fallback
    return _officer_fallback(question, db, loan_id)


# ─────────────────────────────────────────────
# Officer Fallback Response
# ─────────────────────────────────────────────

def _officer_fallback(message: str, db: Session, loan_id: Optional[str] = None) -> str:
    msg = message.lower()
    all_loans = db.query(Loan).all()
    high_risk = [l for l in all_loans if l.risk_segment == "High"]
    medium_risk = [l for l in all_loans if l.risk_segment == "Medium"]
    low_risk = [l for l in all_loans if l.risk_segment == "Low"]

    if loan_id:
        loan = db.query(Loan).filter(Loan.loan_id == loan_id).first()
        if loan:
            customer = db.query(Customer).filter(Customer.customer_id == loan.customer_id).first()
            name = customer.customer_name if customer else "the customer"
            if any(kw in msg for kw in ["grace", "approve", "eligible"]):
                if loan.days_past_due < 30:
                    return (f"For loan {loan_id} ({name}): With {loan.days_past_due} DPD, this customer may be eligible for a grace period. "
                            f"Risk segment is {loan.risk_segment}. Recommend approving a short grace period with follow-up.")
                return (f"Loan {loan_id} has {loan.days_past_due} DPD — grace approval should be carefully reviewed. "
                        f"Consider restructuring instead.")
            if any(kw in msg for kw in ["recovery", "strategy", "channel"]):
                return (f"For loan {loan_id}: Recommended channel is {loan.recommended_channel}. "
                        f"Self-cure probability: {(loan.self_cure_probability or 0)*100:.0f}%. "
                        f"Risk: {loan.risk_segment}. Outstanding: ₹{loan.outstanding_balance:,.0f}.")
            return (f"Loan {loan_id} belongs to {name}. Outstanding: ₹{loan.outstanding_balance:,.0f}, "
                    f"DPD: {loan.days_past_due}, Risk: {loan.risk_segment}.")

    if any(kw in msg for kw in ["high risk", "high-risk", "critical"]):
        return (f"There are {len(high_risk)} high-risk loans in the portfolio. "
                f"Total exposure: ₹{sum(l.outstanding_balance for l in high_risk):,.0f}. "
                f"Immediate outreach is recommended for these accounts.")
    if any(kw in msg for kw in ["overdue", "past due", "delinquent", "summary of overdue"]):
        overdue = [l for l in all_loans if l.days_past_due > 0]
        overdue_total = sum(l.outstanding_balance for l in overdue)
        overdue_lines = "\n".join(
            f"  • {l.loan_id}: ₹{l.outstanding_balance:,.0f} outstanding, {l.days_past_due} DPD, {l.risk_segment} risk"
            for l in sorted(overdue, key=lambda x: -x.days_past_due)
        )
        return (
            f"There are {len(overdue)} overdue loans with a total outstanding of ₹{overdue_total:,.0f}.\n"
            f"{overdue_lines}"
        )
    if any(kw in msg for kw in ["total", "portfolio", "outstanding"]):
        total = sum(l.outstanding_balance for l in all_loans)
        return (f"Portfolio summary: {len(all_loans)} total loans. "
                f"Total outstanding: ₹{total:,.0f}. "
                f"Risk distribution — High: {len(high_risk)}, Medium: {len(medium_risk)}, Low: {len(low_risk)}.")
    if any(kw in msg for kw in ["recovery", "strategy", "strateg"]):
        return ("Best recovery strategies for the current portfolio:\n"
                "1. High-risk accounts: Immediate phone outreach + restructuring offer.\n"
                "2. Medium-risk accounts: Email/SMS reminders + grace period eligibility check.\n"
                "3. Low-risk accounts: Automated payment reminders via preferred channel.")
    return ("I can help you with portfolio analysis, loan-specific intelligence, recovery strategies, and customer insights. "
            "Try asking about high-risk accounts, total outstanding, or specific loan IDs.")