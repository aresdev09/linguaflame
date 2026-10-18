"""add level test question ids

Revision ID: 9c2f4b7a1d38
Revises: e21c45e338b0
Create Date: 2026-10-18 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c2f4b7a1d38"
down_revision: Union[str, Sequence[str], None] = "e21c45e338b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет список вопросов теста уровня."""
    op.add_column(
        "level_tests",
        sa.Column(
            "question_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    """Удаляет список вопросов теста уровня."""
    op.drop_column("level_tests", "question_ids")
