"""add reminder fields

Revision ID: 7b3d9e4a1c52
Revises: 9c2f4b7a1d38
Create Date: 2026-10-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b3d9e4a1c52"
down_revision: str | Sequence[str] | None = "9c2f4b7a1d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет флаг активности и счётчик напоминаний за день."""
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "streaks",
        sa.Column("reminders_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "streaks",
        sa.Column(
            "reminders_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """Удаляет поля напоминаний."""
    op.drop_column("streaks", "reminders_count")
    op.drop_column("streaks", "reminders_date")
    op.drop_column("users", "is_active")
