"""
Policy Guardrail Agent

Responsibilities:
  - Validate AI-generated recommendations against banking policy rules
  - Validate Grace Request eligibility
  - Validate Restructure Request eligibility
  - Flag policy violations before human review
  - Ensure all recommendations are compliant before final decision

This agent acts as the compliance gate in the LangGraph workflow.
Human review happens AFTER this agent approves the recommendation.
"""


# ─────────────────────────────────────────────
# Policy Rules Registry
# ─────────────────────────────────────────────

POLICY_RULES = {
    "GRACE_MAX_DPD": 30,            # Grace allowed only if DPD < 30
    "GRACE_MAX_REQUESTS": 2,        # Max 2 grace requests per loan per year
    "RESTRUCTURE_MIN_DPD": 5,       # Restructure considered only if DPD >= 5
    "RESTRUCTURE_MAX_DPD": 90,      # Restructure not allowed if DPD > 90 (legal path)
    "MIN_CREDIT_SCORE_GRACE": 450,  # Minimum credit score for grace eligibility
    "MIN_CREDIT_SCORE_RESTRUCTURE": 400,
    "HIGH_RISK_HUMAN_REVIEW": True, # High risk loans always require human review
    "MAX_OUTSTANDING_AUTO_APPROVE": 100000.0,  # Auto-approve only below this amount
}


# ─────────────────────────────────────────────
# Grace Request Validation
# ─────────────────────────────────────────────

def validate_grace_request(
    days_past_due: int,
    credit_score: int,
    outstanding_balance: float,
    existing_grace_count: int,
    risk_segment: str
) -> dict:
    """
    Validate whether a grace period request meets policy criteria.

    Args:
        days_past_due:        Current DPD for the loan
        credit_score:         Customer credit score
        outstanding_balance:  Current outstanding loan balance
        existing_grace_count: Number of grace requests already made for this loan
        risk_segment:         Risk segment (Low / Medium / High)

    Returns:
        dict with:
            - eligible (bool)
            - violations (list[str])  ← list of violated rules
            - warnings (list[str])    ← non-blocking cautions
            - requires_human_review (bool)
            - recommendation (str)
    """
    violations = []
    warnings   = []
    eligible   = True

    # Rule 1: DPD must be < 30
    if days_past_due >= POLICY_RULES["GRACE_MAX_DPD"]:
        eligible = False
        violations.append(
            f"Grace not allowed: Days Past Due ({days_past_due}) exceeds maximum "
            f"allowed ({POLICY_RULES['GRACE_MAX_DPD']} days)."
        )

    # Rule 2: Max grace requests per loan
    if existing_grace_count >= POLICY_RULES["GRACE_MAX_REQUESTS"]:
        eligible = False
        violations.append(
            f"Grace not allowed: Maximum grace requests "
            f"({POLICY_RULES['GRACE_MAX_REQUESTS']}) already used for this loan."
        )

    # Rule 3: Minimum credit score
    if credit_score < POLICY_RULES["MIN_CREDIT_SCORE_GRACE"]:
        eligible = False
        violations.append(
            f"Grace not allowed: Credit score ({credit_score}) is below minimum "
            f"required ({POLICY_RULES['MIN_CREDIT_SCORE_GRACE']})."
        )

    # Warning: High risk segment — flag for human review
    if risk_segment == "High":
        warnings.append(
            "High risk segment: Grace approval requires mandatory bank officer review."
        )

    # Warning: Large outstanding balance
    if outstanding_balance > POLICY_RULES["MAX_OUTSTANDING_AUTO_APPROVE"]:
        warnings.append(
            f"Outstanding balance (₹{outstanding_balance:,.0f}) exceeds auto-approve "
            f"threshold. Human review required."
        )

    # Determine if human review is required
    requires_human_review = (
        risk_segment == "High" or
        outstanding_balance > POLICY_RULES["MAX_OUTSTANDING_AUTO_APPROVE"] or
        len(warnings) > 0
    )

    # Build recommendation text
    if not eligible:
        recommendation = "Grace request does not meet policy criteria. Rejection recommended."
    elif requires_human_review:
        recommendation = "Grace request meets basic criteria but requires bank officer review before approval."
    else:
        recommendation = "Grace request meets all policy criteria. Eligible for approval."

    return {
        "eligible":              eligible,
        "violations":            violations,
        "warnings":              warnings,
        "requires_human_review": requires_human_review,
        "recommendation":        recommendation,
    }


# ─────────────────────────────────────────────
# Restructure Request Validation
# ─────────────────────────────────────────────

def validate_restructure_request(
    days_past_due: int,
    credit_score: int,
    outstanding_balance: float,
    risk_segment: str,
    missed_payments: int
) -> dict:
    """
    Validate whether a loan restructure request meets policy criteria.

    Args:
        days_past_due:       Current DPD for the loan
        credit_score:        Customer credit score
        outstanding_balance: Current outstanding loan balance
        risk_segment:        Risk segment (Low / Medium / High)
        missed_payments:     Total missed payment count

    Returns:
        dict with:
            - eligible (bool)
            - violations (list[str])
            - warnings (list[str])
            - requires_human_review (bool)
            - recommendation (str)
    """
    violations = []
    warnings   = []
    eligible   = True

    # Rule 1: DPD must be >= 5 (no restructuring if no delinquency)
    if days_past_due < POLICY_RULES["RESTRUCTURE_MIN_DPD"]:
        eligible = False
        violations.append(
            f"Restructure not applicable: Days Past Due ({days_past_due}) is below "
            f"minimum threshold ({POLICY_RULES['RESTRUCTURE_MIN_DPD']} days). "
            f"No delinquency detected."
        )

    # Rule 2: DPD must be <= 90 (beyond 90 goes to legal/NPA path)
    if days_past_due > POLICY_RULES["RESTRUCTURE_MAX_DPD"]:
        eligible = False
        violations.append(
            f"Restructure not allowed: Days Past Due ({days_past_due}) exceeds "
            f"maximum ({POLICY_RULES['RESTRUCTURE_MAX_DPD']} days). "
            f"Account must be referred to legal recovery team."
        )

    # Rule 3: Minimum credit score
    if credit_score < POLICY_RULES["MIN_CREDIT_SCORE_RESTRUCTURE"]:
        eligible = False
        violations.append(
            f"Restructure not allowed: Credit score ({credit_score}) is below "
            f"minimum required ({POLICY_RULES['MIN_CREDIT_SCORE_RESTRUCTURE']})."
        )

    # Warning: Multiple missed payments
    if missed_payments >= 3:
        warnings.append(
            f"Customer has {missed_payments} missed payments. "
            f"Restructure terms should include stricter repayment schedule."
        )

    # Warning: High risk — mandatory human review
    if risk_segment == "High":
        warnings.append(
            "High risk segment: Restructure approval requires mandatory bank officer review."
        )

    # Warning: Large outstanding balance
    if outstanding_balance > POLICY_RULES["MAX_OUTSTANDING_AUTO_APPROVE"]:
        warnings.append(
            f"Outstanding balance (₹{outstanding_balance:,.0f}) requires "
            f"senior officer sign-off."
        )

    # Human review required
    requires_human_review = (
        risk_segment == "High" or
        outstanding_balance > POLICY_RULES["MAX_OUTSTANDING_AUTO_APPROVE"] or
        missed_payments >= 3 or
        len(warnings) > 0
    )

    # Recommendation text
    if not eligible:
        recommendation = "Restructure request does not meet policy criteria. Rejection recommended."
    elif requires_human_review:
        recommendation = "Restructure request meets basic criteria. Bank officer review required before approval."
    else:
        recommendation = "Restructure request meets all policy criteria. Eligible for approval."

    return {
        "eligible":              eligible,
        "violations":            violations,
        "warnings":              warnings,
        "requires_human_review": requires_human_review,
        "recommendation":        recommendation,
    }


# ─────────────────────────────────────────────
# Recovery Recommendation Validation
# ─────────────────────────────────────────────

def validate_recovery_recommendation(
    strategy: str,
    risk_segment: str,
    days_past_due: int,
    outstanding_balance: float
) -> dict:
    """
    Validate an AI-generated recovery strategy recommendation
    against banking policy before presenting to bank officer.

    Returns:
        dict with:
            - approved (bool)
            - violations (list[str])
            - warnings (list[str])
            - requires_human_review (bool)
            - final_recommendation (str)
    """
    violations = []
    warnings   = []
    approved   = True

    # Rule: Intensive recovery requires human confirmation
    if strategy == "Intensive Recovery" and days_past_due < 30:
        violations.append(
            "Intensive Recovery strategy requires DPD >= 30. "
            "Downgrade recommendation to Loan Restructuring."
        )
        approved = False

    # Rule: Proactive Engagement not suitable for High risk
    if strategy == "Proactive Engagement" and risk_segment == "High":
        violations.append(
            "Proactive Engagement strategy is insufficient for High risk segment. "
            "Escalate to Loan Restructuring or Intensive Recovery."
        )
        approved = False

    # Warning: High outstanding + high risk
    if risk_segment == "High" and outstanding_balance > 500000:
        warnings.append(
            f"High outstanding balance (₹{outstanding_balance:,.0f}) with High risk. "
            f"Escalate to senior collections officer."
        )

    requires_human_review = (
        risk_segment == "High" or
        not approved or
        len(warnings) > 0
    )

    final_recommendation = (
        f"Strategy '{strategy}' validated. Human review {'required' if requires_human_review else 'not required'}."
        if approved else
        f"Strategy '{strategy}' has policy violations. Please review and adjust."
    )

    return {
        "approved":              approved,
        "violations":            violations,
        "warnings":              warnings,
        "requires_human_review": requires_human_review,
        "final_recommendation":  final_recommendation,
    }


# ─────────────────────────────────────────────
# LangGraph-Compatible Node
# ─────────────────────────────────────────────

def run_policy_guardrail_agent(state: dict) -> dict:
    """
    LangGraph-compatible agent node.

    Expects state keys:
        - recovery_strategy (dict)   ← from collections_intelligence_agent
        - risk_segment (str)
        - days_past_due (int)
        - outstanding_balance (float)

    Adds to state:
        - policy_validation (dict)
    """
    recovery_strategy   = state.get("recovery_strategy", {})
    risk_segment        = state.get("risk_segment", "Low")
    days_past_due       = state.get("days_past_due", 0)
    outstanding_balance = state.get("outstanding_balance", 0.0)

    strategy_name = recovery_strategy.get("strategy", "Standard Follow-Up")

    policy_validation = validate_recovery_recommendation(
        strategy            = strategy_name,
        risk_segment        = risk_segment,
        days_past_due       = days_past_due,
        outstanding_balance = outstanding_balance,
    )

    state.update({
        "policy_validation": policy_validation
    })

    return state