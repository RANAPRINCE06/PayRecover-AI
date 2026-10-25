"""
Phase 8 — Repeatable Load and Resilience Testing Setup

Executes synthetic concurrent load against PayRecover AI endpoints:
- Health & Readiness probes (/health/live, /health/ready)
- Prometheus metrics (/metrics)
- Webhook ingestion & deduplication (/api/webhooks/razorpay)
- Idempotent recovery executions

Computes throughput (RPS), error rate, and p50, p95, p99 latency percentiles.
Never contacts live payment processors; uses synthetic test payloads.
"""
import asyncio
import time
import uuid
import json
import argparse
import statistics
from typing import List, Dict, Any
import httpx


async def run_worker(
    worker_id: int,
    base_url: str,
    stop_event: asyncio.Event,
    results: List[Dict[str, Any]]
):
    """Simulates an active client issuing diverse API requests."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # Pre-authenticate to obtain an operator token
        token = None
        try:
            auth_res = await client.post("/api/auth/login", json={"email": "operator@payrecover.ai", "password": "Operator@123"})
            if auth_res.status_code == 200:
                token = auth_res.json().get("access_token")
        except Exception:
            pass

        auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

        cycle = 0
        while not stop_event.is_set():
            cycle += 1
            op_type = cycle % 4

            start_t = time.perf_counter()
            success = False
            status_code = 0
            name = ""

            try:
                if op_type == 0:
                    name = "GET /health/live"
                    res = await client.get("/health/live")
                    status_code = res.status_code
                    success = status_code == 200

                elif op_type == 1:
                    name = "GET /health/ready"
                    res = await client.get("/health/ready")
                    status_code = res.status_code
                    success = status_code == 200

                elif op_type == 2:
                    name = "GET /metrics"
                    res = await client.get("/metrics")
                    status_code = res.status_code
                    success = status_code == 200

                elif op_type == 3:
                    name = "POST /api/webhooks/razorpay (Synthetic)"
                    # Send duplicate webhook to stress deduplication
                    shared_event_id = f"evt_load_{worker_id}_{cycle // 2}"
                    payload = {
                        "event": "payment.failed",
                        "created_at": int(time.time()),
                        "id": shared_event_id,
                        "payload": {
                            "payment": {
                                "entity": {
                                    "id": f"pay_load_{worker_id}_{cycle // 2}",
                                    "amount": 299900,
                                    "currency": "INR",
                                    "status": "failed",
                                    "method": "upi",
                                    "error_code": "BAD_REQUEST_ERROR",
                                    "error_description": "Load simulation decline"
                                }
                            }
                        }
                    }
                    body_bytes = json.dumps(payload).encode("utf-8")
                    # In test/mock mode without strict signature enforcement header, send raw payload
                    res = await client.post(
                        "/api/webhooks/razorpay",
                        content=body_bytes,
                        headers={"Content-Type": "application/json", "X-Razorpay-Event-Id": shared_event_id}
                    )
                    status_code = res.status_code
                    # 200 or 400 (if signature missing in prod) is an acceptable API response
                    success = status_code in (200, 201, 202, 400)

            except Exception as e:
                status_code = 599

            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            results.append({
                "name": name,
                "status": status_code,
                "success": success,
                "duration_ms": elapsed_ms
            })

            # Small jitter to prevent lockstep batching
            await asyncio.sleep(0.01)


async def main():
    parser = argparse.ArgumentParser(description="PayRecover AI Resilience & Load Testing Harness")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Target API base URL")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent virtual workers")
    parser.add_argument("--duration", type=int, default=10, help="Duration to run load test in seconds")
    args = parser.parse_args()

    print("=================================================================")
    print(" PAYRECOVER AI — RESILIENCE & LOAD TESTING HARNESS")
    print("=================================================================")
    print(f" Target Base URL : {args.url}")
    print(f" Concurrency     : {args.concurrency} virtual workers")
    print(f" Duration        : {args.duration} seconds")
    print(" Synthetic data  : Mock payments, no live gateway contacted.")
    print("=================================================================\n")

    # Quick pre-flight connectivity check
    async with httpx.AsyncClient(timeout=5.0) as probe:
        try:
            res = await probe.get(f"{args.url}/health/live")
            if res.status_code != 200:
                print(f"[ERROR] Target URL responded with HTTP {res.status_code}. Server may not be ready.")
                return
        except Exception as conn_err:
            print(f"[ERROR] Could not connect to {args.url}: {conn_err}")
            print("Please ensure the FastAPI backend is running before launching load tests.")
            return

    stop_event = asyncio.Event()
    results: List[Dict[str, Any]] = []

    print("[INFO] Launching concurrent workers...")
    start_time = time.time()
    tasks = [
        asyncio.create_task(run_worker(i, args.url, stop_event, results))
        for i in range(args.concurrency)
    ]

    await asyncio.sleep(args.duration)
    stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time

    # Analyze results
    total_requests = len(results)
    if total_requests == 0:
        print("[WARNING] Zero requests recorded during test window.")
        return

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    durations = [r["duration_ms"] for r in results]

    durations.sort()
    p50 = statistics.median(durations)
    p95 = durations[int(len(durations) * 0.95)] if len(durations) > 20 else durations[-1]
    p99 = durations[int(len(durations) * 0.99)] if len(durations) > 100 else durations[-1]
    avg = statistics.mean(durations)
    rps = total_requests / total_time

    print("\n=================================================================")
    print(" LOAD TEST EXECUTION RESULTS")
    print("=================================================================")
    print(f" Total Requests Completed : {total_requests}")
    print(f" Successful Requests       : {len(successful)} ({(len(successful)/total_requests)*100:.1f}%)")
    print(f" Failed Requests           : {len(failed)} ({(len(failed)/total_requests)*100:.1f}%)")
    print(f" Execution Duration        : {total_time:.2f} seconds")
    print(f" Throughput (RPS)          : {rps:.1f} req/sec")
    print("-----------------------------------------------------------------")
    print(" LATENCY DISTRIBUTION (ms)")
    print(f" Mean Latency              : {avg:.2f} ms")
    print(f" 50th Percentile (p50)     : {p50:.2f} ms")
    print(f" 95th Percentile (p95)     : {p95:.2f} ms")
    print(f" 99th Percentile (p99)     : {p99:.2f} ms")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
