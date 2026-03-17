"""
Sentiment & Interaction Analysis Agent

Sentiment engine (in priority order):
  1. cardiffnlp/twitter-roberta-base-sentiment-latest
     - Trained on 124M tweets → handles conversational/complaint language well
     - Downloads ~476 MB on first use, cached by HuggingFace
     - Labels: LABEL_0=Negative, LABEL_1=Neutral, LABEL_2=Positive
     - Threshold: 0.30 (catches borderline negative sentiment)

  2. Keyword fallback — used only if torch/transformers are not installed.
     - Includes negation handling ("not happy" → Negative)
     - Fuzzy matching via rapidfuzz (catches typos like "frsutrated")

Special handling:
  - Audio/Call transcripts: customer lines are extracted before scoring
    (strips "Bank agent:", "Agent:", "Bank:" lines so agent politeness
     doesn't cancel out customer distress)

Other responsibilities:
  - Classify tonality (Positive / Neutral / Negative)
  - Generate interaction summary
  - Store in SQL + Chroma Vector DB
"""

import re
from datetime import datetime
from sqlalchemy.orm import Session
from backend.db.models import InteractionHistory


# ─────────────────────────────────────────────
# Agent-line prefixes to strip from call transcripts
# ─────────────────────────────────────────────

_AGENT_PREFIXES = re.compile(
    r"^(bank\s*agent|agent|bank\s*officer|officer|representative|rep|"
    r"collection\s*agent|support\s*agent|customer\s*care)\s*[:\-,]",
    re.IGNORECASE,
)

def _extract_customer_lines(transcript: str) -> str:
    """
    For call transcripts, keep only lines spoken by the customer.
    Lines starting with agent prefixes (Bank agent:, Agent:, etc.)
    are stripped out so the agent's polite language doesn't dilute
    the customer's negative sentiment.

    Returns customer-only text, or the full transcript if no agent
    prefix lines are detected (single-speaker recording).
    """
    lines = [l.strip() for l in transcript.splitlines() if l.strip()]
    customer_lines = [l for l in lines if not _AGENT_PREFIXES.match(l)]

    # If nothing was stripped, return full text (single-speaker recording)
    if len(customer_lines) == len(lines):
        return transcript

    return " ".join(customer_lines)


# ─────────────────────────────────────────────
# RoBERTa Model (lazy-loaded singleton)
# ─────────────────────────────────────────────

_roberta_pipeline = None   # loaded once, reused
_roberta_failed   = False  # permanently skip if unavailable

_MODEL_ID = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# cardiffnlp model label mapping
_LABEL_MAP = {
    "negative": "Negative",
    "neutral":  "Neutral",
    "positive": "Positive",
    # also handles numeric label format just in case
    "label_0":  "Negative",
    "label_1":  "Neutral",
    "label_2":  "Positive",
}


def _get_roberta():
    """
    Lazy-load the RoBERTa sentiment pipeline.
    Returns the pipeline or None if unavailable.
    """
    global _roberta_pipeline, _roberta_failed
    if _roberta_failed:
        return None
    if _roberta_pipeline is not None:
        return _roberta_pipeline

    try:
        from transformers import pipeline as hf_pipeline
        print(f"[SentimentAgent] Loading model: {_MODEL_ID}…")
        _roberta_pipeline = hf_pipeline(
            task      = "text-classification",
            model     = _MODEL_ID,
            tokenizer = _MODEL_ID,
            top_k     = None,       # return all label scores
            truncation= True,
            max_length= 512,
        )
        print("[SentimentAgent] Sentiment model loaded ✅")
        return _roberta_pipeline
    except Exception as e:
        print(f"[SentimentAgent] Model unavailable, falling back to keywords: {e}")
        _roberta_failed = True
        return None


# ─────────────────────────────────────────────
# RoBERTa Inference
# ─────────────────────────────────────────────

# Confidence threshold — scores below this are classified as Neutral
_CONFIDENCE_THRESHOLD = 0.30

def _roberta_score(text: str):
    """
    Run RoBERTa on text.
    Returns (net_score: float, label: str) or None if model unavailable.

    net_score:
        +1.0 = fully positive
        -1.0 = fully negative
         0.0 = neutral
    """
    pipe = _get_roberta()
    if pipe is None:
        return None

    try:
        results      = pipe(text[:512])
        scores_list  = results[0] if isinstance(results[0], list) else results

        label_map = {}
        for item in scores_list:
            key = item["label"].lower()
            mapped = _LABEL_MAP.get(key, key)
            label_map[mapped] = item["score"]

        pos = label_map.get("Positive", 0.0)
        neg = label_map.get("Negative", 0.0)

        # Net score: positive pulls toward +1, negative pulls toward -1
        net = round(pos - neg, 3)
        net = max(-1.0, min(1.0, net))

        # Use dominant label if its confidence exceeds threshold
        if neg > pos and neg > _CONFIDENCE_THRESHOLD:
            label = "Negative"
        elif pos > neg and pos > _CONFIDENCE_THRESHOLD:
            label = "Positive"
        else:
            label = "Neutral"

        return net, label
    except Exception as e:
        print(f"[SentimentAgent] Model inference error: {e}")
        return None


# ─────────────────────────────────────────────
# Keyword Fallback — Negation + Fuzzy Matching
# ─────────────────────────────────────────────

POSITIVE_KEYWORDS = [
    "thank", "appreciate", "happy", "great", "good", "excellent",
    "satisfied", "pleased", "helpful", "resolved", "paid", "prepay",
    "on time", "confirm", "agreed", "cooperate", "savings", "wonderful",
    "amazing", "glad", "delighted", "comfortable", "positive", "fine",
]

NEGATIVE_KEYWORDS = [
    # Emotional distress
    "frustrated", "frustrate", "frustration", "angry", "anger",
    "upset", "unhappy", "sad", "depressed", "miserable", "hopeless",
    "helpless", "worried", "stressed", "distressed", "anxious",
    "disgusted", "pathetic", "furious", "terrible", "horrible",
    "disappointed", "dissatisfied",
    # Rude / hostile
    "get lost", "useless", "idiot", "hate", "rubbish", "nonsense",
    "not good", "bad service", "worst", "garbage", "very bad",
    # Service complaints
    "no one is helping", "not helping", "blocking", "blocked",
    "can't access", "cannot access", "days and no one", "inconvenience",
    "calling for days", "no response",
    # Financial hardship
    "cannot pay", "can't pay", "will not pay", "unable to pay",
    "not be able to pay", "no money", "no funds", "cannot", "unable",
    "missed", "delay", "overdue", "problem", "issue", "hardship",
    "struggling", "difficult", "stress", "distress", "loss",
    "business down", "need more time", "emergency",
    # Intent to leave
    "will not continue", "leaving", "closing account", "stop services",
    "not continue", "cancel", "discontinue", "refuse",
]

# Negation words — if found before a positive keyword, flip it negative
NEGATION_WORDS = {
    "not", "no", "never", "don't", "doesn't", "didn't", "won't",
    "can't", "cannot", "isn't", "aren't", "wasn't", "weren't",
    "hardly", "barely", "neither",
}

# Fuzzy match cutoff — words within this similarity match (handles typos)
_FUZZY_CUTOFF = 82   # percent similarity


def _fuzzy_hit(word: str, keyword_list: list) -> bool:
    """
    Check if `word` fuzzy-matches any single-word keyword in the list.
    Uses rapidfuzz if available, otherwise exact match only.
    Only applies to single-word keywords (multi-word uses substring match).
    """
    try:
        from rapidfuzz import fuzz
        for kw in keyword_list:
            if " " in kw:
                continue   # multi-word handled separately
            if fuzz.ratio(word, kw) >= _FUZZY_CUTOFF:
                return True
    except ImportError:
        pass
    return False


def _keyword_score(text: str) -> float:
    """
    Keyword-based fallback with:
    1. Negation window — "not happy" counts as Negative
    2. Fuzzy matching — "frsutrated" matches "frustrated"
    """
    if not text:
        return 0.0

    text_lower = text.lower()
    tokens     = re.split(r"\s+", text_lower)

    def is_negated(kw_start_idx: int) -> bool:
        window_start = max(0, kw_start_idx - 3)
        return any(tok in NEGATION_WORDS for tok in tokens[window_start:kw_start_idx])

    positive_hits = 0
    negative_hits = 0

    # ── Positive keywords ──
    for kw in POSITIVE_KEYWORDS:
        if " " in kw:
            # Multi-word: substring match
            if kw in text_lower:
                positive_hits += 1
        else:
            # Single-word: exact token match OR fuzzy match
            for idx, tok in enumerate(tokens):
                if tok == kw or _fuzzy_hit(tok, [kw]):
                    if is_negated(idx):
                        negative_hits += 1   # "not happy" → negative
                    else:
                        positive_hits += 1
                    break

    # ── Negative keywords ──
    for kw in NEGATIVE_KEYWORDS:
        if " " in kw:
            if kw in text_lower:
                negative_hits += 1
        else:
            for tok in tokens:
                if tok == kw or _fuzzy_hit(tok, [kw]):
                    negative_hits += 1
                    break

    total = positive_hits + negative_hits
    if total == 0:
        return 0.0

    raw = (positive_hits - negative_hits) / total
    return round(max(-1.0, min(1.0, raw)), 2)


# ─────────────────────────────────────────────
# Public API: calculate_sentiment_score
# ─────────────────────────────────────────────

def calculate_sentiment_score(text: str, interaction_type: str = "Chat") -> float:
    """
    Returns sentiment score in [-1.0, +1.0].

    For 'Call' transcripts, only customer-spoken lines are scored.
    Uses RoBERTa if available, falls back to fuzzy keyword matching.
    """
    # Strip agent lines from call transcripts before scoring
    if interaction_type == "Call":
        text = _extract_customer_lines(text)

    roberta_result = _roberta_score(text)
    if roberta_result is not None:
        return roberta_result[0]
    return _keyword_score(text)


# ─────────────────────────────────────────────
# Tonality Classification
# ─────────────────────────────────────────────

def classify_tonality(sentiment_score: float) -> str:
    """
    Classify tonality based on sentiment score.
    Threshold ±0.15 — tighter than default so borderline messages
    don't silently fall into Neutral.

    Returns:
        "Positive"  → score > 0.15
        "Negative"  → score < -0.15
        "Neutral"   → -0.15 <= score <= 0.15
    """
    if sentiment_score > 0.15:
        return "Positive"
    elif sentiment_score < -0.15:
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
    Template-based; replace with LLM call in production.
    """
    if not conversation_text:
        return f"{customer_name} had a {interaction_type.lower()} interaction with the bank."

    text_lower = conversation_text.lower()

    topics = []
    if any(kw in text_lower for kw in ["grace", "grace period"]):
        topics.append("grace period request")
    if any(kw in text_lower for kw in ["restructur"]):
        topics.append("loan restructuring inquiry")
    if any(kw in text_lower for kw in ["emi", "payment", "pay"]):
        topics.append("EMI payment discussion")
    if any(kw in text_lower for kw in ["prepay", "foreclose"]):
        topics.append("prepayment/foreclosure inquiry")
    if any(kw in text_lower for kw in ["outstanding", "balance", "amount"]):
        topics.append("outstanding balance query")
    if any(kw in text_lower for kw in ["salary", "income", "job", "business"]):
        topics.append("financial hardship mention")
    if any(kw in text_lower for kw in ["interest", "rate"]):
        topics.append("interest rate inquiry")
    if any(kw in text_lower for kw in ["blocked", "access", "calling", "helping", "inconvenience"]):
        topics.append("service complaint")

    topic_text = ", ".join(topics) if topics else "general loan query"
    sentiment_text = {
        "Positive": "Customer appeared cooperative and satisfied.",
        "Negative": "Customer expressed distress or frustration.",
        "Neutral":  "Customer tone was neutral and informational."
    }.get(tonality, "")

    return (
        f"{customer_name} contacted the bank via {interaction_type} regarding {topic_text}. "
        f"{sentiment_text}"
    )


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
      1. RoBERTa (or keyword fallback) sentiment — customer lines only for Calls
      2. Classify tonality
      3. Generate interaction summary
      4. Store in SQL (InteractionHistory)
      5. Store summary in Chroma Vector DB
    """
    sentiment_score = calculate_sentiment_score(conversation_text, interaction_type)
    tonality        = classify_tonality(sentiment_score)

    summary = generate_interaction_summary(
        conversation_text = conversation_text,
        interaction_type  = interaction_type,
        tonality          = tonality,
        customer_name     = customer_name,
    )

    interaction = InteractionHistory(
        customer_id         = customer_id,
        interaction_type    = interaction_type,
        interaction_time    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        conversation_text   = conversation_text,
        sentiment_score     = sentiment_score,
        tonality_score      = tonality,
        interaction_summary = summary,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

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
        dict with average_sentiment, dominant_tonality, sentiment_trend
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
    interactions      = state.get("interactions", [])
    sentiment_summary = aggregate_sentiment(interactions)
    state.update({"sentiment_summary": sentiment_summary})
    return state
