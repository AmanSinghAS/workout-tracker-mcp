from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Workout(Base):
    __tablename__ = "workout"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_workout_user_idempotency"),
        UniqueConstraint("user_id", "workout_date", name="uq_workout_user_day"),
        Index("ix_workout_user_started_at_desc", "user_id", desc("started_at")),
        Index("ix_workout_user_date", "user_id", "workout_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workout_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[AppUser] = relationship("AppUser")
    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise", back_populates="workout", cascade="all, delete-orphan"
    )


class Exercise(Base):
    __tablename__ = "exercise"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "canonical_name", name="uq_exercise_owner_canonical"
        ),
        Index("ix_exercise_owner_canonical", "owner_user_id", "canonical_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE")
    )
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    muscle_group: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner: Mapped[AppUser | None] = relationship("AppUser")
    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise", back_populates="exercise"
    )


class WorkoutExercise(Base):
    __tablename__ = "workout_exercise"
    __table_args__ = (
        UniqueConstraint("workout_id", "ordinal", name="uq_workout_exercise_ordinal"),
        Index("ix_workout_exercise_workout_ordinal", "workout_id", "ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workout.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercise.id"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    workout: Mapped[Workout] = relationship("Workout", back_populates="exercises")
    exercise: Mapped[Exercise] = relationship("Exercise", back_populates="workout_exercises")
    sets: Mapped[list["WorkoutSet"]] = relationship(
        "WorkoutSet", back_populates="workout_exercise", cascade="all, delete-orphan"
    )


class WorkoutSet(Base):
    __tablename__ = "workout_set"
    __table_args__ = (
        UniqueConstraint("workout_exercise_id", "set_index", name="uq_workout_set_index"),
        Index("ix_workout_set_workout_exercise_index", "workout_exercise_id", "set_index"),
        CheckConstraint("reps > 0", name="ck_workout_set_reps_positive"),
        CheckConstraint("weight_kg >= 0", name="ck_workout_set_weight_nonnegative"),
        CheckConstraint(
            "weight_original_unit IN ('lb','kg')", name="ck_workout_set_weight_unit"
        ),
        CheckConstraint("rpe >= 0 AND rpe <= 10", name="ck_workout_set_rpe_range"),
        CheckConstraint("rir >= 0", name="ck_workout_set_rir_nonnegative"),
        CheckConstraint("rest_seconds >= 0", name="ck_workout_set_rest_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workout_exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_exercise.id", ondelete="CASCADE"),
        nullable=False,
    )
    set_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reps: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    weight_kg: Mapped[float | None] = mapped_column()
    weight_original_value: Mapped[float | None] = mapped_column()
    weight_original_unit: Mapped[str | None] = mapped_column(String(2))
    rpe: Mapped[float | None] = mapped_column()
    rir: Mapped[int | None] = mapped_column(SmallInteger)
    is_warmup: Mapped[bool | None] = mapped_column(Boolean)
    tempo: Mapped[str | None] = mapped_column(Text)
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    workout_exercise: Mapped[WorkoutExercise] = relationship(
        "WorkoutExercise", back_populates="sets"
    )
