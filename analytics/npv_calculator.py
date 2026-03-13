"""
Analytics Engine — NPV Calculator
Deterministic Python calculations for:
  - Net Present Value (NPV) of recovery strategies
  - Expected Recovery Amount
  - Recovery Rate estimation
  - Portfolio NPV summary

NOTE: LLM does NOT perform these calculations.
All outputs are deterministic and rule-based.
"""


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

DEFAULT_DISCOUNT_RATE = 0.12        # 12% annual discount rate
DEFAULT_RECOVERY_PERIODS = 12       # months


# ─────────────────────────────────────────────
# Recovery Rate by Strategy
# ─────────────────────────────────────────────

RECOVERY_RATES = {
    "Proactive Engagement":      0.95,
    "Self Cure Monitoring":      0.85,
    "Grace Period Outreach":     0.75,
    "Structured Repayment Plan": 0.65,
    "Loan Restructuring":        0.55,
    "Intensive Recovery":        0.35,
    "Standard Follow-Up":        0.70,
}

# Collection cost as % of outstanding balance
COLLECTION_COST_RATES = {
    "Proactive Engagement":      0.01,
    "Self Cure Monitoring":      0.02,
    "Grace Period Outreach":     0.03,
    "Structured Repayment Plan": 0.05,
    "Loan Restructuring":        0.08,
    "Intensive Recovery":        0.15,
    "Standard Follow-Up":        0.04,
}


# ─────────────────────────────────────────────
# Expected Recovery Amount
# ─────────────────────────────────────────────

def calculate_expected_recovery(
    outstanding_balance: float,
    strategy: str,
    self_cure_probability: float
) -> float:
    """
    Calculate the expected recovery amount for a given strategy.

    Formula:
        Expected Recovery = Outstanding × Recovery Rate × Adjusted Probability

    Args:
        outstanding_balance: Total outstanding loan amount
        strategy: Recovery strategy name
        self_cure_probability: Probability borrower pays without intervention (0–1)

    Returns:
        Expected recovery amount (float)
    """
    base_recovery_rate = RECOVERY_RATES.get(strategy, 0.65)

    # Blend strategy recovery rate with self cure probability
    # If self cure is high, expected recovery is naturally higher
    blended_rate = (base_recovery_rate * 0.70) + (self_cure_probability * 0.30)

    return round(outstanding_balance * blended_rate, 2)


# ─────────────────────────────────────────────
# Collection Cost
# ─────────────────────────────────────────────

def calculate_collection_cost(
    outstanding_balance: float,
    strategy: str
) -> float:
    """
    Estimate the cost of executing the recovery strategy.

    Args:
        outstanding_balance: Total outstanding loan amount
        strategy: Recovery strategy name

    Returns:
        Collection cost amount (float)
    """
    cost_rate = COLLECTION_COST_RATES.get(strategy, 0.05)
    return round(outstanding_balance * cost_rate, 2)


# ─────────────────────────────────────────────
# NPV of Recovery
# ─────────────────────────────────────────────

def calculate_npv(
    outstanding_balance: float,
    strategy: str,
    self_cure_probability: float,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    periods: int = DEFAULT_RECOVERY_PERIODS
) -> dict:
    """
    Calculate the Net Present Value of a recovery strategy.

    Formula:
        Monthly Cash Flow = Expected Recovery / periods
        NPV = Σ (Cash Flow / (1 + monthly_rate)^t) - Collection Cost

    Args:
        outstanding_balance: Total outstanding loan amount
        strategy: Recovery strategy name
        self_cure_probability: Self cure probability (0–1)
        discount_rate: Annual discount rate (default 12%)
        periods: Number of months over which recovery occurs

    Returns:
        dict with:
            - expected_recovery (float)
            - collection_cost (float)
            - npv (float)
            - recovery_rate (float)
            - net_benefit (float)
    """
    expected_recovery = calculate_expected_recovery(
        outstanding_balance, strategy, self_cure_probability
    )
    collection_cost = calculate_collection_cost(outstanding_balance, strategy)

    monthly_rate = discount_rate / 12
    monthly_cash_flow = expected_recovery / periods if periods > 0 else expected_recovery

    # Discounted cash flow sum
    dcf_sum = 0.0
    for t in range(1, periods + 1):
        dcf_sum += monthly_cash_flow / ((1 + monthly_rate) ** t)

    npv = round(dcf_sum - collection_cost, 2)
    net_benefit = round(expected_recovery - collection_cost, 2)
    recovery_rate = RECOVERY_RATES.get(strategy, 0.65)

    return {
        "expected_recovery": expected_recovery,
        "collection_cost":   collection_cost,
        "npv":               npv,
        "recovery_rate":     recovery_rate,
        "net_benefit":       net_benefit
    }


# ─────────────────────────────────────────────
# Compare Strategies NPV
# ─────────────────────────────────────────────

def compare_strategies(
    outstanding_balance: float,
    self_cure_probability: float,
    discount_rate: float = DEFAULT_DISCOUNT_RATE
) -> list[dict]:
    """
    Compare NPV across all recovery strategies for a given loan.

    Returns:
        List of strategy NPV results sorted by NPV descending.
    """
    results = []

    for strategy in RECOVERY_RATES.keys():
        npv_result = calculate_npv(
            outstanding_balance=outstanding_balance,
            strategy=strategy,
            self_cure_probability=self_cure_probability,
            discount_rate=discount_rate
        )
        results.append({
            "strategy":          strategy,
            "expected_recovery": npv_result["expected_recovery"],
            "collection_cost":   npv_result["collection_cost"],
            "npv":               npv_result["npv"],
            "net_benefit":       npv_result["net_benefit"],
            "recovery_rate":     npv_result["recovery_rate"],
        })

    # Sort by NPV descending
    results.sort(key=lambda x: x["npv"], reverse=True)
    return results


# ─────────────────────────────────────────────
# Portfolio NPV Summary
# ─────────────────────────────────────────────

def calculate_portfolio_npv(loans: list[dict]) -> dict:
    """
    Calculate portfolio-level NPV summary across all loans.

    Args:
        loans: List of dicts with keys:
            - outstanding_balance (float)
            - strategy (str)
            - self_cure_probability (float)

    Returns:
        dict with:
            - total_outstanding (float)
            - total_expected_recovery (float)
            - total_collection_cost (float)
            - total_npv (float)
            - overall_recovery_rate (float)
    """
    total_outstanding        = 0.0
    total_expected_recovery  = 0.0
    total_collection_cost    = 0.0
    total_npv                = 0.0

    for loan in loans:
        outstanding   = loan.get("outstanding_balance", 0.0)
        strategy      = loan.get("strategy", "Standard Follow-Up")
        self_cure_p   = loan.get("self_cure_probability", 0.50)

        result = calculate_npv(
            outstanding_balance=outstanding,
            strategy=strategy,
            self_cure_probability=self_cure_p
        )

        total_outstanding       += outstanding
        total_expected_recovery += result["expected_recovery"]
        total_collection_cost   += result["collection_cost"]
        total_npv               += result["npv"]

    overall_recovery_rate = (
        round(total_expected_recovery / total_outstanding, 4)
        if total_outstanding > 0 else 0.0
    )

    return {
        "total_outstanding":       round(total_outstanding, 2),
        "total_expected_recovery": round(total_expected_recovery, 2),
        "total_collection_cost":   round(total_collection_cost, 2),
        "total_npv":               round(total_npv, 2),
        "overall_recovery_rate":   overall_recovery_rate
    }