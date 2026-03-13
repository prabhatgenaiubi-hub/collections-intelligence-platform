"""
Customer Preferences Router

Endpoints:
  GET  /preferences          → Get current preferred channel and language
  POST /preferences          → Save / update preferred channel and language
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from backend.db.database import get_db
from backend.db.models import Customer, CustomerPreference
from backend.routers.auth import get_current_customer

router = APIRouter(prefix="/preferences", tags=["Customer Preferences"])


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

VALID_CHANNELS = ["WhatsApp", "SMS", "Email", "Voice Call"]

VALID_LANGUAGES = ["English", "Hindi", "Tamil", "Telugu", "Kannada",
                   "Malayalam", "Bengali", "Marathi", "Gujarati", "Punjabi"]


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class PreferenceUpdate(BaseModel):
    preferred_channel:  Optional[str] = None
    preferred_language: Optional[str] = None


class PreferenceResponse(BaseModel):
    customer_id:        str
    preferred_channel:  str
    preferred_language: str
    updated_at:         str


# ─────────────────────────────────────────────
# GET /preferences
# ─────────────────────────────────────────────

@router.get("/", response_model=PreferenceResponse)
def get_preferences(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return the current communication and language preferences
    for the logged-in customer.
    """
    customer_id = current_user["user_id"]

    # Try preferences table first
    pref = db.query(CustomerPreference).filter(
        CustomerPreference.customer_id == customer_id
    ).first()

    if pref:
        return PreferenceResponse(
            customer_id        = pref.customer_id,
            preferred_channel  = pref.preferred_channel,
            preferred_language = pref.preferred_language,
            updated_at         = pref.updated_at,
        )

    # Fall back to customer table defaults
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    return PreferenceResponse(
        customer_id        = customer.customer_id,
        preferred_channel  = customer.preferred_channel  or "Email",
        preferred_language = customer.preferred_language or "English",
        updated_at         = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ─────────────────────────────────────────────
# POST /preferences
# ─────────────────────────────────────────────

@router.post("/", response_model=PreferenceResponse)
def save_preferences(
    body:         PreferenceUpdate,
    current_user: dict    = Depends(get_current_customer),
    db: Session           = Depends(get_db)
):
    """
    Save or update the customer's preferred communication channel
    and language.

    Validates:
      - Channel must be one of: WhatsApp, SMS, Email, Voice Call
      - Language must be one of the supported languages

    Updates both:
      - customer_preferences table
      - customers table (preferred_channel, preferred_language)
    """
    customer_id = current_user["user_id"]

    # ── Validate inputs ───────────────────────────────────────────
    if body.preferred_channel and body.preferred_channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code = 400,
            detail      = f"Invalid channel. Must be one of: {', '.join(VALID_CHANNELS)}"
        )

    if body.preferred_language and body.preferred_language not in VALID_LANGUAGES:
        raise HTTPException(
            status_code = 400,
            detail      = f"Invalid language. Must be one of: {', '.join(VALID_LANGUAGES)}"
        )

    if not body.preferred_channel and not body.preferred_language:
        raise HTTPException(
            status_code = 400,
            detail      = "At least one of preferred_channel or preferred_language must be provided."
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Update CustomerPreference table ───────────────────────────
    pref = db.query(CustomerPreference).filter(
        CustomerPreference.customer_id == customer_id
    ).first()

    if pref:
        # Update existing record
        if body.preferred_channel:
            pref.preferred_channel  = body.preferred_channel
        if body.preferred_language:
            pref.preferred_language = body.preferred_language
        pref.updated_at = now
    else:
        # Create new preference record
        customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")

        pref = CustomerPreference(
            customer_id        = customer_id,
            preferred_channel  = body.preferred_channel  or customer.preferred_channel  or "Email",
            preferred_language = body.preferred_language or customer.preferred_language or "English",
            updated_at         = now,
        )
        db.add(pref)

    # ── Sync to Customer table ────────────────────────────────────
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        if body.preferred_channel:
            customer.preferred_channel  = body.preferred_channel
        if body.preferred_language:
            customer.preferred_language = body.preferred_language

    db.commit()
    db.refresh(pref)

    return PreferenceResponse(
        customer_id        = pref.customer_id,
        preferred_channel  = pref.preferred_channel,
        preferred_language = pref.preferred_language,
        updated_at         = pref.updated_at,
    )


# ─────────────────────────────────────────────
# GET /preferences/options
# ─────────────────────────────────────────────

@router.get("/options")
def get_preference_options(
    current_user: dict = Depends(get_current_customer)
):
    """
    Return the list of valid channel and language options.
    Used to populate dropdowns in the UI.
    """
    return {
        "channels":  VALID_CHANNELS,
        "languages": VALID_LANGUAGES,
    }