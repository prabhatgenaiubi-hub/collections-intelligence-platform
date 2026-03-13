from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from backend.db.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# Customer Table
# ─────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"

    customer_id         = Column(String, primary_key=True, default=gen_uuid)
    customer_name       = Column(String, nullable=False)
    mobile_number       = Column(String, nullable=False)
    email_id            = Column(String, nullable=False)
    preferred_language  = Column(String, default="English")
    preferred_channel   = Column(String, default="Email")
    relationship_assessment = Column(Text, nullable=True)
    credit_score        = Column(Integer, nullable=True)
    monthly_income      = Column(Float, nullable=True)
    password            = Column(String, nullable=False, default="password123")

    loans               = relationship("Loan", back_populates="customer")
    interactions        = relationship("InteractionHistory", back_populates="customer")
    grace_requests      = relationship("GraceRequest", back_populates="customer")
    restructure_requests = relationship("RestructureRequest", back_populates="customer")
    chat_sessions       = relationship("ChatSession", back_populates="customer")
    preferences         = relationship("CustomerPreference", back_populates="customer", uselist=False)


# ─────────────────────────────────────────────
# Loan Table
# ─────────────────────────────────────────────
class Loan(Base):
    __tablename__ = "loans"

    loan_id              = Column(String, primary_key=True, default=gen_uuid)
    customer_id          = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    loan_type            = Column(String, nullable=False)
    loan_amount          = Column(Float, nullable=False)
    interest_rate        = Column(Float, nullable=False)
    emi_amount           = Column(Float, nullable=False)
    emi_due_date         = Column(String, nullable=False)
    outstanding_balance  = Column(Float, nullable=False)
    days_past_due        = Column(Integer, default=0)
    risk_segment         = Column(String, default="Low")        # Low / Medium / High
    self_cure_probability = Column(Float, default=0.5)
    recommended_channel  = Column(String, default="Email")

    customer             = relationship("Customer", back_populates="loans")
    payment_history      = relationship("PaymentHistory", back_populates="loan")
    grace_requests       = relationship("GraceRequest", back_populates="loan")
    restructure_requests = relationship("RestructureRequest", back_populates="loan")


# ─────────────────────────────────────────────
# Payment History Table
# ─────────────────────────────────────────────
class PaymentHistory(Base):
    __tablename__ = "payment_history"

    payment_id      = Column(String, primary_key=True, default=gen_uuid)
    loan_id         = Column(String, ForeignKey("loans.loan_id"), nullable=False)
    payment_date    = Column(String, nullable=False)
    payment_amount  = Column(Float, nullable=False)
    payment_method  = Column(String, default="Bank Transfer")

    loan            = relationship("Loan", back_populates="payment_history")


# ─────────────────────────────────────────────
# Interaction History Table
# ─────────────────────────────────────────────
class InteractionHistory(Base):
    __tablename__ = "interaction_history"

    interaction_id      = Column(String, primary_key=True, default=gen_uuid)
    customer_id         = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    interaction_type    = Column(String, nullable=False)   # Call / Chat / Email / SMS
    interaction_time    = Column(String, nullable=False)
    conversation_text   = Column(Text, nullable=True)
    sentiment_score     = Column(Float, default=0.0)       # -1.0 to 1.0
    tonality_score      = Column(String, default="Neutral") # Positive / Neutral / Negative
    interaction_summary = Column(Text, nullable=True)

    customer            = relationship("Customer", back_populates="interactions")


# ─────────────────────────────────────────────
# Grace Requests Table
# ─────────────────────────────────────────────
class GraceRequest(Base):
    __tablename__ = "grace_requests"

    request_id       = Column(String, primary_key=True, default=gen_uuid)
    loan_id          = Column(String, ForeignKey("loans.loan_id"), nullable=False)
    customer_id      = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    request_status   = Column(String, default="Pending")   # Pending / Approved / Rejected
    decision_comment = Column(Text, nullable=True)
    request_date     = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d"))
    approved_by      = Column(String, nullable=True)
    decision_date    = Column(String, nullable=True)

    loan             = relationship("Loan", back_populates="grace_requests")
    customer         = relationship("Customer", back_populates="grace_requests")


# ─────────────────────────────────────────────
# Restructure Requests Table
# ─────────────────────────────────────────────
class RestructureRequest(Base):
    __tablename__ = "restructure_requests"

    request_id       = Column(String, primary_key=True, default=gen_uuid)
    loan_id          = Column(String, ForeignKey("loans.loan_id"), nullable=False)
    customer_id      = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    request_status   = Column(String, default="Pending")   # Pending / Approved / Rejected
    decision_comment = Column(Text, nullable=True)
    request_date     = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d"))
    approved_by      = Column(String, nullable=True)
    decision_date    = Column(String, nullable=True)

    loan             = relationship("Loan", back_populates="restructure_requests")
    customer         = relationship("Customer", back_populates="restructure_requests")


# ─────────────────────────────────────────────
# Customer Preferences Table
# ─────────────────────────────────────────────
class CustomerPreference(Base):
    __tablename__ = "customer_preferences"

    customer_id        = Column(String, ForeignKey("customers.customer_id"), primary_key=True)
    preferred_channel  = Column(String, default="Email")
    preferred_language = Column(String, default="English")
    updated_at         = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    customer           = relationship("Customer", back_populates="preferences")


# ─────────────────────────────────────────────
# Chat Sessions Table
# ─────────────────────────────────────────────
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id    = Column(String, primary_key=True, default=gen_uuid)
    customer_id   = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    session_title = Column(String, default="New Chat")
    created_at    = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    last_updated  = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    customer      = relationship("Customer", back_populates="chat_sessions")
    messages      = relationship("ChatMessage", back_populates="session")


# ─────────────────────────────────────────────
# Chat Messages Table
# ─────────────────────────────────────────────
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id   = Column(String, primary_key=True, default=gen_uuid)
    session_id   = Column(String, ForeignKey("chat_sessions.session_id"), nullable=False)
    role         = Column(String, nullable=False)   # user / assistant / system
    message_text = Column(Text, nullable=False)
    timestamp    = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    session      = relationship("ChatSession", back_populates="messages")


# ─────────────────────────────────────────────
# Bank Officer Table
# ─────────────────────────────────────────────
class BankOfficer(Base):
    __tablename__ = "bank_officers"

    officer_id   = Column(String, primary_key=True, default=gen_uuid)
    officer_name = Column(String, nullable=False)
    email        = Column(String, nullable=False)
    password     = Column(String, nullable=False, default="officer123")
    department   = Column(String, default="Collections")