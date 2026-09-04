import uuid
import random
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine, Base
from app.models.entities import (
    Merchant,
    Customer,
    Payment,
    RecoveryCase,
    AgentAction,
    MerchantGuardrail,
    CustomerInteraction,
    PaymentStatus,
    RecoveryStatus,
    PaymentMethod,
    FailureReason,
    AgentType,
    ActionType,
    ActionStatus,
    InteractionChannel,
    InteractionDirection
)


def seed_database(db: Session = None):
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        # Check if already seeded
        if db.query(Customer).count() >= 30:
            print("[SEED] Database already contains sufficient seed data. Skipping full seed.")
            return

        print("[SEED] Starting comprehensive seed generation for PayRecover AI...")

        # 1. Create Primary Merchant
        merchant = db.query(Merchant).filter(Merchant.id == "merchant_primary").first()
        if not merchant:
            merchant = Merchant(
                id="merchant_primary",
                name="BharatTech Commerce Ltd.",
                email="payments@bharattech.in",
                created_at=datetime.utcnow() - timedelta(days=90)
            )
            db.add(merchant)
            db.flush()

        # Guardrails
        guardrail = db.query(MerchantGuardrail).filter(MerchantGuardrail.merchant_id == merchant.id).first()
        if not guardrail:
            guardrail = MerchantGuardrail(
                id="gdr_merchant_primary",
                merchant_id=merchant.id,
                max_retries=3,
                max_discount_percentage=10.0,
                max_campaign_days=3,
                quiet_hours_start="22:00",
                quiet_hours_end="08:00",
                high_value_threshold=50000.0,
                human_approval_required=True,
                max_contact_attempts=4
            )
            db.add(guardrail)
            db.flush()

        # 2. Seed 35 Realistic Customers
        customer_names = [
            ("Aarav Sharma", "aarav.sharma@example.com", "+919876543210", "VIP", "UPI"),
            ("Priya Patel", "priya.patel@example.com", "+919876543211", "HIGH_VALUE", "CARD"),
            ("Rohan Verma", "rohan.verma@example.com", "+919876543212", "VIP", "UPI"),
            ("Ananya Iyer", "ananya.iyer@example.com", "+919876543213", "STANDARD", "UPI"),
            ("Vikram Malhotra", "vikram.m@example.com", "+919876543214", "VIP", "CARD"),
            ("Neha Gupta", "neha.gupta@example.com", "+919876543215", "HIGH_VALUE", "NETBANKING"),
            ("Kavita Rao", "kavita.rao@example.com", "+919876543216", "STANDARD", "UPI"),
            ("Aditya Joshi", "aditya.j@example.com", "+919876543217", "STANDARD", "UPI"),
            ("Sneha Nair", "sneha.nair@example.com", "+919876543218", "HIGH_VALUE", "CARD"),
            ("Arjun Deshmukh", "arjun.d@example.com", "+919876543219", "STANDARD", "UPI"),
            ("Ritu Agarwal", "ritu.a@example.com", "+919876543220", "VIP", "CARD"),
            ("Siddharth Mehra", "sid.mehra@example.com", "+919876543221", "STANDARD", "UPI"),
            ("Divya Menon", "divya.menon@example.com", "+919876543222", "STANDARD", "NETBANKING"),
            ("Manish Kapoor", "manish.k@example.com", "+919876543223", "HIGH_VALUE", "UPI"),
            ("Pooja Singhania", "pooja.s@example.com", "+919876543224", "VIP", "CARD"),
            ("Tarun Reddy", "tarun.reddy@example.com", "+919876543225", "STANDARD", "UPI"),
            ("Meera Sen", "meera.sen@example.com", "+919876543226", "STANDARD", "UPI"),
            ("Gaurav Bansal", "gaurav.b@example.com", "+919876543227", "HIGH_VALUE", "CARD"),
            ("Shweta Kulkarni", "shweta.k@example.com", "+919876543228", "STANDARD", "UPI"),
            ("Nikhil Saxena", "nikhil.s@example.com", "+919876543229", "STANDARD", "NETBANKING"),
            ("Karan Bajaj", "karan.b@example.com", "+919876543230", "VIP", "CARD"),
            ("Sangeeta Roy", "sangeeta.roy@example.com", "+919876543231", "STANDARD", "UPI"),
            ("Akash Bhatia", "akash.bhatia@example.com", "+919876543232", "HIGH_VALUE", "UPI"),
            ("Sunita Pillai", "sunita.p@example.com", "+919876543233", "STANDARD", "CARD"),
            ("Deepak Chawla", "deepak.c@example.com", "+919876543234", "STANDARD", "UPI"),
            ("Harish Nambiar", "harish.n@example.com", "+919876543235", "HIGH_VALUE", "UPI"),
            ("Rashmi Trivedi", "rashmi.t@example.com", "+919876543236", "VIP", "CARD"),
            ("Varun Pillai", "varun.p@example.com", "+919876543237", "STANDARD", "UPI"),
            ("Tanvi Mathur", "tanvi.m@example.com", "+919876543238", "HIGH_VALUE", "UPI"),
            ("Kiran Hegde", "kiran.hegde@example.com", "+919876543239", "STANDARD", "NETBANKING"),
            ("Simran Kaur", "simran.k@example.com", "+919876543240", "VIP", "CARD"),
            ("Rajesh Solanki", "rajesh.s@example.com", "+919876543241", "STANDARD", "UPI"),
            ("Pallavi Dave", "pallavi.d@example.com", "+919876543242", "STANDARD", "UPI"),
            ("Manoj Tiwari", "manoj.t@example.com", "+919876543243", "HIGH_VALUE", "CARD"),
            ("Ishaan Mukherjee", "ishaan.m@example.com", "+919876543244", "VIP", "UPI")
        ]

        customers = []
        for i, (name, email, phone, val, pref_method) in enumerate(customer_names):
            cust_id = f"cust_{100 + i}"
            c = Customer(
                id=cust_id,
                name=name,
                email=email,
                phone=phone,
                customer_value=val,
                preferred_payment_method=pref_method,
                total_successful_payments=random.randint(4, 18) if val == "VIP" else random.randint(1, 7),
                total_failed_payments=random.randint(0, 2),
                created_at=datetime.utcnow() - timedelta(days=random.randint(30, 180))
            )
            db.add(c)
            customers.append(c)

        db.flush()

        # 3. Create Specific Exact Demo Target Scenario
        # Customer: Vikram Malhotra (Returning customer, 10 past success, ₹12,999 Card decline -> UPI recovery link)
        demo_customer = customers[4]  # Vikram Malhotra
        demo_customer.total_successful_payments = 10
        demo_customer.total_failed_payments = 1

        demo_payment = Payment(
            id="pay_demo_12999",
            razorpay_payment_id="pay_RzP92831Demo",
            customer_id=demo_customer.id,
            amount=12999.0,
            currency="INR",
            payment_method=PaymentMethod.CARD.value,
            status=PaymentStatus.FAILED.value,
            failure_reason=FailureReason.CARD_DECLINED.value,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            updated_at=datetime.utcnow() - timedelta(minutes=15)
        )
        db.add(demo_payment)
        db.flush()

        demo_case = RecoveryCase(
            id="rc_demo_12999",
            payment_id=demo_payment.id,
            recovery_score=89.0,
            recovery_probability=0.89,
            customer_intent="ALTERNATE_PAYMENT_METHOD",
            current_strategy="UPI_FALLBACK_LINK",
            status=RecoveryStatus.ACTION_IN_PROGRESS.value,
            retry_count=1,
            recovered_amount=0.0,
            payment_link_url="https://rzp.io/i/recov_pay92831_upi",
            started_at=datetime.utcnow() - timedelta(minutes=40)
        )
        db.add(demo_case)
        db.flush()

        # Seed initial actions for the demo case
        a1 = AgentAction(
            id=f"act_demo_1",
            recovery_case_id=demo_case.id,
            agent_type=AgentType.INVESTIGATOR.value,
            action_type=ActionType.INVESTIGATE_PAYMENT.value,
            reasoning_summary="AI Investigator analyzed PAY_92831. High historical reliability (10/11 successful payments). Gateway reported 3DS card decline. Recovery probability calculated: 89%.",
            status=ActionStatus.EXECUTED.value,
            created_at=datetime.utcnow() - timedelta(minutes=38)
        )
        a2 = AgentAction(
            id=f"act_demo_2",
            recovery_case_id=demo_case.id,
            agent_type=AgentType.STRATEGIST.value,
            action_type=ActionType.SELECT_STRATEGY.value,
            reasoning_summary="AI Strategist selected UPI fallback link over WhatsApp. Do not retry failed card to avoid friction.",
            status=ActionStatus.EXECUTED.value,
            created_at=datetime.utcnow() - timedelta(minutes=35)
        )
        a3 = AgentAction(
            id=f"act_demo_3",
            recovery_case_id=demo_case.id,
            agent_type=AgentType.TOOL_EXECUTOR.value,
            action_type=ActionType.GUARDRAIL_CHECK.value,
            reasoning_summary="Guardrail check passed: Amount (₹12,999) below high-value limit (₹50,000), retry count 0/3 within allowed threshold.",
            status=ActionStatus.EXECUTED.value,
            created_at=datetime.utcnow() - timedelta(minutes=34)
        )
        a4 = AgentAction(
            id=f"act_demo_4",
            recovery_case_id=demo_case.id,
            agent_type=AgentType.TOOL_EXECUTOR.value,
            action_type=ActionType.GENERATE_PAYMENT_LINK.value,
            reasoning_summary="Razorpay Test Mode generated secure 1-click UPI recovery link: https://rzp.io/i/recov_pay92831_upi",
            status=ActionStatus.EXECUTED.value,
            created_at=datetime.utcnow() - timedelta(minutes=33)
        )
        a5 = AgentAction(
            id=f"act_demo_5",
            recovery_case_id=demo_case.id,
            agent_type=AgentType.INTENT_AI.value,
            action_type=ActionType.DISPATCH_MESSAGE.value,
            reasoning_summary="Customer intent detected: ALTERNATE_PAYMENT_METHOD. WhatsApp recovery payload dispatched.",
            status=ActionStatus.EXECUTED.value,
            created_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db.add_all([a1, a2, a3, a4, a5])

        # Add interaction for demo
        m1 = CustomerInteraction(
            id=f"msg_demo_1",
            customer_id=demo_customer.id,
            recovery_case_id=demo_case.id,
            channel=InteractionChannel.WHATSAPP.value,
            direction=InteractionDirection.OUTBOUND.value,
            message=f"Hi Vikram! Your ₹12,999 payment was interrupted by issuing bank card 3DS. Complete with instant 1-click UPI: https://rzp.io/i/recov_pay92831_upi",
            detected_intent="ALTERNATE_PAYMENT_METHOD",
            confidence=0.96,
            created_at=datetime.utcnow() - timedelta(minutes=30)
        )
        m2 = CustomerInteraction(
            id=f"msg_demo_2",
            customer_id=demo_customer.id,
            recovery_case_id=demo_case.id,
            channel=InteractionChannel.WHATSAPP.value,
            direction=InteractionDirection.INBOUND.value,
            message="Thanks! Yes, my card OTP was delayed. Paying via GPay now.",
            detected_intent="ALTERNATE_PAYMENT_METHOD",
            confidence=0.98,
            created_at=datetime.utcnow() - timedelta(minutes=25)
        )
        db.add_all([m1, m2])

        # 4. Generate 110 Payments (45 Failed, 18 Recovered, 47 Successful)
        amounts = [999.0, 1499.0, 2499.0, 3999.0, 4999.0, 8999.0, 12999.0, 25000.0, 49999.0, 75000.0]
        methods = [PaymentMethod.UPI.value, PaymentMethod.CARD.value, PaymentMethod.NETBANKING.value]
        reasons = [
            FailureReason.UPI_TIMEOUT.value,
            FailureReason.CARD_DECLINED.value,
            FailureReason.INSUFFICIENT_FUNDS.value,
            FailureReason.CHECKOUT_ABANDONED.value,
            FailureReason.AUTHENTICATION_FAILED.value,
            FailureReason.BANK_SERVER_DOWN.value,
            FailureReason.SUBSCRIPTION_FAILED.value
        ]

        for i in range(1, 111):
            cust = random.choice(customers)
            amount = random.choice(amounts)
            method = random.choice(methods)
            p_time = datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23), minutes=random.randint(0, 59))
            pay_id = f"pay_{uuid.uuid4().hex[:8]}"
            rzp_id = f"pay_RzP_{random.randint(100000, 999999)}"

            # Distribute statuses
            if i <= 18:
                status = PaymentStatus.RECOVERED.value
                reason = random.choice(reasons)
            elif i <= 65:
                status = PaymentStatus.FAILED.value
                reason = random.choice(reasons)
            else:
                status = PaymentStatus.SUCCESS.value
                reason = None

            p = Payment(
                id=pay_id,
                razorpay_payment_id=rzp_id,
                customer_id=cust.id,
                amount=amount,
                currency="INR",
                payment_method=method,
                status=status,
                failure_reason=reason,
                created_at=p_time,
                updated_at=p_time + timedelta(minutes=15)
            )
            db.add(p)
            db.flush()

            # Create recovery cases for failed & recovered payments
            if status in [PaymentStatus.FAILED.value, PaymentStatus.RECOVERED.value]:
                prob = round(random.uniform(0.40, 0.95), 2)
                score = round(prob * 100, 1)

                if status == PaymentStatus.RECOVERED.value:
                    rc_status = RecoveryStatus.RECOVERED.value
                    recov_amt = amount
                elif amount >= 50000.0:
                    rc_status = RecoveryStatus.AWAITING_HUMAN_APPROVAL.value
                    recov_amt = 0.0
                elif prob > 0.75:
                    rc_status = RecoveryStatus.ACTION_IN_PROGRESS.value
                    recov_amt = 0.0
                else:
                    rc_status = RecoveryStatus.IDENTIFIED.value
                    recov_amt = 0.0

                strategies = ["UPI_FALLBACK_LINK", "INSTANT_WHATSAPP_ONE_CLICK_UPI", "SMART_DISCOUNT_NUDGE", "SCHEDULED_PAY_LATER_REMINDER", "EXECUTIVE_CONCIERGE_CALL"]
                intents = ["ALTERNATE_PAYMENT_METHOD", "PAY_LATER", "PRICE_OBJECTION", "TECH_DIFFICULTY"]

                rc = RecoveryCase(
                    id=f"rc_{uuid.uuid4().hex[:8]}",
                    payment_id=p.id,
                    recovery_score=score,
                    recovery_probability=prob,
                    customer_intent=random.choice(intents),
                    current_strategy=random.choice(strategies),
                    status=rc_status,
                    retry_count=random.randint(1, 2) if rc_status != RecoveryStatus.IDENTIFIED.value else 0,
                    recovered_amount=recov_amt,
                    payment_link_url=f"https://rzp.io/i/demo_{p.id}" if rc_status in [RecoveryStatus.ACTION_IN_PROGRESS.value, RecoveryStatus.RECOVERED.value] else None,
                    started_at=p_time,
                    completed_at=p_time + timedelta(minutes=25) if rc_status == RecoveryStatus.RECOVERED.value else None
                )
                db.add(rc)
                db.flush()

                # Agent actions
                action_investigate = AgentAction(
                    id=f"act_{uuid.uuid4().hex[:8]}",
                    recovery_case_id=rc.id,
                    agent_type=AgentType.INVESTIGATOR.value,
                    action_type=ActionType.INVESTIGATE_PAYMENT.value,
                    reasoning_summary=f"Investigated failure {p.failure_reason}. Customer reliability rate {(cust.total_successful_payments / max(1, cust.total_successful_payments + cust.total_failed_payments))*100:.0f}%. Score assigned: {score}/100.",
                    status=ActionStatus.EXECUTED.value,
                    created_at=p_time + timedelta(minutes=2)
                )
                db.add(action_investigate)

                if rc_status == RecoveryStatus.AWAITING_HUMAN_APPROVAL.value:
                    action_guardrail = AgentAction(
                        id=f"act_{uuid.uuid4().hex[:8]}",
                        recovery_case_id=rc.id,
                        agent_type=AgentType.TOOL_EXECUTOR.value,
                        action_type=ActionType.GUARDRAIL_CHECK.value,
                        reasoning_summary=f"High Value Guardrail Triggered: Payment ₹{p.amount:,.2f} exceeds ₹50,000 threshold. Escalate for human merchant authorization.",
                        status=ActionStatus.BLOCKED_BY_GUARDRAIL.value,
                        created_at=p_time + timedelta(minutes=4)
                    )
                    db.add(action_guardrail)
                elif rc_status in [RecoveryStatus.ACTION_IN_PROGRESS.value, RecoveryStatus.RECOVERED.value]:
                    action_strat = AgentAction(
                        id=f"act_{uuid.uuid4().hex[:8]}",
                        recovery_case_id=rc.id,
                        agent_type=AgentType.STRATEGIST.value,
                        action_type=ActionType.SELECT_STRATEGY.value,
                        reasoning_summary=f"Strategist deployed {rc.current_strategy} with channel {InteractionChannel.WHATSAPP.value}.",
                        status=ActionStatus.EXECUTED.value,
                        created_at=p_time + timedelta(minutes=3)
                    )
                    db.add(action_strat)

                    # Simulated message
                    inter = CustomerInteraction(
                        id=f"msg_{uuid.uuid4().hex[:8]}",
                        customer_id=cust.id,
                        recovery_case_id=rc.id,
                        channel=InteractionChannel.WHATSAPP.value,
                        direction=InteractionDirection.OUTBOUND.value,
                        message=f"Hi {cust.name}! Recover your payment of ₹{p.amount:,.2f} with 1-click UPI: {rc.payment_link_url}",
                        detected_intent=rc.customer_intent,
                        confidence=prob,
                        created_at=p_time + timedelta(minutes=5)
                    )
                    db.add(inter)

                    if rc_status == RecoveryStatus.RECOVERED.value:
                        action_rec = AgentAction(
                            id=f"act_{uuid.uuid4().hex[:8]}",
                            recovery_case_id=rc.id,
                            agent_type=AgentType.TOOL_EXECUTOR.value,
                            action_type=ActionType.PAYMENT_CONFIRMED.value,
                            reasoning_summary=f"Payment verified settled via Razorpay Webhook. Revenue recovered: ₹{p.amount:,.2f}.",
                            status=ActionStatus.EXECUTED.value,
                            created_at=p_time + timedelta(minutes=20)
                        )
                        db.add(action_rec)

        db.commit()
        print(f"[SEED] Seed completed successfully: {db.query(Customer).count()} customers, {db.query(Payment).count()} payments, {db.query(RecoveryCase).count()} recovery cases.")

    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] Seeding failed: {e}")
        raise e
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed_database()
