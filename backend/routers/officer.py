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

from backend.db.database import get_db
from backend.db.models import (
    Customer, Loan, PaymentHistory,
    InteractionHistory, GraceRequest, RestructureRequest
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