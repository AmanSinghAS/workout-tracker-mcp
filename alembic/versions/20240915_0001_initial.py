"""initial schema

Revision ID: 20240915_0001
Revises:
Create Date: 2024-09-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20240915_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "workout",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("timezone", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_workout_user_idempotency"
        ),
    )
    op.create_index(
        "ix_workout_user_started_at_desc",
        "workout",
        ["user_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "exercise",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
        ),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("muscle_group", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "owner_user_id", "canonical_name", name="uq_exercise_owner_canonical"
        ),
    )
    op.create_index(
        "ix_exercise_owner_canonical",
        "exercise",
        ["owner_user_id", "canonical_name"],
    )

    op.create_table(
        "workout_exercise",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workout_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workout.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exercise_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exercise.id"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("workout_id", "ordinal", name="uq_workout_exercise_ordinal"),
    )
    op.create_index(
        "ix_workout_exercise_workout_ordinal",
        "workout_exercise",
        ["workout_id", "ordinal"],
    )

    op.create_table(
        "workout_set",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workout_exercise_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workout_exercise.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("set_index", sa.SmallInteger(), nullable=False),
        sa.Column("reps", sa.SmallInteger(), nullable=False),
        sa.Column("weight_kg", sa.REAL()),
        sa.Column("weight_original_value", sa.REAL()),
        sa.Column("weight_original_unit", sa.String(length=2)),
        sa.Column("rpe", sa.REAL()),
        sa.Column("rir", sa.SmallInteger()),
        sa.Column("is_warmup", sa.Boolean()),
        sa.Column("tempo", sa.Text()),
        sa.Column("rest_seconds", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("workout_exercise_id", "set_index", name="uq_workout_set_index"),
        sa.CheckConstraint("reps > 0", name="ck_workout_set_reps_positive"),
        sa.CheckConstraint("weight_kg >= 0", name="ck_workout_set_weight_nonnegative"),
        sa.CheckConstraint(
            "weight_original_unit IN ('lb','kg')",
            name="ck_workout_set_weight_unit",
        ),
        sa.CheckConstraint("rpe >= 0 AND rpe <= 10", name="ck_workout_set_rpe_range"),
        sa.CheckConstraint("rir >= 0", name="ck_workout_set_rir_nonnegative"),
        sa.CheckConstraint("rest_seconds >= 0", name="ck_workout_set_rest_nonnegative"),
    )
    op.create_index(
        "ix_workout_set_workout_exercise_index",
        "workout_set",
        ["workout_exercise_id", "set_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_workout_set_workout_exercise_index", table_name="workout_set")
    op.drop_table("workout_set")
    op.drop_index("ix_workout_exercise_workout_ordinal", table_name="workout_exercise")
    op.drop_table("workout_exercise")
    op.drop_index("ix_exercise_owner_canonical", table_name="exercise")
    op.drop_table("exercise")
    op.drop_index("ix_workout_user_started_at_desc", table_name="workout")
    op.drop_table("workout")
    op.drop_table("app_user")
