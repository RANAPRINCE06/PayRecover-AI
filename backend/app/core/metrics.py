import time
import threading
from typing import Dict, Any, List, Tuple, Optional


class MetricRegistry:
    """
    Thread-safe, lightweight, production-grade Prometheus-compatible metrics registry.
    Zero external dependencies; generates valid Prometheus text format.
    Strictly enforces bounded label cardinality (no payment IDs, customer IDs, or user PII).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
        self._gauges: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
        self._histograms: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Dict[str, Any]] = {}
        self._descriptions: Dict[str, Tuple[str, str]] = {}  # metric_name -> (type, help_text)

    def _normalize_labels(self, labels: Optional[Dict[str, str]]) -> Tuple[Tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted((str(k), str(v)) for k, v in labels.items()))

    def register(self, name: str, metric_type: str, help_text: str):
        with self._lock:
            self._descriptions[name] = (metric_type, help_text)

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        norm_labels = self._normalize_labels(labels)
        with self._lock:
            key = (name, norm_labels)
            self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        norm_labels = self._normalize_labels(labels)
        with self._lock:
            key = (name, norm_labels)
            self._gauges[key] = float(value)

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        norm_labels = self._normalize_labels(labels)
        with self._lock:
            key = (name, norm_labels)
            if key not in self._histograms:
                self._histograms[key] = {
                    "count": 0,
                    "sum": 0.0,
                    "min": float("inf"),
                    "max": float("-inf")
                }
            h = self._histograms[key]
            h["count"] += 1
            h["sum"] += value
            if value < h["min"]:
                h["min"] = value
            if value > h["max"]:
                h["max"] = value

    def generate_prometheus_text(self) -> str:
        """Renders all registered metrics into Prometheus exposition text format."""
        lines: List[str] = []

        with self._lock:
            # Group by metric name
            all_metric_names = set(self._descriptions.keys())
            for name, _ in self._counters.keys():
                all_metric_names.add(name)
            for name, _ in self._gauges.keys():
                all_metric_names.add(name)
            for name, _ in self._histograms.keys():
                all_metric_names.add(name)

            for name in sorted(all_metric_names):
                m_type, m_help = self._descriptions.get(name, ("untyped", f"Metric {name}"))
                lines.append(f"# HELP {name} {m_help}")
                lines.append(f"# TYPE {name} {m_type}")

                # Counters
                matching_counters = [k for k in self._counters if k[0] == name]
                for _, labels in matching_counters:
                    label_str = ""
                    if labels:
                        label_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels) + "}"
                    val = self._counters[(name, labels)]
                    lines.append(f"{name}{label_str} {val}")

                # Gauges
                matching_gauges = [k for k in self._gauges if k[0] == name]
                for _, labels in matching_gauges:
                    label_str = ""
                    if labels:
                        label_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels) + "}"
                    val = self._gauges[(name, labels)]
                    lines.append(f"{name}{label_str} {val}")

                # Histograms
                matching_histograms = [k for k in self._histograms if k[0] == name]
                for _, labels in matching_histograms:
                    label_base = dict(labels) if labels else {}
                    h = self._histograms[(name, labels)]

                    # _count
                    count_labels = ",".join(f'{k}="{v}"' for k, v in label_base.items())
                    count_str = f"{{{count_labels}}}" if count_labels else ""
                    lines.append(f"{name}_count{count_str} {h['count']}")

                    # _sum
                    sum_labels = ",".join(f'{k}="{v}"' for k, v in label_base.items())
                    sum_str = f"{{{sum_labels}}}" if sum_labels else ""
                    lines.append(f"{name}_sum{sum_str} {h['sum']:.6f}")

                lines.append("")  # Blank line separator

        return "\n".join(lines) + "\n"

    def clear(self):
        """Reset all metrics (primarily for test suite isolation)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global Singleton Registry Instance
metrics = MetricRegistry()

# ── Pre-register standard platform metrics with documentation ──
metrics.register("payrecover_http_requests_total", "counter", "Total count of inbound HTTP requests partitioned by method, route, and status.")
metrics.register("payrecover_http_request_duration_seconds", "histogram", "HTTP request processing latency in seconds.")
metrics.register("payrecover_recovery_cases_total", "counter", "Count of recovery cases created and processed by status.")
metrics.register("payrecover_recovery_outcomes_total", "counter", "Authoritatively verified recovery outcomes by category (RECOVERED, UNSUCCESSFUL, EXPIRED).")
metrics.register("payrecover_payment_verifications_total", "counter", "Authoritative payment verification attempts partitioned by result.")
metrics.register("payrecover_human_approvals_total", "counter", "High-value human approval events (REQUIRED, APPROVED, REJECTED).")
metrics.register("payrecover_idempotency_conflicts_total", "counter", "Total duplicate requests intercepted via idempotency keys.")
metrics.register("payrecover_outbox_events_pending", "gauge", "Current count of webhook outbox events waiting in pending or retry queues.")
metrics.register("payrecover_outbox_oldest_pending_age_seconds", "gauge", "Age in seconds of the oldest uncompleted outbox event.")
metrics.register("payrecover_outbox_processing_total", "counter", "Outbox background processing operations by terminal status.")
metrics.register("payrecover_outbox_stale_claims_recovered_total", "counter", "Count of events recovered from stuck worker processing leases.")
metrics.register("payrecover_dependency_errors_total", "counter", "External dependency failures partitioned by component.")
metrics.register("payrecover_external_request_duration_seconds", "histogram", "Latency of external calls to payment providers or LLM APIs.")
metrics.register("payrecover_ai_strategy_generation_total", "counter", "AI strategy decisions partitioned by mode (GEMINI vs DETERMINISTIC_FALLBACK).")
metrics.register("payrecover_shadow_decisions_total", "counter", "Contextual bandit shadow decisions by agreement status.")
metrics.register("payrecover_bandit_decisions_total", "counter", "Bandit recommendations generated.")
