"""Add webhook_events table for durable Razorpay event processing

Revision ID: 002_webhook_events
Revises: 001_initial_schema
Create Date: 2026-10-14 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_webhook_events'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='razorpay'),
        sa.Column('provider_event_id', sa.String(length=120), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='RECEIVED'),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('internal_payment_id', sa.String(length=50), nullable=True),
        sa.Column('internal_case_id', sa.String(length=50), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('correlation_id', sa.String(length=100), nullable=True),
        sa.Column('processing_metadata_json', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['internal_case_id'], ['recovery_cases.id']),
        sa.ForeignKeyConstraint(['internal_payment_id'], ['payments.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhook_events_id'), 'webhook_events', ['id'], unique=False)
    op.create_index(op.f('ix_webhook_events_provider'), 'webhook_events', ['provider'], unique=False)
    op.create_index(op.f('ix_webhook_events_provider_event_id'), 'webhook_events', ['provider_event_id'], unique=True)
    op.create_index(op.f('ix_webhook_events_event_type'), 'webhook_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_webhook_events_status'), 'webhook_events', ['status'], unique=False)
    op.create_index(op.f('ix_webhook_events_entity_id'), 'webhook_events', ['entity_id'], unique=False)
    op.create_index(op.f('ix_webhook_events_internal_payment_id'), 'webhook_events', ['internal_payment_id'], unique=False)
    op.create_index(op.f('ix_webhook_events_internal_case_id'), 'webhook_events', ['internal_case_id'], unique=False)
    op.create_index(op.f('ix_webhook_events_next_retry_at'), 'webhook_events', ['next_retry_at'], unique=False)
    op.create_index(op.f('ix_webhook_events_correlation_id'), 'webhook_events', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_webhook_events_received_at'), 'webhook_events', ['received_at'], unique=False)
    op.create_index('idx_webhook_status_retry', 'webhook_events', ['status', 'next_retry_at'], unique=False)
    op.create_index('idx_webhook_type_received', 'webhook_events', ['event_type', 'received_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_webhook_type_received', table_name='webhook_events')
    op.drop_index('idx_webhook_status_retry', table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_received_at'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_correlation_id'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_next_retry_at'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_internal_case_id'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_internal_payment_id'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_entity_id'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_status'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_event_type'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_provider_event_id'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_provider'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_id'), table_name='webhook_events')
    op.drop_table('webhook_events')
