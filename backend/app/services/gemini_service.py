import json
import logging
import re
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.schemas.contracts import PaymentInvestigationResult, CustomerIntentResult

logger = logging.getLogger("payrecover.gemini")

INVESTIGATOR_SYSTEM_INSTRUCTION = """
You are PayRecover AI's Payment Investigator. Your job is to assess whether a failed payment is realistically recoverable based on payment context, customer behavior and historical evidence.
Do not invent facts. Do not assume customer information that is not provided.
Distinguish temporary technical failures from customer-driven failures.
Consider the economic value of recovery.
Analyze positive and negative signals rigorously.

Positive signals: high historical payment success, returning customer, recent successful orders, temporary gateway latency/timeout, preferred payment method available, low retry count, high engagement.
Negative signals: repeated payment failures, multiple retries already exhausted, long overdue period, customer cancellation intent, persistent insufficient funds, unrecoverable bank block.

Produce only the requested structured output conforming to the JSON schema.
""".strip()

INTENT_ANALYST_SYSTEM_INSTRUCTION = """
You are PayRecover AI's Customer Intent Analyst.
Your job is to determine the customer's actual intent from the supplied customer message and payment context.
Use only the evidence provided.
Do not invent customer information.
Do not infer unsupported facts.
Distinguish customer intent from sentiment.
Consider the payment status, failure reason, customer history, previous interactions, and wording of the current message.
Identify implicit intent when it is strongly supported by context.
Return only the requested structured output.
""".strip()


class GeminiService:
    """
    Gemini API client service for PayRecover AI.
    Provides structured output generation with strict schema enforcement,
    error handling, timeouts, and safe context isolation.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL or "gemini-1.5-flash"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your-gemini-api-key-here")

    # -------------------------------------------------------------
    # 1. Payment Investigation
    # -------------------------------------------------------------
    def investigate_payment(self, context: Dict[str, Any]) -> PaymentInvestigationResult:
        """
        Sends structured payment & customer context to Gemini to generate
        a validated PaymentInvestigationResult.
        """
        if not self.is_configured():
            logger.info("GEMINI_API_KEY not configured. Using deterministic contextual reasoning engine for investigator.")
            return self._deterministic_fallback_investigation(context)

        prompt = f"""
Analyze the following payment failure context and produce a structured investigation assessment.

--- CONTEXT ---
{json.dumps(context, indent=2, default=str)}

--- REQUIRED JSON OUTPUT FORMAT ---
{{
  "payment_id": "{context.get('payment', {}).get('payment_id', '')}",
  "failure_category": "temporary | customer_action_required | payment_method_issue | insufficient_funds | technical | unknown",
  "failure_explanation": "Detailed explanation of why the payment failed based on telemetry",
  "customer_profile_summary": "Summary of customer segment, loyalty, and past reliability",
  "payment_history_summary": "Summary of recent payment history (success vs failures)",
  "recovery_probability": 0.85,
  "recovery_score": 85,
  "risk_level": "LOW | MEDIUM | HIGH",
  "recommended_next_action": "RETRY | ALTERNATE_PAYMENT_METHOD | PAYMENT_LINK | FOLLOW_UP | INCENTIVE_REVIEW | HUMAN_ESCALATION | STOP_RECOVERY",
  "reasoning_summary": "Comprehensive rationale explaining why this score and action were chosen",
  "contributing_factors": ["factor 1", "factor 2"],
  "negative_factors": ["risk factor 1"],
  "confidence": 0.92
}}
"""

        try:
            raw_text = self._execute_gemini_call(prompt, INVESTIGATOR_SYSTEM_INSTRUCTION)
            cleaned_json = self._extract_json(raw_text)
            data = json.loads(cleaned_json)

            data["payment_id"] = context.get("payment", {}).get("payment_id", data.get("payment_id", ""))

            if "recovery_score" in data:
                data["recovery_score"] = int(round(float(data["recovery_score"])))
            if "recovery_probability" in data:
                data["recovery_probability"] = float(data["recovery_probability"])
            if "confidence" in data:
                data["confidence"] = float(data["confidence"])

            return PaymentInvestigationResult(**data)

        except Exception as e:
            logger.error(f"Gemini investigation API execution failed: {e}", exc_info=True)
            return self._deterministic_fallback_investigation(context, error_note=f"Gemini API Error: {str(e)}")

    # -------------------------------------------------------------
    # 2. Customer Intent Analysis
    # -------------------------------------------------------------
    def analyze_customer_intent(self, context: Dict[str, Any]) -> CustomerIntentResult:
        """
        Sends customer message & interaction telemetry to Gemini to determine
        the true customer intent, sentiment, urgency, and recommended action.
        """
        if not self.is_configured():
            logger.info("GEMINI_API_KEY not configured. Using deterministic contextual reasoning engine for intent.")
            return self._deterministic_fallback_intent(context)

        prompt = f"""
Analyze the following customer message and payment context to classify the customer's intent, sentiment, urgency, and recommended recovery action.

--- CONTEXT ---
{json.dumps(context, indent=2, default=str)}

--- SUPPORTED INTENT TAXONOMY ---
- ALTERNATE_PAYMENT_METHOD (wants UPI/NetBanking/card alternative)
- WILL_PAY_LATER (wants to delay payment, salary wait, reminder request)
- PAYMENT_PROBLEM (asking why payment failed or reporting an error)
- PRICE_CONCERN (asking for discount, coupon, price objection)
- CANCEL_REQUEST (wants to cancel order/subscription)
- ALREADY_PAID (claims money was already deducted or order paid)
- NEEDS_ASSISTANCE (asking human support/agent to help complete)
- NOT_INTERESTED (no longer interested in purchase)
- PAYMENT_LINK_REQUEST (explicitly requesting payment link to be sent)
- RETRY_REQUEST (asking to retry payment immediately)
- UNKNOWN (unclear or unrecognizable message)

--- SUPPORTED SENTIMENTS ---
POSITIVE | NEUTRAL | NEGATIVE | FRUSTRATED

--- SUPPORTED URGENCIES ---
LOW | MEDIUM | HIGH

--- SUPPORTED RECOMMENDED ACTIONS ---
OFFER_ALTERNATE_PAYMENT | WAIT_AND_FOLLOW_UP | INVESTIGATE_PAYMENT | PROVIDE_PAYMENT_LINK | REVIEW_PAYMENT_STATUS | OFFER_ASSISTANCE | STOP_CONTACT | RETRY_PAYMENT | HUMAN_ESCALATION

--- SUPPORTED RECOMMENDED CHANNELS ---
WHATSAPP | SMS | EMAIL | VOICE | NONE

--- REQUIRED JSON OUTPUT FORMAT ---
{{
  "customer_id": "{context.get('customer', {}).get('customer_id', '')}",
  "recovery_case_id": "{context.get('recovery', {}).get('recovery_case_id', '')}",
  "intent": "INTENT_ENUM_VALUE",
  "confidence": 0.95,
  "sentiment": "SENTIMENT_ENUM_VALUE",
  "urgency": "URGENCY_ENUM_VALUE",
  "intent_summary": "Concise summary of customer intent in 1 sentence",
  "evidence": ["evidence point 1", "evidence point 2"],
  "recommended_channel": "WHATSAPP | SMS | EMAIL | VOICE | NONE",
  "recommended_action": "RECOMMENDED_ACTION_ENUM_VALUE",
  "reasoning_summary": "Clear analytical reasoning explaining intent classification and next step"
}}
"""

        try:
            raw_text = self._execute_gemini_call(prompt, INTENT_ANALYST_SYSTEM_INSTRUCTION)
            cleaned_json = self._extract_json(raw_text)
            data = json.loads(cleaned_json)

            data["customer_id"] = context.get("customer", {}).get("customer_id", data.get("customer_id", ""))
            data["recovery_case_id"] = context.get("recovery", {}).get("recovery_case_id", data.get("recovery_case_id"))

            if "confidence" in data:
                data["confidence"] = float(data["confidence"])

            return CustomerIntentResult(**data)

        except Exception as e:
            logger.error(f"Gemini intent API execution failed: {e}", exc_info=True)
            return self._deterministic_fallback_intent(context, error_note=f"Gemini API Error: {str(e)}")

    # -------------------------------------------------------------
    # Shared Gemini Caller
    # -------------------------------------------------------------
    def _execute_gemini_call(self, prompt: str, system_instruction: str) -> str:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return response.text
        except Exception as sdk_err:
            logger.warning(f"google-genai SDK call failed ({sdk_err}), trying REST API endpoint...")
            return self._call_gemini_rest(prompt, system_instruction)

    def _call_gemini_rest(self, prompt: str, system_instruction: str) -> str:
        """Direct fallback REST call to Gemini endpoint with timeout"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }
        with httpx.Client(timeout=12.0) as client:
            res = client.post(url, json=payload)
            res.raise_for_status()
            res_json = res.json()
            return res_json["candidates"][0]["content"]["parts"][0]["text"]

    def _extract_json(self, text: str) -> str:
        """Extract JSON block from text response"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    # -------------------------------------------------------------
    # Deterministic Reasoning Fallback for Investigator
    # -------------------------------------------------------------
    def _deterministic_fallback_investigation(
        self,
        context: Dict[str, Any],
        error_note: Optional[str] = None
    ) -> PaymentInvestigationResult:
        payment = context.get("payment", {})
        customer = context.get("customer", {})

        payment_id = payment.get("payment_id", "unknown")
        amount = float(payment.get("amount", 0.0))
        method = payment.get("payment_method", "CARD").upper()
        failure_reason = payment.get("failure_reason", "UNKNOWN").upper()
        
        success_count = int(customer.get("successful_payments", 0))
        failed_count = int(customer.get("failed_payments", 0))
        total_attempts = max(1, success_count + failed_count)
        success_rate = success_count / total_attempts

        customer_value = customer.get("customer_value", "STANDARD")
        customer_name = customer.get("name", "Customer")
        preferred_method = customer.get("preferred_payment_method", "UPI")

        contributing = []
        negative = []

        if failure_reason in ["CARD_DECLINED", "3DS_TIMEOUT"]:
            failure_category = "payment_method_issue"
            failure_explanation = "Issuing bank 3DS verification failed or timed out during card authentication."
            recommended_action = "ALTERNATE_PAYMENT_METHOD"
            contributing.append(f"Customer has preferred alternative payment method: {preferred_method}")
            base_prob = 0.85
        elif failure_reason in ["UPI_TIMEOUT", "PSP_TIMEOUT"]:
            failure_category = "technical"
            failure_explanation = "UPI PSP application response latency exceeded timeout threshold."
            recommended_action = "PAYMENT_LINK"
            contributing.append("UPI failures are transient technical interrupts with high recovery conversion")
            base_prob = 0.92
        elif failure_reason in ["INSUFFICIENT_FUNDS"]:
            failure_category = "insufficient_funds"
            failure_explanation = "Debit account balance was insufficient at time of transaction."
            recommended_action = "FOLLOW_UP"
            negative.append("Customer had insufficient balance; requires delayed scheduling")
            base_prob = 0.55
        elif failure_reason in ["CHECKOUT_ABANDONED"]:
            failure_category = "customer_action_required"
            failure_explanation = "Customer dropped off at final authentication screen before OTP entry."
            recommended_action = "PAYMENT_LINK"
            contributing.append("Order was active; direct frictionless link recovers abandoned checkouts")
            base_prob = 0.70
        elif failure_reason in ["SUBSCRIPTION_FAILED"]:
            failure_category = "technical"
            failure_explanation = "Recurring auto-debit mandate authentication expired on payment instrument."
            recommended_action = "RETRY"
            contributing.append("Customer is a subscriber with high lifetime retention value")
            base_prob = 0.88
        else:
            failure_category = "unknown"
            failure_explanation = f"Payment failure recorded with reason: {failure_reason}."
            recommended_action = "RETRY"
            base_prob = 0.65

        if success_count >= 5:
            contributing.append(f"High historical reliability: {success_count} previous successful payments ({int(success_rate*100)}% rate)")
            base_prob += 0.08
        elif success_count >= 1:
            contributing.append(f"Returning customer with {success_count} prior orders")
            base_prob += 0.03
        else:
            negative.append("First-time customer with no prior transaction track record")
            base_prob -= 0.05

        if customer_value in ["VIP", "HIGH_VALUE"]:
            contributing.append(f"Customer tier is {customer_value} with high lifetime purchase intent")
            base_prob += 0.04

        if amount >= 50000.0:
            recommended_action = "HUMAN_ESCALATION"
            negative.append(f"High transaction value (₹{amount:,.2f}) requires merchant approval guardrail")

        prob = min(0.98, max(0.10, round(base_prob, 2)))
        score = int(round(prob * 100))
        risk_level = "LOW" if prob >= 0.80 else ("MEDIUM" if prob >= 0.50 else "HIGH")
        confidence = 0.94 if (success_count > 0 and len(contributing) > 1) else 0.82

        profile_summary = f"{customer_name} ({customer_value}) with {success_count} successful orders and {failed_count} failures."
        history_summary = f"{success_count}/{total_attempts} total successful payments ({int(success_rate*100)}% success rate)."
        
        reasoning = (
            f"Assessed payment #{payment_id} for ₹{amount:,.2f}. "
            f"Customer demonstrates strong payment reliability ({int(success_rate*100)}% historical success). "
            f"Failure was categorized as {failure_category} ({failure_reason}). "
            f"Recommended strategy is {recommended_action} with {score}% recovery score."
        )
        if error_note:
            reasoning += f" [Note: {error_note}]"

        return PaymentInvestigationResult(
            payment_id=payment_id,
            failure_category=failure_category,
            failure_explanation=failure_explanation,
            customer_profile_summary=profile_summary,
            payment_history_summary=history_summary,
            recovery_probability=prob,
            recovery_score=score,
            risk_level=risk_level,
            recommended_next_action=recommended_action,
            reasoning_summary=reasoning,
            contributing_factors=contributing,
            negative_factors=negative,
            confidence=confidence
        )

    # -------------------------------------------------------------
    # Deterministic Reasoning Fallback for Intent
    # -------------------------------------------------------------
    def _deterministic_fallback_intent(
        self,
        context: Dict[str, Any],
        error_note: Optional[str] = None
    ) -> CustomerIntentResult:
        customer = context.get("customer", {})
        customer_id = customer.get("customer_id", "unknown")
        recovery_case_id = context.get("recovery", {}).get("recovery_case_id")
        message = context.get("interaction", {}).get("message", "").strip()
        channel = context.get("interaction", {}).get("channel", "WHATSAPP")
        payment = context.get("payment", {})

        msg_lower = message.lower()
        evidence = []

        # Exact Demo Scenarios and Intent Logic
        if any(w in msg_lower for w in ["upi", "gpay", "phonepe", "paytm", "another method", "other way", "alternate", "card isn't working", "card not working", "use upi", "pay through upi"]):
            intent = "ALTERNATE_PAYMENT_METHOD"
            sentiment = "FRUSTRATED" if ("not working" in msg_lower or "isn't working" in msg_lower or "failed" in msg_lower) else "POSITIVE"
            urgency = "HIGH"
            summary = "Customer is unable to complete card payment and explicitly requests an alternate method like UPI."
            recommended_action = "OFFER_ALTERNATE_PAYMENT"
            recommended_channel = "WHATSAPP" if channel == "WHATSAPP" else "SMS"
            evidence.append("Customer explicitly mentioned alternate payment method (UPI/GPay)")
            evidence.append(f"Current transaction method: {payment.get('payment_method', 'CARD')}")
            confidence = 0.96

        elif any(w in msg_lower for w in ["remind me", "later", "tomorrow", "salary", "don't have money", "dont have money", "enough balance", "not enough balance", "balance right now"]):
            intent = "WILL_PAY_LATER"
            sentiment = "NEUTRAL"
            urgency = "MEDIUM"
            summary = "Customer intends to complete payment later due to temporary balance or timing constraints."
            recommended_action = "WAIT_AND_FOLLOW_UP"
            recommended_channel = "WHATSAPP"
            evidence.append("Customer requested a reminder or indicated delayed payment timeline")
            confidence = 0.94

        elif any(w in msg_lower for w in ["already paid", "already completed", "already deducted", "money deducted", "debited", "check your records", "please verify"]):
            intent = "ALREADY_PAID"
            sentiment = "FRUSTRATED"
            urgency = "HIGH"
            summary = "Customer states that funds were already deducted and requests immediate transaction verification."
            recommended_action = "REVIEW_PAYMENT_STATUS"
            recommended_channel = "WHATSAPP"
            evidence.append("Customer claims prior deduction and requested payment verification")
            confidence = 0.95

        elif any(w in msg_lower for w in ["cancel", "dont want", "don't want", "cancel this", "not interested", "dont need", "no longer"]):
            intent = "CANCEL_REQUEST"
            sentiment = "NEGATIVE"
            urgency = "LOW"
            summary = "Customer expressed explicit cancellation intent for the pending order."
            recommended_action = "STOP_CONTACT"
            recommended_channel = "NONE"
            evidence.append("Customer explicitly expressed cancellation intent")
            confidence = 0.93

        elif any(w in msg_lower for w in ["payment link", "send me the link", "send link", "give me link", "send me a payment link", "send payment link"]):
            intent = "PAYMENT_LINK_REQUEST"
            sentiment = "POSITIVE"
            urgency = "HIGH"
            summary = "Customer is actively requesting a direct payment link to finalize the checkout."
            recommended_action = "PROVIDE_PAYMENT_LINK"
            recommended_channel = "WHATSAPP"
            evidence.append("Customer explicitly requested a checkout payment link")
            confidence = 0.98

        elif any(w in msg_lower for w in ["why did", "why failed", "reason", "what happened", "error", "why my payment fail"]):
            intent = "PAYMENT_PROBLEM"
            sentiment = "FRUSTRATED"
            urgency = "MEDIUM"
            summary = "Customer is inquiring about the root cause of the payment failure."
            recommended_action = "INVESTIGATE_PAYMENT"
            recommended_channel = "WHATSAPP"
            evidence.append("Customer inquired about gateway/transaction failure details")
            confidence = 0.91

        elif any(w in msg_lower for w in ["try again", "retry", "charge again", "attempt again", "try the payment again"]):
            intent = "RETRY_REQUEST"
            sentiment = "POSITIVE"
            urgency = "HIGH"
            summary = "Customer is requesting an immediate retry of the payment attempt."
            recommended_action = "RETRY_PAYMENT"
            recommended_channel = "SMS"
            evidence.append("Customer requested transaction retry")
            confidence = 0.92

        elif any(w in msg_lower for w in ["help", "assist", "support", "someone help", "call me", "talk to human"]):
            intent = "NEEDS_ASSISTANCE"
            sentiment = "NEUTRAL"
            urgency = "HIGH"
            summary = "Customer requires human support assistance to complete checkout."
            recommended_action = "OFFER_ASSISTANCE"
            recommended_channel = "VOICE"
            evidence.append("Customer requested human guidance or agent assistance")
            confidence = 0.90

        elif any(w in msg_lower for w in ["discount", "coupon", "cheaper", "expensive", "offer"]):
            intent = "PRICE_CONCERN"
            sentiment = "NEUTRAL"
            urgency = "MEDIUM"
            summary = "Customer is questioning the price or asking for an available discount incentive."
            recommended_action = "WAIT_AND_FOLLOW_UP"
            recommended_channel = "WHATSAPP"
            evidence.append("Customer raised price objections or discount queries")
            confidence = 0.89

        else:
            intent = "UNKNOWN"
            sentiment = "NEUTRAL"
            urgency = "LOW"
            summary = "Message context does not provide sufficient clear signal for conclusive intent mapping."
            recommended_action = "OFFER_ASSISTANCE"
            recommended_channel = "WHATSAPP"
            evidence.append(f"Analyzed raw customer text: '{message[:50]}'")
            confidence = 0.70

        reasoning = f"Customer message '{message}' was classified as {intent} ({confidence*100:.0f}% confidence) with {sentiment} sentiment and {urgency} urgency. Recommended action is {recommended_action} via {recommended_channel}."
        if error_note:
            reasoning += f" [Note: {error_note}]"

        return CustomerIntentResult(
            customer_id=customer_id,
            recovery_case_id=recovery_case_id,
            intent=intent,
            confidence=confidence,
            sentiment=sentiment,
            urgency=urgency,
            intent_summary=summary,
            evidence=evidence,
            recommended_channel=recommended_channel,
            recommended_action=recommended_action,
            reasoning_summary=reasoning
        )


gemini_service = GeminiService()
