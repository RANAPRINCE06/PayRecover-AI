# PayRecover AI: Production-Grade Webhook & Event-Driven Recovery Plan

## 1. Executive Summary & Codebase Audit Findings

### A. Current State & Assets
- **FastAPI Core**: Complete API suite with correlation IDs, security headers, JWT authentication, RBAC (`ADMIN`, `OPERATOR`, `ANALYST`, `VIEWER`), rate limiting, and SSE streaming.
- **Webhook Ingestion**: Implementation in `backend/app/api/webhooks.py` with `RazorpayWebhookVerifier` (HMAC-SHA256 signature verification) and `WebhookService`.
- **Database & Alembic**: SQLite (local) and PostgreSQL (Docker) with Alembic migration `002_webhook_events.py` managing `webhook_events` table (with indexes on provider, status, timestamps, and deduplication keys).
- **Payment Lifecycle & Guardrails**: `PaymentStateMachine` enforcing directional transitions; `MerchantGuardrail` enforcing ₹50,000 threshold human approval, quiet hours, discount caps, and retry caps.
- **Baseline Verification**:
  - Backend Tests: **174 / 174 tests passing** (pytest).
  - Frontend Build: **Production build successful** (`tsc -b && vite build` clean exit 0).

### B. Identified Gaps & Areas for Enterprise Hardening
1. **Concurrency & Race Conditions in Webhook Ingestion**:
   - `WebhookService.ingest_event` queries existing by `provider_event_id`, but concurrent delivery of the identical event can hit a race condition resulting in `IntegrityError` before commit. Must catch `IntegrityError`, roll back cleanly, and return the duplicate event gracefully.
2. **Durable Worker Coordination & Locking**:
   - `WebhookService.process_event` must guard against concurrent worker execution on the same event via an atomic conditional state claim (`UPDATE ... WHERE id = :id AND status IN ('RECEIVED', 'RETRY_PENDING')`) and Redis advisory lock fallback.
3. **Stale Worker Recovery & Retry Backlog Processing**:
   - No automatic sweeper exists to recover crashed workers (events stuck in `PROCESSING` status) or to process `RETRY_PENDING` events whose `next_retry_at <= now()`.
4. **Authoritative State Verification & Mismatch Guardrails**:
   - Ensure webhook correlation strictly prevents unrelated events from settling arbitrary internal payments.
   - For ambiguous transitions or out-of-order events, integrate authoritative payment verification via `RazorpayClientWrapper.fetch_payment`.
5. **Operational Endpoints & Health**:
   - Enhance `/api/webhooks/health` with backlog metrics and worker heartbeat.
   - Provide an authorized endpoint to trigger batch sweep of pending retries / stale events.
6. **Frontend Integration**:
   - In `SettingsPage.tsx`, replace misleading placeholder URL (`:8001`) with dynamic origin `/api/webhooks/razorpay` and comprehensive Razorpay Test Mode setup documentation.
   - Add a dedicated **Webhook Events / Processing Console** with real-time health statistics, paginated event table, event filtering by status and type, payload inspector drawer (with sanitized payload display), and authorized retry action with instant UI feedback.
7. **Comprehensive Test Suite**:
   - Expand `test_webhooks.py` to cover all explicit test cases required in Section 8 (security, concurrency, payment state machine, reliability, and RBAC).
