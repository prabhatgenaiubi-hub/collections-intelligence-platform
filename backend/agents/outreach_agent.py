"""
Multichannel Outreach Agent

Responsibilities:
  - Determine the best outreach channel for a customer
  - Generate channel-appropriate outreach messages
  - Simulate outreach delivery (WhatsApp / SMS / Email / Voice / Chat)
  - Log outreach interaction to SQL

For the prototype, all outreach is SIMULATED (no real API calls).
In production, integrate with:
  - WhatsApp Business API
  - SMS Gateway (Twilio / Gupshup)
  - Email SMTP
  - Voice (Sarvam AI / IVR)
"""

from datetime import datetime
from sqlalchemy.orm import Session
from backend.db.models import InteractionHistory


# ─────────────────────────────────────────────
# Channel Templates
# ─────────────────────────────────────────────

MESSAGE_TEMPLATES = {

    "WhatsApp": {
        "reminder": (
            "Hi {name} 👋, this is a friendly reminder from {bank_name}.\n\n"
            "Your EMI of ₹{emi_amount:,.0f} for loan {loan_id} is due on {due_date}.\n\n"
            "Please ensure timely payment to maintain a healthy credit score.\n\n"
            "For any assistance, reply to this message or call us. 🙏"
        ),
        "overdue": (
            "Dear {name}, your EMI of ₹{emi_amount:,.0f} for loan {loan_id} "
            "is overdue by {dpd} days.\n\n"
            "Please make the payment at the earliest or contact us to discuss "
            "available options like grace period or restructuring.\n\n"
            "We are here to help. 🏦"
        ),
        "grace_approved": (
            "Dear {name}, your grace period request for loan {loan_id} has been ✅ APPROVED.\n\n"
            "{comment}\n\n"
            "Please utilize this time to arrange your payment. Thank you."
        ),
        "grace_rejected": (
            "Dear {name}, your grace period request for loan {loan_id} has been ❌ reviewed.\n\n"
            "{comment}\n\n"
            "Please contact us to explore other available options."
        ),
    },

    "SMS": {
        "reminder": (
            "ALERT: {bank_name} - EMI of Rs.{emi_amount:,.0f} for loan {loan_id} "
            "due on {due_date}. Pay on time to avoid late charges. "
            "Helpline: 1800-XXX-XXXX"
        ),
        "overdue": (
            "URGENT: {bank_name} - EMI for loan {loan_id} overdue by {dpd} days. "
            "Outstanding: Rs.{outstanding:,.0f}. "
            "Call 1800-XXX-XXXX or visit branch immediately."
        ),
        "grace_approved": (
            "{bank_name}: Grace period APPROVED for loan {loan_id}. "
            "{comment} Helpline: 1800-XXX-XXXX"
        ),
        "grace_rejected": (
            "{bank_name}: Grace period request for loan {loan_id} could not be approved. "
            "{comment} Call 1800-XXX-XXXX for assistance."
        ),
    },

    "Email": {
        "reminder": (
            "Subject: EMI Payment Reminder — Loan {loan_id}\n\n"
            "Dear {name},\n\n"
            "This is a friendly reminder that your EMI of ₹{emi_amount:,.0f} "
            "for loan {loan_id} is due on {due_date}.\n\n"
            "Please ensure timely payment to avoid any late payment charges "
            "and to maintain your credit score.\n\n"
            "If you have already made the payment, please disregard this message.\n\n"
            "For any queries or assistance, please contact our collections team.\n\n"
            "Regards,\n{bank_name} Collections Team"
        ),
        "overdue": (
            "Subject: Urgent — Overdue EMI for Loan {loan_id}\n\n"
            "Dear {name},\n\n"
            "We wish to bring to your attention that your EMI of ₹{emi_amount:,.0f} "
            "for loan {loan_id} is overdue by {dpd} days.\n\n"
            "Your current outstanding balance is ₹{outstanding:,.0f}.\n\n"
            "We urge you to clear the outstanding amount at the earliest. "
            "If you are facing financial difficulties, please contact us to discuss "
            "available options such as grace period or loan restructuring.\n\n"
            "Regards,\n{bank_name} Collections Team"
        ),
        "grace_approved": (
            "Subject: Grace Period Approved — Loan {loan_id}\n\n"
            "Dear {name},\n\n"
            "We are pleased to inform you that your grace period request "
            "for loan {loan_id} has been approved.\n\n"
            "Decision: {comment}\n\n"
            "Please utilize this grace period to arrange your payment.\n\n"
            "Regards,\n{bank_name} Collections Team"
        ),
        "grace_rejected": (
            "Subject: Grace Period Request Update — Loan {loan_id}\n\n"
            "Dear {name},\n\n"
            "We regret to inform you that your grace period request "
            "for loan {loan_id} could not be approved at this time.\n\n"
            "Reason: {comment}\n\n"
            "Please contact our collections team to explore other available options.\n\n"
            "Regards,\n{bank_name} Collections Team"
        ),
    },

    "Voice Call": {
        "reminder": (
            "[VOICE SCRIPT] Hello, may I speak with {name}? "
            "This is an automated call from {bank_name}. "
            "Your EMI of Rupees {emi_amount:,.0f} for loan number {loan_id} "
            "is due on {due_date}. "
            "Please ensure timely payment. "
            "For assistance, press 1 to speak with an agent. Thank you."
        ),
        "overdue": (
            "[VOICE SCRIPT] Hello, may I speak with {name}? "
            "This is an important call from {bank_name}. "
            "Your EMI payment for loan {loan_id} is overdue by {dpd} days. "
            "Please contact us immediately at 1800-XXX-XXXX "
            "or visit your nearest branch. Thank you."
        ),
        "grace_approved": (
            "[VOICE SCRIPT] Hello {name}, this is {bank_name}. "
            "We are calling to inform you that your grace period request "
            "for loan {loan_id} has been approved. {comment} "
            "Please arrange your payment within the grace period. Thank you."
        ),
        "grace_rejected": (
            "[VOICE SCRIPT] Hello {name}, this is {bank_name}. "
            "Regarding your grace period request for loan {loan_id}, "
            "we regret that we are unable to approve it at this time. "
            "Please contact us at 1800-XXX-XXXX to discuss other options. Thank you."
        ),
    },
}


# ─────────────────────────────────────────────
# Generate Outreach Message
# ─────────────────────────────────────────────

def generate_outreach_message(
    channel: str,
    message_type: str,
    customer_name: str,
    loan_id: str,
    emi_amount: float,
    due_date: str = "N/A",
    dpd: int = 0,
    outstanding: float = 0.0,
    comment: str = "",
    bank_name: str = "Collections Intelligence Bank"
) -> str:
    """
    Generate a channel-appropriate outreach message using templates.

    Args:
        channel:       WhatsApp | SMS | Email | Voice Call
        message_type:  reminder | overdue | grace_approved | grace_rejected
        ...

    Returns:
        Formatted message string
    """
    channel_templates = MESSAGE_TEMPLATES.get(channel, MESSAGE_TEMPLATES["SMS"])
    template          = channel_templates.get(message_type, channel_templates.get("reminder", ""))

    try:
        message = template.format(
            name        = customer_name,
            bank_name   = bank_name,
            loan_id     = loan_id,
            emi_amount  = emi_amount,
            due_date    = due_date,
            dpd         = dpd,
            outstanding = outstanding,
            comment     = comment or "Please contact us for more information.",
        )
    except KeyError as e:
        message = (
            f"Dear {customer_name}, this is a message from {bank_name} "
            f"regarding your loan {loan_id}. Please contact us for details."
        )

    return message


# ─────────────────────────────────────────────
# Simulate Outreach Delivery
# ─────────────────────────────────────────────

def simulate_outreach_delivery(
    channel: str,
    recipient: str,
    message: str
) -> dict:
    """
    Simulate sending a message via the specified channel.
    In production, replace with real API integrations.

    Returns:
        dict with delivery status and timestamp
    """
    # Simulate delivery success
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*60}")
    print(f"[OUTREACH SIMULATION] Channel: {channel}")
    print(f"Recipient: {recipient}")
    print(f"Timestamp: {timestamp}")
    print(f"Message:\n{message}")
    print(f"{'='*60}\n")

    return {
        "status":    "Delivered",
        "channel":   channel,
        "recipient": recipient,
        "timestamp": timestamp,
        "simulated": True,
    }


# ─────────────────────────────────────────────
# Full Outreach Pipeline
# ─────────────────────────────────────────────

def send_outreach(
    db: Session,
    customer_id: str,
    customer_name: str,
    channel: str,
    message_type: str,
    loan_id: str,
    emi_amount: float,
    contact: str,
    due_date: str = "N/A",
    dpd: int = 0,
    outstanding: float = 0.0,
    comment: str = ""
) -> dict:
    """
    Full outreach pipeline:
      1. Generate message
      2. Simulate delivery
      3. Log interaction to SQL

    Args:
        db:            SQLAlchemy session
        customer_id:   Customer ID
        customer_name: Customer name
        channel:       Outreach channel
        message_type:  reminder | overdue | grace_approved | grace_rejected
        loan_id:       Loan ID
        emi_amount:    EMI amount
        contact:       Phone / email / WhatsApp number
        due_date:      EMI due date
        dpd:           Days past due
        outstanding:   Outstanding balance
        comment:       Decision comment (for grace/restructure notifications)

    Returns:
        dict with delivery result
    """
    # ── Generate Message ──────────────────────────────────────────
    message = generate_outreach_message(
        channel       = channel,
        message_type  = message_type,
        customer_name = customer_name,
        loan_id       = loan_id,
        emi_amount    = emi_amount,
        due_date      = due_date,
        dpd           = dpd,
        outstanding   = outstanding,
        comment       = comment,
    )

    # ── Simulate Delivery ─────────────────────────────────────────
    delivery_result = simulate_outreach_delivery(
        channel   = channel,
        recipient = contact,
        message   = message,
    )

    # ── Log to Interaction History ────────────────────────────────
    try:
        interaction = InteractionHistory(
            customer_id         = customer_id,
            interaction_type    = channel,
            interaction_time    = delivery_result["timestamp"],
            conversation_text   = message,
            sentiment_score     = 0.0,
            tonality_score      = "Neutral",
            interaction_summary = (
                f"Outreach sent via {channel} for loan {loan_id}. "
                f"Message type: {message_type}. Status: {delivery_result['status']}."
            )
        )
        db.add(interaction)
        db.commit()
    except Exception as e:
        print(f"[OutreachAgent] Interaction log failed (non-critical): {e}")

    return {
        "message":         message,
        "delivery_result": delivery_result,
    }


# ─────────────────────────────────────────────
# Determine Message Type from Loan Status
# ─────────────────────────────────────────────

def determine_message_type(dpd: int, risk_segment: str) -> str:
    """
    Determine appropriate message type based on loan delinquency status.
    """
    if dpd == 0:
        return "reminder"
    elif dpd < 30:
        return "overdue"
    else:
        return "overdue"


# ─────────────────────────────────────────────
# LangGraph-Compatible Node
# ─────────────────────────────────────────────

def run_outreach_agent(state: dict) -> dict:
    """
    LangGraph-compatible agent node.

    Expects state keys:
        - db (Session)
        - customer_id (str)
        - customer_profile (dict)
        - loans (list)
        - recommended_channel (str)
        - days_past_due (int)
        - risk_segment (str)

    Adds to state:
        - outreach_result (dict)
    """
    db               = state.get("db")
    customer_id      = state.get("customer_id")
    profile          = state.get("customer_profile", {})
    loans            = state.get("loans", [])
    channel          = state.get("recommended_channel", "Email")
    dpd              = state.get("days_past_due", 0)
    risk_segment     = state.get("risk_segment", "Low")

    if not loans or not db:
        state["outreach_result"] = {"status": "skipped", "reason": "No loans or DB session"}
        return state

    loan         = loans[0]
    message_type = determine_message_type(dpd, risk_segment)
    contact      = profile.get("mobile_number") or profile.get("email_id", "N/A")

    outreach_result = send_outreach(
        db            = db,
        customer_id   = customer_id,
        customer_name = profile.get("customer_name", "Customer"),
        channel       = channel,
        message_type  = message_type,
        loan_id       = loan.get("loan_id"),
        emi_amount    = loan.get("emi_amount", 0),
        contact       = contact,
        due_date      = loan.get("emi_due_date", "N/A"),
        dpd           = dpd,
        outstanding   = loan.get("outstanding_balance", 0),
    )

    state.update({
        "outreach_result": outreach_result
    })

    return state