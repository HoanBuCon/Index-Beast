"""Add durable working state and scoped semantic memory; preserve existing chat tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversation_runtime",
        sa.Column(
            "conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "conversation_memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("key", sa.Text()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("indexed_revision", sa.Integer(), nullable=False),
        sa.Column("index_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_memories_scope_status", "conversation_memories", ["conversation_id", "status"])


def downgrade():
    op.drop_table("conversation_memories")
    op.drop_table("conversation_runtime")
