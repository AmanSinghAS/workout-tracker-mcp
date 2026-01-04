"""drop workout_exercise ordinal

Revision ID: 20241010_0003
Revises: 20241001_0002
Create Date: 2024-10-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20241010_0003"
down_revision = "20241001_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workout_exercise") as batch:
        batch.drop_constraint("uq_workout_exercise_ordinal", type_="unique")
        batch.drop_index("ix_workout_exercise_workout_ordinal")
        batch.drop_column("ordinal")


def downgrade() -> None:
    with op.batch_alter_table("workout_exercise") as batch:
        batch.add_column(
            sa.Column("ordinal", sa.SmallInteger(), nullable=False, server_default="0")
        )
        batch.alter_column("ordinal", server_default=None)
        batch.create_unique_constraint(
            "uq_workout_exercise_ordinal", ["workout_id", "ordinal"]
        )
        batch.create_index(
            "ix_workout_exercise_workout_ordinal", ["workout_id", "ordinal"]
        )
