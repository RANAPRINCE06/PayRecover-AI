"""Add knowledge_documents and knowledge_chunks tables for Phase 5 RAG Knowledge Engine

Revision ID: 004_knowledge_rag
Revises: 003_recovery_outcomes
Create Date: 2026-10-24 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_knowledge_rag'
down_revision: Union[str, None] = '003_recovery_outcomes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create knowledge_documents table
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_reference', sa.String(length=255), nullable=False),
        sa.Column('merchant_id', sa.String(length=50), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('verification_status', sa.String(length=50), nullable=False, server_default='VERIFIED'),
        sa.Column('effective_date', sa.DateTime(), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=False),
        sa.Column('doc_metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_kdoc_cat_verif', 'knowledge_documents', ['category', 'verification_status'], unique=False)
    op.create_index('idx_kdoc_merchant_cat', 'knowledge_documents', ['merchant_id', 'category'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_category'), 'knowledge_documents', ['category'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_content_hash'), 'knowledge_documents', ['content_hash'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_id'), 'knowledge_documents', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_merchant_id'), 'knowledge_documents', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_source_type'), 'knowledge_documents', ['source_type'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_verification_status'), 'knowledge_documents', ['verification_status'], unique=False)

    # 2. Create knowledge_chunks table
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('document_id', sa.String(length=50), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('heading', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('embedding_json', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_kchunk_doc_index', 'knowledge_chunks', ['document_id', 'chunk_index'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_document_id'), 'knowledge_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_id'), 'knowledge_chunks', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_knowledge_chunks_id'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_document_id'), table_name='knowledge_chunks')
    op.drop_index('idx_kchunk_doc_index', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')

    op.drop_index(op.f('ix_knowledge_documents_verification_status'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_source_type'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_merchant_id'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_id'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_content_hash'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_category'), table_name='knowledge_documents')
    op.drop_index('idx_kdoc_merchant_cat', table_name='knowledge_documents')
    op.drop_index('idx_kdoc_cat_verif', table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
