# PayRecover AI — Autonomous Revenue Recovery & Customer Intent Engine

> Autonomous multi-agent revenue recovery engine for Razorpay merchants recovering failed & at-risk payment transactions.

---

## 1. Problem Statement
Every day, online merchants lose **10% to 25% of top-line revenue** to preventable payment failures:
* **Card 3DS timeouts & OTP abandonment**
* **UPI PSP app response latency**
* **Temporary bank server downtime**
* **Insufficient funds requiring delayed follow-up**
* **Recurring subscription e-mandate expiration**

Traditional systems either blindly spam customers with generic emails or do nothing. **PayRecover AI** introduces an autonomous multi-agent engine that investigates payment telemetry, scores recovery probability, understands customer intent, applies strict merchant guardrails, and executes intelligent recovery actions (such as generating 1-click Razorpay UPI links) over WhatsApp, SMS, and Email.

---

## 2. Core Architecture

```
React (TypeScript + Tailwind + Recharts)
           │
           ▼
     FastAPI Backend
 ┌─────────┼───────────────────────────┐
 ▼         ▼                           ▼
PostgreSQL  Redis                  AI Multi-Agent Core
                               ┌───────┼───────────────┐
                               ▼       ▼               ▼
                        Investigator  Intent AI    Strategist
                               │       │               │
                               └───────┼───────────────┘
                                       ▼
                                 Tool Executor
                          (Strict Merchant Guardrails)
                                       │
                  ┌────────────────────┼────────────────────┐
                  ▼                    ▼                    ▼
          Razorpay Test API      Messaging Engine     Payment Simulation
```

---

## 3. Technology Stack

* **Frontend**: React 18, TypeScript, Tailwind CSS, Recharts, Lucide React, Vite.
* **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2.
* **Database**: PostgreSQL (with automatic zero-friction SQLite fallback for local dev).
* **Cache & State**: Redis (with automatic in-memory fallback).
* **AI & Intent**: Structured Output Contracts, Multi-Agent Orchestrator, Gemini AI Copilot.
* **Payments**: Razorpay Test Mode & Mock Payment Simulation Engine.

---

## 4. Key Capabilities & Screens

1. **Command Center**: High-level merchant revenue recovery cockpit (Revenue at Risk, Predicted Recoverable, Revenue Recovered, Live Recovery Pipeline, and High-Priority Queue).
2. **Recovery Intelligence**: Comprehensive Recharts analytics covering failure reasons, payment methods (UPI vs Cards vs NetBanking), customer segments, and channel conversion.
3. **Payments Telemetry**: Searchable and filterable real-time payment log with slide-out payment inspector and autonomous action trigger.
4. **AI Agent Activity**: Live chronological audit timeline capturing every step taken by Investigator, Intent AI, Strategist, and Tool Executor.
5. **AI Copilot**: Interactive fintech recovery assistant answering questions on revenue leakage, gateway latency, and strategy recommendations.
6. **Guardrails**: Merchant-configurable thresholds (Max retries, Max discount %, Quiet hours, High-value human approval threshold) evaluated before any agent action.
7. **Interactive Sandbox / Simulation**: One-click execution of failure scenarios (including the exact ₹12,999 Card Decline ➔ UPI Recovery demo).

---

## 5. Local Setup & Running Instructions

### Prerequisites
* Python 3.11+
* Node.js v18+ & npm

### Quick Start (Backend)
```bash
# 1. Navigate to backend
cd backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend starts at `http://localhost:8000`. The interactive Swagger API documentation is available at `http://localhost:8000/docs`. Database tables and demo data (35 customers, 110 payments, recovery cases, actions) are seeded automatically on first launch.

### Quick Start (Frontend)
```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start Vite dev server
npm run dev
```
The frontend starts at `http://localhost:5173`.

---

## 6. Docker Setup (Optional)
To run PostgreSQL and Redis in Docker containers:
```bash
docker compose up -d
```

---

## 7. Demo Workflow (Exact Scenario)

1. Click **"Launch Simulation"** or **"Run Recovery Demo"** in the top bar.
2. Select **"Exact Demo: Returning Customer (Card Declined -> UPI Recovery)"** (Amount: ₹12,999).
3. **AI Investigator** analyzes customer history (10 past successes) and assigns **89% recovery probability**.
4. **AI Strategist** detects card 3DS failure and selects **UPI Fallback Link**.
5. **Intent AI** identifies customer intent (`ALTERNATE_PAYMENT_METHOD`).
6. **Tool Executor** verifies merchant guardrails, generates a 1-click Razorpay payment link, and dispatches a simulated WhatsApp message.
7. Click **"Simulate Customer Completing UPI Payment"**.
8. Status immediately transitions to **RECOVERED**, and the dashboard metrics update by **+₹12,999**.

---

## 8. REST API Summary

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/health` | GET | Healthcheck and Redis connectivity status |
| `/api/dashboard/metrics` | GET | Aggregated revenue recovery analytics & trends |
| `/api/payments` | GET | List and filter transactions |
| `/api/payments/{id}` | GET | Single payment inspection |
| `/api/recovery/cases` | GET | List active and historical recovery cases |
| `/api/recovery/cases/{id}` | GET | Full case with agent action audit trail |
| `/api/agent/activity` | GET | Chronological multi-agent activity stream |
| `/api/guardrails` | GET / PUT | Retrieve and update merchant guardrail rules |
| `/api/ai/analyze-payment` | POST | Run AI Investigator on a payment |
| `/api/ai/copilot` | POST | Ask natural language queries to AI Copilot |
| `/api/recovery/simulate` | POST | Trigger realistic payment failure & recovery pipeline |
| `/api/recovery/{id}/confirm-settlement` | POST | Simulate customer settling the recovery link |
