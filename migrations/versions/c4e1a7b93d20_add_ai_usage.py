"""add ai usage

Revision ID: c4e1a7b93d20
Revises: 7b3d9e4a1c52
Create Date: 2026-10-18 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e1a7b93d20"
down_revision: Union[str, Sequence[str], None] = "7b3d9e4a1c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BigIntType = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Создаёт счётчик запросов к ИИ по дням."""
    op.create_table(
        "ai_usage",
        sa.Column("user_id", BigIntType, nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "requests",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "day"),
    )


def downgrade() -> None:
    """Удаляет счётчик запросов к ИИ."""
    op.drop_table("ai_usage")
