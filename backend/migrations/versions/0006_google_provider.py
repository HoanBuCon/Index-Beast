"""Cho phép users.provider = 'google' (đăng nhập Google, ADR-005); người dùng Discord hiện có không đổi.

Downgrade trả ràng buộc về chỉ 'discord': phải xóa người dùng Google trước (phiên của họ xóa theo, hội thoại
của họ tự về user_id = NULL), nếu không ràng buộc cũ không áp được.
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_users_provider"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_provider"), "users", "provider IN ('discord', 'google')")


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE provider = 'google'")
    op.drop_constraint(op.f("ck_users_provider"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_provider"), "users", "provider IN ('discord')")
