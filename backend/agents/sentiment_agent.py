"""
Sentiment & Interaction Analysis Agent

Responsibilities:
  - Detect sentiment from conversation text (rule-based for prototype)
  - Classify tonality (Positive / Neutral / Negative)
  - Generate interaction summary
  - Store interaction summary in Chroma Vector DB
  - Update interaction record in SQL

For the prototype, sentiment is computed using keyword-based rules.
In production, this would use a fine-tuned NLP model or LLM.
"""

import re
from datetime import datetime
from sqlalchemy.orm import Session
from backend.db.models import InteractionHistory


# ─────────────────────────────────────────────
# Sentiment Keywords
# ─────────────────────────────────────────────

POSITIVE_KEYWORDS = [
    "thank", "appreciate", "happy", "great", "good", "excellent",
    "satisfied", "pleased", "helpful", "resolved", "paid", "prepay",
    "on time", "confirm", "agreed", "cooperate", "interest", "savings"
]

NEGATIVE_KEYWORDS = [
    "frustrated", "angry", "upset", "cannot", "unable", "missed",
    "delay", "overdue", "problem", "issue", "hardship", "struggling",
    "difficult", "stressed", "distress", "loss", "business down",
    "no money", "cannot pay", "need more time", "emergency", "worried"
]

NEUTRAL_KEYWORDS = [
    "query", "question", "information", "details", "check",
    "status", "update", "inform", "when", "how", "what", "schedule"
]


# ─────────────────────────────────────────────
# Sentiment Score Calculation
# ─────────────────────────────────────────────

def calculate_sentiment_score(text: str) -> float:
    """
    Calculate sentiment score from conversation text.

    Score range: -1.0 (very negative) to +1.0 (very positive)
    0.0 = Neutral

    Method: Keyword counting with weighted scoring.
    """
    if not text:
        return 0.0

    text_lower = text.lower()

    positive_hits = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    negative_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)

    total_hits = positive_hits + negative_hits

    if total_hits == 0:
        return 0.0

    # Score = (positive - negative) / total, clamped to [-1, 1]
    raw_score = (positive_hits - negative_hits) / total_hits
    return round(max(-1.0, min(1.0, raw_score)), 2)


# ─────────────────────────────────────────────
# Tonality Classification
# ─────────────────────────────────────────────

def classify_tonality(sentiment_score: float) -> str:
    """
    Classify tonality based on sentiment score.

    Returns:
        "Positive"  → score > 0.2
        "Negative"  → score < -0.2
        "Neutral"   → -0.2 <= score <= 0.2
    """
    if sentiment_score > 0.2:
        return "Positive"
    elif sentiment_score < -0.2:
        return "Negative"
    else:
        return "Neutral"


# ─────────────────────────────────────────────
# Interaction Summary Generator
# ─────────────────────────────────────────────

def generate_interaction_summary(
    conversation_text: str,
    interaction_type: str,
    tonality: str,
    customer_name: str = "Customer"
) -> str:
    """
    Generate a concise summary of the interaction.

    For the prototype this uses rule-based template generation.
    In production, this would call the LLM Reasoning Agent.
    """
    if not conversation_text:
        return f"{customer_name} had a {interaction_type.lower()} interaction with the bank."

    text_lower = conversation_text.lower()

    # Detect key topics
    topics = []

    if any(kw in text_lower for kw in ["grace", "grace period"]):
        topics.append("grace period request")

    if any(kw in text_lower for kw in ["restructur", "restructure", "restructuring"]):
        topics.append("loan restructuring inquiry")

    if any(kw in text_lower for kw in ["emi", "payment", "pay"]):
        topics.append("EMI payment discussion")

    if any(kw in text_lower for kw in ["prepay", "prepayment", "foreclose"]):
        topics.append("prepayment/foreclosure inquiry")

    if any(kw in text_lower for kw in ["outstanding", "balance", "amount"]):
        topics.append("outstanding balance query")

    if any(kw in text_lower for kw in ["salary", "income", "job", "business"]):
        topics.append("financial hardship mention")

    if any(kw in text_lower for kw in ["interest", "rate"]):
        topics.append("interest rate inquiry")

    # Build summary
    topic_text = ", ".join(topics) if topics else "general loan query"
    sentiment_text = {
        "Positive": "Customer appeared cooperative and satisfied.",
        "Negative": "Customer expressed distress or frustration.",
        "Neutral":  "Customer tone was neutral and informational."
    }.get(tonality, "")

    summary = (
        f"{customer_name} contacted the bank via {interaction_type} regarding {topic_text}. "
        f"{sentiment_text}"
    )

    return summary


# ─────────────────────────────────────────────
# Analyze & Store Interaction
# ─────────────────────────────────────────────

def analyze_and_store_interaction(
    db: Session,
    customer_id: str,
    interaction_type: str,
    conversation_text: str,
    customer_name: str = "Customer"
) -> dict:
    """
    Full pipeline:
      1. Calculate sentiment score
      2. Classify tonality
      3. Generate interaction summary
      4. Store in SQL (InteractionHistory)
      5. Store summary in Chroma Vector DB

    Returns:
        dict with sentiment_score, tonality_score, interaction_summary, interaction_id
    """
    # ── Step 1 & 2: Sentiment & Tonality ──────────────────────────
    sentiment_score = calculate_sentiment_score(conversation_text)
    tonality        = classify_tonality(sentiment_score)

    # ── Step 3: Summary ───────────────────────────────────────────
    summary = generate_interaction_summary(
        conversation_text = conversation_text,
        interaction_type  = interaction_type,
        tonality          = tonality,
        customer_name     = customer_name
    )

    # ── Step 4: Store in SQL ──────────────────────────────────────
    interaction = InteractionHistory(
        customer_id         = customer_id,
        interaction_type    = interaction_type,
        interaction_time    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        conversation_text   = conversation_text,
        sentiment_score     = sentiment_score,
        tonality_score      = tonality,
        interaction_summary = summary
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    # ── Step 5: Store in Chroma Vector DB ─────────────────────────
    try:
        from backend.vector.chroma_store import store_memory
        store_memory(
            customer_id = customer_id,
            summary     = summary,
            metadata    = {
                "interaction_id":   interaction.interaction_id,
                "interaction_type": interaction_type,
                "sentiment_score":  str(sentiment_score),
                "tonality":         tonality,
                "timestamp":        interaction.interaction_time,
            }
        )
    except Exception as e:
        print(f"[SentimentAgent] Chroma store failed (non-critical): {e}")

    return {
        "interaction_id":      interaction.interaction_id,
        "sentiment_score":     sentiment_score,
        "tonality_score":      tonality,
        "interaction_summary": summary,
    }


# ─────────────────────────────────────────────
# Aggregate Sentiment (across interactions)
# ─────────────────────────────────────────────

def aggregate_sentiment(interactions: list[dict]) -> dict:
    """
    Aggregate sentiment scores across multiple interactions.

    Args:
        interactions: List of dicts with sentiment_score and tonality_score

    Returns:
        dict with:
            - average_sentiment (float)
            - dominant_tonality (str)
            - sentiment_trend (str): "Improving" | "Stable" | "Deteriorating"
    """
    if not interactions:
        return {
            "average_sentiment": 0.0,
            "dominant_tonality": "Neutral",
            "sentiment_trend":   "Stable"
        }

    scores   = [i.get("sentiment_score", 0.0) for i in interactions]
    avg      = round(sum(scores) / len(scores), 2)
    dominant = classify_tonality(avg)

    # Trend: compare first half vs second half
    mid    = len(scores) // 2
    first  = sum(scores[:mid]) / max(len(scores[:mid]), 1)
    second = sum(scores[mid:]) / max(len(scores[mid:]), 1)

    if second > first + 0.1:
        trend = "Improving"
    elif second < first - 0.1:
        trend = "Deteriorating"
    else:
        trend = "Stable"

    return {
        "average_sentiment": avg,
        "dominant_tonality": dominant,
        "sentiment_trend":   trend
    }


# ─────────────────────────────────────────────
# LangGraph-Compatible Node
# ─────────────────────────────────────────────

def run_sentiment_agent(state: dict) -> dict:
    """
    LangGraph-compatible agent node.

    Expects state keys:
        - interactions (list[dict])  ← from context_memory_agent

    Adds to state:
        - sentiment_summary (dict)
            - average_sentiment (float)
            - dominant_tonality (str)
            - sentiment_trend (str)
    """
    interactions     = state.get("interactions", [])
    sentiment_summary = aggregate_sentiment(interactions)

    state.update({
        "sentiment_summary": sentiment_summary
    })

    return state