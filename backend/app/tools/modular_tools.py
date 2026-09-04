from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.entities import Payment, Customer, RecoveryCase


class PaymentTools:
    @staticmethod
    def get_payment_details(db: Session, payment_id: str) -> Dict[str, Any]:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return {"error": "Payment not found"}
        return {
            "id": payment.id,
            "razorpay_id": payment.razorpay_payment_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "method": payment.payment_method,
            "status": payment.status,
            "failure_reason": payment.failure_reason,
            "customer_id": payment.customer_id
        }


class CustomerTools:
    @staticmethod
    def get_customer_history(db: Session, customer_id: str) -> Dict[str, Any]:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": "Customer not found"}
        return {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "customer_value": customer.customer_value,
            "preferred_method": customer.preferred_payment_method,
            "successful_payments": customer.total_successful_payments,
            "failed_payments": customer.total_failed_payments,
            "reliability_rate": (
                customer.total_successful_payments / max(1, customer.total_successful_payments + customer.total_failed_payments)
            )
        }


class RecoveryTools:
    @staticmethod
    def calculate_score_and_prob(payment_amount: float, customer_reliability: float, failure_reason: str) -> tuple[float, float]:
        # Domain heuristic logic for deterministic recovery score calculation
        base_prob = customer_reliability * 0.5
        reason_weights = {
            "CARD_DECLINED": 0.38,
            "UPI_TIMEOUT": 0.45,
            "CHECKOUT_ABANDONED": 0.30,
            "INSUFFICIENT_FUNDS": 0.20,
            "SUBSCRIPTION_FAILED": 0.42,
            "AUTHENTICATION_FAILED": 0.25,
            "BANK_SERVER_DOWN": 0.35,
        }
        reason_weight = reason_weights.get(failure_reason, 0.25)
        probability = min(0.98, max(0.15, base_prob + reason_weight))
        score = round(probability * 100, 1)
        return score, round(probability, 2)


class CommunicationTools:
    @staticmethod
    def format_recovery_template(customer_name: str, amount: float, link_url: str, intent: str) -> str:
        if intent == "ALTERNATE_PAYMENT_METHOD":
            return f"Hi {customer_name}! Your recent payment of ₹{amount:,.2f} had a card gateway issue. Use this instant 1-click UPI link to finish securely: {link_url}"
        elif intent == "PAY_LATER":
            return f"Hi {customer_name}, as requested, here is your payment link for ₹{amount:,.2f} valid for the next 24 hours: {link_url}"
        else:
            return f"Hi {customer_name}, we noticed your ₹{amount:,.2f} payment was interrupted. Tap here to complete it instantly: {link_url}"


class RazorpayTools:
    @staticmethod
    def generate_smart_link(amount: float, customer: Customer, discount_pct: float = 0.0) -> str:
        final_amount = amount * (1 - (discount_pct / 100.0))
        return f"https://rzp.io/i/demo_recov_{int(final_amount)}"
