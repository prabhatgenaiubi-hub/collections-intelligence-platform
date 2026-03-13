"""
Authentication Router

Endpoints:
  POST /auth/login       → Login for Customer or Bank Officer
  POST /auth/logout      → Logout (client-side token clear)
  GET  /auth/me          → Get current logged-in user info

Authentication uses simple token-based approach (JWT-like dict for prototype).
In production, replace with proper JWT + OAuth2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
import hashlib
import json
import base64

from backend.db.database import get_db
from backend.db.models import Customer, BankOfficer

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    user_id:  str
    password: str
    role:     str       # "customer" | "officer"


class LoginResponse(BaseModel):
    success:      bool
    token:        str
    role:         str
    user_id:      str
    name:         str
    message:      str


class UserInfo(BaseModel):
    user_id:  str
    name:     str
    role:     str
    email:    str


# ─────────────────────────────────────────────
# Simple Token Utilities (Prototype)
# ─────────────────────────────────────────────

def create_token(user_id: str, role: str, name: str) -> str:
    """
    Create a simple base64-encoded token for prototype use.
    In production, use python-jose JWT with secret key signing.
    """
    payload = {
        "user_id":   user_id,
        "role":      role,
        "name":      name,
        "issued_at": datetime.now().isoformat(),
        "expires":   (datetime.now() + timedelta(hours=8)).isoformat(),
    }
    token_str  = json.dumps(payload)
    token_b64  = base64.b64encode(token_str.encode()).decode()
    return token_b64


def decode_token(token: str) -> dict:
    """
    Decode a prototype base64 token.
    Returns None if invalid or expired.
    """
    try:
        decoded    = base64.b64decode(token.encode()).decode()
        payload    = json.loads(decoded)
        expires_at = datetime.fromisoformat(payload["expires"])
        if datetime.now() > expires_at:
            return None
        return payload
    except Exception:
        return None


def verify_password(plain: str, stored: str) -> bool:
    """
    Simple password verification for prototype.
    In production, use bcrypt hashing.
    """
    return plain == stored


# ─────────────────────────────────────────────
# Token Dependency (for protected routes)
# ─────────────────────────────────────────────

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> dict:
    """
    FastAPI dependency to extract and validate the current user from token.
    Use this as a dependency in protected routes.
    """
    if not credentials:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Authentication token missing. Please log in.",
        )

    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Invalid or expired token. Please log in again.",
        )

    return payload


def get_current_customer(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensure the current user is a customer."""
    if current_user.get("role") != "customer":
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Access denied. Customer role required.",
        )
    return current_user


def get_current_officer(current_user: dict = Depends(get_current_user)) -> dict:
    """Ensure the current user is a bank officer."""
    if current_user.get("role") != "officer":
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Access denied. Bank Officer role required.",
        )
    return current_user


# ─────────────────────────────────────────────
# Login Endpoint
# ─────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login endpoint for both customers and bank officers.

    Customer login:  user_id = customer_id, role = "customer"
    Officer login:   user_id = officer_id,  role = "officer"

    Returns a token on success.
    """

    if request.role == "customer":
        # ── Customer Auth ──────────────────────────────────────────
        customer = db.query(Customer).filter(
            Customer.customer_id == request.user_id
        ).first()

        if not customer:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail      = f"Customer ID '{request.user_id}' not found."
            )

        if not verify_password(request.password, customer.password):
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail      = "Invalid password. Please try again."
            )

        token = create_token(
            user_id = customer.customer_id,
            role    = "customer",
            name    = customer.customer_name,
        )

        return LoginResponse(
            success = True,
            token   = token,
            role    = "customer",
            user_id = customer.customer_id,
            name    = customer.customer_name,
            message = f"Welcome, {customer.customer_name}!",
        )

    elif request.role == "officer":
        # ── Bank Officer Auth ──────────────────────────────────────
        officer = db.query(BankOfficer).filter(
            BankOfficer.officer_id == request.user_id
        ).first()

        if not officer:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail      = f"Officer ID '{request.user_id}' not found."
            )

        if not verify_password(request.password, officer.password):
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail      = "Invalid password. Please try again."
            )

        token = create_token(
            user_id = officer.officer_id,
            role    = "officer",
            name    = officer.officer_name,
        )

        return LoginResponse(
            success = True,
            token   = token,
            role    = "officer",
            user_id = officer.officer_id,
            name    = officer.officer_name,
            message = f"Welcome, {officer.officer_name}!",
        )

    else:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "Invalid role. Must be 'customer' or 'officer'."
        )


# ─────────────────────────────────────────────
# Get Current User Info
# ─────────────────────────────────────────────

@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session        = Depends(get_db)
):
    """
    Return the current logged-in user's profile information.
    """
    role    = current_user.get("role")
    user_id = current_user.get("user_id")

    if role == "customer":
        customer = db.query(Customer).filter(Customer.customer_id == user_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")
        return {
            "user_id": customer.customer_id,
            "name":    customer.customer_name,
            "role":    "customer",
            "email":   customer.email_id,
            "mobile":  customer.mobile_number,
        }

    elif role == "officer":
        officer = db.query(BankOfficer).filter(BankOfficer.officer_id == user_id).first()
        if not officer:
            raise HTTPException(status_code=404, detail="Officer not found.")
        return {
            "user_id":    officer.officer_id,
            "name":       officer.officer_name,
            "role":       "officer",
            "email":      officer.email,
            "department": officer.department,
        }

    raise HTTPException(status_code=400, detail="Invalid role in token.")


# ─────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint.
    For prototype, token invalidation is handled client-side.
    In production, maintain a server-side token blacklist.
    """
    return {
        "success": True,
        "message": f"Goodbye, {current_user.get('name', 'User')}! You have been logged out successfully."
    }