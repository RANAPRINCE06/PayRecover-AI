"""Add recovery_outcomes table for Phase 4 AI Recovery Intelligence Engine

Revision ID: 003_recovery_outcomes
Revises: 002_webhook_events
Create Date: 2026-10-17 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_recovery_outcomes'
down_revision: Union[str, None] = '002_webhook_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recovery_outcomes',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('payment_id', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('failure_category', sa.String(length=100), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('amount_range', sa.String(length=50), nullable=False),
        sa.Column('customer_intent', sa.String(length=100), nullable=True),
        sa.Column('selected_strategy', sa.String(length=100), nullable=False),
        sa.Column('communication_channel', sa.String(length=50), nullable=False, server_default='WHATSAPP'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('discount_offered_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('human_approval_required', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('processing_latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('outcome_status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('recovered_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('verification_source', sa.String(length=150), nullable=True),
        sa.Column('time_to_recovery_seconds', sa.Float(), nullable=True),
        sa.Column('decision_timestamp', sa.DateTime(), nullable=False),
        sa.Column('outcome_timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recovery_case_id')
    )
    op.create_index(op.f('ix_recovery_outcomes_id'), 'recovery_outcomes', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_recovery_case_id'), 'recovery_outcomes', ['recovery_case_id'], unique=True)
    op.create_index(op.f('ix_recovery_outcomes_payment_id'), 'recovery_outcomes', ['payment_id'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_customer_id'), 'recovery_outcomes', ['customer_id'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_failure_category'), 'recovery_outcomes', ['failure_category'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_payment_method'), 'recovery_outcomes', ['payment_method'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_amount_range'), 'recovery_outcomes', ['amount_range'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_customer_intent'), 'recovery_outcomes', ['customer_intent'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_selected_strategy'), 'recovery_outcomes', ['selected_strategy'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_outcome_status'), 'recovery_outcomes', ['outcome_status'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_decision_timestamp'), 'recovery_outcomes', ['decision_timestamp'], unique=False)
    op.create_index(op.f('ix_recovery_outcomes_outcome_timestamp'), 'recovery_outcomes', ['outcome_timestamp'], unique=False)
    op.create_index('idx_outcome_status_decision', 'recovery_outcomes', ['outcome_status', 'decision_timestamp'], unique=False)
    op.create_index('idx_outcome_strategy_failure', 'recovery_outcomes', ['selected_strategy', 'failure_category'], unique=False)
    op.create_index('idx_outcome_method_amount', 'recovery_outcomes', ['payment_method', 'amount_range'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_outcome_method_amount', table_name='recovery_outcomes')
    op.drop_index('idx_outcome_strategy_failure', table_name='recovery_outcomes')
    op.drop_index('idx_outcome_status_decision', table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_outcome_timestamp'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_decision_timestamp'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_outcome_status'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_selected_strategy'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_customer_intent'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_amount_range'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_payment_method'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_failure_category'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_customer_id'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_payment_id'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_recovery_case_id'), table_name='recovery_outcomes')
    op.drop_index(op.f('ix_recovery_outcomes_id'), table_name='recovery_outcomes')
    op.drop_table('recovery_outcomes')
