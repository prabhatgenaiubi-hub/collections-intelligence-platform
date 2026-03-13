
---

# Collections Intelligence Platform

## System Design Document

---

# 1. Project Overview

The **Collections Intelligence Platform** is an AI-driven system designed to help financial institutions **proactively manage loan collections before delinquency occurs**.

The platform integrates:

* predictive analytics
* contextual borrower intelligence
* explainable AI reasoning
* multilingual interaction
* agentic AI orchestration

to enable **data-driven and ethical recovery strategies**.

The system supports two primary users:

1. **Customers (Borrowers)**
2. **Bank Officers (Collections / Risk Teams)**

---

# 2. User Personas

## 2.1 Bank Officer (Internal User)

Primary users include:

* Collections teams
* Recovery operations teams
* Risk management teams

Responsibilities:

* Identify borrowers likely to miss payments
* Analyze repayment patterns
* Review risk segmentation
* Approve Grace / Restructure requests
* Review borrower interaction summaries
* Evaluate recovery recommendations
* Monitor portfolio risk

---

## 2.2 Customer (External User)

Customers use the platform to:

* View loan details
* View EMI payment history
* Request grace period
* Request loan restructuring
* Save preferred communication channel
* Interact with AI assistant

---

# 3. Final UI Design

---

# Login Page

Users select role:

```
Customer
Bank Officer
```

Fields:

```
User ID
Password
```

---

# 3.1 Customer Portal

---

# Customer Profile Header

Displays:

```
Customer Name
Phone Number
Email
Total Loan Exposure
Customer Relationship Assessment
```

---

# Customer Relationship Assessment

This section provides **personalized insights about your loan relationship and repayment activity**.

The assessment is generated using:

* loan interaction history
* recent payment behavior
* next EMI due timeline
* customer tenure with the bank
* overall repayment consistency

Example shown to customer:

```
Customer Relationship Assessment

You have maintained a generally stable repayment pattern with the bank.
There have been a few short-term delays recently, but your overall repayment behavior remains positive.

Your next EMI is due in 10 days.
Based on your recent payment activity and interaction with the bank, you may receive reminders or support options if needed.
```

This ensures the language is **supportive and customer-friendly**.

---

# Customer Menu

Left navigation menu:

```
Your Loans
Preferred Channel
AI Assistant
```

---

# Your Loans Page

Loan table

| Loan ID | Loan Type | Outstanding | Next EMI | Grace Status | Restructure Status | Action |

Actions:

```
Grace Request
Restructure Request
```

---

# Loan Details Panel

Clicking **Loan ID** opens loan details.

Displays:

```
Loan Details
Outstanding Balance
Next EMI
Delinquency Score
Payment History Graph
Recommendation
```

Example:

```
Recommendation

Grace outreach suggested due to temporary payment delay pattern.
```

---

# Preferred Communication Channel

Customer can save preferred communication channel:

```
WhatsApp
SMS
Email
Voice Call
```

This preference is used by the **Multichannel Outreach Agent**.

---

# AI Assistant

Customer AI assistant supports:

```
Loan queries
EMI information
Grace eligibility
Multilingual interaction
Voice interaction
```

---

# Chat Sessions (ChatGPT-Style)

Customers can:

```
View previous chat sessions
Start new chat
Continue previous conversation
```

Example chat sessions:

```
EMI Payment Query
Grace Request Discussion
Loan Restructure Query
```

---

# 3.2 Bank Officer Portal

---

# Dashboard

Displays portfolio insights:

```
Total Borrowers
High Risk Accounts
Expected Recovery
Self Cure Rate
NPV Estimate
```

Charts:

```
Risk Distribution
Recovery Strategy Mix
```

---

# Customer Search

Search filters:

```
Loan ID
Customer ID
Customer Name
Loan Type
Risk Segment
```

Search logic uses **OR condition**.

Example:

```
Loan ID OR Customer ID OR Customer Name OR Loan Type OR Risk Segment
```

---

# Search Results Table

| Loan ID | Customer ID | Name | Loan Type | Loan Amount | Risk | Recommended Channel |

Clicking **Loan ID** opens the **Loan Intelligence Panel**.

---

# Loan Intelligence Panel

Displays:

```
Loan Details
Customer Details
Payment Pattern Graph
Risk Segment
Recommended Channel
Sentiment Analysis
Tonality Analysis
Last 3 Interaction Summaries
Recovery Recommendation
```

---

# Grace Request Page

| Loan ID | Loan Type | Outstanding | Next EMI | Action |

Actions:

```
Approve
Reject
Decision Comment
```

Example decision:

```
Decision: Rejected
Comment: Grace not allowed due to repeated EMI delay.
```

---

# Customer View After Decision

Customer sees:

```
Grace Status

Approved – Grace granted for 7 days
```

or

```
Rejected – Grace not allowed due to repeated EMI delays
```

Same workflow applies for **Restructure Requests**.

---

# 4. High Level Architecture

```
Browser
   │
React Frontend
   │
FastAPI Backend
   │
LangGraph Orchestrator
   │
 ┌─────────────┬─────────────┬─────────────┐
 │             │             │
Context        Collections    Multichannel
Memory Agent   Intelligence   Outreach Agent
(SQL + Vector) Agent          (Communication)
        │
Context Builder
        │
LLM Reasoning (Llama-3 via Ollama)
        │
Policy Guardrails
        │
Human Review
        │
Final Recommendation
```

---

# 5. Agent Architecture

The platform uses **Agentic AI architecture orchestrated with LangGraph**.

Agents include:

### Multichannel Outreach Agent

Handles communication across channels:

```
WhatsApp
SMS
Email
Voice
Chat
```

---

### Customer Context & Memory Agent

Maintains contextual borrower understanding.

Sources:

```
interaction history
chat sessions
sentiment scores
interaction summaries
```

Stored in:

```
PostgreSQL
Chroma Vector Database
```

---

### Collections Intelligence Agent

Performs analytics:

```
risk segmentation
self cure probability
value at risk
recovery strategy generation
NPV calculation
```

---

### Sentiment & Interaction Analysis Agent

Analyzes borrower interactions:

```
sentiment detection
tonality analysis
interaction summarization
```

---

### LLM Reasoning Agent

Uses **Llama-3 via Ollama**.

Responsibilities:

```
generate explainable insights
summarize borrower conversations
produce contextual recommendations
```

---

### Policy Guardrail Agent

Ensures compliance with banking policies before recommendations are finalized.

---

# 6. Chat Session & Conversation Memory

The system supports **ChatGPT-style chat sessions**.

---

## Chat Sessions Table

```
chat_sessions
session_id
customer_id
session_title
created_at
last_updated
```

---

## Chat Messages Table

```
chat_messages
message_id
session_id
role
message_text
timestamp
```

Roles:

```
user
assistant
system
```

---

# Vector Memory Storage

Stored in **Chroma DB**

```
memory_id
customer_id
interaction_summary
embedding_vector
timestamp
```

Example memory:

```
Customer requested grace period due to salary delay.
```

---

# Combined Memory Architecture

```
User Message
     ↓
Save message in SQL
     ↓
Generate interaction summary
     ↓
Store summary in Vector DB
     ↓
Retrieve relevant context for future conversations
```

---

# 7. Context Window Management

LLMs cannot process unlimited chat history.

A **Context Builder** selects relevant context.

Sources used:

```
recent chat messages
semantic memory retrieval
loan data
payment behavior
risk segmentation
```

Only relevant information is sent to the LLM.

---

# 8. Retrieval Augmented Generation (RAG)

Knowledge sources:

```
collection policies
regulatory guidelines
internal recovery procedures
```

Workflow:

```
User Query
   ↓
Vector Search
   ↓
Policy Retrieval
   ↓
LLM Reasoning
   ↓
Explainable Recommendation
```

---

# 9. Human-in-the-Loop Guardrails

Ensures AI outputs are **safe and compliant**.

Workflow:

```
AI Recommendation
      ↓
Policy Guardrail Validation
      ↓
Bank Officer Review
      ↓
Final Decision
```

Example rule:

```
Grace allowed only if Days Past Due < 30
```

---

# 10. Event-Driven Architecture

To support scalability the system can process events such as:

```
EMI Missed
Grace Request Created
Payment Received
Customer Interaction Logged
```

Event flow:

```
Loan Event
    ↓
Event Stream
    ↓
Analytics Engine
    ↓
Collections Intelligence Agent
```

Benefits:

```
real-time risk detection
asynchronous processing
high scalability
```

---

# 11. Technology Stack

| Layer           | Technology       | Purpose             |
| --------------- | ---------------- | ------------------- |
| Frontend        | React + Tailwind | UI                  |
| Backend         | FastAPI          | APIs                |
| Agent Framework | LangGraph        | agent orchestration |
| AI Utilities    | LangChain        | RAG workflows       |
| LLM Runtime     | Ollama           | local inference     |
| LLM Model       | Llama-3 8B       | reasoning           |
| Multilingual AI | Sarvam           | voice & translation |
| Vector DB       | Chroma           | semantic memory     |
| Relational DB   | PostgreSQL       | structured data     |
| Analytics       | Python ML        | risk models         |

---

# 12. Database Design

### Customer Table

```
customer_id
customer_name
mobile_number
email_id
preferred_language
preferred_channel
relationship_assessment
credit_score
monthly_income
```

---

### Loan Table

```
loan_id
customer_id
loan_type
loan_amount
interest_rate
emi_amount
emi_due_date
outstanding_balance
days_past_due
risk_segment
self_cure_probability
```

---

### Payment History

```
payment_id
loan_id
payment_date
payment_amount
payment_method
```

---

### Interaction History

```
interaction_id
customer_id
interaction_type
interaction_time
conversation_text
sentiment_score
tonality_score
interaction_summary
```

---

### Grace Requests

```
request_id
loan_id
customer_id
request_status
decision_comment
request_date
approved_by
decision_date
```

---

### Restructure Requests

```
request_id
loan_id
customer_id
request_status
decision_comment
request_date
approved_by
decision_date
```

---

### Customer Preferences

```
customer_id
preferred_channel
preferred_language
updated_at
```

---

# 13. Analytics Engine

Deterministic Python calculations:

```
Days Past Due
Payment trend analysis
Value at Risk
Self Cure Probability
NPV calculation
```

LLM **does not perform financial calculations**.

---

# 14. Project Folder Structure

```
collections-intelligence-platform
│
├── frontend
│   ├── pages
│   ├── components
│   ├── charts
│   ├── chatbot
│
├── backend
│   ├── main.py
│   ├── routers
│   ├── agents
│   ├── services
│   ├── langgraph
│   ├── db
│   ├── vector
│
├── analytics
│   ├── risk_models.py
│   ├── npv_calculator.py
│
├── docs
│   ├── system_design.md
│   ├── architecture.md
│
└── README.md
```

---

# 15. Local POC Deployment

All components run locally:

```
Browser
   │
React UI
   │
FastAPI API
   │
LangGraph Workflow
   │
 ├ PostgreSQL
 ├ Chroma Vector DB
 ├ Python ML Models
 └ Ollama Llama-3
```

---

# Final Outcome

The **Collections Intelligence Platform** enables banks to:

```
predict repayment risk early
engage borrowers proactively
provide explainable recovery strategies
maintain contextual borrower intelligence
improve collections efficiency
```

---

