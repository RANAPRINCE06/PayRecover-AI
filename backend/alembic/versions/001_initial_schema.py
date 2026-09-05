"""Initial schema for PayRecover AI (11 entities)

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-05 18:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. merchants
    op.create_table(
        'merchants',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_merchants_id'), 'merchants', ['id'], unique=False)
    op.create_index(op.f('ix_merchants_email'), 'merchants', ['email'], unique=True)

    # 2. customers
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('customer_value', sa.String(length=50), nullable=True),
        sa.Column('preferred_payment_method', sa.String(length=50), nullable=True),
        sa.Column('total_successful_payments', sa.Integer(), nullable=True),
        sa.Column('total_failed_payments', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_id'), 'customers', ['id'], unique=False)
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=True)

    # 3. payments
    op.create_table(
        'payments',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('razorpay_payment_id', sa.String(length=100), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('failure_reason', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index(op.f('ix_payments_razorpay_payment_id'), 'payments', ['razorpay_payment_id'], unique=True)
    op.create_index(op.f('ix_payments_customer_id'), 'payments', ['customer_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_failure_reason'), 'payments', ['failure_reason'], unique=False)
    op.create_index(op.f('ix_payments_created_at'), 'payments', ['created_at'], unique=False)
    op.create_index('idx_payment_status_created', 'payments', ['status', 'created_at'], unique=False)
    op.create_index('idx_payment_customer_created', 'payments', ['customer_id', 'created_at'], unique=False)

    # 4. recovery_cases
    op.create_table(
        'recovery_cases',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('payment_id', sa.String(length=50), nullable=False),
        sa.Column('recovery_score', sa.Float(), nullable=True),
        sa.Column('recovery_probability', sa.Float(), nullable=True),
        sa.Column('customer_intent', sa.String(length=100), nullable=True),
        sa.Column('current_strategy', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('recovered_amount', sa.Float(), nullable=True),
        sa.Column('payment_link_url', sa.String(length=255), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_cases_id'), 'recovery_cases', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_cases_payment_id'), 'recovery_cases', ['payment_id'], unique=True)
    op.create_index(op.f('ix_recovery_cases_status'), 'recovery_cases', ['status'], unique=False)
    op.create_index('idx_case_status_started', 'recovery_cases', ['status', 'started_at'], unique=False)
    op.create_index('idx_case_score', 'recovery_cases', ['recovery_score'], unique=False)

    # 5. agent_actions
    op.create_table(
        'agent_actions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('reasoning_summary', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('action_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_actions_id'), 'agent_actions', ['id'], unique=False)
    op.create_index(op.f('ix_agent_actions_recovery_case_id'), 'agent_actions', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_agent_actions_status'), 'agent_actions', ['status'], unique=False)
    op.create_index(op.f('ix_agent_actions_created_at'), 'agent_actions', ['created_at'], unique=False)
    op.create_index('idx_action_case_created', 'agent_actions', ['recovery_case_id', 'created_at'], unique=False)

    # 6. merchant_guardrails
    op.create_table(
        'merchant_guardrails',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('merchant_id', sa.String(length=50), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=True),
        sa.Column('max_discount_percentage', sa.Float(), nullable=True),
        sa.Column('max_campaign_days', sa.Integer(), nullable=True),
        sa.Column('quiet_hours_start', sa.String(length=10), nullable=True),
        sa.Column('quiet_hours_end', sa.String(length=10), nullable=True),
        sa.Column('high_value_threshold', sa.Float(), nullable=True),
        sa.Column('human_approval_required', sa.Boolean(), nullable=True),
        sa.Column('max_contact_attempts', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('merchant_id')
    )
    op.create_index(op.f('ix_merchant_guardrails_id'), 'merchant_guardrails', ['id'], unique=False)

    # 7. customer_interactions
    op.create_table(
        'customer_interactions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=True),
        sa.Column('channel', sa.String(length=50), nullable=True),
        sa.Column('direction', sa.String(length=50), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('detected_intent', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_interactions_id'), 'customer_interactions', ['id'], unique=False)
    op.create_index(op.f('ix_customer_interactions_customer_id'), 'customer_interactions', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_interactions_recovery_case_id'), 'customer_interactions', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_customer_interactions_created_at'), 'customer_interactions', ['created_at'], unique=False)

    # 8. tool_executions
    op.create_table(
        'tool_executions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('execution_id', sa.String(length=100), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('payment_id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('tool_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('provider_reference', sa.String(length=100), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tool_executions_id'), 'tool_executions', ['id'], unique=False)
    op.create_index(op.f('ix_tool_executions_execution_id'), 'tool_executions', ['execution_id'], unique=True)
    op.create_index(op.f('ix_tool_executions_recovery_case_id'), 'tool_executions', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_tool_executions_payment_id'), 'tool_executions', ['payment_id'], unique=False)
    op.create_index(op.f('ix_tool_executions_customer_id'), 'tool_executions', ['customer_id'], unique=False)
    op.create_index(op.f('ix_tool_executions_tool_type'), 'tool_executions', ['tool_type'], unique=False)
    op.create_index(op.f('ix_tool_executions_status'), 'tool_executions', ['status'], unique=False)
    op.create_index(op.f('ix_tool_executions_idempotency_key'), 'tool_executions', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_tool_executions_created_at'), 'tool_executions', ['created_at'], unique=False)

    # 9. human_approvals
    op.create_table(
        'human_approvals',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('execution_id', sa.String(length=100), nullable=True),
        sa.Column('tool_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_human_approvals_id'), 'human_approvals', ['id'], unique=False)
    op.create_index(op.f('ix_human_approvals_recovery_case_id'), 'human_approvals', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_human_approvals_execution_id'), 'human_approvals', ['execution_id'], unique=False)
    op.create_index(op.f('ix_human_approvals_status'), 'human_approvals', ['status'], unique=False)

    # 10. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('merchant_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_merchant_id'), 'users', ['merchant_id'], unique=False)

    # 11. idempotency_records
    op.create_table(
        'idempotency_records',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('key', sa.String(length=120), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_idempotency_records_id'), 'idempotency_records', ['id'], unique=False)
    op.create_index(op.f('ix_idempotency_records_key'), 'idempotency_records', ['key'], unique=True)
    op.create_index(op.f('ix_idempotency_records_recovery_case_id'), 'idempotency_records', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_idempotency_records_created_at'), 'idempotency_records', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('idempotency_records')
    op.drop_table('users')
    op.drop_table('human_approvals')
    op.drop_table('tool_executions')
    op.drop_table('customer_interactions')
    op.drop_table('merchant_guardrails')
    op.drop_table('agent_actions')
    op.drop_table('recovery_cases')
    op.drop_table('payments')
    op.drop_table('customers')
    op.drop_table('merchants')
