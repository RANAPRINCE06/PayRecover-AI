# PayRecover AI — Production Reliability & Operations Runbook

This runbook documents operational procedures, observability mechanisms, fault tolerance behaviors, and recovery runbooks for **PayRecover AI — Autonomous Revenue Recovery Agent**.

---

## 1. Local Development Startup

### Prerequisites
- Python 3.11+
- Node.js 18+ / 20+
- SQLite (included with Python) or PostgreSQL 15+
- Redis (optional — automatic zero-loss in-memory fallback engages if offline)

### Backend Startup
```bash
# Navigate to backend and activate virtualenv
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run ASGI server with live reload
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend initializes database tables, seeds baseline customers and guardrails, launches the background outbox worker loop, and binds structured logging.

### Frontend Startup
```bash
cd frontend
npm install
npm run dev
```
The React development server launches on `http://localhost:5173`.

---

## 2. Docker Compose Startup

```bash
# Verify .env configuration exists
cp .env.example .env

# Build and start all services in detached mode
docker compose up -d --build

# Inspect running container statuses
docker compose ps

# View unified structured logs
docker compose logs -f backend
```

### Containers Created
- `payrecover-postgres` (PostgreSQL 16 on port `5432`)
- `payrecover-redis` (Redis 7 on port `6379`)
- `payrecover-backend` (FastAPI with non-root user `appuser` on port `8000`)
- `payrecover-frontend` (Nginx serving production bundle on port `80`)

---

## 3. Environment Configuration

All configurations are driven by environment variables defined in `.env` (derived from `.env.example`). Secrets must never be committed to source control.

| Variable | Description | Default / Example |
|---|---|---|
| `ENVIRONMENT` | Deployment stage (`development` or `production`) | `development` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/payrecover_db` |
| `SQLITE_FALLBACK_URL` | Local SQLite fallback DB | `sqlite:///./payrecover.db` |
| `REDIS_URL` | Redis cluster or standalone URL | `redis://localhost:6379/0` |
| `JWT_SECRET` | Secret key for HS256 JWT signatures (32+ chars) | `[REDACTED_SECRET]` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session token lifetime | `1440` |
| `RAZORPAY_KEY_ID` | Test mode key ID | `rzp_test_sample_key_12345` |
| `RAZORPAY_KEY_SECRET` | Test mode secret | `[REDACTED_SECRET]` |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook signature verification secret | `[REDACTED_SECRET]` |
| `USE_MOCK_PAYMENTS` | Use deterministic mock payment simulator | `True` |
| `GEMINI_API_KEY` | Google Gemini API key | `[OPTIONAL_REDACTED]` |
| `GEMINI_MODEL` | Gemini model name | `gemini-1.5-flash` |

---

## 4. Database Migration Commands

Alembic manages schema migrations.

```bash
cd backend

# Generate a new migration from entity models
alembic revision --autogenerate -m "describe_migration"

# Upgrade database to latest revision
alembic upgrade head

# Rollback single migration
alembic downgrade -1

# Inspect current schema revision
alembic current
```

---

## 5. Health, Readiness, and Liveness Endpoints

| Endpoint | Target Probe | HTTP Success | Failure Code | Behavior |
|---|---|---|---|---|
| `GET /health/live` | Container Liveness | 200 OK | Process down | Lightweight; confirms process is running and event loop is responsive. |
| `GET /health/ready` | K8s/Docker Readiness | 200 OK | 503 Unavailable | Tests primary DB query execution (`SELECT 1`). Returns 503 if DB is unreachable. |
| `GET /health/deps` | Dependency Health | 200 OK | 200 OK (degraded) | Reports DB, Redis, AI model, and payment gateway modes without exposing credentials. |
| `GET /health/worker` | Worker Queue | 200 OK | 200 OK | Reports worker heartbeat, pending queue depth, retry backlog, and dead letters. |
| `GET /api/system/health` | Legacy Status | 200 OK | 200 OK | Preserved for backward compatibility with existing monitoring clients. |

---

## 6. Metrics Endpoint and Inspection

PayRecover AI exposes standard Prometheus exposition format (2.0) at:
```bash
curl http://localhost:8000/metrics
```

### Key Metrics Monitored
- `payrecover_http_requests_total{method, path, status_code}`: Request volume and status code distribution.
- `payrecover_http_request_duration_seconds{method, path}`: Latency histogram for API routes.
- `payrecover_outbox_events_pending`: Gauge of unprocessed webhook events.
- `payrecover_outbox_events_dead_letter`: Gauge of terminal failures requiring operator attention.
- `payrecover_outbox_processing_total{outcome}`: Processing outcomes (`success`, `retry_scheduled`, `dead_letter`, `duplicate`).
- `payrecover_idempotency_conflicts_total`: Duplicate idempotency key requests handled.
- `payrecover_ai_strategy_generation_total{mode}`: Frequency of `GEMINI` vs `DETERMINISTIC_FALLBACK` executions.
- `payrecover_recovery_outcomes_total{status}`: Business recovery outcomes (`RECOVERED`, `FAILED`, `EXPIRED`).

---

## 7. Background Worker Operation

The `OutboxWorker` runs as a continuous non-blocking `asyncio` background task inside FastAPI's application lifecycle:
- **Poll Interval**: 2.0 seconds between idle cycles.
- **Batch Size**: Up to 10 events claimed per cycle.
- **Atomic Locking**: Uses SQL `UPDATE ... WHERE id = :id AND status IN ('RECEIVED', 'RETRY_PENDING')` to ensure only one worker claims any job.
- **Crash Recovery**: Automatically scans for events stuck in `PROCESSING` longer than 120 seconds and recovers them to `RETRY_PENDING`.
- **Graceful Shutdown**: On `SIGTERM` or `SIGINT`, the worker halts new claims and allows up to 15 seconds for active operations to cleanly drain.

---

## 8. Diagnosing a Stuck Outbox Event

If a webhook event appears stuck in `PROCESSING`:
1. Check the worker status:
   ```bash
   curl http://localhost:8000/health/worker
   ```
2. Inspect the database directly:
   ```sql
   SELECT id, event_type, status, attempt_count, updated_at, last_error
   FROM webhook_events
   WHERE status = 'PROCESSING';
   ```
3. If the worker crashed mid-flight, the crash recovery mechanism will transition it to `RETRY_PENDING` within 120 seconds.
4. To trigger an immediate manual crash recovery cycle:
   ```bash
   curl -X POST http://localhost:8000/api/webhooks/sweep \
     -H "Authorization: Bearer <OPERATOR_JWT>"
   ```

---

## 9. Diagnosing Repeated Provider Failures

If Razorpay or Gemini responses fail:
1. **Gemini Latency or Quota Exhaustion (429/500)**:
   - PayRecover automatically switches to `DETERMINISTIC_FALLBACK` strategy generation.
   - Guardrails, retry limits, and discount caps remain 100% active.
   - Verify metric: `payrecover_ai_strategy_generation_total{mode="DETERMINISTIC_FALLBACK"}`.
2. **Razorpay Gateway Timeout or Network Drop**:
   - The system **never** marks a payment as failed solely because an API call timed out.
   - Payment remains in `PENDING` until authoritative settlement is confirmed via webhook.

---

## 10. Recovering from Redis Unavailability

1. **Failure Mode**: If Redis goes down or times out during startup or request handling, `RedisService` falls back instantly to thread-safe in-memory caching.
2. **Safety Rule**: Security-critical state (such as high-value payment approvals, recovery outcomes, and outbox queues) is **always** committed to the database table, never ephemeral memory.
3. **Restoration**: Once Redis restarts, restart the backend or reconnect:
   ```bash
   docker compose restart redis
   ```

---

## 11. Handling Dead-Letter Events Safely

An event enters `DEAD_LETTER` state after exhausting `max_attempts` (default: 5 retries with exponential backoff and jitter).

### Inspection
1. Open the UI: **Settings > Webhook Processing Console** or **Operations & Reliability**.
2. Filter by status: `DEAD_LETTER`.
3. View the sanitized error stack in `last_error` and the full retry audit history in `processing_metadata_json`.

---

## 12. Replaying Failed Jobs with Proper Authorization

Only authenticated users with `OPERATOR` or `ADMIN` roles may trigger operational replay. Replaying an event requires audit logging and respects idempotency.

### Via API
```bash
curl -X POST http://localhost:8000/api/webhooks/events/{event_id}/retry \
  -H "Authorization: Bearer <OPERATOR_OR_ADMIN_TOKEN>"
```

### Response
```json
{
  "message": "Event whe_dl_1234 queued for reprocessing.",
  "event_id": "whe_dl_1234",
  "status": "RETRY_PENDING",
  "operator": "operator@payrecover.ai"
}
```
The audit record records the operator's email and timestamp inside the event metadata.

---

## 13. Graceful Shutdown and Restart Behavior

When receiving `SIGTERM` or `SIGINT`:
1. FastAPI `lifespan` triggers shutdown.
2. `outbox_worker.stop(timeout=15.0)` signals the background worker loop to cease new claims.
3. Active worker operations in-flight finish writing results.
4. Database connection pools close cleanly.
5. Incomplete jobs left in `PROCESSING` are safely reset to `RETRY_PENDING` on next boot.

---

## 14. Running the Automated Test Suite

```bash
cd backend

# Run the 15 Phase 8 Reliability and Concurrency Tests:
python -m pytest tests/test_reliability_concurrency.py -v

# Run the complete test suite (275 tests):
python -m pytest -q
```

---

## 15. Running Load Tests

A dedicated, synthetic load-testing harness is provided in `backend/tests/load_test.py`:

```bash
# Ensure backend is running locally on port 8000
python backend/tests/load_test.py --url http://127.0.0.1:8000 --concurrency 15 --duration 10
```

### Alternatively with Locust
```bash
locust -f backend/tests/locustfile.py --headless -u 20 -r 5 --run-time 30s --host http://localhost:8000
```

The load test outputs total requests, success rate, throughput (RPS), and p50, p95, p99 latencies without contacting live payment gateways.

---

## 16. Simulating Provider Failures in a Safe Test Environment

To test degraded behaviors:
1. **Simulate AI Provider Outage**:
   Set `GEMINI_API_KEY=""` in `.env` and restart. Recovery cases seamlessly execute deterministic rule-based strategies.
2. **Simulate Redis Outage**:
   Stop Redis (`docker stop payrecover-redis`). The app continues serving traffic using in-memory token and rate-limit fallbacks.
3. **Simulate Payment Gateway Timeout**:
   Use `USE_MOCK_PAYMENTS=True` and trigger `VERIFY_PAYMENT` with a non-captured mock ID. The state machine preserves `PENDING` rather than falsely marking the payment failed.

---

## 17. Known Limitations and Remaining Production Prerequisites

1. **PostgreSQL Concurrency Locks in SQLite Mode**:
   While SQLite supports our atomic row update claims (`UPDATE ... WHERE status = 'RECEIVED'`), production environments with high concurrency (> 50 workers) should run on PostgreSQL to leverage row-level locking (`SELECT FOR UPDATE SKIP LOCKED`).
2. **Prometheus Scraping Setup**:
   A production deployment requires adding a Prometheus scrape job targeting `/metrics` every 15s.
3. **External Secrets Manager**:
   In production Kubernetes/AWS/GCP deployments, mount `JWT_SECRET`, `RAZORPAY_KEY_SECRET`, and `GEMINI_API_KEY` via HashiCorp Vault, AWS Secrets Manager, or Google Secret Manager rather than plaintext environment files.
