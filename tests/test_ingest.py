import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from src.db.models import Exercise, Workout, WorkoutExercise, WorkoutSet
from src.service.ingest_workout import get_workout_for_day, ingest_workout


def build_payload(user_id: uuid.UUID | None = None, idempotency_key: str | None = None):
    return {
        "user_id": str(user_id or uuid.uuid4()),
        "idempotency_key": idempotency_key,
        "workout": {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "title": "Session",
        },
        "exercises": [
            {
                "display_name": "Bench Press",
                "canonical_name": "bench press",
                "sets": [
                    {"reps": 8, "weight": {"value": 135, "unit": "lb"}, "rpe": 7.5},
                    {"reps": 8, "weight": {"value": 60, "unit": "kg"}},
                ],
            }
        ],
    }


def test_ingest_happy_path(db_session):
    payload = build_payload()

    result = ingest_workout(db_session, payload)
    workout_id = uuid.UUID(result["workout_id"])

    assert result["written_workout_exercises"] == 1
    assert result["written_sets"] == 2
    assert result["idempotent_replay"] is False

    stored_workout = db_session.get(Workout, workout_id)
    assert stored_workout is not None

    workout_exercises = db_session.execute(
        select(func.count()).select_from(WorkoutExercise)
    ).scalar_one()
    assert workout_exercises == 1

    workout_sets = db_session.execute(
        select(func.count()).select_from(WorkoutSet)
    ).scalar_one()
    assert workout_sets == 2

    weight_kg = db_session.execute(select(WorkoutSet.weight_kg)).scalars().first()
    assert weight_kg == pytest.approx(61.235, rel=1e-3)


def test_idempotent_replay_skips_children(db_session):
    user_id = uuid.uuid4()
    payload = build_payload(user_id=user_id, idempotency_key="abc123")

    first = ingest_workout(db_session, payload)
    second = ingest_workout(db_session, payload)

    assert first["workout_id"] == second["workout_id"]
    assert second["idempotent_replay"] is True
    assert second["written_sets"] == 0

    workout_sets = db_session.execute(
        select(func.count()).select_from(WorkoutSet)
    ).scalar_one()
    assert workout_sets == first["written_sets"]


def test_exercise_upsert_reuses_existing(db_session):
    user_id = uuid.uuid4()
    payload_one = {
        "user_id": str(user_id),
        "idempotency_key": "one",
        "workout": {"started_at": "2024-09-01T10:00:00Z"},
        "exercises": [{"display_name": "Deadlift", "sets": [{"reps": 5}]}],
    }
    payload_two = {
        "user_id": str(user_id),
        "idempotency_key": "two",
        "workout": {"started_at": "2024-09-02T10:00:00Z"},
        "exercises": [{"display_name": "deadlift ", "sets": [{"reps": 3}]}],
    }

    ingest_workout(db_session, payload_one)
    ingest_workout(db_session, payload_two)

    exercise_rows = db_session.execute(
        select(Exercise).where(Exercise.owner_user_id == user_id)
    ).scalars().all()
    assert len(exercise_rows) == 1

    workout_exercises = db_session.execute(select(WorkoutExercise)).scalars().all()
    assert len(workout_exercises) == 2
    assert workout_exercises[0].exercise_id == workout_exercises[1].exercise_id


def test_append_same_day_appends_to_existing_workout(db_session):
    user_id = uuid.uuid4()
    payload_one = build_payload(user_id=user_id, idempotency_key="one")
    payload_two = build_payload(user_id=user_id, idempotency_key="two")
    payload_one["workout"]["started_at"] = "2024-09-05T10:00:00Z"
    payload_two["workout"]["started_at"] = "2024-09-05T12:00:00Z"

    first = ingest_workout(db_session, payload_one)
    second = ingest_workout(db_session, payload_two)

    assert first["workout_id"] == second["workout_id"]
    assert second["appended_to_existing"] is True
    workout_exercises = db_session.execute(select(WorkoutExercise)).scalars().all()
    assert len(workout_exercises) == 2
    ordinals = sorted(ex.ordinal for ex in workout_exercises)
    assert ordinals == [0, 1]


def test_get_workout_for_day_returns_nested_payload(db_session):
    user_id = uuid.uuid4()
    payload = build_payload(user_id=user_id)
    ingest_workout(db_session, payload)

    workout_date = payload["workout"]["started_at"][:10]
    result = get_workout_for_day(db_session, {"user_id": str(user_id), "workout_date": workout_date})

    workout = result["workout"]
    assert workout is not None
    assert workout["workout_date"] == workout_date
    assert len(workout["exercises"]) == 1
    assert len(workout["exercises"][0]["sets"]) == 2
