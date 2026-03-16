"""
Chat Router

Customer AI Assistant Endpoints:
  GET  /chat/sessions                        → List all chat sessions for customer
  POST /chat/sessions                        → Create a new chat session
  GET  /chat/sessions/{session_id}           → Get session details + messages
  POST /chat/sessions/{session_id}/message   → Send a message and get AI response
  DELETE /chat/sessions/{session_id}         → Delete a chat session

All chat responses are powered by the LangGraph chat workflow
(Context Memory Agent → LLM Reasoning Agent).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from backend.db.database import get_db
from backend.db.models import ChatSession, ChatMessage, Customer, Loan
from backend.routers.auth import get_current_customer
from backend.services.context_builder import ContextBuilder
from backend.app.services.memory_extractor import MemoryExtractor
from backend.agents.llm_reasoning_agent import call_ollama, is_ollama_available

router = APIRouter(prefix="/chat", tags=["Chat Assistant"])


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class NewSessionRequest(BaseModel):
    session_title: Optional[str] = "New Chat"


class SendMessageRequest(BaseModel):
    message:  str
    loan_id:  Optional[str] = None     # optional loan context


# ─────────────────────────────────────────────
# Helper: format session
# ─────────────────────────────────────────────

def format_session(session: ChatSession, db: Session) -> dict:
    message_count = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.session_id
    ).count()

    # Get last message preview
    last_msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.session_id)
        .order_by(ChatMessage.timestamp.desc())
        .first()
    )

    return {
        "session_id":    session.session_id,
        "session_title": session.session_title,
        "created_at":    session.created_at,
        "last_updated":  session.last_updated,
        "message_count": message_count,
        "last_message":  last_msg.message_text[:80] + "..." if last_msg and len(last_msg.message_text) > 80 else (last_msg.message_text if last_msg else None),
    }


# ─────────────────────────────────────────────
# GET /chat/sessions  (Customer)
# ─────────────────────────────────────────────

@router.get("/sessions")
def list_chat_sessions(
    current_user: dict = Depends(get_current_customer),
    db: Session        = Depends(get_db)
):
    """
    Return all chat sessions for the logged-in customer.
    Ordered by last_updated descending (most recent first).
    """
    customer_id = current_user["user_id"]

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.customer_id == customer_id)
        .order_by(ChatSession.last_updated.desc())
        .all()
    )

    return {
        "sessions": [format_session(s, db) for s in sessions],
        "total":    len(sessions),
    }


# ─────────────────────────────────────────────
# POST /chat/sessions  (Customer)
# ─────────────────────────────────────────────

@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_chat_session(
    body:         NewSessionRequest,
    current_user: dict    = Depends(get_current_customer),
    db: Session           = Depends(get_db)
):
    """
    Create a new chat session for the customer.
    Returns the new session with a system welcome message.
    """
    customer_id = current_user["user_id"]
    customer    = db.query(Customer).filter(Customer.customer_id == customer_id).first()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create session
    session = ChatSession(
        customer_id   = customer_id,
        session_title = body.session_title or "New Chat",
        created_at    = now,
        last_updated  = now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Add system welcome message
    welcome_text = (
        f"Hello{', ' + customer.customer_name if customer else ''}! "
        "I'm your AI banking assistant. I can help you with:\n"
        "• EMI payment information\n"
        "• Outstanding balance queries\n"
        "• Grace period eligibility\n"
        "• Loan restructuring options\n\n"
        "How can I assist you today?"
    )

    system_msg = ChatMessage(
        session_id   = session.session_id,
        role         = "assistant",
        message_text = welcome_text,
        timestamp    = now,
    )
    db.add(system_msg)
    db.commit()

    return {
        "success":    True,
        "session_id": session.session_id,
        "session":    format_session(session, db),
        "message":    "Chat session created successfully.",
    }


# ─────────────────────────────────────────────
# GET /chat/sessions/{session_id}  (Customer)
# ─────────────────────────────────────────────

@router.get("/sessions/{session_id}")
def get_chat_session(
    session_id:   str,
    current_user: dict  = Depends(get_current_customer),
    db: Session         = Depends(get_db)
):
    """
    Return a chat session with all messages.
    """
    customer_id = current_user["user_id"]

    session = db.query(ChatSession).filter(
        ChatSession.session_id  == session_id,
        ChatSession.customer_id == customer_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found.")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.asc())
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
# POST /chat/sessions/{session_id}/message  (Customer)
# ─────────────────────────────────────────────

@router.post("/sessions/{session_id}/message")
def send_message(
    session_id:   str,
    body:         SendMessageRequest,
    current_user: dict    = Depends(get_current_customer),
    db: Session           = Depends(get_db)
):
    """
    Customer sends a message in a chat session.

    Pipeline:
      1. Save user message to SQL
      2. Run LangGraph chat workflow (context + LLM reasoning)
      3. Save AI response to SQL
      4. Store interaction summary in Chroma Vector DB
      5. Return AI response

    The LLM uses:
      - Recent chat history
      - Customer profile + loan data
      - Semantic vector memory
    """
    customer_id = current_user["user_id"]

    # ── Validate session ownership ────────────────────────────────
    session = db.query(ChatSession).filter(
        ChatSession.session_id  == session_id,
        ChatSession.customer_id == customer_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found.")

    # Check if assistant has already responded in this session
    assistant_count = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id,
        ChatMessage.role == "assistant"
    ).count()
    is_first_assistant_reply = assistant_count == 0

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Extract and persist structured memory (preferences) ───────
    try:
        MemoryExtractor.process_message(
            db=db,
            customer_id=customer_id,
            user_message=body.message.strip(),
        )
    except Exception as e:
        print(f"[ChatRouter] Memory extraction failed (non-critical): {e}")

    # ── Save user message ─────────────────────────────────────────
    user_msg = ChatMessage(
        session_id   = session_id,
        role         = "user",
        message_text = body.message.strip(),
        timestamp    = now,
    )
    db.add(user_msg)
    db.commit()

    # ── Special deterministic handling: conversation recall + EMI ──
    msg_lower = body.message.strip().lower()
    recall_phrases = [
        "what did i ask earlier",
        "have i asked anything",
        "asked anything earlier",
        "list the questions",
        "what question did i ask",
    ]
    is_history_question = any(phrase in msg_lower for phrase in recall_phrases)
    is_emi_question     = "what is my emi" in msg_lower or "emi amount" in msg_lower
    needs_loan_number   = "loan number" in msg_lower or "loan id" in msg_lower
    is_grace_question   = "grace" in msg_lower or "extension" in msg_lower
    is_outstanding_question = any(kw in msg_lower for kw in ["outstanding", "balance", "total due", "amount due"])
    is_restructure_question = any(
        kw in msg_lower
        for kw in [
            "restructur",
            "reduce emi",
            "extend tenure",
            "reschedule",
            "modify loan",
            "extend the tenure",
            "lower my emi",
            "decrease my emi",
        ]
    )

    ai_response = ""

    def _format_loans(loans):
        lines = []
        for l in loans:
            lines.append(
                f"- {l.loan_id}: {l.loan_type} | EMI ₹{l.emi_amount:,.0f} due {l.emi_due_date} | Outstanding ₹{l.outstanding_balance:,.0f}"
            )
        return "\n".join(lines)

    def _extract_loan_ids(text: str):
        import re
        ids = []
        for match in re.findall(r"loan\s*([a-zA-Z0-9]+)", text, flags=re.IGNORECASE):
            candidate = match.strip().upper()
            if candidate.startswith("LOAN"):
                ids.append(candidate)
            else:
                ids.append(f"LOAN{candidate}")
        return ids

    loans_list_phrases = [
        "what are my loans",
        "list my loans",
        "show my loans",
        "how many loans",
        "loan list",
        "my loans",
    ]

    is_loans_list_question = any(p in msg_lower for p in loans_list_phrases)

    if is_history_question:
        # Pull all user messages in this session (including current), ordered ASC, then drop the latest to avoid echoing current question
        user_questions = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == "user")
            .order_by(ChatMessage.timestamp.asc())
            .all()
        )
        earlier_questions = [m.message_text for m in user_questions[:-1]] if len(user_questions) > 1 else []

        # Filter out meta/history questions and keep only banking-relevant queries
        meta_phrases = [
            "what did i ask earlier",
            "have i asked",
            "list the questions",
            "summarize our conversation",
            "what question did i ask",
            "what did we discuss",
            "conversation summary",
        ]
        banking_keywords = [
            "loan",
            "emi",
            "grace",
            "restructure",
            "restructuring",
            "payment",
            "balance",
            "due",
            "interest",
            "amount",
            "outstanding",
            "installment",
        ]

        def is_meta(text: str) -> bool:
            return any(p in text.lower() for p in meta_phrases)

        def is_banking(text: str) -> bool:
            lower_q = text.lower()
            return any(k in lower_q for k in banking_keywords)

        filtered = [q for q in earlier_questions if not is_meta(q) and is_banking(q)]

        def normalize(q: str) -> str:
            cleaned = q.strip().lower()
            # remove leading/trailing quotes and punctuation variants
            cleaned = cleaned.strip('"“”‘’\' )')
            cleaned = cleaned.rstrip(".?!")
            return cleaned

        # De-duplicate while preserving order with normalization
        seen = set()
        deduped = []
        for q in filtered:
            key = normalize(q)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(q)

        if deduped:
            formatted = "\n\n".join([f"{i+1}. {q}" for i, q in enumerate(deduped)])
            ai_response = f"You asked the following questions earlier in this conversation:\n\n{formatted}"
        else:
            ai_response = "You have not asked any banking-related questions yet in this conversation."

    elif is_loans_list_question:
        loans = (
            db.query(Loan)
            .filter(Loan.customer_id == customer_id)
            .order_by(Loan.emi_due_date.desc())
            .all()
        )
        if loans:
            summary = _format_loans(loans)
            ai_response = (
                f"You have {len(loans)} loan(s). Here are the details:\n{summary}\n"
                "Tell me a loan ID if you want details for a specific one."
            )
        else:
            ai_response = "I could not find any loan details for your account."

    elif is_emi_question:
        try:
            loans = (
                db.query(Loan)
                .filter(Loan.customer_id == customer_id)
                .order_by(Loan.emi_due_date.desc())
                .all()
            )
            if loans:
                if len(loans) == 1:
                    loan = loans[0]
                    prefix = f"Your loan number is {loan.loan_id}. " if needs_loan_number else ""
                    ai_response = f"{prefix}Your EMI amount is ₹{loan.emi_amount:,.0f} due on {loan.emi_due_date}."
                else:
                    summary = _format_loans(loans)
                    ai_response = (
                        "You have multiple loans. Here are your EMIs and details:\n"
                        f"{summary}\n"
                        "Please tell me a loan ID if you want details for a specific loan."
                    )
            else:
                ai_response = "I could not find any loan details for your account."
        except Exception as e:
            print(f"[ChatRouter] EMI lookup failed: {e}")
            ai_response = "I'm having trouble processing your request right now."  # Only on true backend error

    elif is_outstanding_question:
        try:
            loans = (
                db.query(Loan)
                .filter(Loan.customer_id == customer_id)
                .order_by(Loan.emi_due_date.desc())
                .all()
            )
            if loans:
                total_outstanding = sum(l.outstanding_balance for l in loans)
                if len(loans) == 1:
                    l = loans[0]
                    ai_response = (
                        f"Your outstanding balance for loan {l.loan_id} is ₹{l.outstanding_balance:,.0f}. "
                        f"Your next EMI of ₹{l.emi_amount:,.0f} is due on {l.emi_due_date}."
                    )
                else:
                    summary = _format_loans(loans)
                    ai_response = (
                        f"Across all loans, your total outstanding is ₹{total_outstanding:,.0f}.\n"
                        f"Here are the details:\n{summary}\n"
                        "Tell me a loan ID if you want a specific breakdown."
                    )
            else:
                ai_response = "I could not find any loan details for your account."
        except Exception as e:
            print(f"[ChatRouter] Outstanding lookup failed: {e}")
            ai_response = "I'm having trouble retrieving your outstanding balance right now."

    elif is_grace_question or is_restructure_question:
        try:
            loans = (
                db.query(Loan)
                .filter(Loan.customer_id == customer_id)
                .order_by(Loan.emi_due_date.desc())
                .all()
            )
            if not loans:
                ai_response = "I could not find any loan details for your account."
            else:
                requested_ids = _extract_loan_ids(msg_lower)
                if requested_ids:
                    loans = [l for l in loans if l.loan_id.upper() in requested_ids]
                if not loans:
                    ai_response = "I couldn't match the loan ID you mentioned. Please provide a valid loan ID."
                else:
                    parts = []
                    if is_grace_question:
                        for l in loans:
                            if l.days_past_due < 30:
                                parts.append(
                                    f"Grace – {l.loan_id}: Eligible for up to 7 days. Submit a grace request from 'Your Loans'."
                                )
                            else:
                                parts.append(
                                    f"Grace – {l.loan_id}: Grace may not be available automatically given the current status. Please contact the bank or submit a grace request from your loan details page."
                                )
                    if is_restructure_question:
                        for l in loans:
                            parts.append(
                                f"Restructure – {l.loan_id}: EMI ₹{l.emi_amount:,.0f}, outstanding ₹{l.outstanding_balance:,.0f}. You can submit a restructure request from 'Your Loans'; a bank officer will review it within 2 business days."
                            )
                    ai_response = "\n".join(parts)
        except Exception as e:
            print(f"[ChatRouter] Grace/Restructure lookup failed: {e}")
            ai_response = "I'm having trouble checking grace/restructure options right now."

    else:
        # ── Build context and call LLM ─────────────────────────────
        context_prompt = ContextBuilder.build_context(
            db=db,
            session_id=session_id,
            user_message=body.message.strip(),
            top_k_memories=3,
        )

        try:
            if is_ollama_available():
                system_prompt = (
                    "You are a helpful banking virtual assistant. Use only the provided context. "
                    "If information is missing, say so briefly. Be concise and factual."
                )
                ai_response = call_ollama(prompt=context_prompt, system_prompt=system_prompt)
        except Exception as e:
            print(f"[ChatRouter] LLM call error: {e}")

        # ── Fallback response if workflow fails ───────────────────
        if not ai_response:
            ai_response = _fallback_response(body.message, db, customer_id)

    # If first assistant reply, prepend a one-time intro
    if is_first_assistant_reply and ai_response:
        intro = (
            "Hello! I'm your AI assistant. I can help with EMIs, outstanding balances, "
            "grace/restructure options, and loan questions.\n\n"
        )
        ai_response = intro + ai_response

    # ── Save assistant response ───────────────────────────────────
    assistant_msg = ChatMessage(
        session_id   = session_id,
        role         = "assistant",
        message_text = ai_response,
        timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(assistant_msg)

    # ── Update session last_updated ───────────────────────────────
    session.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Auto-update session title from first user message ─────────
    if session.session_title == "New Chat":
        title = body.message.strip()[:50]
        session.session_title = title

    db.commit()
    db.refresh(assistant_msg)

    # ── Store interaction in Vector DB (async-style, non-blocking) ─
    try:
        from backend.vector.chroma_store import store_memory
        store_memory(
            customer_id = customer_id,
            summary     = f"User asked: {body.message.strip()[:100]}. Assistant replied: {ai_response[:100]}",
            metadata    = {
                "session_id": session_id,
                "timestamp":  now,
                "type":       "chat_interaction",
            }
        )
    except Exception as e:
        print(f"[ChatRouter] Vector store failed (non-critical): {e}")

    return {
        "success":       True,
        "session_id":    session_id,
        "user_message": {
            "role":         "user",
            "message_text": body.message.strip(),
            "timestamp":    now,
        },
        "ai_response": {
            "message_id":   assistant_msg.message_id,
            "role":         "assistant",
            "message_text": ai_response,
            "timestamp":    assistant_msg.timestamp,
        },
    }


# ─────────────────────────────────────────────
# DELETE /chat/sessions/{session_id}  (Customer)
# ─────────────────────────────────────────────

@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id:   str,
    current_user: dict  = Depends(get_current_customer),
    db: Session         = Depends(get_db)
):
    """
    Delete a chat session and all its messages.
    """
    customer_id = current_user["user_id"]

    session = db.query(ChatSession).filter(
        ChatSession.session_id  == session_id,
        ChatSession.customer_id == customer_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found.")

    # Delete all messages first
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()

    return {
        "success": True,
        "message": f"Chat session {session_id} deleted successfully.",
    }


# ─────────────────────────────────────────────
# Fallback Response (if LLM + workflow both fail)
# ─────────────────────────────────────────────

def _fallback_response(user_message: str, db: Session, customer_id: str) -> str:
    """
    Simple rule-based fallback when LangGraph workflow is unavailable.
    """
    msg   = user_message.lower()
    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()

    if any(kw in msg for kw in ["emi", "payment", "due", "next", "amount"]):
        if loans:
            loan = loans[0]
            return (
                f"Your next EMI of ₹{loan.emi_amount:,.0f} is due on {loan.emi_due_date}. "
                f"Your outstanding balance is ₹{loan.outstanding_balance:,.0f}."
            )

    if any(kw in msg for kw in ["grace", "extension", "more time"]):
        if loans and loans[0].days_past_due < 30:
            return (
                "You may be eligible for a grace period of up to 7 days. "
                "Please submit a grace request from the 'Your Loans' section."
            )
        return (
            "Please contact the bank to discuss your repayment options. "
            "You can also submit a restructure request from your loan details page."
        )

    if any(kw in msg for kw in ["restructur", "reduce emi", "extend"]):
        return (
            "Loan restructuring options are available if you are facing repayment difficulties. "
            "You can submit a restructure request from the 'Your Loans' section. "
            "A bank officer will review it within 2 business days."
        )

    if any(kw in msg for kw in ["balance", "outstanding", "total"]):
        if loans:
            total = sum(l.outstanding_balance for l in loans)
            return f"Your total outstanding balance across all loans is ₹{total:,.0f}."

    if any(kw in msg for kw in ["hello", "hi", "help", "assist"]):
        return (
            "Hello! I'm here to help you with your loan queries. "
            "I can assist you with EMI information, outstanding balance, "
            "grace period requests, and loan restructuring options. "
            "What would you like to know?"
        )

    return (
        "Thank you for your message. I can help you with EMI schedules, outstanding balances, "
        "grace period eligibility, and loan restructuring options. "
        "Please feel free to ask a specific question about your loan."
    )