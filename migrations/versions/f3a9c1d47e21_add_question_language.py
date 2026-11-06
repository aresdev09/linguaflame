"""add language to questions

Revision ID: f3a9c1d47e21
Revises: c4e1a7b93d20
Create Date: 2026-11-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c1d47e21"
down_revision: str | Sequence[str] | None = "c4e1a7b93d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Язык пояснений и формулировок вопроса (ru по умолчанию — банк русскоязычный)."""
    op.add_column(
        "questions",
        sa.Column(
            "language",
            sa.String(8),
            nullable=False,
            server_default=sa.text("'ru'"),
        ),
    )


def downgrade() -> None:
    """Удаляет язык вопроса."""
    op.drop_column("questions", "language")
