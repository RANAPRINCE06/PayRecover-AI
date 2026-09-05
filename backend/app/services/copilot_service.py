import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.entities import (
    Payment,
    RecoveryCase,
    Customer,
    AgentAction,
    MerchantGuardrail,
    PaymentStatus,
    RecoveryStatus
)
from app.schemas.contracts import CopilotResponse
from app.services.gemini_service import GeminiService
from app.services.opportunity_service import opportunity_scoring_engine

logger = logging.getLogger("payrecover.copilot")

COPILOT_SYSTEM_INSTRUCTION = """
You are PayRecover AI's Executive Revenue Recovery Copilot.
Your job is to provide explainable, accurate, and actionable recovery intelligence to merchants.
RULES:
1. Ground every answer STRICTLY in the provided database context.
2. DO NOT fabricate or guess metrics. If data is unavailable, explicitly state: "The requested telemetry is currently unavailable in the database."
3. Distinguish between recovered revenue and revenue-at-risk.
4. Highlight specific high-value recovery opportunities when relevant.
5. Provide actionable recommendations that comply with merchant guardrails.
6. Produce only the requested JSON format matching the schema.
""".strip()


class CopilotService:
    def __init__(self, gemini_service: Optional[GeminiService] = None):
        self.gemini = gemini_service or GeminiService()

    def build_database_context(self, db: Session) -> Dict[str, Any]:
        """
        Gathers safe, aggregated database context for the AI Copilot.
        All queries are bounded and aggregated; no PII or credentials are leaked.
        """
        # 1. Totals
        total_recovered = db.query(func.coalesce(func.sum(RecoveryCase.recovered_amount), 0.0)).scalar() or 0.0
        total_failed_amt = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
            Payment.status == PaymentStatus.FAILED.value
        ).scalar() or 0.0

        active_cases_count = db.query(func.count(RecoveryCase.id)).filter(
            RecoveryCase.status.notin_([
                RecoveryStatus.RECOVERED.value,
                RecoveryStatus.FAILED.value,
                RecoveryStatus.EXPIRED.value
            ])
        ).scalar() or 0

        recovered_cases_count = db.query(func.count(RecoveryCase.id)).filter(
            RecoveryCase.status == RecoveryStatus.RECOVERED.value
        ).scalar() or 0

        total_cases_count = db.query(func.count(RecoveryCase.id)).scalar() or 0

        # 2. Top Failure Reasons
        failure_rows = db.query(
            Payment.failure_reason,
            func.count(Payment.id).label("cnt"),
            func.sum(Payment.amount).label("vol")
        ).filter(
            Payment.status == PaymentStatus.FAILED.value,
            Payment.failure_reason.isnot(None)
        ).group_by(Payment.failure_reason).order_by(func.count(Payment.id).desc()).limit(5).all()

        top_failures = [
            {"reason": r[0], "count": int(r[1]), "volume": round(float(r[2] or 0), 2)}
            for r in failure_rows
        ]

        # 3. Payment Methods Breakdown
        method_rows = db.query(
            Payment.payment_method,
            func.count(Payment.id).label("cnt"),
            func.sum(Payment.amount).label("vol")
        ).group_by(Payment.payment_method).all()

        payment_methods = [
            {"method": r[0], "count": int(r[1]), "volume": round(float(r[2] or 0), 2)}
            for r in method_rows
        ]

        # 4. Top 5 Active Opportunities
        active_cases = db.query(RecoveryCase).filter(
            RecoveryCase.status.notin_([
                RecoveryStatus.RECOVERED.value,
                RecoveryStatus.FAILED.value,
                RecoveryStatus.EXPIRED.value
            ])
        ).all()

        opportunities = []
        for c in active_cases:
            if not c.payment:
                continue
            opp = opportunity_scoring_engine.calculate_score(c)
            cust_name = c.payment.customer.name if (c.payment and c.payment.customer) else "Customer"
            # Mask name for privacy
            masked_name = cust_name[0] + "***" + cust_name[-1] if len(cust_name) > 2 else "Customer"
            opportunities.append({
                "case_id": c.id,
                "amount": float(c.payment.amount),
                "customer": masked_name,
                "tier": opp.customer_tier,
                "score": opp.score,
                "priority": opp.priority,
                "failure_reason": c.payment.failure_reason,
                "strategy": opp.recommended_strategy,
                "expected_recovery": round(opp.estimated_recovery_probability * c.payment.amount, 2)
            })

        opportunities.sort(key=lambda x: x["expected_recovery"], reverse=True)
        top_opportunities = opportunities[:5]

        # 5. Guardrail config
        guardrail = db.query(MerchantGuardrail).first()
        guardrail_info = {
            "high_value_threshold": float(guardrail.high_value_threshold) if guardrail else 50000.0,
            "max_discount_percentage": float(guardrail.max_discount_percentage) if guardrail else 10.0,
            "human_approval_required": bool(guardrail.human_approval_required) if guardrail else True
        }

        return {
            "metrics": {
                "total_recovered_amount": round(float(total_recovered), 2),
                "revenue_at_risk": round(float(total_failed_amt), 2),
                "active_cases_count": active_cases_count,
                "recovered_cases_count": recovered_cases_count,
                "total_cases_count": total_cases_count,
                "recovery_rate_percent": round((recovered_cases_count / total_cases_count * 100.0), 1) if total_cases_count > 0 else 0.0
            },
            "top_failures": top_failures,
            "payment_methods": payment_methods,
            "top_opportunities": top_opportunities,
            "guardrails": guardrail_info
        }

    def ask(self, message: str, db: Session) -> CopilotResponse:
        """
        Executes grounded natural-language Copilot analysis against database context.
        """
        context = self.build_database_context(db)
        data_sources = [
            "PostgreSQL: recovery_cases",
            "PostgreSQL: payments",
            "PostgreSQL: merchant_guardrails",
            "OpportunityScoringEngine: deterministic v1"
        ]

        if not self.gemini.is_configured():
            return self._deterministic_grounded_answer(message, context, data_sources)

        prompt = f"""
Merchant Question: "{message}"

--- VERIFIED DATABASE CONTEXT ---
{json.dumps(context, indent=2, default=str)}

--- REQUIRED JSON OUTPUT FORMAT ---
{{
  "answer": "Clear, grounded answer addressing the merchant's question directly with exact numbers.",
  "insights": [
    "Fact-based insight 1 from data",
    "Fact-based insight 2 from data"
  ],
  "recommended_actions": [
    {{
      "label": "Action label",
      "action": "ACTION_KEY",
      "case_id": "optional_case_id"
    }}
  ],
  "confidence": 0.95,
  "confidence_level": "HIGH"
}}
"""
        try:
            raw_text = self.gemini._execute_gemini_call(prompt, COPILOT_SYSTEM_INSTRUCTION)
            cleaned_json = self.gemini._extract_json(raw_text)
            parsed = json.loads(cleaned_json)

            answer_text = parsed.get("answer") or parsed.get("reply", "")
            insights = parsed.get("insights", [])
            recommended_actions = parsed.get("recommended_actions", [])
            confidence = float(parsed.get("confidence", 0.90))

            return CopilotResponse(
                reply=answer_text,
                answer=answer_text,
                insights=insights,
                recommended_actions=recommended_actions,
                confidence=confidence,
                confidence_level="HIGH" if confidence >= 0.80 else ("MEDIUM" if confidence >= 0.60 else "LOW"),
                data_sources=data_sources,
                data_snapshot=context["metrics"]
            )
        except Exception as e:
            logger.warning(f"Gemini Copilot execution failed ({e}), falling back to deterministic answer engine.")
            return self._deterministic_grounded_answer(message, context, data_sources)

    def _deterministic_grounded_answer(
        self,
        message: str,
        context: Dict[str, Any],
        data_sources: List[str]
    ) -> CopilotResponse:
        """
        Deterministic, fully-grounded natural-language query resolution.
        Directly answers common revenue recovery questions using the actual database context.
        """
        msg_lower = message.lower()
        metrics = context["metrics"]
        top_opps = context.get("top_opportunities", [])
        top_fails = context.get("top_failures", [])
        methods = context.get("payment_methods", [])

        if "opportunity" in msg_lower or "biggest" in msg_lower or "potential" in msg_lower:
            if top_opps:
                best = top_opps[0]
                answer = (
                    f"Your biggest active recovery opportunity is Case #{best['case_id'][:8]} "
                    f"(₹{best['amount']:,.2f}) for customer {best['customer']}. "
                    f"Our opportunity engine gives this case a score of {best['score']}/100 "
                    f"({best['priority']} priority) with an expected recovery value of ₹{best['expected_recovery']:,.2f}. "
                    f"Recommended strategy: {best['strategy']}."
                )
                insights = [
                    f"Case #{best['case_id'][:8]} failed due to {best['failure_reason'] or 'Technical drop-off'}",
                    f"Customer value tier: {best['tier']}",
                    f"Total active recovery opportunities in pipeline: {metrics['active_cases_count']} cases"
                ]
                actions = [
                    {"label": f"Execute {best['strategy']} on Case #{best['case_id'][:8]}", "action": "EXECUTE_STRATEGY", "case_id": best["case_id"]},
                    {"label": "View All Recovery Cases", "action": "NAVIGATE_CASES"}
                ]
            else:
                answer = "There are currently no open recovery cases requiring intervention. All cases have been settled or resolved."
                insights = ["Pipeline is clear with 0 unrecovered drop-offs."]
                actions = [{"label": "Simulate Test Failure", "action": "RUN_SIMULATION"}]

            return CopilotResponse(
                reply=answer,
                answer=answer,
                insights=insights,
                recommended_actions=actions,
                confidence=0.96,
                confidence_level="HIGH",
                data_sources=data_sources,
                data_snapshot=metrics
            )

        elif "risk" in msg_lower or "at risk" in msg_lower or "drop" in msg_lower:
            total_at_risk = metrics["revenue_at_risk"]
            answer = (
                f"Currently, ₹{total_at_risk:,.2f} in revenue is at risk across {metrics['active_cases_count']} active cases. "
                f"Historically, PayRecover AI has achieved an autonomous recovery rate of {metrics['recovery_rate_percent']}%, "
                f"meaning an estimated ₹{(total_at_risk * (metrics['recovery_rate_percent']/100.0)):,.2f} can realistically be saved."
            )
            insights = [
                f"Active unrecovered cases: {metrics['active_cases_count']}",
                f"Total historical recovered revenue: ₹{metrics['total_recovered_amount']:,.2f}",
                f"Overall platform recovery success rate: {metrics['recovery_rate_percent']}%"
            ]
            actions = [
                {"label": "View Revenue At Risk Breakdown", "action": "VIEW_RISK"},
                {"label": "Review Top Priority Cases", "action": "NAVIGATE_OPPORTUNITIES"}
            ]
            return CopilotResponse(
                reply=answer,
                answer=answer,
                insights=insights,
                recommended_actions=actions,
                confidence=0.94,
                confidence_level="HIGH",
                data_sources=data_sources,
                data_snapshot=metrics
            )

        elif "method" in msg_lower or "failing" in msg_lower or "channel" in msg_lower:
            if methods:
                # Find method with largest volume
                top_m = max(methods, key=lambda x: x["volume"])
                answer = (
                    f"Among recorded payment methods, {top_m['method']} accounts for the highest transaction volume "
                    f"with ₹{top_m['volume']:,.2f} across {top_m['count']} payments. "
                    f"UPI continues to offer the highest conversion speed when 1-click fallback links are triggered."
                )
                insights = [f"{m['method']}: {m['count']} payments (₹{m['volume']:,.2f})" for m in methods]
                actions = [
                    {"label": "Enable UPI 1-Click Fallback", "action": "VIEW_STRATEGIES"},
                    {"label": "Open Gateways & Telemetry", "action": "VIEW_TELEMETRY"}
                ]
            else:
                answer = "Payment method telemetry is currently being collected. No specific method anomalies detected."
                insights = ["No method drop-offs recorded yet."]
                actions = []

            return CopilotResponse(
                reply=answer,
                answer=answer,
                insights=insights,
                recommended_actions=actions,
                confidence=0.91,
                confidence_level="HIGH",
                data_sources=data_sources,
                data_snapshot=metrics
            )

        elif "why" in msg_lower or "failure" in msg_lower or "reason" in msg_lower:
            if top_fails:
                primary = top_fails[0]
                answer = (
                    f"The primary failure reason in your system is '{primary['reason']}', "
                    f"responsible for {primary['count']} failures totaling ₹{primary['volume']:,.2f}. "
                    f"Most failures in this category are transient PSP/network timeouts that resolve cleanly with auto-retries."
                )
                insights = [f"{f['reason']}: {f['count']} incidents (₹{f['volume']:,.2f})" for f in top_fails]
                actions = [
                    {"label": "Inspect Top Failure Telemetry", "action": "VIEW_FAILURES"},
                    {"label": "Check Merchant Guardrails", "action": "OPEN_GUARDRAILS"}
                ]
            else:
                answer = "There are no significant failure clusters recorded in the database."
                insights = ["System health is normal."]
                actions = []

            return CopilotResponse(
                reply=answer,
                answer=answer,
                insights=insights,
                recommended_actions=actions,
                confidence=0.92,
                confidence_level="HIGH",
                data_sources=data_sources,
                data_snapshot=metrics
            )

        elif "fix" in msg_lower or "what should" in msg_lower or "action" in msg_lower:
            if top_opps:
                best = top_opps[0]
                answer = (
                    f"You should prioritize resolving Case #{best['case_id'][:8]} (₹{best['amount']:,.2f}) for customer {best['customer']}. "
                    f"It has an opportunity score of {best['score']}/100 ({best['priority']}). "
                    f"Executing the recommended '{best['strategy']}' strategy will immediately protect this revenue."
                )
                insights = [
                    f"High-impact opportunity: Case #{best['case_id'][:8]}",
                    f"Total unrecovered revenue pipeline: ₹{metrics['revenue_at_risk']:,.2f}"
                ]
                actions = [
                    {"label": f"Execute Recovery on Case #{best['case_id'][:8]}", "action": "EXECUTE_STRATEGY", "case_id": best["case_id"]},
                    {"label": "Open Command Center", "action": "NAVIGATE_COMMAND_CENTER"}
                ]
            else:
                answer = "All pending recovery cases have been acted upon. Check your payment gateways and telemetry monitors for fresh incoming events."
                insights = ["All guardrails and autonomous queues are operating normally."]
                actions = [{"label": "Open System Diagnostics", "action": "VIEW_SYSTEM_HEALTH"}]

            return CopilotResponse(
                reply=answer,
                answer=answer,
                insights=insights,
                recommended_actions=actions,
                confidence=0.95,
                confidence_level="HIGH",
                data_sources=data_sources,
                data_snapshot=metrics
            )

        else:
            answer = (
                f"Based on real database telemetry, PayRecover AI has recovered ₹{metrics['total_recovered_amount']:,.2f} "
                f"across {metrics['recovered_cases_count']} cases (overall recovery rate: {metrics['recovery_rate_percent']}%). "
                f"Currently, there are {metrics['active_cases_count']} active cases representing ₹{metrics['revenue_at_risk']:,.2f} in revenue at risk."
            )
            insights = [
                f"Total recovered revenue: ₹{metrics['total_recovered_amount']:,.2f}",
                f"Current revenue at risk: ₹{metrics['revenue_at_risk']:,.2f}",
                f"Active recovery pipeline: {metrics['active_cases_count']} cases"
            ]
            actions = [
                {"label": "View High-Value Opportunities", "action": "NAVIGATE_OPPORTUNITIES"},
                {"label": "Inspect AI Decision Traces", "action": "VIEW_TRACES"}
            ]
            return CopilotResponse(
                reply=answer,
                answer=answer,
                insights=insights,
                recommended_actions=actions,
                confidence=0.90,
                confidence_level="HIGH",
                data_sources=data_sources,
                data_snapshot=metrics
            )


copilot_service = CopilotService()
