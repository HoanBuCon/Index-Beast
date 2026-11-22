"""Add discord_guild_channels (kênh bot tự trả lời, `/setup`) and an index on conversations.guild_id.

conversations.guild_id đã có từ 0001 nhưng chưa được ghi; hội thoại tạo trước bản này vẫn NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discord_guild_channels",
        sa.Column("guild_id", sa.Text(), nullable=False),
        sa.Column("channel_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("guild_id", "channel_id", name=op.f("pk_discord_guild_channels")),
    )
    op.create_index("ix_conversations_guild_id", "conversations", ["guild_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_conversations_guild_id", table_name="conversations")
    op.drop_table("discord_guild_channels")
