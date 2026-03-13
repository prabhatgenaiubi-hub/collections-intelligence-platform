"""
Collections Intelligence Agent

Responsibilities:
  - Compute risk segmentation
  - Calculate self cure probability
  - Estimate value at risk
  - Analyze payment trends
  - Calculate delinquency score
  - Generate recovery strategy recommendation
  - Calculate NPV of recovery strategies

This agent uses only deterministic analytics (no LLM).
LLM reasoning is handled by the LLM Reasoning Agent.
"""

import sys
import os

# Ensure analytics module is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from analytics.risk_models import (
    get_risk_segment,
    calculate_self_cure_probability,
    calculate_value_at_risk,
    analyze_payment_trend,
    calculate_delinquency_score,
    recommend_recovery_strategy,
    recommend_channel,
)
from analytics.npv_calculator import calculate_npv, compare_strategies


# ─────────────────────────────────────────────
# Main Agent Function
# ─────────────────────────────────────────────

def run_collections_intelligence_agent(state: dict) -> dict:
    """
    LangGraph-compatible agent node.

    Input state keys:
        - customer_id (str)
        - loan_id (str)
        - days_past_due (int)
        - credit_score (int)
        - monthly_income (float)
        - emi_amount (float)
        - outstanding_balance (float)
        - preferred_channel (str)
        - payment_history (list[dict])   ← list of {payment_amount, emi_amount, payment_date}

    Output state keys (added/updated):
        - risk_segment (str)
        - self_cure_probability (float)
        - value_at_risk (float)
        - delinquency_score (int)
        - payment_trend (dict)
        - recovery_strategy (dict)
        - recommended_channel (str)
        - npv_result (dict)
        - strategy_comparison (list[dict])
    """

    # ── Extract inputs from state ──────────────────────────────────
    days_past_due        = state.get("days_past_due", 0)
    credit_score         = state.get("credit_score", 650)
    monthly_income       = state.get("monthly_income", 30000.0)
    emi_amount           = state.get("emi_amount", 5000.0)
    outstanding_balance  = state.get("outstanding_balance", 0.0)
    preferred_channel    = state.get("preferred_channel", "Email")
    payment_history      = state.get("payment_history", [])

    # ── Payment Trend Analysis ─────────────────────────────────────
    payment_trend   = analyze_payment_trend(payment_history)
    missed_payments = payment_trend.get("missed_payments", 0)

    # ── Self Cure Probability ──────────────────────────────────────
    self_cure_probability = calculate_self_cure_probability(
        days_past_due   = days_past_due,
        credit_score    = credit_score,
        monthly_income  = monthly_income,
        emi_amount      = emi_amount,
        missed_payments = missed_payments,
    )

    # ── Risk Segmentation ─────────────────────────────────────────
    risk_segment = get_risk_segment(
        days_past_due         = days_past_due,
        credit_score          = credit_score,
        self_cure_probability = self_cure_probability,
    )

    # ── Value at Risk ─────────────────────────────────────────────
    value_at_risk = calculate_value_at_risk(
        outstanding_balance = outstanding_balance,
        risk_segment        = risk_segment,
    )

    # ── Delinquency Score ─────────────────────────────────────────
    delinquency_score = calculate_delinquency_score(
        days_past_due         = days_past_due,
        credit_score          = credit_score,
        missed_payments       = missed_payments,
        self_cure_probability = self_cure_probability,
    )

    # ── Recovery Strategy ─────────────────────────────────────────
    recovery_strategy = recommend_recovery_strategy(
        days_past_due         = days_past_due,
        risk_segment          = risk_segment,
        self_cure_probability = self_cure_probability,
        outstanding_balance   = outstanding_balance,
        missed_payments       = missed_payments,
    )

    # ── Recommended Channel ───────────────────────────────────────
    recommended_channel = recommend_channel(
        preferred_channel = preferred_channel,
        risk_segment      = risk_segment,
        days_past_due     = days_past_due,
    )

    # ── NPV Calculation ───────────────────────────────────────────
    npv_result = calculate_npv(
        outstanding_balance   = outstanding_balance,
        strategy              = recovery_strategy["strategy"],
        self_cure_probability = self_cure_probability,
    )

    # ── Strategy Comparison ───────────────────────────────────────
    strategy_comparison = compare_strategies(
        outstanding_balance   = outstanding_balance,
        self_cure_probability = self_cure_probability,
    )

    # ── Update State ──────────────────────────────────────────────
    state.update({
        "risk_segment":          risk_segment,
        "self_cure_probability": self_cure_probability,
        "value_at_risk":         value_at_risk,
        "delinquency_score":     delinquency_score,
        "payment_trend":         payment_trend,
        "recovery_strategy":     recovery_strategy,
        "recommended_channel":   recommended_channel,
        "npv_result":            npv_result,
        "strategy_comparison":   strategy_comparison,
    })

    return state


# ─────────────────────────────────────────────
# Standalone Helper (used by routers directly)
# ─────────────────────────────────────────────

def analyze_loan(
    days_past_due: int,
    credit_score: int,
    monthly_income: float,
    emi_amount: float,
    outstanding_balance: float,
    preferred_channel: str,
    payment_history: list
) -> dict:
    """
    Convenience wrapper to run the agent without LangGraph state.
    Used directly by FastAPI routers.
    """
    state = {
        "days_past_due":       days_past_due,
        "credit_score":        credit_score,
        "monthly_income":      monthly_income,
        "emi_amount":          emi_amount,
        "outstanding_balance": outstanding_balance,
        "preferred_channel":   preferred_channel,
        "payment_history":     payment_history,
    }
    return run_collections_intelligence_agent(state)