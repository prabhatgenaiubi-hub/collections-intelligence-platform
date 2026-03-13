"""
Customer Router

Endpoints:
  GET  /customer/profile              → Get customer profile + relationship assessment
  GET  /customer/loans                → Get all loans for the customer
  GET  /customer/loans/{loan_id}      → Get loan details with analytics
  GET  /customer/loans/{loan_id}/payments → Get payment history for a loan
  GET  /customer/interactions         → Get interaction history
  GET  /customer/dashboard            → Get customer dashboard summary
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import (
    Customer, Loan, PaymentHistory, InteractionHistory,
    GraceRequest, RestructureRequest
)
from backend.routers.auth import get_current_customer
from backend.agents.collections_intelligence_agent import analyze_loan
from backend.agents.llm_reasoning_agent import generate_relationship_assessment

router = APIRouter(prefix="/customer", tags=["Customer"])


# ─────────────────────────────────────────────
# Helper: format loan dict
# ─────────────────────────────────────────────

def format_loan(loan: Loan, db: Session) -> dict:
    """Format a Loan ORM object into a response dict with grace/restructure status."""

    # Latest grace request status
    grace = (
        db.query(GraceRequest)
        .filter(GraceRequest.loan_id == loan.loan_id)
        .order_by(GraceRequest.request_date.desc())
        .first()
    )

    # Latest restructure request status
    restructure = (
        db.query(RestructureRequest)
        .filter(RestructureRequest.loan_id == loan.loan_id)
        .order_by(RestructureRequest.request_date.desc())
        .first()
    )

    return {
        "loan_id":               loan.loan_id,
        "loan_type":             loan.loan_type,
        "loan_amount":           loan.loan_amount,
        "interest_rate":         loan.interest_rate,
        "emi_amount":            loan.emi_amount,
        "emi_due_date":          loan.emi_due_date,
        "outstanding_balance":   loan.outstanding_balance,
        "days_past_due":         loan.days_past_due,
        "risk_segment":          loan.risk_segment,
        "self_cure_probability": loan.self_cure_probability,
        "recommended_channel":   loan.recommended_channel,
        "grace_status":          grace.request_status          if grace       else "None",
        "grace_comment":         grace.decision_comment        if grace       else None,
        "restructure_status":    restructure.request_status    if restructure else "None",
        "restructure_comment":   restructure.decision_comment  if restructure else None,
    }


# ─────────────────────────────────────────────
# GET /customer/profile
# ─────────────────────────────────────────────

@router.get("/profile")
def get_customer_profile(
    current_user: dict  = Depends(get_current_customer),
    db: Session         = Depends(get_db)
):
    """
    Return full customer profile including relationship assessment.
    Relationship assessment is generated/refreshed via LLM if needed.
    """
    customer_id = current_user["user_id"]

    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    # Fetch loans and payment history for assessment context
    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()
    loan_dicts = [format_loan(l, db) for l in loans]

    payments = []
    if loans:
        payments = (
            db.query(PaymentHistory)
            .filter(PaymentHistory.loan_id == loans[0].loan_id)
            .order_by(PaymentHistory.payment_date.desc())
            .limit(6)
            .all()
        )
        payments = [
            {
                "payment_date":   p.payment_date,
                "payment_amount": p.payment_amount,
                "payment_method": p.payment_method,
            }
            for p in payments
        ]

    interactions = (
        db.query(InteractionHistory)
        .filter(InteractionHistory.customer_id == customer_id)
        .order_by(InteractionHistory.interaction_time.desc())
        .limit(3)
        .all()
    )
    interaction_dicts = [
        {"interaction_type": i.interaction_type, "interaction_summary": i.interaction_summary}
        for i in interactions
    ]

    # Generate / refresh relationship assessment
    assessment = customer.relationship_assessment
    if not assessment:
        assessment = generate_relationship_assessment(
            customer_name   = customer.customer_name,
            loans           = loan_dicts,
            payment_history = payments,
            interactions    = interaction_dicts,
        )
        # Persist updated assessment
        customer.relationship_assessment = assessment
        db.commit()

    # Total loan exposure
    total_exposure = sum(l.outstanding_balance for l in loans)

    return {
        "customer_id":             customer.customer_id,
        "customer_name":           customer.customer_name,
        "mobile_number":           customer.mobile_number,
        "email_id":                customer.email_id,
        "preferred_language":      customer.preferred_language,
        "preferred_channel":       customer.preferred_channel,
        "credit_score":            customer.credit_score,
        "monthly_income":          customer.monthly_income,
        "total_loan_exposure":     total_exposure,
        "relationship_assessment": assessment,
        "total_loans":             len(loans),
    }


# ─────────────────────────────────────────────
# GET /customer/loans
# ─────────────────────────────────────────────

@router.get("/loans")
def get_customer_loans(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return all loans for the logged-in customer.
    Includes grace and restructure request status for each loan.
    """
    customer_id = current_user["user_id"]

    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()
    if not loans:
        return {"loans": [], "total": 0}

    return {
        "loans": [format_loan(l, db) for l in loans],
        "total": len(loans),
    }


# ─────────────────────────────────────────────
# GET /customer/loans/{loan_id}
# ─────────────────────────────────────────────

@router.get("/loans/{loan_id}")
def get_loan_detail(
    loan_id:      str,
    current_user: dict    = Depends(get_current_customer),
    db: Session           = Depends(get_db)
):
    """
    Return detailed loan information including:
      - Loan details
      - Payment history
      - Delinquency score
      - Risk analytics
      - AI recommendation
    """
    customer_id = current_user["user_id"]

    loan = db.query(Loan).filter(
        Loan.loan_id    == loan_id,
        Loan.customer_id == customer_id
    ).first()

    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found.")

    # Payment history
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
        }
        for p in payments
    ]

    # Customer info for analytics
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()

    # Run analytics
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

    # Grace & restructure status
    grace = (
        db.query(GraceRequest)
        .filter(GraceRequest.loan_id == loan_id)
        .order_by(GraceRequest.request_date.desc())
        .first()
    )
    restructure = (
        db.query(RestructureRequest)
        .filter(RestructureRequest.loan_id == loan_id)
        .order_by(RestructureRequest.request_date.desc())
        .first()
    )

    return {
        "loan_id":               loan.loan_id,
        "loan_type":             loan.loan_type,
        "loan_amount":           loan.loan_amount,
        "interest_rate":         loan.interest_rate,
        "emi_amount":            loan.emi_amount,
        "emi_due_date":          loan.emi_due_date,
        "outstanding_balance":   loan.outstanding_balance,
        "days_past_due":         loan.days_past_due,

        # Analytics
        "risk_segment":          analytics.get("risk_segment"),
        "self_cure_probability": analytics.get("self_cure_probability"),
        "delinquency_score":     analytics.get("delinquency_score"),
        "value_at_risk":         analytics.get("value_at_risk"),
        "payment_trend":         analytics.get("payment_trend"),
        "recovery_strategy":     analytics.get("recovery_strategy"),
        "recommended_channel":   analytics.get("recommended_channel"),

        # Payment history (for graph)
        "payment_history": payment_dicts,

        # Request statuses
        "grace_status":          grace.request_status       if grace       else "None",
        "grace_comment":         grace.decision_comment     if grace       else None,
        "restructure_status":    restructure.request_status if restructure else "None",
        "restructure_comment":   restructure.decision_comment if restructure else None,
    }


# ─────────────────────────────────────────────
# GET /customer/loans/{loan_id}/payments
# ─────────────────────────────────────────────

@router.get("/loans/{loan_id}/payments")
def get_loan_payments(
    loan_id:      str,
    current_user: dict  = Depends(get_current_customer),
    db: Session         = Depends(get_db)
):
    """
    Return full payment history for a specific loan.
    """
    customer_id = current_user["user_id"]

    loan = db.query(Loan).filter(
        Loan.loan_id     == loan_id,
        Loan.customer_id == customer_id
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail=f"Loan {loan_id} not found.")

    payments = (
        db.query(PaymentHistory)
        .filter(PaymentHistory.loan_id == loan_id)
        .order_by(PaymentHistory.payment_date.desc())
        .all()
    )

    return {
        "loan_id":  loan_id,
        "payments": [
            {
                "payment_id":     p.payment_id,
                "payment_date":   p.payment_date,
                "payment_amount": p.payment_amount,
                "payment_method": p.payment_method,
                "emi_amount":     loan.emi_amount,
            }
            for p in payments
        ],
        "total": len(payments),
    }


# ─────────────────────────────────────────────
# GET /customer/interactions
# ─────────────────────────────────────────────

@router.get("/interactions")
def get_customer_interactions(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return interaction history for the logged-in customer.
    """
    customer_id = current_user["user_id"]

    interactions = (
        db.query(InteractionHistory)
        .filter(InteractionHistory.customer_id == customer_id)
        .order_by(InteractionHistory.interaction_time.desc())
        .all()
    )

    return {
        "interactions": [
            {
                "interaction_id":      i.interaction_id,
                "interaction_type":    i.interaction_type,
                "interaction_time":    i.interaction_time,
                "sentiment_score":     i.sentiment_score,
                "tonality_score":      i.tonality_score,
                "interaction_summary": i.interaction_summary,
            }
            for i in interactions
        ],
        "total": len(interactions),
    }


# ─────────────────────────────────────────────
# GET /customer/dashboard
# ─────────────────────────────────────────────

@router.get("/dashboard")
def get_customer_dashboard(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return a dashboard summary for the customer portal home page.
    """
    customer_id = current_user["user_id"]

    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()

    total_exposure    = sum(l.outstanding_balance for l in loans)
    overdue_loans     = [l for l in loans if l.days_past_due > 0]
    pending_grace     = db.query(GraceRequest).filter(
        GraceRequest.customer_id  == customer_id,
        GraceRequest.request_status == "Pending"
    ).count()
    pending_restructure = db.query(RestructureRequest).filter(
        RestructureRequest.customer_id    == customer_id,
        RestructureRequest.request_status == "Pending"
    ).count()

    next_due = None
    if loans:
        next_due = min(loans, key=lambda l: l.emi_due_date).emi_due_date

    return {
        "customer_name":          customer.customer_name,
        "total_loans":            len(loans),
        "total_loan_exposure":    total_exposure,
        "overdue_loans":          len(overdue_loans),
        "next_emi_due_date":      next_due,
        "pending_grace_requests": pending_grace,
        "pending_restructure_requests": pending_restructure,
        "credit_score":           customer.credit_score,
        "preferred_channel":      customer.preferred_channel,
        "relationship_assessment": customer.relationship_assessment,
    }