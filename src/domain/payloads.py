from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .normalize import normalize_canonical_name, weight_to_kg, WeightInput


def ensure_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


class Weight(BaseModel):
    value: float
    unit: Annotated[str, Field(pattern="^(lb|kg)$")]

    model_config = {"extra": "forbid"}

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weight value must be non-negative")
        return v

    def as_input(self) -> WeightInput:
        return {"value": self.value, "unit": self.unit}  # type: ignore[return-value]


class WorkoutInfo(BaseModel):
    started_at: datetime
    ended_at: Optional[datetime] = None
    timezone: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("started_at")
    @classmethod
    def ensure_started_timezone(cls, v: datetime) -> datetime:
        return ensure_timezone(v)

    @field_validator("ended_at")
    @classmethod
    def ensure_ended_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        return ensure_timezone(v)

    @model_validator(mode="after")
    def validate_chronology(self) -> "WorkoutInfo":
        if self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must be greater than or equal to started_at")
        return self


class WorkoutSetInput(BaseModel):
    reps: int
    weight: Optional[Weight] = None
    rpe: Optional[float] = None
    rir: Optional[int] = None
    is_warmup: Optional[bool] = None
    tempo: Optional[str] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("reps")
    @classmethod
    def reps_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("reps must be greater than 0")
        return v

    @field_validator("rpe")
    @classmethod
    def validate_rpe(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not (0 <= v <= 10):
            raise ValueError("rpe must be between 0 and 10")
        return v

    @field_validator("rir")
    @classmethod
    def validate_rir(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("rir must be non-negative")
        return v

    @field_validator("rest_seconds")
    @classmethod
    def validate_rest(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("rest_seconds must be non-negative")
        return v

    def weight_values(self) -> tuple[float | None, float | None, str | None]:
        if self.weight is None:
            return None, None, None
        original = self.weight
        weight_kg = weight_to_kg(original.as_input())
        return weight_kg, original.value, original.unit


class ExerciseInput(BaseModel):
    display_name: str
    exercise_id: Optional[uuid.UUID] = None
    canonical_name: Optional[str] = None
    notes: Optional[str] = None
    sets: List[WorkoutSetInput]

    model_config = {"extra": "forbid"}

    @field_validator("sets")
    @classmethod
    def require_sets(cls, v: List[WorkoutSetInput]) -> List[WorkoutSetInput]:
        if len(v) == 0:
            raise ValueError("each exercise must have at least one set")
        return v

    def normalized_canonical_name(self) -> str:
        base_name = self.canonical_name or self.display_name
        return normalize_canonical_name(base_name)


class WorkoutIngestPayload(BaseModel):
    user_id: uuid.UUID
    idempotency_key: Optional[str] = None
    workout: WorkoutInfo
    exercises: List[ExerciseInput]

    model_config = {"extra": "forbid"}

    @field_validator("exercises")
    @classmethod
    def exercises_not_empty(cls, v: List[ExerciseInput]) -> List[ExerciseInput]:
        if len(v) == 0:
            raise ValueError("exercises cannot be empty")
        return v


def validate_payload(payload: dict) -> WorkoutIngestPayload:
    try:
        return WorkoutIngestPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def workout_payload_schema() -> dict:
    """Return the JSON schema for the workout ingestion payload."""
    return WorkoutIngestPayload.model_json_schema()
