"""
Grace Request Router

Customer Endpoints:
  POST /grace/request              → Submit a grace period request
  GET  /grace/my-requests          → Get all grace requests for logged-in customer

Bank Officer Endpoints:
  GET  /grace/pending              → Get all pending grace requests
  POST /grace/{request_id}/decide  → Approve or Reject a grace request

Shared:
  GET  /grace/{request_id}         → Get a specific grace request detail
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from backend.db.database import get_db
from backend.db.models import (
    GraceRequest, Loan, Customer
)
from backend.routers.auth import get_current_customer, get_current_officer, get_current_user
from backend.agents.policy_guardrail_agent import validate_grace_request
from backend.agents.collections_intelligence_agent import analyze_loan

router = APIRouter(prefix="/grace", tags=["Grace Requests"])


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class GraceRequestCreate(BaseModel):
    loan_id: str


class GraceDecision(BaseModel):
    decision:         str           # "Approved" | "Rejected"
    decision_comment: str


# ─────────────────────────────────────────────
# Helper: format grace request dict
# ─────────────────────────────────────────────

def format_grace_request(gr: GraceRequest, db: Session) -> dict:
    loan = db.query(Loan).filter(Loan.loan_id == gr.loan_id).first()
    customer = db.query(Customer).filter(Customer.customer_id == gr.customer_id).first()

    return {
        "request_id":       gr.request_id,
        "loan_id":          gr.loan_id,
        "customer_id":      gr.customer_id,
        "customer_name":    customer.customer_name if customer else "N/A",
        "loan_type":        loan.loan_type         if loan     else "N/A",
        "outstanding":      loan.outstanding_balance if loan   else 0.0,
        "emi_amount":       loan.emi_amount         if loan     else 0.0,
        "emi_due_date":     loan.emi_due_date        if loan     else "N/A",
        "days_past_due":    loan.days_past_due       if loan     else 0,
        "request_status":   gr.request_status,
        "decision_comment": gr.decision_comment,
        "request_date":     gr.request_date,
        "approved_by":      gr.approved_by,
        "decision_date":    gr.decision_date,
    }


# ─────────────────────────────────────────────
# POST /grace/request  (Customer)
# ─────────────────────────────────────────────

@router.post("/request", status_code=status.HTTP_201_CREATED)
def submit_grace_request(
    body:         GraceRequestCreate,
    current_user: dict    = Depends(get_current_customer),
    db: Session           = Depends(get_db)
):
    """
    Customer submits a grace period request for a loan.

    Validates:
      - Loan belongs to the customer
      - No existing Pending request for the same loan
      - Policy guardrail check (DPD, credit score, request count)
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

    # ── Check existing Pending request ────────────────────────────
    existing_pending = db.query(GraceRequest).filter(
        GraceRequest.loan_id        == body.loan_id,
        GraceRequest.request_status == "Pending"
    ).first()

    if existing_pending:
        raise HTTPException(
            status_code = 400,
            detail      = "A grace request is already pending for this loan. Please wait for the officer's decision."
        )

    # ── Count existing grace requests for this loan ───────────────
    existing_count = db.query(GraceRequest).filter(
        GraceRequest.loan_id == body.loan_id
    ).count()

    # ── Fetch customer for credit score ───────────────────────────
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()

    # ── Policy Guardrail Validation ───────────────────────────────
    policy_result = validate_grace_request(
        days_past_due       = loan.days_past_due,
        credit_score        = customer.credit_score or 650,
        outstanding_balance = loan.outstanding_balance,
        existing_grace_count = existing_count,
        risk_segment        = loan.risk_segment or "Medium",
    )

    if not policy_result["eligible"]:
        raise HTTPException(
            status_code = 400,
            detail      = {
                "message":    "Grace request does not meet eligibility criteria.",
                "violations": policy_result["violations"],
                "warnings":   policy_result["warnings"],
            }
        )

    # ── Create Grace Request ──────────────────────────────────────
    grace_request = GraceRequest(
        loan_id        = body.loan_id,
        customer_id    = customer_id,
        request_status = "Pending",
        request_date   = datetime.now().strftime("%Y-%m-%d"),
    )
    db.add(grace_request)
    db.commit()
    db.refresh(grace_request)

    return {
        "success":          True,
        "request_id":       grace_request.request_id,
        "message":          "Grace request submitted successfully. A bank officer will review it within 1-2 business days.",
        "policy_warnings":  policy_result["warnings"],
        "requires_review":  policy_result["requires_human_review"],
    }


# ─────────────────────────────────────────────
# GET /grace/my-requests  (Customer)
# ─────────────────────────────────────────────

@router.get("/my-requests")
def get_my_grace_requests(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return all grace requests submitted by the logged-in customer.
    """
    customer_id = current_user["user_id"]

    requests = (
        db.query(GraceRequest)
        .filter(GraceRequest.customer_id == customer_id)
        .order_by(GraceRequest.request_date.desc())
        .all()
    )

    return {
        "requests": [format_grace_request(gr, db) for gr in requests],
        "total":    len(requests),
    }


# ─────────────────────────────────────────────
# GET /grace/pending  (Bank Officer)
# ─────────────────────────────────────────────

@router.get("/pending")
def get_pending_grace_requests(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db)
):
    """
    Return all pending grace requests for bank officer review.
    """
    requests = (
        db.query(GraceRequest)
        .filter(GraceRequest.request_status == "Pending")
        .order_by(GraceRequest.request_date.asc())
        .all()
    )

    return {
        "requests": [format_grace_request(gr, db) for gr in requests],
        "total":    len(requests),
    }


# ─────────────────────────────────────────────
# GET /grace/all  (Bank Officer)
# ─────────────────────────────────────────────

@router.get("/all")
def get_all_grace_requests(
    current_user: dict = Depends(get_current_officer),
    db: Session        = Depends(get_db)
):
    """
    Return all grace requests (all statuses) for bank officer.
    """
    requests = (
        db.query(GraceRequest)
        .order_by(GraceRequest.request_date.desc())
        .all()
    )

    return {
        "requests": [format_grace_request(gr, db) for gr in requests],
        "total":    len(requests),
    }


# ─────────────────────────────────────────────
# GET /grace/{request_id}  (Any authenticated user)
# ─────────────────────────────────────────────

@router.get("/{request_id}")
def get_grace_request_detail(
    request_id:   str,
    current_user: dict  = Depends(get_current_user),
    db: Session         = Depends(get_db)
):
    """
    Return details for a specific grace request.
    Customers can only view their own requests.
    Officers can view any request.
    """
    gr = db.query(GraceRequest).filter(GraceRequest.request_id == request_id).first()
    if not gr:
        raise HTTPException(status_code=404, detail=f"Grace request {request_id} not found.")

    # Customers can only see their own requests
    if current_user["role"] == "customer" and gr.customer_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Run policy check to show eligibility context
    loan     = db.query(Loan).filter(Loan.loan_id == gr.loan_id).first()
    customer = db.query(Customer).filter(Customer.customer_id == gr.customer_id).first()
    existing_count = db.query(GraceRequest).filter(GraceRequest.loan_id == gr.loan_id).count()

    policy_result = {}
    if loan and customer:
        policy_result = validate_grace_request(
            days_past_due        = loan.days_past_due,
            credit_score         = customer.credit_score or 650,
            outstanding_balance  = loan.outstanding_balance,
            existing_grace_count = existing_count,
            risk_segment         = loan.risk_segment or "Medium",
        )

    return {
        **format_grace_request(gr, db),
        "policy_check": policy_result,
    }


# ─────────────────────────────────────────────
# POST /grace/{request_id}/decide  (Bank Officer)
# ─────────────────────────────────────────────

@router.post("/{request_id}/decide")
def decide_grace_request(
    request_id:   str,
    body:         GraceDecision,
    current_user: dict  = Depends(get_current_officer),
    db: Session         = Depends(get_db)
):
    """
    Bank officer approves or rejects a grace period request.

    - Updates request_status, decision_comment, approved_by, decision_date
    - Triggers outreach notification to customer (simulated)
    """
    if body.decision not in ["Approved", "Rejected"]:
        raise HTTPException(
            status_code = 400,
            detail      = "Decision must be 'Approved' or 'Rejected'."
        )

    gr = db.query(GraceRequest).filter(GraceRequest.request_id == request_id).first()
    if not gr:
        raise HTTPException(status_code=404, detail=f"Grace request {request_id} not found.")

    if gr.request_status != "Pending":
        raise HTTPException(
            status_code = 400,
            detail      = f"Grace request is already {gr.request_status}. Cannot modify."
        )

    # ── Update Decision ───────────────────────────────────────────
    gr.request_status   = body.decision
    gr.decision_comment = body.decision_comment
    gr.approved_by      = current_user["user_id"]
    gr.decision_date    = datetime.now().strftime("%Y-%m-%d")
    db.commit()
    db.refresh(gr)

    # ── Trigger Outreach Notification ─────────────────────────────
    try:
        from backend.agents.outreach_agent import send_outreach
        loan     = db.query(Loan).filter(Loan.loan_id == gr.loan_id).first()
        customer = db.query(Customer).filter(Customer.customer_id == gr.customer_id).first()

        if loan and customer:
            msg_type = "grace_approved" if body.decision == "Approved" else "grace_rejected"
            send_outreach(
                db            = db,
                customer_id   = gr.customer_id,
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
        print(f"[GraceRouter] Outreach notification failed (non-critical): {e}")

    return {
        "success":          True,
        "request_id":       gr.request_id,
        "decision":         gr.request_status,
        "decision_comment": gr.decision_comment,
        "decided_by":       gr.approved_by,
        "decision_date":    gr.decision_date,
        "message":          f"Grace request has been {gr.request_status} successfully.",
    }