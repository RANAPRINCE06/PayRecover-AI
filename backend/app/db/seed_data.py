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
    InteractionDirection,
    User,
    UserRole,
    IdempotencyRecord,
    RecoveryOutcome,
    RecoveryOutcomeStatus,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeCategory,
    VerificationStatus
)
from app.services.intelligence_service import amount_to_range, normalize_strategy_name
from app.services.ingestion_service import ingestion_service


def seed_database(db: Session = None):
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        # Ensure default Phase 8 users exist
        _seed_default_users(db)

        # Check if already seeded
        if db.query(Customer).count() >= 30:
            print("[SEED] Database already contains sufficient seed data. Ensuring recovery outcomes and knowledge docs are synchronized.")
            _seed_recovery_outcomes(db)
            _seed_knowledge_documents(db)
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
        # Synchronize Recovery Outcomes for AI Intelligence Engine
        _seed_recovery_outcomes(db)
        print(f"[SEED] Seed completed successfully: {db.query(Customer).count()} customers, {db.query(Payment).count()} payments, {db.query(RecoveryCase).count()} recovery cases.")

    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] Seeding failed: {e}")
        raise e
    finally:
        if own_session:
            db.close()


def _seed_default_users(db: Session):
    """Seed the 4 default role-based accounts for Phase 8 testing and operation."""
    from app.models.entities import User, UserRole
    from app.core.auth import hash_password

    default_users = [
        {
            "id": "usr_admin_default",
            "email": "admin@payrecover.ai",
            "name": "Sarah Chen",
            "role": UserRole.ADMIN.value,
            "password": "Admin@123"
        },
        {
            "id": "usr_analyst_default",
            "email": "analyst@payrecover.ai",
            "name": "Dev Sharma",
            "role": UserRole.ANALYST.value,
            "password": "Analyst@123"
        },
        {
            "id": "usr_operator_default",
            "email": "operator@payrecover.ai",
            "name": "Priya Nair",
            "role": UserRole.OPERATOR.value,
            "password": "Operator@123"
        },
        {
            "id": "usr_viewer_default",
            "email": "viewer@payrecover.ai",
            "name": "Rohan Mehta",
            "role": UserRole.VIEWER.value,
            "password": "Viewer@123"
        }
    ]

    created_count = 0
    for u_data in default_users:
        existing = db.query(User).filter(User.email == u_data["email"]).first()
        if not existing:
            u = User(
                id=u_data["id"],
                email=u_data["email"],
                name=u_data["name"],
                role=u_data["role"],
                hashed_password=hash_password(u_data["password"]),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(u)
            created_count += 1
    if created_count > 0:
        db.commit()
        print(f"[SEED] Created {created_count} default system users.")


def _seed_recovery_outcomes(db: Session):
    """
    Ensure every historical RecoveryCase has a corresponding, verified RecoveryOutcome record.
    Prevents duplicate outcome records and preserves authoritative payment status labels.
    """
    cases = db.query(RecoveryCase).all()
    count = 0
    for c in cases:
        existing = db.query(RecoveryOutcome).filter(RecoveryOutcome.recovery_case_id == c.id).first()
        if not existing and c.payment:
            p = c.payment
            is_rec = (c.status == RecoveryStatus.RECOVERED.value and p.status in [PaymentStatus.RECOVERED.value, PaymentStatus.SUCCESS.value])
            is_unsuccessful = (c.status in [RecoveryStatus.FAILED.value, RecoveryStatus.EXPIRED.value] or p.status == PaymentStatus.ABANDONED.value)
            
            dec_time = c.started_at or (p.created_at + timedelta(minutes=2))
            comp_time = c.completed_at or (dec_time + timedelta(minutes=22)) if is_rec else (
                (dec_time + timedelta(hours=24)) if is_unsuccessful else None
            )

            if is_rec:
                status_val = RecoveryOutcomeStatus.RECOVERED.value
                rec_amt = float(c.recovered_amount or p.amount)
                verified = True
                verif_src = "razorpay_webhook:payment.captured"
                ttr = max(60.0, (comp_time - dec_time).total_seconds()) if comp_time else 1320.0
            elif is_unsuccessful:
                status_val = RecoveryOutcomeStatus.UNSUCCESSFUL.value
                rec_amt = 0.0
                verified = True
                verif_src = "payment_workflow:retries_exhausted"
                ttr = None
            else:
                status_val = RecoveryOutcomeStatus.PENDING.value
                rec_amt = 0.0
                verified = False
                verif_src = None
                ttr = None

            strat_name = normalize_strategy_name(c.current_strategy or "PAYMENT_LINK")

            outcome = RecoveryOutcome(
                id=f"out_{uuid.uuid4().hex[:12]}",
                recovery_case_id=c.id,
                payment_id=p.id,
                customer_id=p.customer_id,
                failure_category=p.failure_reason or "UNKNOWN",
                payment_method=p.payment_method,
                amount=float(p.amount),
                amount_range=amount_to_range(float(p.amount)),
                customer_intent=c.customer_intent,
                selected_strategy=strat_name,
                communication_channel="WHATSAPP",
                retry_count=c.retry_count or 0,
                discount_offered_percent=0.0,
                human_approval_required=(p.amount >= 50000.0),
                processing_latency_ms=random.randint(110, 420),
                outcome_status=status_val,
                recovered_amount=rec_amt,
                is_verified=verified,
                verification_source=verif_src,
                time_to_recovery_seconds=ttr,
                decision_timestamp=dec_time,
                outcome_timestamp=comp_time,
                created_at=dec_time,
                updated_at=comp_time or dec_time
            )
            db.add(outcome)
            count += 1

    if count > 0:
        db.commit()
        print(f"[SEED] Synchronized {count} RecoveryOutcome records for AI Intelligence Engine.")


def _seed_knowledge_documents(db: Session):
    """
    Seeds initial enterprise knowledge base across 4 categories:
    MERCHANT_POLICY, FAILURE_KNOWLEDGE, RECOVERY_PLAYBOOK, HISTORICAL_INSIGHT.
    Uses DocumentIngestionService to generate chunks and embeddings.
    """
    docs_to_seed = [
        {
            "custom_id": "doc_policy_bharattech",
            "title": "BharatTech Merchant Recovery Policy & Guardrails",
            "category": KnowledgeCategory.MERCHANT_POLICY.value,
            "source_type": "POLICY",
            "source_reference": "merchant_ops_manual_v2.4",
            "merchant_id": "merchant_primary",
            "verification_status": VerificationStatus.VERIFIED.value,
            "raw_content": """# BharatTech Commerce Recovery Policy

## Communication Channel Rules
BharatTech authorizes WhatsApp as the primary recovery channel for standard transactions under ₹50,000. Email is approved as a secondary notification channel for order confirmation and high-value recovery cases. SMS is designated strictly as an emergency fallback. Voice calls are explicitly prohibited unless requested by the customer.

## Retry Timing and Limits
Automated payment retries must not exceed 3 attempts per recovery case. Retries must enforce an exponential backoff schedule with a mandatory minimum 4-hour delay between automated execution attempts. Immediate synchronous retries on card declines are prohibited.

## Discount and Incentive Limits
Promotional conversion incentives are capped at a maximum of 10% discount. Discounts may only be offered for checkout abandonment cases where customer intent exhibits price sensitivity. Under no circumstances may discounts be applied to transactions exceeding ₹50,000 or to subscription renewal payments.

## High-Value Escalation and Human Review
Any recovery case with transaction amount equal to or exceeding ₹50,000 is classified as high-value. Automated tool execution is blocked until explicit human approval is granted by an authorized merchant operator or admin. The recovery status must remain AWAITING_HUMAN_APPROVAL until approved.

## Quiet Hours Enforcement
Merchant quiet hours are strictly enforced between 22:00 IST and 08:00 IST. No outbound customer messages or push notifications may be dispatched during quiet hours. Scheduled recovery actions must be delayed until the quiet hours window closes at 08:00 IST."""
        },
        {
            "custom_id": "doc_fail_gateway",
            "title": "Payment Gateway Failure Troubleshooting & Recovery Guide",
            "category": KnowledgeCategory.FAILURE_KNOWLEDGE.value,
            "source_type": "FAILURE_GUIDE",
            "source_reference": "gateway_engineering_spec_v3",
            "merchant_id": None,  # Global platform knowledge
            "verification_status": VerificationStatus.VERIFIED.value,
            "raw_content": """# Payment Gateway Failure Troubleshooting

## UPI Latency and Timeout Handling
UPI timeouts occur when NPCI switch processing exceeds bank response thresholds (typically 30 seconds), or when customer UPI apps fail to prompt. Immediate re-attempts against the same VPA have a 78% failure rate during active bank degraded performance. The optimal strategy is waiting 15 minutes before dispatching an instant pre-filled UPI payment link (rzp.io) via WhatsApp.

## Card Decline Root Causes
Card declines fall into three distinct sub-categories:
1. Do Not Honor (bank block / fraud filter): Issuing bank has blocked the card. Direct retries against the same card will consistently fail and risk blacklisting. The mandatory remedy is offering an alternate payment method (UPI, NetBanking, or alternate card).
2. Insufficient Funds: The cardholder balance is inadequate. Retrying within 24 hours has a dismal 12% recovery rate. Schedule a gentle follow-up reminder after payday or provide a payment link valid for 72 hours.
3. 3DS Authentication Failure: OTP expired or mobile network drop. The customer had purchase intent. An instant payment link sent via WhatsApp recovers over 85% of these transactions within 10 minutes.

## Bank Core Server Downtime
Gateway HTTP 504 and Bank Server Down errors indicate transient outages at the acquiring or issuing bank. The recommended action is delaying automated retries by 30 to 45 minutes or routing through an alternate gateway route if available."""
        },
        {
            "custom_id": "doc_play_recovery",
            "title": "Autonomous Revenue Recovery Playbooks & Stop Conditions",
            "category": KnowledgeCategory.RECOVERY_PLAYBOOK.value,
            "source_type": "PLAYBOOK",
            "source_reference": "playrecover_playbooks_v1.8",
            "merchant_id": None,  # Global platform knowledge
            "verification_status": VerificationStatus.VERIFIED.value,
            "raw_content": """# Autonomous Revenue Recovery Playbooks

## Playbook 1: Card Decline to UPI Instant Link
When a customer experiences a card decline (either 3DS failure or temporary decline) and customer intent indicates ongoing purchase interest, the autonomous engine must generate a pre-filled Razorpay UPI payment link. The link should be dispatched via WhatsApp with an informative, helpful notification explaining that the card was declined by their bank.

## Playbook 2: High-Value Recovery Workflow
For transactions exceeding the merchant high-value threshold (₹50,000), the engine must NOT auto-dispatch payment links or retries. Instead, it creates a pending HumanApproval record, notifies the merchant operator console, and prepares a tailored high-touch communication draft.

## Playbook 3: Checkout Abandonment Incentive Playbook
When telemetry indicates checkout abandonment with hesitation, and customer profile reflects high lifetime value (VIP or HIGH_VALUE), the engine is authorized to formulate an INCENTIVE strategy offering up to 10% discount to secure immediate conversion.

## Playbook 4: Stop Recovery Conditions
Recovery must immediately cease under any of the following stop conditions:
1. Customer explicitly indicates cancellation, lack of interest, or requests not to be contacted.
2. Payment state verification confirms the order was already paid or captured through another session.
3. Maximum retry count (3 attempts) has been exhausted.
4. Suspected fraudulent activity or chargeback threat reported."""
        },
        {
            "custom_id": "doc_hist_insights",
            "title": "Empirical Recovery Outcomes & Conversion Benchmarks",
            "category": KnowledgeCategory.HISTORICAL_INSIGHT.value,
            "source_type": "HISTORICAL_REPORT",
            "source_reference": "payrecover_quarterly_intelligence_q3",
            "merchant_id": "merchant_primary",
            "verification_status": VerificationStatus.VERIFIED.value,
            "raw_content": """# Verified Recovery Outcomes & Intelligence Benchmarks

## Payment Method Recovery Rates
Analysis of historical recovery cases demonstrates:
- Card-to-UPI switch strategies achieve an empirical 92.3% recovery rate (n=65, 95% Wilson CI: [83.2%, 96.7%]).
- Direct payment retries for insufficient funds achieve only 11.8% success (n=34), while offering a payment link with flexible timing increases conversion to 64.7%.
- Immediate UPI retries after timeout fail in 78.4% of cases; introducing a 15-minute buffer increases recovery to 88.1%.

## Communication Channel Effectiveness
- WhatsApp messages dispatched within 15 minutes of payment failure achieve a 71.4% click-through rate and 62.8% settlement within 2 hours.
- Email recovery notices achieve a 22.1% open rate and 18.5% recovery rate over 24 hours.
- SMS notifications show diminishing returns with a 9.2% recovery rate.

## Recovery Latency Benchmarks
The median time-to-recovery (TTR) for successful automated recovery is 18.4 minutes. Cases resolved within 30 minutes account for 84% of total recovered revenue."""
        }
    ]

    indexed_count = 0
    for doc_data in docs_to_seed:
        existing = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == doc_data["custom_id"]
        ).first()
        if not existing:
            ingestion_service.ingest_document(
                db=db,
                title=doc_data["title"],
                category=doc_data["category"],
                source_type=doc_data["source_type"],
                source_reference=doc_data["source_reference"],
                raw_content=doc_data["raw_content"],
                merchant_id=doc_data["merchant_id"],
                verification_status=doc_data["verification_status"],
                custom_id=doc_data["custom_id"]
            )
            indexed_count += 1

    if indexed_count > 0:
        print(f"[SEED] Ingested and indexed {indexed_count} initial RAG knowledge documents.")


def reset_demo_data(db: Session = None):
    """
    Cleans up simulated demo cases and resets merchant guardrails to default baseline.
    Ensures seed customers and system users remain intact.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        # 1. Delete simulated actions, approvals, and cases
        sim_cases = db.query(RecoveryCase).filter(
            (RecoveryCase.id.like("rc_sim_%")) | (RecoveryCase.id.like("rc_sample_%"))
        ).all()
        sim_case_ids = [c.id for c in sim_cases]

        if sim_case_ids:
            db.query(AgentAction).filter(AgentAction.recovery_case_id.in_(sim_case_ids)).delete(synchronize_session=False)
            db.query(CustomerInteraction).filter(CustomerInteraction.recovery_case_id.in_(sim_case_ids)).delete(synchronize_session=False)
            for c in sim_cases:
                db.delete(c)

        # 2. Delete simulated payments
        sim_payments = db.query(Payment).filter(
            (Payment.id.like("pay_sim_%")) | (Payment.id.like("pay_sample_%"))
        ).all()
        for p in sim_payments:
            db.delete(p)

        # 3. Reset merchant guardrails
        guardrail = db.query(MerchantGuardrail).filter(MerchantGuardrail.merchant_id == "merchant_primary").first()
        if guardrail:
            guardrail.max_retries = 3
            guardrail.max_discount_percentage = 10.0
            guardrail.max_campaign_days = 3
            guardrail.quiet_hours_start = "22:00"
            guardrail.quiet_hours_end = "08:00"
            guardrail.high_value_threshold = 50000.0
            guardrail.human_approval_required = True
            guardrail.max_contact_attempts = 4

        # 4. Ensure default users exist
        _seed_default_users(db)

        db.commit()
        return {
            "status": "SUCCESS",
            "message": "Demo data and simulations reset successfully.",
            "cleared_cases": len(sim_cases),
            "cleared_payments": len(sim_payments)
        }
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed_database()

