"""
Analytics Engine — Risk Models
Deterministic Python calculations for:
  - Days Past Due classification
  - Risk Segmentation
  - Self Cure Probability
  - Value at Risk
  - Payment Trend Analysis
  - Recovery Strategy Generation

NOTE: LLM does NOT perform these calculations.
All outputs here are deterministic and rule-based.
"""


# ─────────────────────────────────────────────
# Risk Segmentation
# ─────────────────────────────────────────────

def get_risk_segment(days_past_due: int, credit_score: int, self_cure_probability: float) -> str:
    """
    Classify borrower into risk segment based on DPD, credit score, and self cure probability.

    Returns:
        "High" | "Medium" | "Low"
    """
    if days_past_due >= 30 or credit_score < 550 or self_cure_probability < 0.25:
        return "High"
    elif days_past_due >= 10 or credit_score < 650 or self_cure_probability < 0.60:
        return "Medium"
    else:
        return "Low"


# ─────────────────────────────────────────────
# Self Cure Probability
# ─────────────────────────────────────────────

def calculate_self_cure_probability(
    days_past_due: int,
    credit_score: int,
    monthly_income: float,
    emi_amount: float,
    missed_payments: int
) -> float:
    """
    Estimate probability that borrower will self-cure (pay without intervention).

    Rules:
    - Start with base score of 1.0
    - Penalize for DPD, missed payments, low credit score, high EMI-to-income ratio
    - Clamp result between 0.05 and 0.95
    """
    score = 1.0

    # Penalty for days past due
    if days_past_due >= 30:
        score -= 0.50
    elif days_past_due >= 15:
        score -= 0.30
    elif days_past_due >= 5:
        score -= 0.10

    # Penalty for missed payments
    score -= missed_payments * 0.10

    # Penalty for low credit score
    if credit_score < 550:
        score -= 0.25
    elif credit_score < 650:
        score -= 0.10
    elif credit_score >= 750:
        score += 0.10

    # Penalty for high EMI-to-income ratio
    if monthly_income > 0:
        emi_ratio = emi_amount / monthly_income
        if emi_ratio > 0.5:
            score -= 0.20
        elif emi_ratio > 0.35:
            score -= 0.10

    # Clamp between 0.05 and 0.95
    return round(max(0.05, min(0.95, score)), 2)


# ─────────────────────────────────────────────
# Value at Risk
# ─────────────────────────────────────────────

def calculate_value_at_risk(outstanding_balance: float, risk_segment: str) -> float:
    """
    Estimate value at risk (amount likely to be unrecovered).

    Risk factors by segment:
    - High   → 60% of outstanding at risk
    - Medium → 30% of outstanding at risk
    - Low    → 10% of outstanding at risk
    """
    risk_factors = {
        "High":   0.60,
        "Medium": 0.30,
        "Low":    0.10,
    }
    factor = risk_factors.get(risk_segment, 0.30)
    return round(outstanding_balance * factor, 2)


# ─────────────────────────────────────────────
# Payment Trend Analysis
# ─────────────────────────────────────────────

def analyze_payment_trend(payment_history: list[dict]) -> dict:
    """
    Analyze payment history to identify trends.

    Args:
        payment_history: List of dicts with keys:
            - payment_amount (float)
            - emi_amount (float)
            - payment_date (str)

    Returns:
        dict with:
            - total_payments (int)
            - missed_payments (int)
            - partial_payments (int)
            - full_payments (int)
            - trend (str): "Improving" | "Stable" | "Deteriorating"
    """
    if not payment_history:
        return {
            "total_payments": 0,
            "missed_payments": 0,
            "partial_payments": 0,
            "full_payments": 0,
            "trend": "Unknown"
        }

    total    = len(payment_history)
    missed   = 0
    partial  = 0
    full     = 0

    for p in payment_history:
        paid = p.get("payment_amount", 0)
        emi  = p.get("emi_amount", paid)   # fallback to paid if emi not provided

        if paid == 0:
            missed += 1
        elif paid < emi * 0.95:            # less than 95% of EMI = partial
            partial += 1
        else:
            full += 1

    # Determine trend from last 3 payments
    recent = payment_history[-3:] if len(payment_history) >= 3 else payment_history
    recent_fulls = sum(
        1 for p in recent
        if p.get("payment_amount", 0) >= p.get("emi_amount", p.get("payment_amount", 0)) * 0.95
    )

    if recent_fulls == len(recent):
        trend = "Improving"
    elif recent_fulls == 0:
        trend = "Deteriorating"
    else:
        trend = "Stable"

    return {
        "total_payments":   total,
        "missed_payments":  missed,
        "partial_payments": partial,
        "full_payments":    full,
        "trend":            trend
    }


# ─────────────────────────────────────────────
# Delinquency Score (0–100)
# ─────────────────────────────────────────────

def calculate_delinquency_score(
    days_past_due: int,
    credit_score: int,
    missed_payments: int,
    self_cure_probability: float
) -> int:
    """
    Generate a delinquency risk score from 0 (no risk) to 100 (maximum risk).
    """
    score = 0

    # DPD contribution (max 40 points)
    score += min(40, days_past_due * 1.5)

    # Credit score contribution (max 25 points)
    if credit_score < 500:
        score += 25
    elif credit_score < 600:
        score += 18
    elif credit_score < 700:
        score += 10
    else:
        score += 2

    # Missed payments contribution (max 25 points)
    score += min(25, missed_payments * 8)

    # Self cure probability (max 10 points — inverse)
    score += round((1 - self_cure_probability) * 10)

    return min(100, int(score))


# ─────────────────────────────────────────────
# Recovery Strategy Generation
# ─────────────────────────────────────────────

def recommend_recovery_strategy(
    days_past_due: int,
    risk_segment: str,
    self_cure_probability: float,
    outstanding_balance: float,
    missed_payments: int
) -> dict:
    """
    Recommend a recovery strategy based on risk profile.

    Returns:
        dict with:
            - strategy (str)
            - action (str)
            - priority (str): "High" | "Medium" | "Low"
            - recommended_channel (str)
    """

    if days_past_due == 0 and risk_segment == "Low":
        return {
            "strategy": "Proactive Engagement",
            "action": "Send friendly EMI reminder 7 days before due date.",
            "priority": "Low",
            "recommended_channel": "WhatsApp"
        }

    elif risk_segment == "Low" and self_cure_probability >= 0.70:
        return {
            "strategy": "Self Cure Monitoring",
            "action": "Monitor for self-cure. Send soft reminder via preferred channel.",
            "priority": "Low",
            "recommended_channel": "SMS"
        }

    elif risk_segment == "Medium" and days_past_due < 15:
        return {
            "strategy": "Grace Period Outreach",
            "action": "Offer grace period of 7 days. Engage via preferred channel.",
            "priority": "Medium",
            "recommended_channel": "WhatsApp"
        }

    elif risk_segment == "Medium" and days_past_due >= 15:
        return {
            "strategy": "Structured Repayment Plan",
            "action": "Propose structured repayment plan or EMI deferral.",
            "priority": "Medium",
            "recommended_channel": "Email"
        }

    elif risk_segment == "High" and days_past_due < 30:
        return {
            "strategy": "Loan Restructuring",
            "action": "Initiate loan restructuring discussion. Escalate to collections officer.",
            "priority": "High",
            "recommended_channel": "Voice Call"
        }

    elif risk_segment == "High" and days_past_due >= 30:
        return {
            "strategy": "Intensive Recovery",
            "action": "Immediate officer intervention required. Legal notice if no response in 7 days.",
            "priority": "High",
            "recommended_channel": "Voice Call"
        }

    else:
        return {
            "strategy": "Standard Follow-Up",
            "action": "Send payment reminder and provide repayment options.",
            "priority": "Medium",
            "recommended_channel": "Email"
        }


# ─────────────────────────────────────────────
# Recommended Outreach Channel
# ─────────────────────────────────────────────

def recommend_channel(
    preferred_channel: str,
    risk_segment: str,
    days_past_due: int
) -> str:
    """
    Determine the best outreach channel based on risk and preference.

    High risk overrides preference with direct Voice Call.
    """
    if risk_segment == "High" and days_past_due >= 30:
        return "Voice Call"
    elif risk_segment == "High":
        return preferred_channel if preferred_channel in ["Voice Call", "WhatsApp"] else "WhatsApp"
    else:
        return preferred_channel