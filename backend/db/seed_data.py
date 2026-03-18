from backend.db.database import engine, SessionLocal, Base
from backend.db.models import (
    Customer, Loan, PaymentHistory, InteractionHistory,
    GraceRequest, RestructureRequest, CustomerPreference,
    ChatSession, ChatMessage, BankOfficer
)

def seed():
    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # Check if already seeded
    if db.query(Customer).count() > 0:
        print("Database already seeded. Skipping.")
        db.close()
        return

    print("Seeding database...")

    # ─────────────────────────────────────────────
    # Bank Officers
    # ─────────────────────────────────────────────
    officers = [
        BankOfficer(
            officer_id="OFF001",
            officer_name="Rajesh Kumar",
            email="rajesh.kumar@bank.com",
            password="officer123",
            department="Collections"
        ),
        BankOfficer(
            officer_id="OFF002",
            officer_name="Priya Sharma",
            email="priya.sharma@bank.com",
            password="officer123",
            department="Recovery"
        ),
    ]
    db.add_all(officers)

    # ─────────────────────────────────────────────
    # Customers
    # ─────────────────────────────────────────────
    customers = [
        Customer(
            customer_id="CUST001",
            customer_name="Arun Mehta",
            mobile_number="9876543210",
            email_id="arun.mehta@email.com",
            preferred_language="English",
            preferred_channel="WhatsApp",
            credit_score=620,
            monthly_income=45000.0,
            password="password123",
            relationship_assessment=(
                "You have maintained a generally stable repayment pattern with the bank. "
                "There have been a few short-term delays recently, but your overall repayment "
                "behavior remains positive. Your next EMI is due in 10 days. Based on your recent "
                "payment activity and interaction with the bank, you may receive reminders or "
                "support options if needed."
            )
        ),
        Customer(
            customer_id="CUST002",
            customer_name="Sunita Rao",
            mobile_number="9845678901",
            email_id="sunita.rao@email.com",
            preferred_language="Hindi",
            preferred_channel="SMS",
            credit_score=710,
            monthly_income=72000.0,
            password="password123",
            relationship_assessment=(
                "You have an excellent repayment track record with the bank. "
                "Your consistency and timely payments reflect strong financial discipline. "
                "Your next EMI is due in 5 days. Keep up the great work!"
            )
        ),
        Customer(
            customer_id="CUST003",
            customer_name="Vikram Nair",
            mobile_number="9712345678",
            email_id="vikram.nair@email.com",
            preferred_language="English",
            preferred_channel="Email",
            credit_score=540,
            monthly_income=38000.0,
            password="password123",
            relationship_assessment=(
                "Your recent payment behavior shows some irregularity. "
                "There have been multiple missed EMI payments in the past 3 months. "
                "Your next EMI is overdue by 15 days. We encourage you to contact the bank "
                "to discuss available support options such as grace period or restructuring."
            )
        ),
        Customer(
            customer_id="CUST004",
            customer_name="Meena Pillai",
            mobile_number="9632587410",
            email_id="meena.pillai@email.com",
            preferred_language="Tamil",
            preferred_channel="Voice Call",
            credit_score=680,
            monthly_income=55000.0,
            password="password123",
            relationship_assessment=(
                "You have shown consistent repayment behavior over the past year. "
                "A minor delay was observed last month, which appears to be an isolated incident. "
                "Your next EMI is due in 3 days. We appreciate your commitment to timely payments."
            )
        ),
        Customer(
            customer_id="CUST005",
            customer_name="Rahul Joshi",
            mobile_number="9523698741",
            email_id="rahul.joshi@email.com",
            preferred_language="English",
            preferred_channel="Email",
            credit_score=490,
            monthly_income=32000.0,
            password="password123",
            relationship_assessment=(
                "Your account has been flagged for high delinquency risk. "
                "Multiple EMIs have been missed in the past 2 months. "
                "Your outstanding balance requires immediate attention. "
                "Please contact the bank at the earliest to explore recovery options."
            )
        ),
        Customer(
            customer_id="CUST006",
            customer_name="Anjali Singh",
            mobile_number="9874563210",
            email_id="anjali.singh@email.com",
            preferred_language="Hindi",
            preferred_channel="WhatsApp",
            credit_score=750,
            monthly_income=90000.0,
            password="password123",
            relationship_assessment=(
                "You are a premium customer with an outstanding repayment history. "
                "All EMIs have been paid on time and your credit profile is excellent. "
                "Your next EMI is due in 12 days. Thank you for your continued trust in the bank."
            )
        ),
    ]
    db.add_all(customers)
    db.flush()

    # ─────────────────────────────────────────────
    # Customer Preferences
    # ─────────────────────────────────────────────
    preferences = [
        CustomerPreference(customer_id="CUST001", preferred_channel="WhatsApp", preferred_language="English"),
        CustomerPreference(customer_id="CUST002", preferred_channel="SMS",       preferred_language="Hindi"),
        CustomerPreference(customer_id="CUST003", preferred_channel="Email",     preferred_language="English"),
        CustomerPreference(customer_id="CUST004", preferred_channel="Voice Call",preferred_language="Tamil"),
        CustomerPreference(customer_id="CUST005", preferred_channel="Email",     preferred_language="English"),
        CustomerPreference(customer_id="CUST006", preferred_channel="WhatsApp",  preferred_language="Hindi"),
    ]
    db.add_all(preferences)

    # ─────────────────────────────────────────────
    # Loans
    # ─────────────────────────────────────────────
    loans = [
        Loan(
            loan_id="LOAN001", customer_id="CUST001",
            loan_type="Personal Loan", loan_amount=300000.0, interest_rate=12.5,
            emi_amount=6800.0, emi_due_date="2026-03-23",
            outstanding_balance=210000.0, days_past_due=10,
            risk_segment="Medium", self_cure_probability=0.55,
            recommended_channel="WhatsApp"
        ),
        Loan(
            loan_id="LOAN002", customer_id="CUST002",
            loan_type="Home Loan", loan_amount=2500000.0, interest_rate=8.75,
            emi_amount=22000.0, emi_due_date="2026-03-18",
            outstanding_balance=1800000.0, days_past_due=0,
            risk_segment="Low", self_cure_probability=0.90,
            recommended_channel="SMS"
        ),
        Loan(
            loan_id="LOAN003", customer_id="CUST003",
            loan_type="Personal Loan", loan_amount=150000.0, interest_rate=16.0,
            emi_amount=4200.0, emi_due_date="2026-02-28",
            outstanding_balance=120000.0, days_past_due=15,
            risk_segment="High", self_cure_probability=0.25,
            recommended_channel="Email"
        ),
        Loan(
            loan_id="LOAN004", customer_id="CUST004",
            loan_type="Car Loan", loan_amount=800000.0, interest_rate=9.5,
            emi_amount=16500.0, emi_due_date="2026-03-16",
            outstanding_balance=560000.0, days_past_due=3,
            risk_segment="Low", self_cure_probability=0.80,
            recommended_channel="Voice Call"
        ),
        Loan(
            loan_id="LOAN005", customer_id="CUST005",
            loan_type="Business Loan", loan_amount=500000.0, interest_rate=14.0,
            emi_amount=11500.0, emi_due_date="2026-02-15",
            outstanding_balance=430000.0, days_past_due=28,
            risk_segment="High", self_cure_probability=0.15,
            recommended_channel="Email"
        ),
        Loan(
            loan_id="LOAN006", customer_id="CUST006",
            loan_type="Home Loan", loan_amount=4000000.0, interest_rate=8.25,
            emi_amount=35000.0, emi_due_date="2026-03-25",
            outstanding_balance=3200000.0, days_past_due=0,
            risk_segment="Low", self_cure_probability=0.95,
            recommended_channel="WhatsApp"
        ),
        Loan(
            loan_id="LOAN007", customer_id="CUST001",
            loan_type="Car Loan", loan_amount=600000.0, interest_rate=10.0,
            emi_amount=13000.0, emi_due_date="2026-03-20",
            outstanding_balance=480000.0, days_past_due=5,
            risk_segment="Medium", self_cure_probability=0.60,
            recommended_channel="WhatsApp"
        ),
    ]
    db.add_all(loans)
    db.flush()

    # ─────────────────────────────────────────────
    # Payment History
    # ─────────────────────────────────────────────
    payments = [
        # LOAN001 - Arun Mehta (some delays)
        PaymentHistory(loan_id="LOAN001", payment_date="2026-02-23", payment_amount=6800.0, payment_method="UPI"),
        PaymentHistory(loan_id="LOAN001", payment_date="2026-01-25", payment_amount=6800.0, payment_method="UPI"),
        PaymentHistory(loan_id="LOAN001", payment_date="2025-12-28", payment_amount=6800.0, payment_method="Bank Transfer"),
        PaymentHistory(loan_id="LOAN001", payment_date="2025-11-30", payment_amount=6800.0, payment_method="UPI"),
        PaymentHistory(loan_id="LOAN001", payment_date="2025-10-23", payment_amount=6800.0, payment_method="Bank Transfer"),

        # LOAN002 - Sunita Rao (consistent)
        PaymentHistory(loan_id="LOAN002", payment_date="2026-03-01", payment_amount=22000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN002", payment_date="2026-02-01", payment_amount=22000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN002", payment_date="2026-01-02", payment_amount=22000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN002", payment_date="2025-12-01", payment_amount=22000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN002", payment_date="2025-11-01", payment_amount=22000.0, payment_method="NEFT"),

        # LOAN003 - Vikram Nair (frequent delays)
        PaymentHistory(loan_id="LOAN003", payment_date="2026-01-10", payment_amount=4200.0, payment_method="UPI"),
        PaymentHistory(loan_id="LOAN003", payment_date="2025-12-15", payment_amount=2100.0, payment_method="UPI"),
        PaymentHistory(loan_id="LOAN003", payment_date="2025-11-20", payment_amount=4200.0, payment_method="Bank Transfer"),
        PaymentHistory(loan_id="LOAN003", payment_date="2025-10-18", payment_amount=4200.0, payment_method="UPI"),

        # LOAN004 - Meena Pillai (mostly on time)
        PaymentHistory(loan_id="LOAN004", payment_date="2026-03-10", payment_amount=16500.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN004", payment_date="2026-02-10", payment_amount=16500.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN004", payment_date="2026-01-12", payment_amount=16500.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN004", payment_date="2025-12-10", payment_amount=16500.0, payment_method="Bank Transfer"),

        # LOAN005 - Rahul Joshi (high risk - missed multiple)
        PaymentHistory(loan_id="LOAN005", payment_date="2026-01-05", payment_amount=11500.0, payment_method="UPI"),
        PaymentHistory(loan_id="LOAN005", payment_date="2025-11-20", payment_amount=5750.0,  payment_method="UPI"),
        PaymentHistory(loan_id="LOAN005", payment_date="2025-10-15", payment_amount=11500.0, payment_method="Bank Transfer"),

        # LOAN006 - Anjali Singh (premium - always on time)
        PaymentHistory(loan_id="LOAN006", payment_date="2026-03-05", payment_amount=35000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN006", payment_date="2026-02-05", payment_amount=35000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN006", payment_date="2026-01-05", payment_amount=35000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN006", payment_date="2025-12-05", payment_amount=35000.0, payment_method="NEFT"),
        PaymentHistory(loan_id="LOAN006", payment_date="2025-11-05", payment_amount=35000.0, payment_method="NEFT"),
    ]
    db.add_all(payments)

    # ─────────────────────────────────────────────
    # Interaction History
    # ─────────────────────────────────────────────
    interactions = [
        InteractionHistory(
            interaction_id="INT001", customer_id="CUST001",
            interaction_type="Call", interaction_time="2026-03-05 10:30:00",
            conversation_text="Customer called to inquire about grace period options due to salary delay.",
            sentiment_score=0.2, tonality_score="Neutral",
            interaction_summary="Customer requested grace period due to temporary salary delay. Informed about eligibility criteria."
        ),
        InteractionHistory(
            interaction_id="INT002", customer_id="CUST001",
            interaction_type="Chat", interaction_time="2026-03-10 14:00:00",
            conversation_text="Customer asked about EMI schedule and outstanding balance.",
            sentiment_score=0.3, tonality_score="Positive",
            interaction_summary="Customer inquired about EMI schedule. Provided loan details and next due date."
        ),
        InteractionHistory(
            interaction_id="INT003", customer_id="CUST003",
            interaction_type="Call", interaction_time="2026-03-01 09:00:00",
            conversation_text="Customer expressed frustration about high EMI amount. Requested restructuring.",
            sentiment_score=-0.6, tonality_score="Negative",
            interaction_summary="Customer highly stressed about repayment burden. Expressed interest in loan restructuring."
        ),
        InteractionHistory(
            interaction_id="INT004", customer_id="CUST003",
            interaction_type="Email", interaction_time="2026-03-08 11:30:00",
            conversation_text="Customer sent email requesting information about restructuring eligibility.",
            sentiment_score=-0.3, tonality_score="Neutral",
            interaction_summary="Customer submitted written request for restructuring information."
        ),
        InteractionHistory(
            interaction_id="INT005", customer_id="CUST005",
            interaction_type="Call", interaction_time="2026-03-02 16:00:00",
            conversation_text="Customer mentioned business downturn and inability to pay EMI for the next 2 months.",
            sentiment_score=-0.8, tonality_score="Negative",
            interaction_summary="Customer in financial distress due to business losses. Requested emergency support."
        ),
        InteractionHistory(
            interaction_id="INT006", customer_id="CUST005",
            interaction_type="SMS", interaction_time="2026-03-10 08:00:00",
            conversation_text="Customer replied to SMS reminder saying they need more time.",
            sentiment_score=-0.4, tonality_score="Negative",
            interaction_summary="Customer acknowledged EMI overdue and requested extended time."
        ),
        InteractionHistory(
            interaction_id="INT007", customer_id="CUST002",
            interaction_type="Chat", interaction_time="2026-03-09 12:00:00",
            conversation_text="Customer asked about prepayment options and interest savings.",
            sentiment_score=0.7, tonality_score="Positive",
            interaction_summary="Customer interested in prepayment. Provided details on prepayment charges and savings."
        ),
        InteractionHistory(
            interaction_id="INT008", customer_id="CUST004",
            interaction_type="Call", interaction_time="2026-03-11 10:00:00",
            conversation_text="Customer called to confirm EMI due date and payment method.",
            sentiment_score=0.5, tonality_score="Positive",
            interaction_summary="Customer proactively confirmed EMI due date. Updated preferred payment method."
        ),
    ]
    db.add_all(interactions)

    # ─────────────────────────────────────────────
    # Grace Requests
    # ─────────────────────────────────────────────
    grace_requests = [
        GraceRequest(
            request_id="GR001", loan_id="LOAN001", customer_id="CUST001",
            request_status="Pending",
            decision_comment=None,
            request_date="2026-03-10",
            approved_by=None, decision_date=None
        ),
        GraceRequest(
            request_id="GR002", loan_id="LOAN003", customer_id="CUST003",
            request_status="Rejected",
            decision_comment="Grace not allowed due to repeated EMI delays beyond 30 days.",
            request_date="2026-03-05",
            approved_by="OFF001", decision_date="2026-03-07"
        ),
        GraceRequest(
            request_id="GR003", loan_id="LOAN005", customer_id="CUST005",
            request_status="Approved",
            decision_comment="Grace granted for 7 days considering business hardship.",
            request_date="2026-03-08",
            approved_by="OFF002", decision_date="2026-03-09"
        ),
    ]
    db.add_all(grace_requests)

    # ─────────────────────────────────────────────
    # Restructure Requests
    # ─────────────────────────────────────────────
    restructure_requests = [
        RestructureRequest(
            request_id="RR001", loan_id="LOAN003", customer_id="CUST003",
            request_status="Pending",
            decision_comment=None,
            request_date="2026-03-09",
            approved_by=None, decision_date=None
        ),
        RestructureRequest(
            request_id="RR002", loan_id="LOAN005", customer_id="CUST005",
            request_status="Pending",
            decision_comment=None,
            request_date="2026-03-11",
            approved_by=None, decision_date=None
        ),
    ]
    db.add_all(restructure_requests)

    # ─────────────────────────────────────────────
    # Chat Sessions & Messages
    # ─────────────────────────────────────────────
    chat_sessions = [
        ChatSession(
            session_id="SESS001", customer_id="CUST001",
            session_title="EMI Payment Query",
            created_at="2026-03-10 14:00:00", last_updated="2026-03-10 14:15:00"
        ),
        ChatSession(
            session_id="SESS002", customer_id="CUST001",
            session_title="Grace Request Discussion",
            created_at="2026-03-11 09:00:00", last_updated="2026-03-11 09:20:00"
        ),
        ChatSession(
            session_id="SESS003", customer_id="CUST003",
            session_title="Loan Restructure Query",
            created_at="2026-03-08 11:00:00", last_updated="2026-03-08 11:30:00"
        ),
    ]
    db.add_all(chat_sessions)
    db.flush()

    chat_messages = [
        ChatMessage(session_id="SESS001", role="user",      message_text="What is my next EMI amount?",                                    timestamp="2026-03-10 14:01:00"),
        ChatMessage(session_id="SESS001", role="assistant", message_text="Your next EMI of ₹6,800 is due on 23rd March 2026 for LOAN001.", timestamp="2026-03-10 14:01:30"),
        ChatMessage(session_id="SESS001", role="user",      message_text="Can I get a grace period?",                                      timestamp="2026-03-10 14:02:00"),
        ChatMessage(session_id="SESS001", role="assistant", message_text="Based on your account, you may be eligible for a grace period of up to 7 days. Would you like me to submit a request?", timestamp="2026-03-10 14:02:30"),

        ChatMessage(session_id="SESS002", role="user",      message_text="I submitted a grace request. What is its status?",               timestamp="2026-03-11 09:01:00"),
        ChatMessage(session_id="SESS002", role="assistant", message_text="Your grace request GR001 is currently Pending review by the bank officer.",  timestamp="2026-03-11 09:01:30"),

        ChatMessage(session_id="SESS003", role="user",      message_text="I want to restructure my loan. What are my options?",            timestamp="2026-03-08 11:01:00"),
        ChatMessage(session_id="SESS003", role="assistant", message_text="Based on your current outstanding balance of ₹1,20,000, restructuring options include extending tenure by 12-24 months or reducing EMI by adjusting the interest rate. Would you like me to submit a restructure request?", timestamp="2026-03-08 11:01:45"),
        ChatMessage(session_id="SESS003", role="user",      message_text="Yes, please submit a request.",                                  timestamp="2026-03-08 11:02:00"),
        ChatMessage(session_id="SESS003", role="assistant", message_text="Your restructure request has been submitted successfully. A bank officer will review it within 2 business days.",     timestamp="2026-03-08 11:02:30"),
    ]
    db.add_all(chat_messages)

    db.commit()
    db.close()
    print("✅ Database seeded successfully.")


if __name__ == "__main__":
    seed()