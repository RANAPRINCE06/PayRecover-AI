# PayRecover AI — Architecture Specification

PayRecover AI is an autonomous, multi-agent AI revenue recovery platform built specifically for Indian fintech ecosystems. It intercepts transaction drop-offs across UPI, Credit/Debit cards, Net Banking, and recurring e-mandates, dynamically orchestrates omnichannel recovery workflows, and strictly enforces merchant safety guardrails.

---

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph Client Layer
        WebUI[React 18 + Vite SPA]
        SSEListener[SSE Live Event Stream]
    end

    subgraph API & Gateway Layer
        Nginx[Nginx Reverse Proxy]
        FastAPI[FastAPI Gateway]
        AuthGuard[JWT Auth & RBAC Middleware]
        IdempotencyGuard[Idempotency & Concurrency Guard]
    end

    subgraph Autonomous Multi-Agent Core
        Orchestrator[Multi-Agent Recovery Orchestrator]
        Investigator[Agent 1: Payment Investigator]
        IntentAI[Agent 2: Customer Intent AI]
        Strategist[Agent 3: Recovery Strategist]
        ToolExecutor[Agent 4: Tool Execution Agent]
        Copilot[Agent 5: AI Recovery Copilot]
    end

    subgraph Safety & Rule Engine
        GuardrailEngine[Deterministic Merchant Guardrails]
        ApprovalQueue[Human-in-the-Loop Review Queue]
    end

    subgraph Data & Telemetry Tier
        Postgres[(PostgreSQL / SQLite Storage)]
        RedisCache[(Redis / In-Memory State & PubSub)]
        Telemetry[AI Telemetry & Agent Traces]
    end

    subgraph Payment & Channel Providers
        Razorpay[Razorpay Gateway API]
        WhatsApp[WhatsApp Business API (Mock/Live)]
        SMSGateway[SMS Gateway]
    end

    WebUI -->|REST API| Nginx
    Nginx --> FastAPI
    FastAPI --> AuthGuard
    AuthGuard --> IdempotencyGuard
    IdempotencyGuard --> Orchestrator
    FastAPI --> SSEListener

    Orchestrator --> Investigator
    Orchestrator --> IntentAI
    Orchestrator --> Strategist
    Strategist --> GuardrailEngine
    GuardrailEngine -->|Passed / Capped| ToolExecutor
    GuardrailEngine -->|High Value >= ₹50,000| ApprovalQueue
    ApprovalQueue -->|Manual Merchant Approval| ToolExecutor

    ToolExecutor --> Razorpay
    ToolExecutor --> WhatsApp
    ToolExecutor --> SMSGateway

    Orchestrator --> Telemetry
    Investigator --> Postgres
    ToolExecutor --> Postgres
    FastAPI --> RedisCache
```

---

## 2. Multi-Agent Lifecycle & Coordination

The recovery lifecycle executes as an event-driven 5-stage state machine:

### Stage 1: Ingestion & Investigation (Agent 1 — Investigator)
- **Input**: Failed payment payload containing `payment_id`, `amount`, `payment_method`, `failure_reason`, and customer history.
- **Processing**: Evaluates historical transaction patterns, failure transience (e.g., PSP timeouts vs. insufficient funds), and customer tier.
- **Output**: Generates a normalized `recovery_score` (0–100), `recovery_probability` (0.0–1.0), and root-cause risk classification (`LOW`, `MEDIUM`, `HIGH`).

### Stage 2: Intent Analysis (Agent 2 — Intent AI)
- **Input**: Inbound customer communications, drop-off timing, and behavioral telemetry.
- **Processing**: Natural-language intent classification extracting explicit customer goals (`ALTERNATE_PAYMENT_METHOD`, `PAY_LATER`, `PRICE_CONCERN`, `ALREADY_PAID`, `TECH_DIFFICULTY`).
- **Output**: Categorized intent with confidence score and conversational context.

### Stage 3: Strategy Formulation (Agent 3 — Strategist)
- **Input**: Combined investigation diagnostics and customer intent signals.
- **Processing**: Formulates optimal recovery strategy (`UPI_FALLBACK_LINK`, `SMART_DISCOUNT_INCENTIVE`, `AUTO_RETRY_MANDATE_UPDATE`, `EXECUTIVE_CONCIERGE_CALL`).
- **Output**: Structured proposal containing recommended channel, discount percentage, time-to-dispatch, and alternative fallback.

### Stage 4: Guardrail Enforcement (Deterministic Backend Engine)
- **Strict Deterministic Verification**: Ensures AI proposals never execute without merchant verification.
- **Policy Rules**:
  1. *High-Value Threshold*: Transactions $\ge$ ₹50,000 mandate human signoff prior to customer outreach.
  2. *Discount Capping*: Promotional discounts strictly capped at merchant ceiling (default 10%).
  3. *Max Retry Protection*: Halts automated retries once retry threshold (default 3) is reached.
  4. *Quiet Hours*: Blocks non-urgent customer notifications between 22:00 and 08:00 IST.
  5. *Already-Paid Interception*: Prevents duplicate charging if payment was already settled.

### Stage 5: Tool Execution & Real-Time Broadcast (Agent 4 — Tool Executor)
- **Allowlisted Execution**: Only registered, secure tools are executable (`create_payment_link`, `send_recovery_message`, `retry_payment`, `offer_alternate_payment`, `verify_payment`, `escalate_to_human`).
- **Broadcast**: Dispatches real-time SSE events to the frontend Command Center feed.

---

## 3. Database Schema Architecture

The relational layer is managed via PostgreSQL (with SQLite zero-config fallback) and tracked by Alembic migrations:

| Entity | Description | High-Frequency Indexes |
| :--- | :--- | :--- |
| `merchants` | Primary account & business profile | `id`, `email` |
| `customers` | Customer identity, lifetime metrics & risk tier | `id`, `email` |
| `payments` | Transaction record & provider IDs | `razorpay_payment_id`, `(status, created_at)`, `(customer_id, created_at)` |
| `recovery_cases` | State machine recovery case tracking | `payment_id`, `(status, started_at)`, `recovery_score` |
| `agent_actions` | Full audit log of agent decisions | `(recovery_case_id, created_at)`, `status` |
| `merchant_guardrails` | Merchant policy thresholds & quiet hours | `merchant_id` (Unique) |
| `customer_interactions` | Omnichannel message history | `customer_id`, `recovery_case_id`, `created_at` |
| `tool_executions` | Discrete tool runs with idempotency keys | `execution_id`, `idempotency_key`, `recovery_case_id` |
| `human_approvals` | Pending & resolved high-value reviews | `recovery_case_id`, `status` |
| `users` | RBAC accounts (`ADMIN`, `ANALYST`, `OPERATOR`, `VIEWER`) | `email` (Unique), `role` |
| `idempotency_records` | Cached cryptographic response replays | `key` (Unique), `created_at` |

---

## 4. Security & Compliance Architecture

### Authentication & RBAC
- Stateless JWT authentication signed with HMAC-SHA256.
- Role-Based Access Control matrix:
  - `ADMIN`: Full access to user management, guardrails, analytics, and approvals.
  - `OPERATOR`: Can approve/reject high-value cases and trigger recovery executions.
  - `ANALYST`: Read-only access to analytics, traces, and metrics.
  - `VIEWER`: Read-only view of dashboard; execution endpoints return `403 Forbidden`.

### Idempotency & Concurrency Control
- Client operations support `Idempotency-Key` headers.
- Duplicate payloads return the cached execution result with identical status code and payload without re-triggering provider APIs.
- Concurrency locks prevent duplicate simultaneous recovery execution on the same case.
