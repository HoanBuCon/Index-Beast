"""Add messages.rag_trace: RAG trace kept apart from messages.trace so loading history does not read it."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("rag_trace", postgresql.JSONB()))


def downgrade():
    op.drop_column("messages", "rag_trace")
