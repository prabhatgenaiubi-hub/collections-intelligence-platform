"""
Restructure Request Router

Customer Endpoints:
  POST /restructure/request              → Submit a loan restructure request
  GET  /restructure/my-requests          → Get all restructure requests for logged-in customer

Bank Officer Endpoints:
  GET  /restructure/pending              → Get all pending restructure requests
  GET  /restructure/all                  → Get all restructure requests
  POST /restructure/{request_id}/decide  → Approve or Reject a restructure request

Shared:
  GET  /restructure/{request_id}         → Get a specific restructure request detail
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from backend.db.database import get_db
from backend.db.models import (
    RestructureRequest, Loan, Customer, PaymentHistory
)
from backend.routers.auth import get_current_customer, get_current_officer, get_current_user
from backend.agents.policy_guardrail_agent import validate_restructure_request

router = APIRouter(prefix="/restructure", tags=["Restructure Requests"])


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class RestructureRequestCreate(BaseModel):
    loan_id: str


class RestructureDecision(BaseModel):
    decision:         str        # "Approved" | "Rejected"
    decision_comment: str


# ─────────────────────────────────────────────
# Helper: format restructure request dict
# ─────────────────────────────────────────────

def format_restructure_request(rr: RestructureRequest, db: Session) -> dict:
    loan     = db.query(Loan).filter(Loan.loan_id == rr.loan_id).first()
    customer = db.query(Customer).filter(Customer.customer_id == rr.customer_id).first()

    return {
        "request_id":       rr.request_id,
        "loan_id":          rr.loan_id,
        "customer_id":      rr.customer_id,
        "customer_name":    customer.customer_name    if customer else "N/A",
        "loan_type":        loan.loan_type            if loan     else "N/A",
        "loan_amount":      loan.loan_amount          if loan     else 0.0,
        "outstanding":      loan.outstanding_balance  if loan     else 0.0,
        "emi_amount":       loan.emi_amount           if loan     else 0.0,
        "emi_due_date":     loan.emi_due_date         if loan     else "N/A",
        "days_past_due":    loan.days_past_due        if loan     else 0,
        "risk_segment":     loan.risk_segment         if loan     else "N/A",
        "request_status":   rr.request_status,
        "decision_comment": rr.decision_comment,
        "request_date":     rr.request_date,
        "approved_by":      rr.approved_by,
        "decision_date":    rr.decision_date,
    }


# ─────────────────────────────────────────────
# POST /restructure/request  (Customer)
# ─────────────────────────────────────────────

@router.post("/request", status_code=status.HTTP_201_CREATED)
def submit_restructure_request(
    body:         RestructureRequestCreate,
    current_user: dict    = Depends(get_current_customer),
    db: Session           = Depends(get_db)
):
    """
    Customer submits a loan restructure request.

    Validates:
      - Loan belongs to the customer
      - No existing Pending restructure request for the same loan
      - Policy guardrail check (DPD range, credit score, missed payments)
    """
    customer_id = current_user["user_id"]

    # ── Fetch Loan ────────────────────────────────────────────────
    loan = db.query(Loan).filter(
        Loan.loan_id     == body.loan_id,
        Loan.customer_id == customer_id
    ).first()

    if not loan:
        raise HTTPException(
            status_code = 404,
            detail      = f"Loan {body.loan_id} not found for your account."
        )

    # ── Check for existing Pending request ────────────────────────
    existing_pending = db.query(RestructureRequest).filter(
        RestructureRequest.loan_id        == body.loan_id,
        RestructureRequest.request_status == "Pending"
    ).first()

    if existing_pending:
        raise HTTPException(
            status_code = 400,
            detail      = "A restructure request is already pending for this loan. Please wait for the officer's decision."
        )

    # ── Count missed payments ─────────────────────────────────────
    payments = (
        db.query(PaymentHistory)
        .filter(PaymentHistory.loan_id == body.loan_id)
        .all()
    )
    missed_payments = sum(
        1 for p in payments if p.payment_amount < loan.emi_amount * 0.95
    )

    # ── Fetch customer for credit score ───────────────────────────
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()

    # ── Policy Guardrail Validation ───────────────────────────────
    policy_result = validate_restructure_request(
        days_past_due       = loan.days_past_due,
        credit_score        = customer.credit_score or 650,
        outstanding_balance = loan.outstanding_balance,
        risk_segment        = loan.risk_segment or "Medium",
        missed_payments     = missed_payments,
    )

    if not policy_result["eligible"]:
        raise HTTPException(
            status_code = 400,
            detail      = {
                "message":    "Restructure request does not meet eligibility criteria.",
                "violations": policy_result["violations"],
                "warnings":   policy_result["warnings"],
            }
        )

    # ── Create Restructure Request ────────────────────────────────
    restructure_request = RestructureRequest(
        loan_id        = body.loan_id,
        customer_id    = customer_id,
        request_status = "Pending",
        request_date   = datetime.now().strftime("%Y-%m-%d"),
    )
    db.add(restructure_request)
    db.commit()
    db.refresh(restructure_request)

    return {
        "success":         True,
        "request_id":      restructure_request.request_id,
        "message":         "Restructure request submitted successfully. A bank officer will review it within 2 business days.",
        "policy_warnings": policy_result["warnings"],
        "requires_review": policy_result["requires_human_review"],
    }


# ─────────────────────────────────────────────
# GET /restructure/my-requests  (Customer)
# ─────────────────────────────────────────────

@router.get("/my-requests")
def get_my_restructure_requests(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return all restructure requests submitted by the logged-in customer.
    """
    customer_id = current_user["user_id"]

    requests = (
        db.query(RestructureRequest)
        .filter(RestructureRequest.customer_id == customer_id)
        .order_by(RestructureRequest.request_date.desc())
        .all()
    )

    return {
        "requests": [format_restructure_request(rr, db) for rr in requests],
        "total":    len(requests),
    }


# ─────────────────────────────────────────────
# GET /restructure/pending  (Bank Officer)
# ─────────────────────────────────────────────

@router.get("/pending")
def get_pending_restructure_requests(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db)
):
    """
    Return all pending restructure requests for bank officer review.
    """
    requests = (
        db.query(RestructureRequest)
        .filter(RestructureRequest.request_status == "Pending")
        .order_by(RestructureRequest.request_date.asc())
        .all()
    )

    return {
        "requests": [format_restructure_request(rr, db) for rr in requests],
        "total":    len(requests),
    }


# ─────────────────────────────────────────────
# GET /restructure/all  (Bank Officer)
# ─────────────────────────────────────────────

@router.get("/all")
def get_all_restructure_requests(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db)
):
    """
    Return all restructure requests (all statuses) for bank officer.
    """
    requests = (
        db.query(RestructureRequest)
        .order_by(RestructureRequest.request_date.desc())
        .all()
    )

    return {
        "requests": [format_restructure_request(rr, db) for rr in requests],
        "total":    len(requests),
    }


# ─────────────────────────────────────────────
# GET /restructure/{request_id}  (Any authenticated user)
# ─────────────────────────────────────────────

@router.get("/{request_id}")
def get_restructure_request_detail(
    request_id:   str,
    current_user: dict  = Depends(get_current_user),
    db: Session         = Depends(get_db)
):
    """
    Return details for a specific restructure request.
    Customers can only view their own requests.
    Officers can view any request.
    """
    rr = db.query(RestructureRequest).filter(
        RestructureRequest.request_id == request_id
    ).first()

    if not rr:
        raise HTTPException(status_code=404, detail=f"Restructure request {request_id} not found.")

    # Customers can only access their own requests
    if current_user["role"] == "customer" and rr.customer_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Run policy check to show eligibility context
    loan     = db.query(Loan).filter(Loan.loan_id == rr.loan_id).first()
    customer = db.query(Customer).filter(Customer.customer_id == rr.customer_id).first()

    policy_result = {}
    if loan and customer:
        payments = db.query(PaymentHistory).filter(
            PaymentHistory.loan_id == rr.loan_id
        ).all()
        missed = sum(1 for p in payments if p.payment_amount < loan.emi_amount * 0.95)

        policy_result = validate_restructure_request(
            days_past_due       = loan.days_past_due,
            credit_score        = customer.credit_score or 650,
            outstanding_balance = loan.outstanding_balance,
            risk_segment        = loan.risk_segment or "Medium",
            missed_payments     = missed,
        )

    return {
        **format_restructure_request(rr, db),
        "policy_check": policy_result,
    }


# ─────────────────────────────────────────────
# POST /restructure/{request_id}/decide  (Bank Officer)
# ─────────────────────────────────────────────

@router.post("/{request_id}/decide")
def decide_restructure_request(
    request_id:   str,
    body:         RestructureDecision,
    current_user: dict  = Depends(get_current_officer),
    db: Session         = Depends(get_db)
):
    """
    Bank officer approves or rejects a loan restructure request.

    - Updates request_status, decision_comment, approved_by, decision_date
    - Triggers outreach notification to customer (simulated)
    """
    if body.decision not in ["Approved", "Rejected"]:
        raise HTTPException(
            status_code = 400,
            detail      = "Decision must be 'Approved' or 'Rejected'."
        )

    rr = db.query(RestructureRequest).filter(
        RestructureRequest.request_id == request_id
    ).first()

    if not rr:
        raise HTTPException(status_code=404, detail=f"Restructure request {request_id} not found.")

    if rr.request_status != "Pending":
        raise HTTPException(
            status_code = 400,
            detail      = f"Restructure request is already {rr.request_status}. Cannot modify."
        )

    # ── Update Decision ───────────────────────────────────────────
    rr.request_status   = body.decision
    rr.decision_comment = body.decision_comment
    rr.approved_by      = current_user["user_id"]
    rr.decision_date    = datetime.now().strftime("%Y-%m-%d")
    db.commit()
    db.refresh(rr)

    # ── Trigger Outreach Notification ─────────────────────────────
    try:
        from backend.agents.outreach_agent import send_outreach
        loan     = db.query(Loan).filter(Loan.loan_id == rr.loan_id).first()
        customer = db.query(Customer).filter(Customer.customer_id == rr.customer_id).first()

        if loan and customer:
            msg_type = "grace_approved" if body.decision == "Approved" else "grace_rejected"
            send_outreach(
                db            = db,
                customer_id   = rr.customer_id,
                customer_name = customer.customer_name,
                channel       = customer.preferred_channel or "Email",
                message_type  = msg_type,
                loan_id       = loan.loan_id,
                emi_amount    = loan.emi_amount,
                contact       = customer.mobile_number or customer.email_id,
                due_date      = loan.emi_due_date,
                dpd           = loan.days_past_due,
                outstanding   = loan.outstanding_balance,
                comment       = body.decision_comment,
            )
    except Exception as e:
        print(f"[RestructureRouter] Outreach notification failed (non-critical): {e}")

    return {
        "success":          True,
        "request_id":       rr.request_id,
        "decision":         rr.request_status,
        "decision_comment": rr.decision_comment,
        "decided_by":       rr.approved_by,
        "decision_date":    rr.decision_date,
        "message":          f"Restructure request has been {rr.request_status} successfully.",
    }