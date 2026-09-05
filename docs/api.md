# PayRecover AI — REST API Reference

PayRecover AI exposes a comprehensive RESTful API built with FastAPI. All endpoints accept and return JSON unless otherwise noted.

## Base URL
- **Local Development**: `http://localhost:8000/api`
- **Docker Production**: `http://localhost/api` (via Nginx reverse proxy)

## Authentication
Protected endpoints require a Bearer token in the `Authorization` header:
```http
Authorization: Bearer <jwt_access_token>
```

---

## 1. Authentication & RBAC

### `POST /auth/login`
Authenticates a user and issues a JWT token.
- **Request**:
  ```json
  {
    "email": "admin@payrecover.ai",
    "password": "Admin@123"
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "user": {
      "id": "usr_admin_default",
      "email": "admin@payrecover.ai",
      "name": "Ananya Roy",
      "role": "ADMIN"
    }
  }
  ```

### `GET /auth/me`
Retrieves the profile and role of the currently authenticated user.
- **Headers**: `Authorization: Bearer <token>`
- **Response** `200 OK`:
  ```json
  {
    "id": "usr_operator_default",
    "email": "operator@payrecover.ai",
    "name": "Priya Nair",
    "role": "OPERATOR"
  }
  ```

### `POST /auth/logout`
Invalidates client session.
- **Headers**: `Authorization: Bearer <token>`
- **Response** `200 OK`: `{"message": "Logged out successfully."}`

---

## 2. Recovery Engine & Operations

### `POST /recovery/simulate`
Simulates an Indian payment failure and runs the multi-agent recovery pipeline.
- **Request**:
  ```json
  {
    "scenario_type": "DEMO_CARD_DECLINE_UPI",
    "amount": 12999.0
  }
  ```
- **Supported Scenarios**:
  - `DEMO_CARD_DECLINE_UPI`: Card 3DS drop-off -> instant UPI recovery link.
  - `HIGH_VALUE_APPROVAL`: ₹75,000 order -> held for human review.
  - `UPI_TIMEOUT`: Latency timeout -> instant prefilled UPI Intent link.
  - `CHECKOUT_ABANDONED`: Cart abandonment -> smart discount nudge.
  - `SUBSCRIPTION_FAILED`: RBI e-mandate expiry -> WhatsApp mandate renewal.
- **Response** `200 OK`:
  ```json
  {
    "scenario": "Exact Demo: Returning Customer Card Declined -> UPI Recovery",
    "payment_id": "pay_sim_1234abcd",
    "case_id": "rc_sim_5678efgh",
    "amount": 12999.0,
    "actions_count": 5
  }
  ```

### `POST /recovery/{case_id}/execute`
Executes an allowlisted recovery action with guardrail checks.
- **Headers**: Optional `Idempotency-Key: <unique_key>`
- **Request**:
  ```json
  {
    "recovery_case_id": "rc_sim_5678efgh",
    "tool_type": "CREATE_PAYMENT_LINK",
    "parameters": {
      "discount_percentage": 5.0,
      "preferred_method": "upi"
    }
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "execution_id": "exec_9a8b7c6d5e",
    "status": "SUCCESS",
    "tool_type": "CREATE_PAYMENT_LINK",
    "payment_link_url": "https://rzp.io/i/plink_12345",
    "guardrail_status": "SAFE",
    "requires_human_approval": false
  }
  ```

### `POST /recovery/{case_id}/approve`
Merchant human signoff for high-value transactions ($\ge$ ₹50,000).
- **Access**: `ADMIN` or `OPERATOR` role required. (Viewer receives `403 Forbidden`).
- **Response** `200 OK`:
  ```json
  {
    "execution_id": "exec_approved_1234",
    "status": "APPROVED",
    "message": "Approved high-value recovery outreach."
  }
  ```

### `POST /recovery/{case_id}/reject`
Rejects a proposed recovery action.
- **Request**: `{"reason": "Customer cancelled order directly."}`
- **Response** `200 OK`: `{"message": "Recovery action rejected by merchant", "case_id": "rc_123"}`

---

## 3. AI Agents & Recovery Intelligence

### `POST /ai/copilot`
Natural-language query endpoint for recovery analytics and merchant decision support.
- **Request**:
  ```json
  {
    "query": "Which failure reason caused the most revenue loss this week?"
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "answer": "UPI_TIMEOUT caused 44% of total failed volume, representing ₹184,200 in revenue at risk.",
    "confidence": 0.96,
    "cited_metrics": {
      "primary_failure": "UPI_TIMEOUT",
      "revenue_at_risk": 184200
    },
    "suggested_actions": [
      "Enable instant WhatsApp fallback link for UPI timeouts",
      "Review bank gateway status"
    ]
  }
  ```

### `GET /analytics/opportunity-score/{case_id}`
Returns explainable opportunity score (0–100) and priority classification.
- **Response** `200 OK`:
  ```json
  {
    "case_id": "rc_123",
    "score": 88.0,
    "priority": "HIGH",
    "positive_factors": [
      "Loyal customer with 10 prior successful payments (+20 pts)",
      "Native UPI transaction: instant deep-link supported (+10 pts)"
    ],
    "negative_factors": [],
    "recommended_strategy": "UPI_FALLBACK_LINK",
    "estimated_recovery_probability": 0.88
  }
  ```

### `GET /analytics/revenue-at-risk`
Aggregates active failure volume by risk priority tier (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).

---

## 4. Real-Time Operations & Demo Management

### `GET /events/live`
Server-Sent Events (SSE) stream streaming live platform events:
- `PAYMENT_FAILED`
- `CASE_CREATED`
- `RECOVERY_EXECUTED`
- `APPROVAL_REQUIRED`
- `DEMO_RESET`

### `POST /demo/reset`
Cleans up simulated demo cases, resets merchant guardrails to baseline, and provides a fresh state for live demos.
- **Response** `200 OK`:
  ```json
  {
    "status": "SUCCESS",
    "message": "Demo data and simulations reset successfully.",
    "cleared_cases": 4,
    "cleared_payments": 4
  }
  ```
