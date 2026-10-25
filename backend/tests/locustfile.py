"""
Phase 8 — Locust Load Testing Specification
Run locally:
    locust -f backend/tests/locustfile.py --headless -u 20 -r 5 --run-time 30s --host http://localhost:8000
"""
from locust import HttpUser, task, between
import json
import time
import uuid


class PayRecoverLoadUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Authenticate user on start."""
        res = self.client.post("/api/auth/login", json={"email": "operator@payrecover.ai", "password": "Operator@123"})
        if res.status_code == 200:
            token = res.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

    @task(4)
    def test_liveness(self):
        self.client.get("/health/live")

    @task(3)
    def test_readiness(self):
        self.client.get("/health/ready")

    @task(2)
    def test_metrics(self):
        self.client.get("/metrics")

    @task(2)
    def test_synthetic_webhook(self):
        evt_id = f"evt_locust_{uuid.uuid4().hex[:8]}"
        payload = {
            "event": "payment.failed",
            "created_at": int(time.time()),
            "id": evt_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_locust_{uuid.uuid4().hex[:8]}",
                        "amount": 499900,
                        "currency": "INR",
                        "status": "failed"
                    }
                }
            }
        }
        self.client.post(
            "/api/webhooks/razorpay",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "X-Razorpay-Event-Id": evt_id}
        )
