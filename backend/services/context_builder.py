from typing import List
from sqlalchemy.orm import Session

from backend.db.models import ChatMessage, ChatSession, Customer, Loan, CustomerPreference
from backend.vector.chroma_store import retrieve_memories


class ContextBuilder:
    """
    Build LLM prompt context for chatbot conversations.
    """

    @staticmethod
    def build_context(
        db: Session,
        session_id: str,
        user_message: str,
        top_k_memories: int = 3,
        loan_id: str = None,          # ← NEW: scope to a specific loan
    ) -> str:
        # Fetch session and customer
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            return f"User Question:\n{user_message.strip()}"

        customer = db.query(Customer).filter(Customer.customer_id == session.customer_id).first()

        # ── Fetch the correct loan ────────────────────────────────
        loan_q = db.query(Loan).filter(Loan.customer_id == session.customer_id)
        if loan_id:
            loan_q = loan_q.filter(Loan.loan_id == loan_id.strip().upper())
        loan = loan_q.order_by(Loan.emi_due_date.desc()).first()

        # Preferences
        prefs = (
            db.query(CustomerPreference)
            .filter(CustomerPreference.customer_id == session.customer_id)
            .all()
        )
        pref_map = {p.preferred_channel if hasattr(p, 'preferred_channel') else p.preference_key: getattr(p, 'preferred_channel', None) or getattr(p, 'preference_value', None) for p in []}

        # Last 10 messages (most recent first), then reverse to chronological for readability
        messages: List[ChatMessage] = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp.asc())
            .limit(20)
            .all()
        )
        if messages:
            history = "\n".join([f"{m.role.capitalize()}: {m.message_text}" for m in messages])
        else:
            history = "No prior conversation in this session."

        # Retrieve vector memories (semantic recall)
        memories: List[str] = []
        try:
            memories = retrieve_memories(
                customer_id=customer.customer_id if customer else "",
                query=user_message,
                top_k=top_k_memories,
            ) or []
        except Exception as e:
            print(f"[ContextBuilder] memory retrieval failed: {e}")
            memories = []
        memory_block = "\n".join([f"- {m}" for m in memories]) or "None."

        # Build preferences map
        preference_entries = {}
        for p in prefs:
            key = getattr(p, "preference_key", None) or getattr(p, "preferred_channel", None)
            val = getattr(p, "preference_value", None) or getattr(p, "preferred_channel", None)
            if key and val:
                preference_entries[key] = val

        # System context lines
        system_ctx = [
            f"Customer Name: {customer.customer_name if customer else 'N/A'}",
            f"ACTIVE LOAN (answer ONLY about this loan): {loan.loan_id if loan else 'N/A'}",
            f"Loan Type: {loan.loan_type if loan else 'N/A'}",
            f"EMI Amount: {f'₹{loan.emi_amount:,.0f}' if loan else 'N/A'}",
            f"EMI Due Date: {loan.emi_due_date if loan else 'N/A'}",
            f"Outstanding Balance: {f'₹{loan.outstanding_balance:,.0f}' if loan else 'N/A'}",
            f"Preferred Channel: {preference_entries.get('preferred_channel') or (customer.preferred_channel if customer else 'N/A')}",
        ]
        for k, v in preference_entries.items():
            if k == 'preferred_channel':
                continue
            system_ctx.append(f"Preference - {k}: {v}")

        # Strong instruction to prevent cross-loan context bleed
        scope_instruction = (
            f"\n[IMPORTANT] You are assisting with loan {loan.loan_id if loan else 'N/A'} ONLY. "
            "Do not reference or answer about any other loan, even if it appears in your memories. "
            "If the user asks about a different loan, redirect them to open that loan's chat."
        )

        prompt = (
            "System Context:\n" + "\n".join(system_ctx) + "\n" +
            scope_instruction + "\n\n" +
            "Relevant Memories:\n" + memory_block + "\n\n" +
            "Conversation History:\n" + history + "\n\n" +
            "User Question:\n" + user_message.strip()
        )
        return prompt
