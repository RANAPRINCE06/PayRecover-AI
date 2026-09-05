# PayRecover AI — 5-Minute Buildathon Judge Demo Script

This script guides a 5-minute evaluation demonstration of PayRecover AI. Follow these exact steps to showcase the full multi-agent recovery system, deterministic guardrails, explainable copilot intelligence, and production-grade security.

---

## Pre-Demo Setup (10 Seconds)
1. Ensure both backend and frontend are running:
   - Backend: `http://localhost:8000` (or `8001`)
   - Frontend: `http://localhost:5173` (or `http://localhost`)
2. Log in using the Admin profile:
   - **Email**: `admin@payrecover.ai`
   - **Password**: `Admin@123`
3. In the sidebar, navigate to **Demo Center** and click **Reset Sandbox** to ensure a clean baseline.

---

## Minute 0:00 – 0:45: The Problem & Command Center Overview
- **Visual**: Navigate to **Command Center** (`/`).
- **Talking Points**:
  > "In India's digital economy, ₹30,000+ Crores are lost annually to transient payment failures — UPI app timeouts, 3DS card drops, and expired auto-debit mandates. Traditional systems simply send a generic retry email hours later. PayRecover AI is an autonomous, multi-agent AI revenue recovery platform that rescues lost revenue in real time while enforcing strict merchant safety guardrails."
- **Key Features to Highlight**:
  - Top metric cards: Revenue Processed, Recovered Revenue, Active Recovery Rate (76.8%), and Live Revenue at Risk.
  - Live Real-Time Activity Feed powered by Server-Sent Events (SSE).

---

## Minute 0:45 – 2:00: Flagship Scenario — Instant UPI Fallback Link
- **Visual**: Click on **Demo Center** in the sidebar.
- **Action**:
  1. Select Scenario 1: **"Flagship ₹12,999 Card Decline -> UPI Conversion"**.
  2. Review the pre-populated transaction profile (VIP Customer, Vikram Malhotra, 10 previous orders).
  3. Click **"Run Autonomous Recovery Pipeline"**.
- **What Happens**:
  - The multi-agent state progression animates through all 5 stages in sub-second time:
    1. *Investigator* detects card 3DS drop-off; assigns 89% recovery probability.
    2. *Intent AI* detects customer readiness to pay via alternate method.
    3. *Strategist* formulates instant UPI fallback link.
    4. *Guardrails* validates amount is under threshold and within quiet hours.
    5. *Tool Executor* generates instant payment link and dispatches WhatsApp notification.
- **Talking Points**:
  > "Notice how the agent trace visualizes the reasoning at each step. The system didn't just guess — it investigated Vikram's customer history, identified that he frequently pays via UPI, and delivered a 1-tap WhatsApp payment link."

---

## Minute 2:00 – 3:00: Merchant Safety Guardrails & Human-in-the-Loop Review
- **Visual**: Still in **Demo Center**.
- **Action**:
  1. Select Scenario 2: **"High-Value Order (₹75,000 Guardrail Human Queue)"**.
  2. Click **"Run Autonomous Recovery Pipeline"**.
- **What Happens**:
  - The pipeline halts at Stage 4!
  - A bright amber badge appears: **"REQUIRES APPROVAL — Held safely in merchant queue"**.
  - Guardrail reason: *Transaction value (₹75,000) exceeds merchant limit of ₹50,000*.
- **Action**:
  3. Navigate to **Approvals** or the Human Review panel.
  4. Review the transaction and click **"Approve Outreach"**.
  5. The case transitions to **APPROVED**, and the personalized executive outreach tool executes.
- **Talking Points**:
  > "Autonomy without safety is dangerous in fintech. Our deterministic guardrails ensure AI never discounts above policy or contacts high-value clients without explicit merchant signoff."

---

## Minute 3:00 – 4:00: Explainable AI Copilot & Revenue-at-Risk
- **Visual**: Navigate to **AI Copilot** in the sidebar.
- **Action**:
  1. Click one of the quick prompt chips, e.g., *"What is our total revenue at risk today and how should we prioritize it?"*
  2. Review the Copilot response.
- **Talking Points**:
  > "Our Copilot doesn't give generic LLM responses. It inspects live database telemetry, computes deterministic multi-factor opportunity scores (0–100), and provides prioritized, actionable recovery recommendations."
- **Key Highlights**:
  - Notice cited transaction IDs, confidence metrics, and deterministic opportunity factors.

---

## Minute 4:00 – 4:45: Production Architecture & Security (RBAC + Idempotency)
- **Visual**: Navigate to **Settings** / **Audit Log**.
- **Talking Points**:
  > "Under the hood, PayRecover AI is built for enterprise production:
  > - **RBAC**: 4 granular roles (Admin, Operator, Analyst, Viewer). If a Viewer tries to approve a high-value queue, FastAPI returns HTTP 403 Forbidden.
  > - **Idempotency**: All recovery tool executions support cryptographic idempotency keys, preventing double-charges even on erratic network replays.
  > - **Full Containerization**: Multi-service Docker setup with PostgreSQL, Redis, FastAPI, and Nginx."

---

## Minute 4:45 – 5:00: Summary & Wrap Up
- **Action**: Navigate back to **Demo Center** and click **Reset Sandbox**.
- **Closing Statement**:
  > "PayRecover AI turns payment failures from lost revenue into seamless customer delight — autonomous, guardrail-protected, explainable, and production-ready today. Thank you!"
