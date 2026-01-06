"""add workout_date and per-day uniqueness

Revision ID: 20241001_0002
Revises: 20240915_0001
Create Date: 2024-10-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20241001_0002"
down_revision = "20240915_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable column first so we can backfill
    op.add_column("workout", sa.Column("workout_date", sa.Date(), nullable=True))

    workout = sa.table(
        "workout",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("started_at", sa.DateTime(timezone=True)),
        sa.column("workout_date", sa.Date()),
    )
    # Backfill using the UTC date of started_at to avoid nulls
    op.execute(workout.update().values(workout_date=sa.func.date(workout.c.started_at)))

    # De-duplicate any existing per-day workouts by keeping the earliest per user/day
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    user_id,
                    workout_date,
                    started_at,
                    idempotency_key,
                    row_number() OVER (
                        PARTITION BY user_id, workout_date
                        ORDER BY (idempotency_key IS NOT NULL) DESC, started_at, id
                    ) AS rn,
                    first_value(id) OVER (
                        PARTITION BY user_id, workout_date
                        ORDER BY (idempotency_key IS NOT NULL) DESC, started_at, id
                    ) AS keep_id
                FROM workout
            )
            UPDATE workout_exercise AS we
            SET workout_id = r.keep_id
            FROM ranked r
            WHERE we.workout_id = r.id
              AND r.rn > 1
              AND we.workout_id <> r.keep_id;
            """
        )
    )

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    user_id,
                    workout_date,
                    started_at,
                    idempotency_key,
                    row_number() OVER (
                        PARTITION BY user_id, workout_date
                        ORDER BY (idempotency_key IS NOT NULL) DESC, started_at, id
                    ) AS rn
                FROM workout
            )
            DELETE FROM workout w
            USING ranked r
            WHERE w.id = r.id
              AND r.rn > 1;
            """
        )
    )

    with op.batch_alter_table("workout") as batch:
        batch.alter_column("workout_date", nullable=False)
        batch.create_unique_constraint(
            "uq_workout_user_day", ["user_id", "workout_date"]
        )
        batch.create_index("ix_workout_user_date", ["user_id", "workout_date"])


def downgrade() -> None:
    with op.batch_alter_table("workout") as batch:
        batch.drop_index("ix_workout_user_date")
        batch.drop_constraint("uq_workout_user_day", type_="unique")
        batch.drop_column("workout_date")
