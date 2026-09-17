"""add knowledge base tables

Revision ID: a33f0d420da5
Revises: 79d5c9dc732d
Create Date: 2026-09-17 15:31:08.785434

"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a33f0d420da5'
down_revision: Union[str, Sequence[str], None] = '79d5c9dc732d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('knowledge_documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('source', sa.String(length=300), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_knowledge_documents_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_documents')),
    sa.UniqueConstraint('id', 'organization_id', name=op.f('uq_knowledge_documents_id')),
    sa.UniqueConstraint('organization_id', 'source', name=op.f('uq_knowledge_documents_organization_id'))
    )
    op.create_table('knowledge_chunks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('heading', sa.String(length=300), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', heading || ' ' || content)", persisted=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id', 'organization_id'], ['knowledge_documents.id', 'knowledge_documents.organization_id'], name=op.f('fk_knowledge_chunks_document_id_knowledge_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_knowledge_chunks_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_chunks'))
    )
    op.create_index('ix_knowledge_chunks_embedding', 'knowledge_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_knowledge_chunks_org_document', 'knowledge_chunks', ['organization_id', 'document_id'], unique=False)
    op.create_index('ix_knowledge_chunks_search_vector', 'knowledge_chunks', ['search_vector'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_knowledge_chunks_search_vector', table_name='knowledge_chunks', postgresql_using='gin')
    op.drop_index('ix_knowledge_chunks_org_document', table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_embedding', table_name='knowledge_chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')