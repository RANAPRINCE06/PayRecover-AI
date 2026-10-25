"""Add recovery_experiments, experiment_assignments, and experiment_outcome_attributions tables for Phase 6

Revision ID: 005_recovery_experiments
Revises: 004_knowledge_rag
Create Date: 2026-10-25 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_recovery_experiments'
down_revision: Union[str, None] = '004_knowledge_rag'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create recovery_experiments table
    op.create_table(
        'recovery_experiments',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('merchant_id', sa.String(length=50), nullable=True),
        sa.Column('owner_email', sa.String(length=150), nullable=False),
        sa.Column('primary_metric', sa.String(length=50), nullable=False, server_default='recovery_rate'),
        sa.Column('is_sandbox_only', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('target_failure_categories_json', sa.Text(), nullable=True),
        sa.Column('target_payment_methods_json', sa.Text(), nullable=True),
        sa.Column('min_amount', sa.Float(), nullable=True),
        sa.Column('max_amount', sa.Float(), nullable=True),
        sa.Column('target_customer_intent_json', sa.Text(), nullable=True),
        sa.Column('candidate_strategies_json', sa.Text(), nullable=False),
        sa.Column('max_sample_size', sa.Integer(), nullable=True),
        sa.Column('min_observation_count', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_exp_status_merchant', 'recovery_experiments', ['status', 'merchant_id'], unique=False)
    op.create_index('idx_exp_status_created', 'recovery_experiments', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_recovery_experiments_id'), 'recovery_experiments', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_experiments_merchant_id'), 'recovery_experiments', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_recovery_experiments_status'), 'recovery_experiments', ['status'], unique=False)

    # 2. Create experiment_assignments table
    op.create_table(
        'experiment_assignments',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('experiment_id', sa.String(length=50), nullable=False),
        sa.Column('experiment_version', sa.Integer(), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('payment_id', sa.String(length=50), nullable=False),
        sa.Column('arm_id', sa.String(length=50), nullable=False),
        sa.Column('assigned_strategy', sa.String(length=100), nullable=False),
        sa.Column('is_control', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('hash_bucket', sa.Integer(), nullable=False),
        sa.Column('assignment_salt', sa.String(length=50), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('eligibility_snapshot_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['recovery_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id', 'recovery_case_id', name='uq_exp_case_assignment')
    )
    op.create_index('idx_exp_assign_arm', 'experiment_assignments', ['experiment_id', 'arm_id'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_arm_id'), 'experiment_assignments', ['arm_id'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_assigned_at'), 'experiment_assignments', ['assigned_at'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_assigned_strategy'), 'experiment_assignments', ['assigned_strategy'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_experiment_id'), 'experiment_assignments', ['experiment_id'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_id'), 'experiment_assignments', ['id'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_payment_id'), 'experiment_assignments', ['payment_id'], unique=False)
    op.create_index(op.f('ix_experiment_assignments_recovery_case_id'), 'experiment_assignments', ['recovery_case_id'], unique=False)

    # 3. Create experiment_outcome_attributions table
    op.create_table(
        'experiment_outcome_attributions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('assignment_id', sa.String(length=50), nullable=False),
        sa.Column('experiment_id', sa.String(length=50), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=50), nullable=False),
        sa.Column('payment_id', sa.String(length=50), nullable=False),
        sa.Column('arm_id', sa.String(length=50), nullable=False),
        sa.Column('assigned_strategy', sa.String(length=100), nullable=False),
        sa.Column('actual_executed_strategy', sa.String(length=100), nullable=False),
        sa.Column('is_strategy_deviated', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('deviation_reason', sa.String(length=255), nullable=True),
        sa.Column('outcome_status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('recovered_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('discount_offered', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('human_escalated', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('time_to_recovery_seconds', sa.Float(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('attributed_at', sa.DateTime(), nullable=True),
        sa.Column('verification_source', sa.String(length=150), nullable=True),
        sa.Column('attribution_window_valid', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['experiment_assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['experiment_id'], ['recovery_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assignment_id')
    )
    op.create_index('idx_att_exp_arm_outcome', 'experiment_outcome_attributions', ['experiment_id', 'arm_id', 'outcome_status'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_arm_id'), 'experiment_outcome_attributions', ['arm_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_assignment_id'), 'experiment_outcome_attributions', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_experiment_id'), 'experiment_outcome_attributions', ['experiment_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_id'), 'experiment_outcome_attributions', ['id'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_outcome_status'), 'experiment_outcome_attributions', ['outcome_status'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_payment_id'), 'experiment_outcome_attributions', ['payment_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcome_attributions_recovery_case_id'), 'experiment_outcome_attributions', ['recovery_case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_experiment_outcome_attributions_recovery_case_id'), table_name='experiment_outcome_attributions')
    op.drop_index(op.f('ix_experiment_outcome_attributions_payment_id'), table_name='experiment_outcome_attributions')
    op.drop_index(op.f('ix_experiment_outcome_attributions_outcome_status'), table_name='experiment_outcome_attributions')
    op.drop_index(op.f('ix_experiment_outcome_attributions_id'), table_name='experiment_outcome_attributions')
    op.drop_index(op.f('ix_experiment_outcome_attributions_experiment_id'), table_name='experiment_outcome_attributions')
    op.drop_index(op.f('ix_experiment_outcome_attributions_assignment_id'), table_name='experiment_outcome_attributions')
    op.drop_index(op.f('ix_experiment_outcome_attributions_arm_id'), table_name='experiment_outcome_attributions')
    op.drop_index('idx_att_exp_arm_outcome', table_name='experiment_outcome_attributions')
    op.drop_table('experiment_outcome_attributions')

    op.drop_index(op.f('ix_experiment_assignments_recovery_case_id'), table_name='experiment_assignments')
    op.drop_index(op.f('ix_experiment_assignments_payment_id'), table_name='experiment_assignments')
    op.drop_index(op.f('ix_experiment_assignments_id'), table_name='experiment_assignments')
    op.drop_index(op.f('ix_experiment_assignments_experiment_id'), table_name='experiment_assignments')
    op.drop_index(op.f('ix_experiment_assignments_assigned_strategy'), table_name='experiment_assignments')
    op.drop_index(op.f('ix_experiment_assignments_assigned_at'), table_name='experiment_assignments')
    op.drop_index(op.f('ix_experiment_assignments_arm_id'), table_name='experiment_assignments')
    op.drop_index('idx_exp_assign_arm', table_name='experiment_assignments')
    op.drop_table('experiment_assignments')

    op.drop_index(op.f('ix_recovery_experiments_status'), table_name='recovery_experiments')
    op.drop_index(op.f('ix_recovery_experiments_merchant_id'), table_name='recovery_experiments')
    op.drop_index(op.f('ix_recovery_experiments_id'), table_name='recovery_experiments')
    op.drop_index('idx_exp_status_created', table_name='recovery_experiments')
    op.drop_index('idx_exp_status_merchant', table_name='recovery_experiments')
    op.drop_table('recovery_experiments')
