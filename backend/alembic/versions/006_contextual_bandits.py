"""Add bandit_policy_configs and bandit_shadow_decisions tables for Phase 7

Revision ID: 006_contextual_bandits
Revises: 005_recovery_experiments
Create Date: 2026-10-25 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_contextual_bandits'
down_revision: Union[str, None] = '005_recovery_experiments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create bandit_policy_configs table
    op.create_table(
        'bandit_policy_configs',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('merchant_id', sa.String(length=50), nullable=False),
        sa.Column('policy_name', sa.String(length=100), nullable=False),
        sa.Column('policy_type', sa.String(length=50), nullable=False, server_default='LINUCB'),
        sa.Column('version', sa.String(length=20), nullable=False, server_default='v1.0'),
        sa.Column('feature_schema_version', sa.String(length=20), nullable=False, server_default='v1.0'),
        sa.Column('is_shadow_mode', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('alpha_exploration', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('ridge_lambda', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('min_sample_threshold', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('evaluation_summary_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bandit_policy_configs_id'), 'bandit_policy_configs', ['id'], unique=False)
    op.create_index(op.f('ix_bandit_policy_configs_merchant_id'), 'bandit_policy_configs', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_bandit_policy_configs_version'), 'bandit_policy_configs', ['version'], unique=False)

    # 2. Create bandit_shadow_decisions table
    op.create_table(
        'bandit_shadow_decisions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('policy_id', sa.String(length=50), nullable=True),
        sa.Column('policy_version', sa.String(length=20), nullable=False, server_default='v1.0'),
        sa.Column('context_schema_version', sa.String(length=20), nullable=False, server_default='v1.0'),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('payment_id', sa.String(length=50), nullable=False),
        sa.Column('merchant_id', sa.String(length=50), nullable=False),
        sa.Column('eligible_actions_json', sa.Text(), nullable=False),
        sa.Column('selected_action', sa.String(length=100), nullable=False),
        sa.Column('selection_reason', sa.Text(), nullable=False),
        sa.Column('predicted_reward', sa.Float(), nullable=False),
        sa.Column('confidence_width', sa.Float(), nullable=False),
        sa.Column('feature_vector_json', sa.Text(), nullable=False),
        sa.Column('feature_attributions_json', sa.Text(), nullable=True),
        sa.Column('production_strategy', sa.String(length=100), nullable=False),
        sa.Column('is_agreement', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('guardrail_evaluation_json', sa.Text(), nullable=True),
        sa.Column('eventual_outcome', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('actual_reward', sa.Float(), nullable=True),
        sa.Column('decision_timestamp', sa.DateTime(), nullable=False),
        sa.Column('outcome_timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['bandit_policy_configs.id']),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bandit_shadow_decisions_id'), 'bandit_shadow_decisions', ['id'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_merchant_id'), 'bandit_shadow_decisions', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_payment_id'), 'bandit_shadow_decisions', ['payment_id'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_policy_id'), 'bandit_shadow_decisions', ['policy_id'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_policy_version'), 'bandit_shadow_decisions', ['policy_version'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_recovery_case_id'), 'bandit_shadow_decisions', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_eventual_outcome'), 'bandit_shadow_decisions', ['eventual_outcome'], unique=False)
    op.create_index(op.f('ix_bandit_shadow_decisions_is_agreement'), 'bandit_shadow_decisions', ['is_agreement'], unique=False)
    op.create_index('idx_shadow_policy_decision', 'bandit_shadow_decisions', ['policy_version', 'decision_timestamp'], unique=False)
    op.create_index('idx_shadow_case_agreement', 'bandit_shadow_decisions', ['recovery_case_id', 'is_agreement'], unique=False)


def downgrade() -> None:
    op.drop_table('bandit_shadow_decisions')
    op.drop_table('bandit_policy_configs')
