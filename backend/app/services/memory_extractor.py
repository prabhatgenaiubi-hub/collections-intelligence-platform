from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.vector.chroma_store import store_memory


PREFERENCE_KEYWORDS = [
    "remember this",
    "i prefer",
    "my preference is",
]

CHANNEL_KEYWORDS = {
    "whatsapp": "preferred_channel",
    "sms": "preferred_channel",
    "text": "preferred_channel",
    "email": "preferred_channel",
    "mail": "preferred_channel",
    "call": "preferred_channel",
    "phone": "preferred_channel",
    "phone call": "preferred_channel",
}


class MemoryExtractor:
    """
    Extract structured preferences from user messages and persist to DB + Chroma.
    Expected DB table: customer_preferences (customer_id, preference_key, preference_value, created_at).
    """

    @staticmethod
    def extract_memory(user_message: str) -> Optional[Dict[str, str]]:
        if not user_message:
            return None

        msg_lower = user_message.lower()
        if not any(kw in msg_lower for kw in PREFERENCE_KEYWORDS):
            return None

        # Naive channel extraction
        detected_channel = None
        for kw in CHANNEL_KEYWORDS:
            if kw in msg_lower:
                detected_channel = kw.capitalize() if kw != "sms" else "SMS"
                break

        if detected_channel:
            return {
                "memory_type": "preference",
                "key": "preferred_channel",
                "value": detected_channel,
            }

        # Fallback generic preference capture
        # Example: "I prefer paper statements" → key: preference_note, value: that phrase
        return {
            "memory_type": "preference",
            "key": "preference_note",
            "value": user_message.strip(),
        }

    @staticmethod
    def save_memory(db: Session, customer_id: str, memory: Dict[str, str]) -> bool:
        if not memory:
            return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stmt = text(
            """
            INSERT INTO customer_preferences (customer_id, preference_key, preference_value, created_at)
            VALUES (:cid, :pkey, :pval, :created_at)
            """
        )
        try:
            db.execute(stmt, {
                "cid": customer_id,
                "pkey": memory.get("key"),
                "pval": memory.get("value"),
                "created_at": now,
            })
            db.commit()
            # Store semantic summary in vector DB
            summary = f"Customer prefers {memory.get('value', '')}."
            try:
                store_memory(
                    customer_id=customer_id,
                    summary=summary,
                    metadata={"type": memory.get("memory_type", "preference"), "preference_key": memory.get("key")}
                )
            except Exception as ve:
                print(f"[MemoryExtractor] Chroma store failed (non-critical): {ve}")
            return True
        except Exception as e:
            print(f"[MemoryExtractor] DB insert failed: {e}")
            db.rollback()
            return False

    @staticmethod
    def process_message(db: Session, customer_id: str, user_message: str) -> Optional[Dict[str, str]]:
        """
        Detect preference statements, extract structured memory, save to DB and vector store.
        Returns the saved memory dict, or None if nothing detected.
        """
        memory = MemoryExtractor.extract_memory(user_message)
        if not memory:
            return None
        saved = MemoryExtractor.save_memory(db, customer_id, memory)
        return memory if saved else None
